"""llama-index LLM construction for OpenAI-compatible endpoints.

llama-index's ``OpenAI`` class has two gaps that bite new models:

* It always sends ``temperature`` (a non-optional float, default 0.1). Models
  in ``model_helpers``' reject list — GPT-6, Claude Opus 5.5 / Sonnet 5 — answer
  that with a 400.
* It only works for model names in its own built-in table. ``metadata`` raises
  ``Unknown model 'gpt-6-luna'`` and ``is_chat_model`` comes back False for
  anything else, so a model released after the installed llama-index (or an
  Azure deployment with a custom name) cannot be used at all.

``build_openai_compatible_llm`` returns an ``OpenAI`` subclass that declares
the chat/function-calling capabilities and context window explicitly instead
of looking them up by name, and strips the sampling fields the target model
rejects.

It deliberately builds on ``llama_index.llms.openai`` rather than
``llama_index.llms.openai_like.OpenAILike``: autobotAI-core ships the former
but not the latter, so OpenRouter's ``load_llama_index_llm`` (which imported
``OpenAILike``) failed with ImportError in core for every model.

llama-index is an optional dependency (``[full]`` extra), so every import here
is deferred to call time.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from autobotAI_integrations.utils.model_helpers import model_rejects_temperature

# Context window assumed for a model llama-index has no entry for. It only
# sizes prompt packing (chat memory buffers, query-engine chunk budgets), never
# what the provider accepts. 128K is below every current GPT-5/6 and Claude
# window, so it can under-fill a prompt but never overflow one.
UNKNOWN_MODEL_CONTEXT_WINDOW = 128_000

# llama-index's own default for OpenAI-compatible models it cannot size.
_DEFAULT_CONTEXT_WINDOW = 3900


@lru_cache(maxsize=1)
def _sampling_safe_openai_like_cls():
    from llama_index.core.base.llms.types import LLMMetadata
    from llama_index.llms.openai import OpenAI
    from pydantic import Field

    class SamplingSafeOpenAILike(OpenAI):
        """OpenAI-compatible LLM with declared capabilities.

        Never sends a sampling field the model rejects.
        """

        context_window: int = Field(default=_DEFAULT_CONTEXT_WINDOW)
        is_chat_model: bool = Field(default=True)
        is_function_calling_model: bool = Field(default=False)

        @classmethod
        def class_name(cls) -> str:
            return "sampling_safe_openai_like"

        @property
        def metadata(self) -> LLMMetadata:
            return LLMMetadata(
                context_window=self.context_window,
                num_output=self.max_tokens or -1,
                is_chat_model=self.is_chat_model,
                is_function_calling_model=self.is_function_calling_model,
                model_name=self.model,
            )

        @property
        def _tokenizer(self):
            # tiktoken raises KeyError for ids it does not know
            # (anthropic/..., gpt-6-luna). Only the legacy completions path
            # uses this, and None is the documented "unknown" answer.
            try:
                return super()._tokenizer
            except Exception:
                return None

        def _get_model_kwargs(self, **kwargs: Any) -> dict:
            model_kwargs = super()._get_model_kwargs(**kwargs)
            if model_rejects_temperature(self.model):
                model_kwargs.pop("temperature", None)
                model_kwargs.pop("top_p", None)
                # Same models are reasoning models, which reject `max_tokens`
                # on Chat Completions (OpenAI / Azure). OpenRouter accepts
                # either name, so the rename is safe on every route.
                if "max_tokens" in model_kwargs:
                    model_kwargs.setdefault(
                        "max_completion_tokens", model_kwargs.pop("max_tokens")
                    )
            return model_kwargs

    return SamplingSafeOpenAILike


def llama_index_knows_openai_model(model: str) -> bool:
    """True when llama-index's ``OpenAI`` class has a table entry for ``model``."""
    try:
        from llama_index.llms.openai.utils import ALL_AVAILABLE_MODELS
    except ImportError:
        return False
    return model in ALL_AVAILABLE_MODELS


def openai_context_window(model: str) -> int:
    """llama-index's table size for ``model``, else ``UNKNOWN_MODEL_CONTEXT_WINDOW``.

    Keeps a known model (gpt-5.6-sol: 1.05M) at the window the stock class
    would have used when it is routed here only to drop temperature.
    """
    try:
        from llama_index.llms.openai.utils import ALL_AVAILABLE_MODELS
    except ImportError:
        return UNKNOWN_MODEL_CONTEXT_WINDOW
    return ALL_AVAILABLE_MODELS.get(model, UNKNOWN_MODEL_CONTEXT_WINDOW)


def build_openai_compatible_llm(
    model: str,
    *,
    api_key: Optional[str],
    api_base: str,
    is_chat_model: bool = True,
    is_function_calling_model: bool = False,
    context_window: Optional[int] = None,
    **kwargs: Any,
):
    """A llama-index LLM for ``model`` on an OpenAI-compatible endpoint."""
    cls = _sampling_safe_openai_like_cls()
    if context_window is not None:
        kwargs["context_window"] = context_window
    return cls(
        model=model,
        api_key=api_key,
        api_base=api_base,
        is_chat_model=is_chat_model,
        is_function_calling_model=is_function_calling_model,
        **kwargs,
    )
