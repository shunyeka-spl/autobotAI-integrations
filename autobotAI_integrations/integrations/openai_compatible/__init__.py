"""OpenAI-compatible LLM gateway integration.

One integration for any endpoint that speaks the OpenAI Chat Completions API:
self-hosted routers (LiteLLM proxy, Portkey gateway, Envoy AI Gateway, Kong AI
Gateway, Routerly, Bifrost, ...), inference servers (vLLM, TGI, Ollama's /v1)
and OpenAI-compatible vendors (Sarvam, Together, Groq, ...).

Deliberately Chat Completions only: the Responses API is OpenAI-specific and
most gateways either lack it or implement it partially.

Auth is key based. The key always goes out as ``Authorization: Bearer <key>``
(the OpenAI SDK cannot drop that header), and additionally in a custom header
when the gateway expects one (``x-api-key``, ``api-key``, ...).
"""

import importlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from pydantic import Field, field_validator

from autobotAI_integrations import (
    AIBaseService,
    BaseSchema,
    CLICreds,
    ConnectionInterfaces,
    PayloadTask,
    RestAPICreds,
    SDKClient,
    SDKCreds,
)
from autobotAI_integrations.models import IntegrationCategory
from autobotAI_integrations.utils.logging_config import logger

DEFAULT_AUTH_HEADER = "Authorization"
# The OpenAI SDK refuses to build a client without a key. Keyless local
# servers (vLLM / Ollama without --api-key) ignore the header entirely.
NO_KEY_PLACEHOLDER = "not-needed"
_HTTP_TIMEOUT_SECONDS = 20
_MAX_ERROR_BODY = 300
# Room for a reasoning model to think briefly before the gateway returns 2xx.
_PROBE_MAX_TOKENS = 64
_SSL_ERROR = (
    "TLS certificate verification failed. If the gateway uses a "
    "private or self-signed certificate, turn off 'Verify SSL'."
)
_CONNECT_ERROR = (
    "Could not connect to the gateway. Check the base URL and that "
    "it is reachable from autobotAI (private gateways must be exposed "
    "or allowlist autobotAI's egress)."
)


class OpenAICompatibleIntegration(BaseSchema):
    base_url: Optional[str] = None
    api_key: Optional[str] = Field(default=None, exclude=True)
    auth_header_name: Optional[str] = DEFAULT_AUTH_HEADER
    # Gateway routing/config headers (Portkey x-portkey-*, tenant ids, ...).
    # Stored as a secret: these often carry keys too.
    extra_headers: Optional[Dict[str, str]] = Field(default=None, exclude=True)
    models: Optional[str] = None
    model_aliases: Optional[str] = None
    verify_ssl: Optional[bool] = True
    skip_test: Optional[bool] = Field(default=None, exclude=False)

    name: Optional[str] = "OpenAI-Compatible Gateway"
    category: Optional[str] = IntegrationCategory.AI.value
    description: Optional[str] = (
        "Connect any OpenAI-compatible endpoint: self-hosted LLM gateways and "
        "routers (LiteLLM, Portkey, Envoy AI Gateway, Kong, Routerly), "
        "inference servers (vLLM, TGI, Ollama) or OpenAI-compatible providers."
    )

    @field_validator("base_url")
    @classmethod
    def _normalize_base_url(cls, v):
        if v is None:
            return v
        v = str(v).strip().rstrip("/")
        # Users paste the full chat endpoint from gateway docs; the SDKs append
        # /chat/completions themselves.
        for suffix in ("/chat/completions", "/completions"):
            if v.endswith(suffix):
                v = v[: -len(suffix)]
        return v

    @field_validator("extra_headers", mode="before")
    @classmethod
    def _parse_extra_headers(cls, v):
        if v in (None, "", {}):
            return None
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except ValueError as e:
                raise ValueError(
                    'Extra headers must be a JSON object, e.g. {"x-portkey-provider": "openai"}'
                ) from e
        if not isinstance(v, dict):
            raise ValueError("Extra headers must be a JSON object of header: value pairs")
        return {str(k).strip(): str(val) for k, val in v.items() if str(k).strip()}

    @field_validator("verify_ssl", mode="before")
    @classmethod
    def _coerce_verify_ssl(cls, v):
        if v is None or v == "":
            return True
        if isinstance(v, str):
            return v.strip().lower() not in ("false", "0", "no", "off")
        return bool(v)


def parse_model_list(raw) -> List[str]:
    """Model ids from the textarea: one per line or comma separated."""
    if not raw:
        return []
    items = raw if isinstance(raw, list) else str(raw).replace(",", "\n").splitlines()
    seen, out = set(), []
    for item in items:
        item = str(item).split("#", 1)[0].strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def build_headers(
    api_key: Optional[str],
    auth_header_name: Optional[str],
    extra_headers: Optional[Dict[str, str]],
) -> Dict[str, str]:
    """Headers to send on every request, in addition to the SDK's Bearer header.

    Extra headers go first so the auth header wins on a name clash.
    """
    headers: Dict[str, str] = dict(extra_headers or {})
    name = (auth_header_name or DEFAULT_AUTH_HEADER).strip() or DEFAULT_AUTH_HEADER
    if api_key and name.lower() != DEFAULT_AUTH_HEADER.lower():
        headers[name] = api_key
    return headers


def _client_api_key(api_key: Optional[str]) -> str:
    key = (api_key or "").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key or NO_KEY_PLACEHOLDER


class OpenAICompatibleService(AIBaseService):
    def __init__(self, ctx, integration: OpenAICompatibleIntegration):
        if isinstance(integration, dict):
            integration = OpenAICompatibleIntegration(**integration)
        super().__init__(ctx, integration)

    # -- connection helpers -------------------------------------------------

    @property
    def _api_key(self) -> str:
        return _client_api_key(self.integration.api_key)

    @property
    def _verify(self) -> bool:
        return self.integration.verify_ssl is not False

    def _default_headers(self) -> Dict[str, str]:
        return build_headers(
            self._api_key if self.integration.api_key else None,
            self.integration.auth_header_name,
            self.integration.extra_headers,
        )

    def _request_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            **self._default_headers(),
        }

    def _require_base_url(self) -> str:
        if not self.integration.base_url:
            raise ValueError("Base URL is required for an OpenAI-compatible gateway.")
        return self.integration.base_url

    def _fetch_gateway_models(self) -> List[str]:
        """Model ids from GET {base_url}/models. Raises on any HTTP failure."""
        response = requests.get(
            f"{self._require_base_url()}/models",
            headers=self._request_headers(),
            timeout=_HTTP_TIMEOUT_SECONDS,
            verify=self._verify,
        )
        response.raise_for_status()
        body = response.json()
        data = body.get("data") if isinstance(body, dict) else body
        ids = []
        for item in data or []:
            model_id = item.get("id") if isinstance(item, dict) else item
            if isinstance(model_id, str) and model_id.strip():
                ids.append(model_id.strip())
        return ids

    @staticmethod
    def _auth_error(status_code: int) -> str:
        return (
            f"Authentication failed (HTTP {status_code}). Check the API key and, if "
            "your gateway does not use 'Authorization: Bearer', the auth header name."
        )

    def _probe_chat(self, model: str) -> dict:
        """One tiny raw completion; any 2xx means the gateway serves the model.

        The reply text is not checked: reasoning models (e.g. Sarvam's
        sarvam-105b) can spend a small token budget thinking and return no
        content, which is still a working model.
        """
        start = time.time()
        chat = requests.post(
            f"{self._require_base_url()}/chat/completions",
            headers=self._request_headers(),
            json={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": _PROBE_MAX_TOKENS,
            },
            timeout=_HTTP_TIMEOUT_SECONDS * 3,
            verify=self._verify,
        )
        if chat.ok:
            return {"success": True, "latency_ms": int((time.time() - start) * 1000)}
        if chat.status_code in (401, 403):
            return {"success": False, "error": self._auth_error(chat.status_code)}
        return {
            "success": False,
            "error": (
                f"Test call to model '{model}' failed: HTTP "
                f"{chat.status_code} - {chat.text[:_MAX_ERROR_BODY]}"
            ),
        }

    # -- AIBaseService ------------------------------------------------------

    def test_model(self, model: str) -> dict:
        """Per-model probe behind the model picker's "selectable" check."""
        try:
            wire_model = (model or "").strip()
            if not wire_model:
                return {"success": False, "model": model, "error": "Model is required."}
            result = self._probe_chat(wire_model)
        except requests.exceptions.SSLError:
            result = {"success": False, "error": _SSL_ERROR}
        except requests.exceptions.ConnectionError:
            result = {"success": False, "error": _CONNECT_ERROR}
        except Exception as e:
            result = {"success": False, "error": str(e)}
        return {"model": model, **result}

    def _test_integration(self):
        try:
            if self.integration.skip_test:
                return {"success": True}
            base_url = self._require_base_url()
            response = requests.get(
                f"{base_url}/models",
                headers=self._request_headers(),
                timeout=_HTTP_TIMEOUT_SECONDS,
                verify=self._verify,
            )
            if response.ok:
                return {"success": True}
            if response.status_code in (401, 403):
                return {"success": False, "error": self._auth_error(response.status_code)}

            # Many gateways (Routerly, Portkey OSS, ...) have no /models route.
            # Fall back to one tiny completion against a model the user listed.
            configured = parse_model_list(self.integration.models)
            if not configured:
                return {
                    "success": False,
                    "error": (
                        f"{base_url}/models returned HTTP {response.status_code}. "
                        "If your gateway has no /models endpoint, list your model IDs "
                        "in the Models field so the connection can be tested with them."
                    ),
                }
            probe = self._probe_chat(configured[0])
            return {k: v for k, v in probe.items() if k != "latency_ms"}
        except requests.exceptions.SSLError:
            return {"success": False, "error": _SSL_ERROR}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": _CONNECT_ERROR}
        except BaseException as e:
            return {"success": False, "error": str(e)}

    def get_integration_specific_details(self) -> dict:
        configured = parse_model_list(self.integration.models)
        discovered: List[str] = []
        try:
            discovered = self._fetch_gateway_models()
        except Exception as e:
            logger.info("openai_compatible: /models unavailable, using configured list: %s", e)
        # Configured models first: they are the user's explicit choice.
        known = set(configured)
        models = configured + [m for m in discovered if m not in known]
        if not models:
            return {
                "integration_id": self.integration.accountId,
                "models": [],
                "error": (
                    "No models found. The gateway's /models endpoint returned nothing; "
                    "add your model IDs in the integration's Models field."
                ),
            }
        # Gateways mix chat and embedding models in one list and give no
        # reliable way to tell them apart, so Memory Spaces gets the same list
        # and the user picks the embedding model by name.
        return {
            "integration_id": self.integration.accountId,
            "models": models,
            "embedding_models": models,
        }

    @staticmethod
    def ai_prompt_python_template():
        current_directory = Path(__file__).resolve().parent
        with open(os.path.join(current_directory, "ai_evaluator_code.py")) as f:
            return {
                "integration_type": "openai_compatible",
                "ai_client": "openai",
                "param_definitions": [
                    {
                        "name": "prompt",
                        "type": "handlebars-text",
                        "description": "The prompt to use for the AI model",
                        "required": True,
                    },
                    {
                        "name": "model",
                        "type": "str",
                        "description": "The model to use for the AI model",
                        "required": True,
                    },
                    {
                        "name": "resources",
                        "type": "list",
                        "description": "The resources to use for the AI model",
                        "required": True,
                    },
                ],
                "code": f.read(),
            }

    @staticmethod
    def get_forms():
        return {
            "label": "OpenAI-Compatible Gateway",
            "type": "form",
            "children": [
                {
                    "name": "base_url",
                    "type": "text/url",
                    "label": "Base URL",
                    "placeholder": "https://llm-gateway.example.com/v1",
                    "description": (
                        "The OpenAI-compatible API root, including the version path "
                        "(usually /v1). Requests go to <Base URL>/chat/completions."
                    ),
                    "required": True,
                },
                {
                    "name": "api_key",
                    "type": "text/password",
                    "label": "API Key",
                    "placeholder": "Enter the gateway API key",
                    "description": "Leave empty for gateways that need no key.",
                    "required": False,
                },
                {
                    "name": "auth_header_name",
                    "type": "text",
                    "label": "Auth Header Name",
                    "placeholder": "Authorization",
                    "description": (
                        "Header that carries the key. Keep 'Authorization' for "
                        "'Bearer <key>' (LiteLLM, Routerly, vLLM). Set e.g. 'x-api-key' "
                        "or 'api-key' if your gateway expects the raw key there."
                    ),
                    "required": False,
                    "default": DEFAULT_AUTH_HEADER,
                },
                {
                    "name": "extra_headers",
                    "type": "textarea",
                    "label": "Extra Headers (JSON)",
                    "placeholder": '{"x-portkey-provider": "openai"}',
                    "description": (
                        "Optional headers sent on every request, e.g. Portkey routing "
                        "headers. Stored encrypted."
                    ),
                    "required": False,
                },
                {
                    "name": "models",
                    "type": "textarea",
                    "label": "Models",
                    "placeholder": "gpt-5-mini\nclaude-sonnet\nllama-3.3-70b",
                    "description": (
                        "Optional. One model ID per line, exactly as the gateway names "
                        "them. Merged with the gateway's /models list; required when "
                        "the gateway has no /models endpoint."
                    ),
                    "required": False,
                },
                {
                    "name": "model_aliases",
                    "type": "textarea",
                    "label": "Model Aliases",
                    "placeholder": "smart=claude-opus-5-5\nfast=gpt-5-mini",
                    "description": (
                        "Optional. When a gateway model name hides the real model, map "
                        "it as alias=underlying-model, one per line. Used only to send "
                        "parameters that model accepts (e.g. some models reject "
                        "temperature)."
                    ),
                    "required": False,
                },
                {
                    "name": "verify_ssl",
                    "type": "checkbox",
                    "label": "Verify SSL",
                    "default": True,
                    "description": (
                        "Turn off only for gateways with a private or self-signed "
                        "certificate."
                    ),
                },
                {
                    "name": "skip_test",
                    "type": "select",
                    "label": "Skip Test Integration",
                    "placeholder": "Skip the integration test",
                    "description": "If enabled, skips the connection test (useful when the gateway is not reachable at setup time)",
                    "required": True,
                    "options": [
                        {"label": "No", "value": False},
                        {"label": "Yes", "value": True},
                    ],
                    "default": False,
                },
            ],
        }

    @staticmethod
    def get_schema(ctx=None):
        return OpenAICompatibleIntegration

    @staticmethod
    def supported_connection_interfaces():
        return [
            ConnectionInterfaces.REST_API,
            ConnectionInterfaces.PYTHON_SDK,
        ]

    def build_python_exec_combinations_hook(
        self, payload_task: PayloadTask, client_definitions: List[SDKClient]
    ) -> list:
        openai = importlib.import_module(
            client_definitions[0].import_library_names[0], package=None
        )
        envs = payload_task.creds.envs if payload_task.creds else {}
        headers = json.loads(envs.get("OPENAI_DEFAULT_HEADERS") or "{}")
        client_kwargs: Dict[str, Any] = {
            "api_key": envs.get("OPENAI_API_KEY") or NO_KEY_PLACEHOLDER,
            "base_url": envs.get("OPENAI_BASE_URL"),
            "default_headers": headers or None,
        }
        if str(envs.get("OPENAI_VERIFY_SSL", "true")).lower() == "false":
            import httpx

            client_kwargs["http_client"] = httpx.Client(verify=False)
        return [
            {
                "clients": {"openai": openai.OpenAI(**client_kwargs)},
                "params": self.prepare_params(payload_task.params),
                "context": payload_task.context,
            }
        ]

    def generate_rest_api_creds(self) -> RestAPICreds:
        return RestAPICreds(
            base_url=self._require_base_url(),
            api_key=self.integration.api_key,
            headers=self._request_headers(),
            verify_ssl=self._verify,
        )

    def generate_python_sdk_creds(self) -> SDKCreds:
        return SDKCreds(
            envs={
                "OPENAI_API_KEY": self._api_key,
                "OPENAI_BASE_URL": self._require_base_url(),
                "OPENAI_DEFAULT_HEADERS": json.dumps(self._default_headers()),
                "OPENAI_VERIFY_SSL": "true" if self._verify else "false",
            }
        )

    def generate_cli_creds(self) -> CLICreds:
        pass

    def generate_llm_credentials(self):
        # Consumed by core's resolve_llm_config -> LLMConfig -> the agent's
        # LLMProvider (ChatOpenAI) and llm_utils.quick_llm_call.
        return {
            "api_key": self._api_key,
            "base_url": self._require_base_url(),
            "default_headers": self._default_headers() or None,
            "verify_ssl": self._verify,
            "model_aliases": self._model_aliases() or None,
        }

    def _model_aliases(self) -> Dict[str, str]:
        from autobotAI_integrations.utils.model_helpers import parse_model_aliases

        return parse_model_aliases(self.integration.model_aliases)

    # -- model builders -----------------------------------------------------

    def get_pydantic_agent(
        self, model: str, tools, system_prompt: str, options: dict = {}
    ):
        from pydantic_ai import Agent
        from autobotAI_integrations.utils.agent_settings import prepare_agent_options
        from autobotAI_integrations.utils.model_helpers import resolve_model_alias

        model_instance = self.get_pydantic_model(model)
        underlying = resolve_model_alias(model, self._model_aliases() or None)
        options = prepare_agent_options("openai_compatible", underlying, options)
        return Agent(model_instance, system_prompt=system_prompt, tools=tools, **options)

    def get_pydantic_model(self, model_name: str):
        return self.build_model_from_credentials(model_name, self.generate_llm_credentials())

    @staticmethod
    def build_model_from_credentials(model_name: str, credentials: dict):
        from openai import AsyncOpenAI
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        from autobotAI_integrations.utils.model_helpers import (
            openai_profile_overrides,
            resolve_model_alias,
        )

        client_kwargs: Dict[str, Any] = {
            "api_key": _client_api_key(credentials.get("api_key")),
            "base_url": credentials.get("base_url"),
            "default_headers": credentials.get("default_headers") or None,
        }
        if credentials.get("verify_ssl") is False:
            import httpx

            client_kwargs["http_client"] = httpx.AsyncClient(verify=False)
        underlying = resolve_model_alias(model_name, credentials.get("model_aliases"))
        return OpenAIChatModel(
            model_name=model_name,
            provider=OpenAIProvider(openai_client=AsyncOpenAI(**client_kwargs)),
            profile=openai_profile_overrides(underlying) or None,
        )

    def load_llama_index_llm(self, model, **kwargs):
        from autobotAI_integrations.utils.llama_index_helpers import (
            build_openai_compatible_llm,
            openai_context_window,
        )

        kwargs.setdefault("context_window", openai_context_window(model))
        headers = self._default_headers()
        if headers:
            kwargs.setdefault("default_headers", headers)
        if not self._verify:
            import httpx

            kwargs.setdefault("http_client", httpx.Client(verify=False))
            kwargs.setdefault("async_http_client", httpx.AsyncClient(verify=False))
        return build_openai_compatible_llm(
            model,
            api_key=self._api_key,
            api_base=self._require_base_url(),
            is_chat_model=True,
            **kwargs,
        )

    def load_llama_index_embedding_model(
        self, model_name: Optional[str] = None, **kwargs
    ):
        """Embeddings via the gateway's OpenAI-compatible ``/embeddings`` route.

        There is no safe default: a gateway's embedding model names are its
        own. ``model_name`` (not ``model``) carries the id, because llama-index
        validates ``model`` against OpenAI's fixed enum.
        """
        if not model_name:
            raise ValueError(
                "Choose an embedding model for this OpenAI-compatible gateway "
                "(the memory space's Embedding Model)."
            )
        from llama_index.embeddings.openai import OpenAIEmbedding

        headers = self._default_headers()
        if headers:
            kwargs.setdefault("default_headers", headers)
        if not self._verify:
            import httpx

            kwargs.setdefault("http_client", httpx.Client(verify=False))
            kwargs.setdefault("async_http_client", httpx.AsyncClient(verify=False))
        return OpenAIEmbedding(
            api_key=self._api_key,
            api_base=self._require_base_url(),
            model_name=model_name,
            **kwargs,
        )
