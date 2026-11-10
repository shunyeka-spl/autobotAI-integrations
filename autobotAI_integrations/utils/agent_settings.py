"""One place that turns the settings a caller asks for into settings a model accepts.

Every ``get_pydantic_agent`` runs its ``model_settings`` through
``prepare_agent_model_settings`` so callers (AI Agent node v1/v2, end_chat,
memory, quick calls) never filter per model on their own.

What it does:

* ``reasoning_effort`` (``off | minimal | low | medium | high | max``) becomes
  pydantic-ai's unified ``thinking`` setting, or OpenRouter's ``reasoning``
  body field (see ``llm_utils.reasoning_settings``).
* ``temperature`` / ``top_p`` are dropped for models that reject them
  (``model_rejects_temperature``).
* With thinking on, Claude models that can think reject sampling settings
  (temperature must be 1, ``top_k`` is not allowed), so ``temperature`` /
  ``top_p`` / ``top_k`` are dropped. Claude models that cannot think keep them,
  because pydantic-ai ignores ``thinking`` there.
* Budget-based Claude thinking needs ``max_tokens`` above the thinking budget,
  so ``max_tokens`` is raised when it is missing or too small. When the model's
  output maximum cannot hold the budget, the thinking level is lowered until it
  fits. Adaptive-thinking models size thinking themselves, so their
  ``max_tokens`` is left alone.
* ``max_tokens`` given as a numeric string becomes an int; an unusable value is
  dropped.
* ``None`` values are removed, so "not set" never reaches a provider.
  ``enable_prompt_caching=None`` is kept, because Bedrock reads it as "off".
* ``max_tokens`` is clamped to the model's known output maximum
  (``model_max_output_tokens``), so a 16K request does not 400 on an older
  model. Open-weight and AWS families (Llama, Mistral, Nova, ...) are clamped
  only on Bedrock; other hosts serve them with their own, often larger, limits.

Unknown models keep the settings they were given. ``bedrock_fallback`` still
retries once without a field a provider names in a 400, as the last guard.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from autobotAI_integrations.utils.model_helpers import (
    _normalized_model_needle,
    model_rejects_temperature,
)

REASONING_EFFORT_KEY = "reasoning_effort"

_SAMPLING_KEYS = ("temperature", "top_p", "top_k")

# pydantic-ai's ANTHROPIC_THINKING_BUDGET_MAP (profiles/anthropic.py). Kept
# here so this module does not import pydantic-ai profiles at import time.
_CLAUDE_THINKING_BUDGET = {
    True: 10000,
    "minimal": 1024,
    "low": 2048,
    "medium": 10000,
    "high": 16384,
    "xhigh": 32768,
}
# Thinking levels from largest to smallest budget, used to step down when the
# budget does not fit under the model's output maximum.
_LEVELS_BY_BUDGET = ("xhigh", "high", "medium", "low", "minimal")
# Room for the visible answer on top of the thinking budget.
_ANSWER_TOKENS = 4096

# Models whose maximum output is below what callers may ask for (AI agents ask
# for at least 16384; budget thinking may ask for up to 36864). A request above
# the model's maximum is rejected with a 400, so ``max_tokens`` is clamped.
# Matched on the normalized model id; first match wins, so specific ids come
# before families. Unlisted models keep the requested value (newer models allow
# more; core retries lower on a 400). These limits hold on every provider.
_MAX_OUTPUT_TOKENS = (
    ("claude-opus-4-1", 32000),
    ("claude-opus-4-0", 32000),
    ("claude-opus-4-2025", 32000),
    ("claude-opus-4-v", 32000),
    ("claude-3-7-sonnet", 64000),
    ("claude-3-5-sonnet", 8192),
    ("claude-3-5-haiku", 8192),
    ("claude-3-haiku", 4096),
    ("claude-3-sonnet", 4096),
    ("claude-3-opus", 4096),
    ("claude-instant", 4096),
    ("claude-v2", 4096),
    ("gpt-4o-mini", 16384),
    ("gpt-4o", 16384),
    ("gpt-4-turbo", 4096),
    ("gpt-3-5", 4096),
)
# Limits of the Bedrock deployments of open-weight and AWS families. Other
# hosts (Ollama, vLLM, OpenRouter) serve the same names with their own limits.
_BEDROCK_MAX_OUTPUT_TOKENS = (
    ("nova-micro-v1", 10000),
    ("nova-lite-v1", 10000),
    ("nova-pro-v1", 10000),
    ("titan-text", 8192),
    ("mistral", 8192),
    ("mixtral", 8192),
    ("llama", 8192),
    ("command-r", 4096),
    ("jamba", 4096),
)
_BEDROCK_PROVIDERS = frozenset({"aws_bedrock", "bedrock"})

# Mirrors pydantic-ai's ``supports_adaptive`` list (profiles/anthropic.py).
_CLAUDE_ADAPTIVE_THINKING = (
    "claude-fable-5",
    "claude-mythos-5",
    "claude-mythos-preview",
    "claude-sonnet-4-6",
    "claude-sonnet-5",
    "claude-opus-4-6",
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-opus-5",
    "claude-haiku-5",
)
# Claude models with budget-based thinking (pydantic-ai sends ``budget_tokens``).
# Checked after the adaptive list. Every other Claude id cannot think.
_CLAUDE_BUDGET_THINKING = (
    "claude-3-7-sonnet",
    "claude-sonnet-4",
    "claude-haiku-4-5",
    "claude-opus-4",
)


def _lookup(table, needle: str) -> Optional[int]:
    for key, limit in table:
        if key in needle:
            return limit
    return None


def model_max_output_tokens(
    model: Optional[str], provider: Optional[str] = None
) -> Optional[int]:
    """Known output-token maximum for ``model`` on ``provider``, or None when not listed.

    Without ``provider`` only the provider-independent limits are used.
    """
    if not model:
        return None
    needle = _normalized_model_needle(model)
    limit = _lookup(_MAX_OUTPUT_TOKENS, needle)
    if limit is None and provider in _BEDROCK_PROVIDERS:
        limit = _lookup(_BEDROCK_MAX_OUTPUT_TOKENS, needle)
    return limit


def is_claude_model(model: Optional[str]) -> bool:
    if not model:
        return False
    needle = _normalized_model_needle(model)
    return "claude" in needle or needle.startswith("anthropic-")


def claude_thinking_kind(model: Optional[str]) -> Optional[str]:
    """``"adaptive"``, ``"budget"``, or None when ``model`` is not a Claude model that thinks."""
    if not is_claude_model(model):
        return None
    needle = _normalized_model_needle(model)
    if any(key in needle for key in _CLAUDE_ADAPTIVE_THINKING):
        return "adaptive"
    if any(key in needle for key in _CLAUDE_BUDGET_THINKING):
        return "budget"
    return None


def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _thinking_level(settings: Dict[str, Any]) -> Any:
    """The thinking level the settings turn on, or None when thinking is off/unset."""
    level = settings.get("thinking")
    if level not in (None, False):
        return level
    reasoning = (settings.get("extra_body") or {}).get("reasoning")
    if isinstance(reasoning, dict) and reasoning.get("enabled") is not False:
        return reasoning.get("effort") or True
    return None


def _fit_thinking_level(level: Any, limit: Optional[int]) -> Any:
    """Largest thinking level, at most ``level``, whose budget fits under ``limit``.

    Returns ``level`` unchanged when there is no limit or the level has no known
    budget, and None when even the smallest budget does not fit.
    """
    budget = _CLAUDE_THINKING_BUDGET.get(level)
    if not limit or not budget or budget + _ANSWER_TOKENS <= limit:
        return level
    for candidate in _LEVELS_BY_BUDGET:
        candidate_budget = _CLAUDE_THINKING_BUDGET[candidate]
        if candidate_budget <= budget and candidate_budget + _ANSWER_TOKENS <= limit:
            return candidate
    return None


def prepare_agent_model_settings(
    provider: Optional[str],
    model: Optional[str],
    model_settings: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return a new settings dict that ``model`` on ``provider`` accepts."""
    from autobotAI_integrations.llm_utils import reasoning_settings

    settings: Dict[str, Any] = dict(model_settings or {})

    effort = settings.pop(REASONING_EFFORT_KEY, None)
    if effort is not None:
        reasoning = reasoning_settings(provider, effort)
        extra_body = reasoning.pop("extra_body", None)
        if extra_body:
            settings["extra_body"] = {**(settings.get("extra_body") or {}), **extra_body}
        settings.update(reasoning)

    settings = {
        k: v
        for k, v in settings.items()
        if v is not None or k == "enable_prompt_caching"
    }

    if "max_tokens" in settings:
        max_tokens = _as_int(settings["max_tokens"])
        if max_tokens is None or max_tokens <= 0:
            settings.pop("max_tokens")
        else:
            settings["max_tokens"] = max_tokens

    if model_rejects_temperature(model or ""):
        settings.pop("temperature", None)
        settings.pop("top_p", None)

    limit = model_max_output_tokens(model, provider)

    level = _thinking_level(settings)
    kind = claude_thinking_kind(model) if level is not None else None
    if kind is not None:
        for key in _SAMPLING_KEYS:
            settings.pop(key, None)
    if kind == "budget":
        fitted = _fit_thinking_level(level, limit)
        if "thinking" in settings:
            if fitted is None:
                settings.pop("thinking")
            else:
                settings["thinking"] = fitted
        budget = _CLAUDE_THINKING_BUDGET.get(fitted)
        if budget and settings.get("max_tokens", 0) < budget + _ANSWER_TOKENS:
            settings["max_tokens"] = budget + _ANSWER_TOKENS

    if limit and settings.get("max_tokens", 0) > limit:
        settings["max_tokens"] = limit

    return settings


def prepare_agent_options(
    provider: Optional[str], model: Optional[str], options: Optional[dict]
) -> dict:
    """Copy of ``options`` (``Agent(**options)``) with cleaned ``model_settings``."""
    options = dict(options or {})
    if "model_settings" in options:
        cleaned = prepare_agent_model_settings(provider, model, options.get("model_settings"))
        if cleaned:
            options["model_settings"] = cleaned
        else:
            options.pop("model_settings")
    return options
