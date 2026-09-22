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
