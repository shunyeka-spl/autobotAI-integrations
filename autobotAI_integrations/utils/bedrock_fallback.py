"""Survive Bedrock 400s that reject an inference field the model doesn't take.

Bedrock answers an unsupported inference parameter with a hard 400 that kills
the whole call — there is no partial success and no server-side degradation:

    ValidationException: This model doesn't support the temperature field.
    Remove temperature and try again.                      (xai.grok-4.6)

    ValidationException: Extended TTL prompt caching is only supported for
    Anthropic models                                (amazon.nova-2-lite-v1:0)

``model_helpers.bedrock_model_rejects_temperature()`` and
``bedrock_model_supports_extended_cache_ttl()`` keep known offenders out of the
request in the first place, but an allow-list only knows the models someone has
already hit in production. Bedrock adds models continuously, so the list is
permanently one incident behind.

This module closes that gap: when Bedrock names the field it rejects, drop
exactly that field and re-issue the call. The allow-list becomes an
optimisation — it avoids the wasted round trip — rather than the only defence.

Deliberately narrow, because a retry layer that guesses is worse than the 400
it replaces:

  * Only a 400 ``ValidationException`` is considered. Every other status, error
    code and exception type propagates untouched.
  * Only a field the error message *names* is removed, and only when it is
    actually present in this request's settings. An unrecognised message
    changes nothing and the original error is raised.
  * Only sampling parameters and cache hints are ever dropped — never
    ``max_tokens``, the tool config, the output schema or the messages.
    Dropping a sampling parameter costs determinism; dropping anything else
    would silently change what the caller asked for.
  * Settings only ever shrink, every retry must remove something new, and the
    attempt count is capped, so no request can loop.

What Bedrock rejects is a property of the model, not of the request, so the
adjustment is remembered per model id for the life of the process and applied
up front on later calls. A warm Lambda or ECS task pays the wasted round trip
once, not on every invocation.
"""

from __future__ import annotations

import re
import threading
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

from autobotAI_integrations.utils.logging_config import logger

# Sampling knobs are the only settings safe to drop: the request still means
# what the caller intended, it just stops asking for a particular distribution.
# `max_tokens`, `stop_sequences`, tools and output schemas are contractual —
# dropping one would change the answer rather than the sampling of it.
_DROPPABLE_SETTINGS = frozenset(
    {
        "temperature",
        "top_p",
        "top_k",
        "presence_penalty",
        "frequency_penalty",
        "seed",
    }
)

# Bedrock spells these camelCase in its error text; pydantic-ai's ModelSettings
# uses snake_case.
_FIELD_ALIASES = {
    "temperature": "temperature",
    "temp": "temperature",
    "topp": "top_p",
    "topk": "top_k",
    "presencepenalty": "presence_penalty",
    "frequencypenalty": "frequency_penalty",
    "seed": "seed",
}

_CACHE_SETTINGS = (
    "bedrock_cache_instructions",
    "bedrock_cache_tool_definitions",
    "bedrock_cache_messages",
)

# Each pattern captures the field Bedrock is complaining about. They run only
# after the error is known to be a 400 ValidationException, so a stray sentence
# in some other error cannot trigger them.
_FIELD_PATTERNS = (
    re.compile(r"support the ([A-Za-z_]+) field", re.I),
    re.compile(r"[Rr]emove ([A-Za-z_]+) and try again"),
    re.compile(r"([A-Za-z_]+) is not supported (?:for|by|on) this model", re.I),
    re.compile(r"(?:doesn't|does not) support ([A-Za-z_]+)", re.I),
)

# Actions are plain strings so they can be logged and remembered as-is.
DROP_PREFIX = "drop:"
CACHE_TTL_ACTION = "cache:ttl"
CACHE_OFF_ACTION = "cache:off"

MAX_ATTEMPTS = 3  # the original call plus at most two narrowed retries

_learned: Dict[str, List[str]] = {}
_learned_lock = threading.Lock()

# Built on first use by resilient_model_class(); see the note there on why the
# pydantic_ai import cannot happen at module scope.
_model_cls: Any = None


# ---------------------------------------------------------------------------
# error inspection
# ---------------------------------------------------------------------------

def validation_message(exc: BaseException) -> Optional[str]:
    """Return the Bedrock ValidationException text, or None if this isn't one.

    Handles both layers this error surfaces at: botocore's ``ClientError``
    (``exc.response``) and pydantic-ai's ``ModelHTTPError``, which wraps that
    same response dict in ``exc.body`` and carries ``status_code``.
    """
    body = getattr(exc, "body", None)
    if not isinstance(body, Mapping):
        body = getattr(exc, "response", None)
    if not isinstance(body, Mapping):
        return None

    status = getattr(exc, "status_code", None)
    if status is None:
        meta = body.get("ResponseMetadata")
        if isinstance(meta, Mapping):
            status = meta.get("HTTPStatusCode")
    if status != 400:
        return None

    error = body.get("Error")
    if not isinstance(error, Mapping):
        return None
    if error.get("Code") != "ValidationException":
        return None

    message = error.get("Message")
    return message if isinstance(message, str) else None


def detect_actions(message: str, settings: Optional[Mapping[str, Any]]) -> List[str]:
    """Work out what to remove from `settings` so this message stops happening.

    Returns an empty list when the message names nothing we understand, or when
    everything it names is already absent. In both cases the caller must let the
    original error propagate rather than resend an identical request.
    """
    settings = settings or {}
    low = message.lower()
    actions: List[str] = []

    # Caching: an explicit cachePoint ttl is Anthropic-only, but the bare
    # cachePoint underneath it is not. Try the downgrade before the heavier
    # "this model cannot cache at all" reading.
    if "extended ttl" in low:
        if any(isinstance(settings.get(key), str) for key in _CACHE_SETTINGS):
            actions.append(CACHE_TTL_ACTION)
    elif "prompt caching" in low or "cachepoint" in low:
        if any(key in settings for key in _CACHE_SETTINGS):
            actions.append(CACHE_OFF_ACTION)

    for pattern in _FIELD_PATTERNS:
        for raw in pattern.findall(message):
            key = _FIELD_ALIASES.get(raw.replace("_", "").lower())
            if key is None or key not in _DROPPABLE_SETTINGS:
                continue
            if key not in settings:
                continue
            action = DROP_PREFIX + key
            if action not in actions:
                actions.append(action)

    return actions


def apply_actions(
    settings: Optional[Mapping[str, Any]], actions: Iterable[str]
) -> Dict[str, Any]:
    """Return a copy of `settings` with `actions` applied. Never mutates input."""
    adjusted = dict(settings or {})
    for action in actions:
        if action == CACHE_TTL_ACTION:
            for key in _CACHE_SETTINGS:
                if isinstance(adjusted.get(key), str):
                    # True is a bare cachePoint: still cached, at Bedrock's
                    # default 5 minutes, with no Anthropic-only ttl field.
                    adjusted[key] = True
        elif action == CACHE_OFF_ACTION:
            for key in _CACHE_SETTINGS:
                adjusted.pop(key, None)
        elif action.startswith(DROP_PREFIX):
            adjusted.pop(action[len(DROP_PREFIX) :], None)
    return adjusted


# ---------------------------------------------------------------------------
# per-model memory
# ---------------------------------------------------------------------------

def remember(model_name: str, actions: Iterable[str]) -> None:
    if not model_name:
        return
    with _learned_lock:
        known = _learned.setdefault(model_name, [])
        for action in actions:
            if action not in known:
                known.append(action)


def learned_actions(model_name: str) -> List[str]:
    with _learned_lock:
        return list(_learned.get(model_name, ()))


def reset_learned() -> None:
    """Forget every remembered adjustment (used by tests)."""
    with _learned_lock:
        _learned.clear()


def prepare_settings(
    model_name: str, settings: Optional[Mapping[str, Any]]
) -> Optional[Mapping[str, Any]]:
    """Pre-apply whatever this model has already rejected in this process."""
    actions = learned_actions(model_name)
    if not actions:
        return settings
    adjusted = apply_actions(settings, actions)
    if adjusted != dict(settings or {}):
        logger.debug(
            "bedrock_fallback: %s — applying learned adjustments %s up front",
            model_name,
            actions,
        )
    return adjusted


def next_attempt(
    model_name: str, settings: Optional[Mapping[str, Any]], exc: BaseException
) -> Optional[Dict[str, Any]]:
    """Settings to retry `exc` with, or None when it is not recoverable.

    None means "re-raise": either the error is not a field rejection we
    understand, or nothing in the current settings would change, so the retry
    would send a byte-identical request and fail identically.
    """
    message = validation_message(exc)
    if message is None:
        return None
    actions = detect_actions(message, settings)
    if not actions:
        return None
    adjusted = apply_actions(settings, actions)
    if adjusted == dict(settings or {}):
        return None
    remember(model_name, actions)
    logger.warning(
        "bedrock_fallback: %s rejected a request field (%s) — retrying with %s applied",
        model_name or "<unknown model>",
        message.strip(),
        actions,
    )
    return adjusted


def resilient_model_class() -> Any:
    """Build (once) a ``BedrockConverseModel`` subclass that self-heals 400s.

    Defined lazily inside the function because ``pydantic_ai`` is an optional,
    lazily imported dependency everywhere else in this package — importing it
    at module import time would drag it into processes that never touch
    Bedrock.
    """
    global _model_cls
    if _model_cls is not None:
        return _model_cls

    from contextlib import asynccontextmanager

    from pydantic_ai.models.bedrock import BedrockConverseModel

    class ResilientBedrockConverseModel(BedrockConverseModel):
        """Drops a field Bedrock names in a 400 and re-issues the call.

        ``super()`` is spelled out explicitly rather than zero-arg: the closure
        below runs outside the method body, where the implicit ``__class__``
        cell is not available.
        """

        async def request(self, messages, model_settings, model_request_parameters):
            async def call(settings):
                return await BedrockConverseModel.request(
                    self, messages, settings, model_request_parameters
                )

            return await run_with_field_fallback(self.model_name, model_settings, call)

        @asynccontextmanager
        async def request_stream(
            self,
            messages,
            model_settings,
            model_request_parameters,
            run_context=None,
        ):
            settings = prepare_settings(self.model_name, model_settings)
            for attempt in range(MAX_ATTEMPTS):
                streaming = False
                try:
                    async with BedrockConverseModel.request_stream(
                        self, messages, settings, model_request_parameters, run_context
                    ) as response:
                        # Past this point the model is already producing output,
                        # so a later failure belongs to the caller's consumption
                        # of the stream, not to the request we could retry.
                        streaming = True
                        yield response
                    return
                except Exception as exc:  # noqa: BLE001 — re-raised unless recoverable
                    if streaming or attempt == MAX_ATTEMPTS - 1:
                        raise
                    retry_settings = next_attempt(self.model_name, settings, exc)
                    if retry_settings is None:
                        raise
                    settings = retry_settings

    _model_cls = ResilientBedrockConverseModel
    return _model_cls


def build_model(model_name: str, provider: Any) -> Any:
    """``BedrockConverseModel(model_name, provider=provider)`` with the fallback."""
    return resilient_model_class()(model_name, provider=provider)


async def run_with_field_fallback(
    model_name: str,
    settings: Optional[Mapping[str, Any]],
    call: Callable[[Optional[Mapping[str, Any]]], Any],
) -> Any:
    """Await `call(settings)`, narrowing the settings on a field-rejection 400.

    `call` must be safe to invoke more than once. It is only ever re-invoked
    after Bedrock refused the request outright, so nothing was generated,
    streamed or billed on the failed attempt.
    """
    attempt_settings = prepare_settings(model_name, settings)
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await call(attempt_settings)
        except Exception as exc:  # noqa: BLE001 — re-raised unless recoverable
            if attempt == MAX_ATTEMPTS - 1:
                raise
            retry_settings = next_attempt(model_name, attempt_settings, exc)
            if retry_settings is None:
                raise
            attempt_settings = retry_settings
    raise AssertionError("unreachable")  # pragma: no cover
