"""AIBaseService.test_model — the model picker's "selectable" probe.

Reasoning models (DeepSeek, gpt-5.x, Sarvam) can spend the probe's token
budget thinking and return no text. That is still a working model, so the
probe must pass on any provider response and fail only on real errors.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import autobotAI_integrations.integrations.openrouter as openrouter_mod
from autobotAI_integrations.integrations.azure_foundry_openai import AzureOpenAIService
from autobotAI_integrations.integrations.openai import OpenAIService

_CHAT_REASONING_ONLY = {
    "id": "c",
    "object": "chat.completion",
    "created": 0,
    "model": "m",
    "choices": [
        {
            "index": 0,
            "finish_reason": "length",
            "message": {"role": "assistant", "content": None, "reasoning_content": "thinking"},
        }
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 64, "total_tokens": 65},
}

_RESPONSES_REASONING_ONLY = {
    "id": "resp_1",
    "object": "response",
    "created_at": 0,
    "model": "m",
    "status": "incomplete",
    "incomplete_details": {"reason": "max_output_tokens"},
    "output": [{"id": "rs_1", "type": "reasoning", "summary": []}],
    "parallel_tool_calls": True,
    "tool_choice": "auto",
    "tools": [],
    "usage": {
        "input_tokens": 1,
        "output_tokens": 64,
        "total_tokens": 65,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 64},
    },
}


class _Provider(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.calls.append((self.path, body))
        code, payload = self.server.reply(self.path, body)
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _reasoning_only(path, body):
    if path.endswith("/responses"):
        return 200, _RESPONSES_REASONING_ONLY
    return 200, _CHAT_REASONING_ONLY


@pytest.fixture
def provider(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _Provider)
    server.calls = []
    server.reply = _reasoning_only
    threading.Thread(target=server.serve_forever, daemon=True).start()
    server.base = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setenv("OPENAI_BASE_URL", f"{server.base}/v1")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "0")
    monkeypatch.setattr(openrouter_mod, "OPENROUTER_BASE_URL", f"{server.base}/v1")
    yield server
    server.shutdown()


_COMMON = {"userId": "t@pytest.com", "alias": "x", "accountId": "a", "api_key": "k"}


def _openai():
    return OpenAIService(ctx=None, integration={**_COMMON, "cspName": "openai"})


def _openrouter():
    return openrouter_mod.OpenRouterService(
        ctx=None, integration={**_COMMON, "cspName": "openrouter"}
    )


def _azure(base):
    svc = AzureOpenAIService(
        ctx=None,
        integration={
            **_COMMON,
            "cspName": "azure_foundry_openai",
            "azure_endpoint": "https://placeholder.example.com",
        },
    )
    svc.integration.azure_endpoint = base  # schema requires https; the fake is http
    return svc


@pytest.mark.parametrize(
    "make, model, path",
    [
        (lambda p: _openai(), "gpt-5.4", "/v1/responses"),
        (lambda p: _openrouter(), "deepseek/deepseek-v4-flash", "/v1/chat/completions"),
        (lambda p: _azure(p.base), "gpt-5.4", "/openai/v1/responses"),
    ],
    ids=["openai", "openrouter", "azure_foundry_openai"],
)
def test_reasoning_model_with_no_text_is_selectable(provider, make, model, path):
    res = make(provider).test_model(model)
    assert res["success"] is True, res
    assert res["model"] == model and isinstance(res["latency_ms"], int)
    assert len(provider.calls) == 1  # one request, no retry loop
    called_path, body = provider.calls[0]
    assert called_path == path
    assert body["model"] == model
    sent_cap = body.get("max_tokens") or body.get("max_output_tokens") or body.get(
        "max_completion_tokens"
    )
    assert sent_cap == 64


@pytest.mark.parametrize(
    "code, err",
    [(401, {"error": {"message": "invalid api key", "type": "auth"}}),
     (404, {"error": {"message": "model not found", "type": "invalid_request_error"}})],
)
def test_provider_errors_still_fail(provider, code, err):
    provider.reply = lambda path, body: (code, err)
    res = _openrouter().test_model("nope")
    assert res["success"] is False
    assert res["model"] == "nope"
    assert str(code) in res["error"] or err["error"]["message"] in res["error"]
