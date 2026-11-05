"""OpenAI-compatible gateway integration, exercised against a local fake gateway."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from autobotAI_integrations.deep_agent_schema import LLMConfig
from autobotAI_integrations.integrations.openai_compatible import (
    OpenAICompatibleIntegration,
    OpenAICompatibleService,
    build_headers,
    parse_model_list,
)
from autobotAI_integrations.llm_utils import quick_llm_call
from autobotAI_integrations.utils.model_helpers import (
    parse_model_aliases,
    resolve_model_alias,
)


class _Gateway(BaseHTTPRequestHandler):
    """Minimal OpenAI-compatible gateway. Behaviour is set on the server."""

    def log_message(self, *args):
        pass

    def _authorized(self):
        srv = self.server
        if srv.auth_header is None:
            return True
        return self.headers.get(srv.auth_header) == srv.expected_auth

    def _send(self, code, body):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.server.requests.append(("GET", self.path, dict(self.headers), None))
        if not self._authorized():
            return self._send(403, {"error": "invalid_api_key"})
        if self.path == "/v1/models" and self.server.has_models:
            return self._send(
                200,
                {"object": "list", "data": [{"id": m, "object": "model"} for m in self.server.models]},
            )
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        self.server.requests.append(("POST", self.path, dict(self.headers), body))
        if not self._authorized():
            return self._send(401, {"error": "invalid_api_key"})
        if self.path == "/v1/embeddings" and getattr(self.server, "embeddings_handler", None):
            return self.server.embeddings_handler(self, body)
        if self.path != "/v1/chat/completions":
            return self._send(404, {"error": "not found"})
        if body.get("model") not in self.server.models:
            return self._send(404, {"error": f"model {body.get('model')} not found"})
        if getattr(self.server, "chat_handler", None):
            return self.server.chat_handler(self, body)
        return self._send(
            200,
            {
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 0,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "pong"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )


@pytest.fixture
def gateway():
    server = HTTPServer(("127.0.0.1", 0), _Gateway)
    server.requests = []
    server.models = ["smart", "fast"]
    server.has_models = True
    server.auth_header = "Authorization"
    server.expected_auth = "Bearer sk-rt-good"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.base_url = f"http://127.0.0.1:{server.server_port}/v1"
    yield server
    server.shutdown()


_BASE = {"userId": "test@pytest.com", "cspName": "openai_compatible", "alias": "gw"}


def _schema(**fields):
    return OpenAICompatibleIntegration(**_BASE, **fields)


def _service(**fields):
    integration = {**_BASE, "accountId": "acc-1", **fields}
    return OpenAICompatibleService(ctx=None, integration=integration)


# -- schema / helpers ---------------------------------------------------------


def test_base_url_strips_trailing_slash_and_chat_path():
    s = _schema(base_url=" https://gw.example.com/v1/chat/completions/ ")
    assert s.base_url == "https://gw.example.com/v1"


def test_extra_headers_accepts_json_string_and_rejects_garbage():
    s = _schema(extra_headers='{"x-portkey-provider": "openai"}')
    assert s.extra_headers == {"x-portkey-provider": "openai"}
    with pytest.raises(ValueError):
        _schema(extra_headers="not json")
    with pytest.raises(ValueError):
        _schema(extra_headers='["a"]')


def test_verify_ssl_defaults_true_and_coerces_strings():
    assert _schema().verify_ssl is True
    assert _schema(verify_ssl="false").verify_ssl is False
    assert _schema(verify_ssl=None).verify_ssl is True


def test_custom_auth_header_carries_the_key_and_wins_over_extra_headers():
    headers = build_headers("k", "x-api-key", {"x-api-key": "stale", "x-tenant": "t1"})
    assert headers == {"x-api-key": "k", "x-tenant": "t1"}
    assert build_headers("k", "Authorization", None) == {}
    assert build_headers(None, "x-api-key", None) == {}


def test_model_list_and_alias_parsing():
    assert parse_model_list("a\n b ,c\n# note\na") == ["a", "b", "c"]
    aliases = parse_model_aliases("smart = claude-opus-5-5\nfast: gpt-5-mini\nbroken\n# x=y")
    assert aliases == {"smart": "claude-opus-5-5", "fast": "gpt-5-mini"}
    assert resolve_model_alias("smart", aliases) == "claude-opus-5-5"
    assert resolve_model_alias("other", aliases) == "other"
    assert resolve_model_alias("smart", {"smart": "x"}) == "x"


# -- connection test ----------------------------------------------------------


def test_connection_ok_via_models_endpoint(gateway):
    svc = _service(base_url=gateway.base_url, api_key="sk-rt-good")
    assert svc._test_integration() == {"success": True}


def test_bad_key_reports_auth_failure_on_403(gateway):
    svc = _service(base_url=gateway.base_url, api_key="wrong")
    result = svc._test_integration()
    assert result["success"] is False
    assert "Authentication failed (HTTP 403)" in result["error"]


def test_no_models_endpoint_falls_back_to_a_configured_model(gateway):
    gateway.has_models = False
    svc = _service(base_url=gateway.base_url, api_key="sk-rt-good", models="smart")
    assert svc._test_integration() == {"success": True}
    method, path, _, body = gateway.requests[-1]
    assert (method, path, body["model"]) == ("POST", "/v1/chat/completions", "smart")


def test_no_models_endpoint_and_no_configured_models_explains_the_fix(gateway):
    gateway.has_models = False
    svc = _service(base_url=gateway.base_url, api_key="sk-rt-good")
    result = svc._test_integration()
    assert result["success"] is False
    assert "Models field" in result["error"]


def test_custom_header_gateway(gateway):
    gateway.auth_header = "x-api-key"
    gateway.expected_auth = "k-123"
    svc = _service(base_url=gateway.base_url, api_key="k-123", auth_header_name="x-api-key")
    assert svc._test_integration() == {"success": True}


def test_unreachable_gateway_gives_a_network_hint():
    svc = _service(base_url="http://127.0.0.1:9/v1", api_key="k")
    result = svc._test_integration()
    assert result["success"] is False
    assert "Could not connect" in result["error"]


# -- model listing ------------------------------------------------------------


def test_models_merge_configured_first_then_discovered(gateway):
    svc = _service(base_url=gateway.base_url, api_key="sk-rt-good", models="fast\nextra")
    details = svc.get_integration_specific_details()
    assert details["models"] == ["fast", "extra", "smart"]
    assert details["embedding_models"] == details["models"]


def test_models_fall_back_to_configured_when_gateway_has_no_list(gateway):
    gateway.has_models = False
    svc = _service(base_url=gateway.base_url, api_key="sk-rt-good", models="smart")
    assert svc.get_integration_specific_details()["models"] == ["smart"]


# -- llm credentials / runtime ------------------------------------------------


def test_llm_credentials_shape():
    svc = _service(
        base_url="https://gw/v1",
        api_key="Bearer k",
        auth_header_name="api-key",
        extra_headers={"x-route": "a"},
        model_aliases="smart=claude-opus-5-5",
        verify_ssl=False,
    )
    creds = svc.generate_llm_credentials()
    assert creds == {
        "api_key": "k",
        "base_url": "https://gw/v1",
        "default_headers": {"x-route": "a", "api-key": "k"},
        "verify_ssl": False,
        "model_aliases": {"smart": "claude-opus-5-5"},
    }
    # Round-trips through the shared schema core builds for the agent.
    cfg = LLMConfig(provider="openai_compatible", model="smart", **creds)
    assert cfg.default_headers == {"x-route": "a", "api-key": "k"}
    assert cfg.verify_ssl is False


def test_keyless_gateway_still_builds_a_client():
    creds = _service(base_url="http://vllm:8000/v1").generate_llm_credentials()
    assert creds["api_key"] == "not-needed"
    assert creds["default_headers"] is None


def test_quick_llm_call_sends_headers_and_drops_temperature_for_aliased_model(gateway):
    gateway.auth_header = "x-api-key"
    gateway.expected_auth = "k-1"
    creds = _service(
        base_url=gateway.base_url,
        api_key="k-1",
        auth_header_name="x-api-key",
        extra_headers={"x-route": "blue"},
        model_aliases="smart=claude-opus-5-5",
    ).generate_llm_credentials()

    out = asyncio.run(
        quick_llm_call("ping", LLMConfig(provider="openai_compatible", model="smart", **creds))
    )
    assert out == "pong"
    _, path, headers, body = gateway.requests[-1]
    lower = {k.lower(): v for k, v in headers.items()}
    assert path == "/v1/chat/completions"
    assert body["model"] == "smart"  # the gateway's name goes on the wire
    assert "temperature" not in body  # ...but claude-opus-5-5's rules apply
    assert lower["x-api-key"] == "k-1"
    assert lower["x-route"] == "blue"


def test_quick_llm_call_keeps_temperature_for_unaliased_model(gateway):
    creds = _service(base_url=gateway.base_url, api_key="sk-rt-good").generate_llm_credentials()
    asyncio.run(quick_llm_call("ping", LLMConfig(provider="openai_compatible", model="fast", **creds)))
    assert gateway.requests[-1][3]["temperature"] == pytest.approx(0.1)


def test_embeddings_require_a_model_and_hit_the_gateway(gateway):
    gateway.models = ["embed-small"]

    def do_post_embeddings(handler, body):
        return handler._send(
            200,
            {
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]}],
                "model": body["model"],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    gateway.embeddings_handler = do_post_embeddings
    svc = _service(
        base_url=gateway.base_url,
        api_key="sk-rt-good",
        extra_headers={"x-route": "e"},
    )
    with pytest.raises(ValueError, match="embedding model"):
        svc.load_llama_index_embedding_model()
    emb = svc.load_llama_index_embedding_model("embed-small")
    assert emb.get_text_embedding("hello") == [0.1, 0.2, 0.3]
    _, path, headers, body = gateway.requests[-1]
    assert path == "/v1/embeddings"
    assert body["model"] == "embed-small"
    assert {k.lower(): v for k, v in headers.items()}["x-route"] == "e"


def test_llama_index_llm_goes_through_the_gateway_with_headers(gateway):
    gateway.auth_header = "api-key"
    gateway.expected_auth = "k-9"
    svc = _service(base_url=gateway.base_url, api_key="k-9", auth_header_name="api-key")
    llm = svc.load_llama_index_llm("fast")
    from llama_index.core.llms import ChatMessage

    assert llm.chat([ChatMessage(role="user", content="ping")]).message.content == "pong"
    _, path, headers, body = gateway.requests[-1]
    assert path == "/v1/chat/completions"
    assert {k.lower(): v for k, v in headers.items()}["api-key"] == "k-9"


# -- per-model probe (model picker "selectable" check) -------------------------


def test_test_model_accepts_a_reasoning_model_with_no_content(gateway):
    """sarvam-105b-style: 2xx with empty content + finish_reason=length is fine."""
    gateway.models = ["sarvam-105b"]

    def reasoning_only(handler, body):
        return handler._send(
            200,
            {
                "id": "c",
                "object": "chat.completion",
                "created": 0,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": None, "reasoning_content": "Hmm"},
                        "finish_reason": "length",
                    }
                ],
            },
        )

    gateway.chat_handler = reasoning_only
    svc = _service(base_url=gateway.base_url, api_key="sk-rt-good")
    res = svc.test_model("sarvam-105b")
    assert res["success"] is True and res["model"] == "sarvam-105b"
    assert isinstance(res["latency_ms"], int)
    body = gateway.requests[-1][3]
    assert body["max_tokens"] >= 64


def test_test_model_reports_unknown_model_and_bad_key(gateway):
    svc = _service(base_url=gateway.base_url, api_key="sk-rt-good")
    res = svc.test_model("nope")
    assert res["success"] is False and "HTTP 404" in res["error"]
    bad = _service(base_url=gateway.base_url, api_key="wrong").test_model("smart")
    assert bad["success"] is False and "Authentication failed" in bad["error"]


def test_test_model_unreachable_gateway():
    res = _service(base_url="http://127.0.0.1:9/v1", api_key="k").test_model("m")
    assert res["success"] is False and "Could not connect" in res["error"]
