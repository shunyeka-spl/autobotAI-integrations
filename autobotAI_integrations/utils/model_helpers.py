"""Model-specific helper functions and compatibility checks for LLM calls."""

_LLAMA_PROMPT_MARKERS = (
    "<|begin_of_text|>",
    "<|eot_id|>",
    "<|start_header_id|>user<|end_header_id|>",
    "<|start_header_id|>assistant<|end_header_id|>",
)


def is_meta_llama_model(model: str) -> bool:
    if not model:
        return False
    normalized = model.lower()
    for prefix in ("global.", "us.", "eu.", "apac."):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    return normalized.startswith("meta.llama")


_BEDROCK_TEMPERATURE_REJECT_MARKERS = (
    "claude-sonnet-5",
    "claude-opus-5",
    "claude-fable-5",
    "claude-opus-4-7",
    "claude-opus-4-8",
    "gpt-5-6",
    # The whole GPT-6 family (luna, sol, astra, 6.1-*): OpenRouter's catalog
    # lists no `temperature` among their supported parameters, same as
    # gpt-5.6. Matched on the family for the reason given for grok below. This
    # matters more than usual because neither langchain-openai nor pydantic-ai
    # strips temperature for these ids — both only special-case `gpt-5*` — so
    # nothing downstream would catch it before Azure 400s the call.
    "gpt-6",
    # Every xAI Grok model on Bedrock: "This model doesn't support the
    # temperature field. Remove temperature and try again."
    # (ValidationException, 400). Matched on the family, not one version:
    # grok-4.6 broke production, and a narrow marker means the next grok id
    # breaks it again. Omitting temperature on a grok that would have accepted
    # it costs sampling determinism; sending it to one that does not costs the
    # whole call.
    "grok",
)


_BEDROCK_EXTENDED_CACHE_TTL_MARKERS = (
    "anthropic",
    "claude",
)


def bedrock_model_rejects_temperature(model: str) -> bool:
    """Return True when Bedrock rejects `temperature` for this model id.

    Used by Bedrock Converse call sites to omit temperature instead of
    sending a value that 400s the whole request. Safe no-op for every other
    model: callers only skip temperature when this returns True.
    """
    if not model:
        return False
    normalized = model.lower()
    for prefix in ("global.", "us.", "eu.", "apac."):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    needle = normalized.replace("/", "-").replace(".", "-").replace("_", "-")
    return any(marker in needle for marker in _BEDROCK_TEMPERATURE_REJECT_MARKERS)


# The marker list above is not Bedrock-specific in practice: the AI agent,
# quick_llm_call and the Optimus runtime apply it to every provider. New code
# should use this name; the old one stays for existing callers.
model_rejects_temperature = bedrock_model_rejects_temperature


# Models that 400 on a forced `tool_choice` (`any` / `tool`, OpenAI-compatible
# `required`) regardless of thinking settings. pydantic-ai forces tool choice
# whenever an agent has a structured `output_type` and text output is not
# allowed, which covers quick_llm_call(output_schema=...) — the goal
# classifier, capability analysis and suggestions run that on every Optimus
# turn. pydantic-ai's own Anthropic profile only knows Fable/Mythos, and on an
# OpenAI-compatible gateway (OpenRouter) it has no Anthropic profile at all.
_FORCED_TOOL_CHOICE_REJECT_MARKERS = (
    "claude-opus-5-5",
    "claude-sonnet-5-5",
    "claude-fable-5",
    "claude-mythos-5",
)


def _normalized_model_needle(model: str) -> str:
    normalized = model.lower()
    for prefix in ("global.", "us.", "eu.", "apac."):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    return normalized.replace("/", "-").replace(".", "-").replace("_", "-")


def model_rejects_forced_tool_choice(model: str) -> bool:
    """Return True when the model rejects a forced tool choice.

    Accepts Bedrock (``global.anthropic.claude-opus-5-5``), first-party
    (``claude-opus-5-5``) and OpenRouter (``anthropic/claude-opus-5.5``) ids.
    """
    if not model:
        return False
    needle = _normalized_model_needle(model)
    return any(marker in needle for marker in _FORCED_TOOL_CHOICE_REJECT_MARKERS)


def openai_profile_overrides(model: str) -> dict:
    """Partial pydantic-ai ``OpenAIModelProfile`` for an OpenAI-compatible model.

    Pass as ``profile=`` to ``OpenAIChatModel`` / ``OpenAIResponsesModel``;
    pydantic-ai merges a partial dict on top of the provider's own profile.
    Applying it where the model is built protects every caller at once — the
    AI agent nodes, end_chat, conversation memory, memory spaces and
    quick_llm_call — instead of relying on each to filter its own settings.

    Returns ``{}`` for models that need nothing, so callers can pass
    ``profile=openai_profile_overrides(m) or None`` and keep today's behaviour.
    """
    overrides: dict = {}
    if model_rejects_temperature(model):
        # Dropped from model_settings before the request is built, on both the
        # Chat Completions and Responses paths.
        overrides["openai_unsupported_model_settings"] = ("temperature", "top_p")
    if model_rejects_forced_tool_choice(model):
        # Structured output then goes out with tool_choice="auto"; pydantic-ai
        # still validates the output tool and re-prompts if the model answers
        # in plain text instead.
        overrides["openai_supports_tool_choice_required"] = False
    return overrides


def bedrock_model_supports_extended_cache_ttl(model: str) -> bool:
    """Return True when Bedrock accepts an explicit cachePoint `ttl` for this model.

    Bedrock splits prompt caching in two: the *default* cachePoint
    (``{"type": "default"}``, ~5 minutes) which every caching-capable model
    accepts, and *extended TTL* caching (``{"type": "default", "ttl": "1h"}``)
    which is Anthropic-only. Sending any explicit `ttl` — even ``"5m"`` — to a
    non-Anthropic model is read as extended TTL and 400s the whole call:

        ValidationException: Extended TTL prompt caching is only supported for
        Anthropic models        (seen on global.amazon.nova-2-lite-v1:0)

    Callers should omit the `ttl` key entirely when this returns False; the
    bare cachePoint still caches, just at the 5-minute default.
    """
    if not model:
        return False
    normalized = model.lower()
    for prefix in ("global.", "us.", "us-gov.", "eu.", "apac.", "sa.", "amer.", "jp.", "au."):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    return any(marker in normalized for marker in _BEDROCK_EXTENDED_CACHE_TTL_MARKERS)


def format_prompt_for_model(prompt: str, model: str) -> str:
    """Keep Meta Llama chat tokens; strip them for other model families."""
    if is_meta_llama_model(model):
        return prompt
    cleaned = prompt
    for marker in _LLAMA_PROMPT_MARKERS:
        cleaned = cleaned.replace(marker, "")
    return cleaned.strip()
