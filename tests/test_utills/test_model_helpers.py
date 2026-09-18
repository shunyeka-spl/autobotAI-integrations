"""Bedrock per-model compatibility gates.

Both checks exist because Bedrock answers an unsupported field with a 400
ValidationException that takes the entire turn down — there is no graceful
degradation to fall back on.
"""

import unittest

from autobotAI_integrations.utils.model_helpers import (
    bedrock_model_rejects_temperature,
    bedrock_model_supports_extended_cache_ttl,
)


class TestTemperatureRejection(unittest.TestCase):
    def test_grok_4_6_rejects_temperature(self):
        # "This model doesn't support the temperature field. Remove
        # temperature and try again."
        for model in (
            "global.xai.grok-4.6",
            "us.xai.grok-4.6",
            "xai.grok-4.6",
        ):
            self.assertTrue(bedrock_model_rejects_temperature(model), model)

    def test_other_models_still_take_temperature(self):
        for model in (
            "global.amazon.nova-2-lite-v1:0",
            "us.meta.llama4-maverick-17b-instruct-v1:0",
            "global.xai.grok-4-fast",
            "",
        ):
            self.assertFalse(bedrock_model_rejects_temperature(model), model)


class TestExtendedCacheTTL(unittest.TestCase):
    def test_only_anthropic_models_accept_an_explicit_ttl(self):
        self.assertTrue(
            bedrock_model_supports_extended_cache_ttl(
                "global.anthropic.claude-sonnet-5-20250929-v1:0"
            )
        )
        self.assertTrue(
            bedrock_model_supports_extended_cache_ttl(
                "anthropic.claude-3-5-sonnet-20240620-v1:0"
            )
        )

    def test_non_anthropic_models_must_use_the_bare_cache_point(self):
        # "Extended TTL prompt caching is only supported for Anthropic models"
        for model in (
            "global.amazon.nova-2-lite-v1:0",
            "global.xai.grok-4.6",
            "us.meta.llama4-maverick-17b-instruct-v1:0",
            "",
        ):
            self.assertFalse(bedrock_model_supports_extended_cache_ttl(model), model)


if __name__ == "__main__":
    unittest.main()
