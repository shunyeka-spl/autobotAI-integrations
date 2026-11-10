"""prepare_agent_model_settings: settings each model family accepts."""

import pytest

from autobotAI_integrations.utils.agent_settings import (
    is_claude_model,
    prepare_agent_model_settings,
    prepare_agent_options,
)

BEDROCK_OPUS_55 = "global.anthropic.claude-opus-5-5"
BEDROCK_SONNET_45 = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
NOVA = "global.amazon.nova-2-lite-v1:0"
LLAMA = "us.meta.llama3-3-70b-instruct-v1:0"
GROK = "xai.grok-4-6"


def test_none_values_removed():
    assert prepare_agent_model_settings("aws_bedrock", NOVA, {"temperature": None}) == {}


def test_temperature_kept_for_models_that_accept_it():
    for model in (NOVA, LLAMA, BEDROCK_SONNET_45, "gpt-4.1"):
        out = prepare_agent_model_settings("aws_bedrock", model, {"temperature": 0.2})
        assert out == {"temperature": 0.2}, model


@pytest.mark.parametrize("model", [BEDROCK_OPUS_55, GROK, "gpt-5-6", "gpt-6-luna", "anthropic/claude-opus-5.5"])
def test_temperature_dropped_for_models_that_reject_it(model):
    out = prepare_agent_model_settings("openrouter", model, {"temperature": 0.2, "top_p": 0.9})
    assert "temperature" not in out and "top_p" not in out


def test_reasoning_effort_maps_to_thinking():
    out = prepare_agent_model_settings("aws_bedrock", NOVA, {"reasoning_effort": "high"})
    assert out == {"thinking": "high"}


def test_reasoning_off():
    out = prepare_agent_model_settings("aws_bedrock", NOVA, {"reasoning_effort": "off", "temperature": 0.3})
    assert out == {"thinking": False, "temperature": 0.3}


def test_unknown_effort_is_ignored():
    out = prepare_agent_model_settings("aws_bedrock", NOVA, {"reasoning_effort": "turbo"})
    assert out == {}


def test_claude_thinking_drops_sampling_and_raises_max_tokens():
    out = prepare_agent_model_settings(
        "aws_bedrock",
        BEDROCK_SONNET_45,
        {"reasoning_effort": "medium", "temperature": 0.2, "top_p": 0.9, "top_k": 5, "max_tokens": 1000},
    )
    assert out == {"thinking": "medium", "max_tokens": 10000 + 4096}


def test_claude_thinking_keeps_large_max_tokens():
    out = prepare_agent_model_settings(
        "aws_bedrock", BEDROCK_SONNET_45, {"reasoning_effort": "low", "max_tokens": 50000}
    )
    assert out["max_tokens"] == 50000


def test_claude_without_thinking_keeps_temperature():
    out = prepare_agent_model_settings("aws_bedrock", BEDROCK_SONNET_45, {"temperature": 0.4})
    assert out == {"temperature": 0.4}


def test_non_claude_thinking_keeps_temperature():
    out = prepare_agent_model_settings("aws_bedrock", NOVA, {"reasoning_effort": "low", "temperature": 0.4})
    assert out == {"thinking": "low", "temperature": 0.4}


def test_openrouter_uses_reasoning_body_and_merges_extra_body():
    out = prepare_agent_model_settings(
        "openrouter",
        "anthropic/claude-sonnet-4.5",
        {"reasoning_effort": "high", "temperature": 0.2, "extra_body": {"provider": {"sort": "price"}}},
    )
    assert out["extra_body"] == {"provider": {"sort": "price"}, "reasoning": {"effort": "high"}}
    assert "temperature" not in out
    assert "thinking" not in out


def test_input_not_mutated():
    given = {"reasoning_effort": "high", "temperature": 0.2}
    prepare_agent_model_settings("aws_bedrock", BEDROCK_SONNET_45, given)
    assert given == {"reasoning_effort": "high", "temperature": 0.2}


def test_prepare_agent_options_removes_empty_settings():
    assert prepare_agent_options("openai", "gpt-4.1", {"name": "a", "model_settings": {"temperature": None}}) == {"name": "a"}
    assert prepare_agent_options("openai", "gpt-4.1", {"name": "a"}) == {"name": "a"}


@pytest.mark.parametrize(
    "model,requested,expected",
    [
        ("us.anthropic.claude-3-5-sonnet-20241022-v2:0", 16384, 8192),
        ("anthropic.claude-3-haiku-20240307-v1:0", 16384, 4096),
        ("amazon.nova-lite-v1:0", 16384, 10000),
        ("us.meta.llama3-3-70b-instruct-v1:0", 16384, 8192),
        ("gpt-4o", 32000, 16384),
        (BEDROCK_OPUS_55, 16384, 16384),
        (NOVA, 16384, 16384),  # nova 2 is not in the low-limit list
        ("unknown-model", 16384, 16384),
        ("anthropic.claude-3-haiku-20240307-v1:0", 1000, 1000),
    ],
)
def test_max_tokens_clamped_to_model_limit(model, requested, expected):
    out = prepare_agent_model_settings("aws_bedrock", model, {"max_tokens": requested})
    assert out["max_tokens"] == expected


@pytest.mark.parametrize(
    "model,expected",
    [
        (BEDROCK_OPUS_55, True),
        ("anthropic/claude-opus-5.5", True),
        ("claude-sonnet-5-5", True),
        (NOVA, False),
        ("gpt-5", False),
        ("", False),
    ],
)
def test_is_claude_model(model, expected):
    assert is_claude_model(model) is expected


# --- review fixes -----------------------------------------------------------


def test_adaptive_claude_thinking_leaves_max_tokens_unset():
    out = prepare_agent_model_settings(
        "aws_bedrock", BEDROCK_OPUS_55, {"reasoning_effort": "medium", "temperature": 0.2}
    )
    assert out == {"thinking": "medium"}


def test_adaptive_claude_thinking_keeps_given_max_tokens():
    out = prepare_agent_model_settings(
        "aws_bedrock", BEDROCK_OPUS_55, {"reasoning_effort": "high", "max_tokens": 16384}
    )
    assert out == {"thinking": "high", "max_tokens": 16384}


@pytest.mark.parametrize("value,expected", [("16384", 16384), (" 2000 ", 2000), (8000.0, 8000)])
def test_max_tokens_string_is_coerced(value, expected):
    out = prepare_agent_model_settings("aws_bedrock", NOVA, {"max_tokens": value})
    assert out == {"max_tokens": expected}


@pytest.mark.parametrize("value", ["abc", "", 0, -5, True, 1.5])
def test_unusable_max_tokens_is_dropped(value):
    assert prepare_agent_model_settings("aws_bedrock", NOVA, {"max_tokens": value}) == {}


def test_string_max_tokens_with_claude_thinking():
    out = prepare_agent_model_settings(
        "aws_bedrock", BEDROCK_SONNET_45, {"reasoning_effort": "high", "max_tokens": "16384"}
    )
    assert out == {"thinking": "high", "max_tokens": 16384 + 4096}


def test_opus_41_max_effort_steps_thinking_down_to_fit():
    out = prepare_agent_model_settings(
        "aws_bedrock", "us.anthropic.claude-opus-4-1-20250805-v1:0", {"reasoning_effort": "max"}
    )
    assert out["thinking"] == "high"
    assert out["max_tokens"] == 16384 + 4096
    assert out["max_tokens"] <= 32000


def test_opus_4_max_tokens_clamped():
    out = prepare_agent_model_settings(
        "aws_bedrock", "us.anthropic.claude-opus-4-20250514-v1:0", {"max_tokens": 64000}
    )
    assert out["max_tokens"] == 32000


@pytest.mark.parametrize(
    "model",
    [
        "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        "anthropic.claude-3-haiku-20240307-v1:0",
        "anthropic.claude-3-opus-20240229-v1:0",
    ],
)
def test_claude_without_thinking_support_keeps_temperature(model):
    out = prepare_agent_model_settings(
        "aws_bedrock", model, {"reasoning_effort": "low", "temperature": 0.1, "max_tokens": 4000}
    )
    assert out["temperature"] == 0.1
    assert out["max_tokens"] == 4000


@pytest.mark.parametrize(
    "provider,model",
    [
        ("ollama", "llama3.1"),
        ("openai_compatible", "meta-llama/Llama-3.1-70B-Instruct"),
        ("openrouter", "mistralai/mistral-large"),
    ],
)
def test_open_weight_limits_only_apply_on_bedrock(provider, model):
    out = prepare_agent_model_settings(provider, model, {"max_tokens": 32000})
    assert out["max_tokens"] == 32000


def test_provider_independent_limits_apply_everywhere():
    out = prepare_agent_model_settings("openrouter", "anthropic/claude-3.5-sonnet", {"max_tokens": 16384})
    assert out["max_tokens"] == 8192


def test_prompt_caching_none_is_kept_as_off():
    out = prepare_agent_model_settings(
        "aws_bedrock", NOVA, {"enable_prompt_caching": None, "temperature": None}
    )
    assert out == {"enable_prompt_caching": None}
