"""quick_llm_call sends a reasoning setting when asked, in the field each
provider reads (OpenRouter: its own `reasoning` body field)."""
import asyncio
import json

import httpx
import pytest

from autobotAI_integrations import llm_utils
from autobotAI_integrations.deep_agent_schema import LLMConfig
from autobotAI_integrations.llm_utils import quick_llm_call, reasoning_settings


def test_reasoning_settings_per_provider():
    assert reasoning_settings("openrouter", "low") == {"extra_body": {"reasoning": {"effort": "low"}}}
    assert reasoning_settings("openrouter", "max") == {"extra_body": {"reasoning": {"effort": "high"}}}
    assert reasoning_settings("openrouter", "off") == {"extra_body": {"reasoning": {"enabled": False}}}
    assert reasoning_settings("aws_bedrock", "medium") == {"thinking": "medium"}
    assert reasoning_settings("openai", "max") == {"thinking": "xhigh"}
    assert reasoning_settings("openai", "off") == {"thinking": False}


@pytest.mark.parametrize("effort", [None, "", "bogus"])
def test_unset_or_unknown_effort_sends_nothing(effort):
    assert reasoning_settings("openrouter", effort) == {}


def _capture_openrouter_body(monkeypatch, **call_kw):
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.update(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    model = OpenAIChatModel("deepseek/deepseek-v4.1-flash", provider=OpenAIProvider(
        api_key="k", base_url="https://openrouter.test/api/v1", http_client=client))
    monkeypatch.setattr(llm_utils, "_build_model", lambda cfg: model)
    cfg = LLMConfig(provider="openrouter", model="deepseek/deepseek-v4.1-flash", api_key="k",
                    **call_kw.pop("cfg", {}))
    out = asyncio.run(quick_llm_call("hi", cfg, max_tokens=50, **call_kw))
    assert out == "ok"
    return sent


def test_openrouter_request_carries_reasoning_effort(monkeypatch):
    sent = _capture_openrouter_body(monkeypatch, reasoning_effort="low")
    assert sent["reasoning"] == {"effort": "low"}
    assert 50 in (sent.get("max_tokens"), sent.get("max_completion_tokens"))


def test_llm_config_effort_is_the_fallback(monkeypatch):
    sent = _capture_openrouter_body(monkeypatch, cfg={"reasoning_effort": "medium"})
    assert sent["reasoning"] == {"effort": "medium"}


def test_no_effort_leaves_the_request_unchanged(monkeypatch):
    sent = _capture_openrouter_body(monkeypatch)
    assert "reasoning" not in sent
    assert sent["temperature"] == 0.1


def test_reasoning_on_omits_temperature(monkeypatch):
    # Anthropic with thinking on 400s on temperature != 1 (goal review on
    # global.anthropic.claude-opus-4-6-v1 with reasoning_effort="low").
    sent = _capture_openrouter_body(monkeypatch, reasoning_effort="low", temperature=0.0)
    assert "temperature" not in sent


def test_reasoning_off_keeps_temperature(monkeypatch):
    sent = _capture_openrouter_body(monkeypatch, reasoning_effort="off", temperature=0.0)
    assert sent["temperature"] == 0.0


def _capture_model_settings(monkeypatch, provider, model_id, **call_kw):
    captured = {}

    class _Result:
        output = "ok"

    class _FakeAgent:
        def __init__(self, model, *, model_settings, **_):
            captured.update(model_settings)

        async def run(self, prompt):
            return _Result()

    monkeypatch.setattr(llm_utils, "_build_model", lambda cfg: object())
    monkeypatch.setattr(llm_utils, "Agent", _FakeAgent)
    cfg = LLMConfig(provider=provider, model=model_id, api_key="k")
    asyncio.run(quick_llm_call("hi", cfg, **call_kw))
    return captured


def test_bedrock_opus_4_6_thinking_drops_temperature(monkeypatch):
    settings = _capture_model_settings(
        monkeypatch, "aws_bedrock", "global.anthropic.claude-opus-4-6-v1",
        reasoning_effort="low", temperature=0.0,
    )
    assert settings["thinking"] == "low"
    assert "temperature" not in settings


def test_bedrock_opus_4_6_without_thinking_keeps_temperature(monkeypatch):
    settings = _capture_model_settings(
        monkeypatch, "aws_bedrock", "global.anthropic.claude-opus-4-6-v1", temperature=0.0,
    )
    assert settings["temperature"] == 0.0
