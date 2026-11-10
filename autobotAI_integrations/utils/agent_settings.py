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
* With thinking on, Claude models reject sampling settings (temperature must be
  1, ``top_k`` is not allowed), so ``temperature`` / ``top_p`` / ``top_k`` are
  dropped. Budget-based Claude thinking also needs ``max_tokens`` above the
  thinking budget, so ``max_tokens`` is raised when it is missing or too small.
* ``None`` values are removed, so "not set" never reaches a provider.
* ``max_tokens`` is clamped to the model's known output maximum
  (``model_max_output_tokens``), so a 16K request does not 400 on an older model.

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
# Room for the visible answer on top of the thinking budget.
_ANSWER_TOKENS = 4096

# Models whose maximum output is below what callers may ask for (AI agents ask
# for at least 16384). A request above the model's maximum is rejected with a
# 400, so ``max_tokens`` is clamped. Matched on the normalized model id; first
# match wins, so specific ids come before families. Unlisted models keep the
# requested value (newer models allow 16K+; core retries lower on a 400).
_MAX_OUTPUT_TOKENS = (
    ("claude-3-5-sonnet", 8192),
    ("claude-3-5-haiku", 8192),
    ("claude-3-haiku", 4096),
    ("claude-3-sonnet", 4096),
    ("claude-3-opus", 4096),
    ("claude-instant", 4096),
    ("claude-v2", 4096),
    ("nova-micro-v1", 10000),
    ("nova-lite-v1", 10000),
    ("nova-pro-v1", 10000),
    ("titan-text", 8192),
    ("mistral", 8192),
    ("mixtral", 8192),
    ("llama", 8192),
    ("command-r", 4096),
    ("jamba", 4096),
    ("gpt-4o-mini", 16384),
    ("gpt-4o", 16384),
    ("gpt-4-turbo", 4096),
    ("gpt-3-5", 4096),
)


def model_max_output_tokens(model: Optional[str]) -> Optional[int]:
    """Known output-token maximum for ``model``, or None when not listed."""
    if not model:
        return None
    needle = _normalized_model_needle(model)
    for key, limit in _MAX_OUTPUT_TOKENS:
        if key in needle:
            return limit
    return None


def is_claude_model(model: Optional[str]) -> bool:
    if not model:
        return False
    needle = _normalized_model_needle(model)
    return "claude" in needle or needle.startswith("anthropic-")


def _thinking_level(settings: Dict[str, Any]) -> Any:
    """The thinking level the settings turn on, or None when thinking is off/unset."""
    level = settings.get("thinking")
    if level not in (None, False):
        return level
    reasoning = (settings.get("extra_body") or {}).get("reasoning")
    if isinstance(reasoning, dict) and reasoning.get("enabled") is not False:
        return reasoning.get("effort") or True
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

    settings = {k: v for k, v in settings.items() if v is not None}

    if model_rejects_temperature(model or ""):
        settings.pop("temperature", None)
        settings.pop("top_p", None)

    level = _thinking_level(settings)
    if level is not None and is_claude_model(model):
        for key in _SAMPLING_KEYS:
            settings.pop(key, None)
        budget = _CLAUDE_THINKING_BUDGET.get(level)
        if budget:
            minimum = budget + _ANSWER_TOKENS
            if (settings.get("max_tokens") or 0) < minimum:
                settings["max_tokens"] = minimum

    limit = model_max_output_tokens(model)
    if limit and isinstance(settings.get("max_tokens"), int) and settings["max_tokens"] > limit:
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
