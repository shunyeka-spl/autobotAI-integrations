"""The Bedrock field-rejection fallback.

Two things have to hold at once: a 400 that names an unsupported field must
stop killing the run, and *nothing else* may change. The second half is why
most of these tests assert that an error propagates untouched.
"""

import unittest

from pydantic_ai.exceptions import ModelHTTPError

from autobotAI_integrations.utils import bedrock_fallback as bf


def _validation_error(message, model="global.xai.grok-4.6", code="ValidationException"):
    """A ModelHTTPError shaped exactly like the ones Bedrock produces."""
    return ModelHTTPError(
        status_code=400,
        model_name=model,
        body={
            "Error": {"Message": message, "Code": code},
            "ResponseMetadata": {"HTTPStatusCode": 400, "RetryAttempts": 0},
        },
    )


GROK_TEMPERATURE = (
    "This model doesn't support the temperature field. "
    "Remove temperature and try again."
)
NOVA_EXTENDED_TTL = "Extended TTL prompt caching is only supported for Anthropic models"


class TestErrorInspection(unittest.TestCase):
    def test_recognises_a_bedrock_validation_exception(self):
        exc = _validation_error(GROK_TEMPERATURE)
        self.assertEqual(bf.validation_message(exc), GROK_TEMPERATURE)

    def test_ignores_other_error_codes(self):
        exc = _validation_error("Too many requests", code="ThrottlingException")
        self.assertIsNone(bf.validation_message(exc))

    def test_ignores_other_status_codes(self):
        exc = ModelHTTPError(
            status_code=500,
            model_name="m",
            body={"Error": {"Message": GROK_TEMPERATURE, "Code": "ValidationException"}},
        )
        self.assertIsNone(bf.validation_message(exc))

    def test_ignores_unrelated_exceptions(self):
        self.assertIsNone(bf.validation_message(RuntimeError("boom")))
        self.assertIsNone(bf.validation_message(TimeoutError()))

    def test_reads_a_raw_botocore_client_error_shape(self):
        class _ClientError(Exception):
            response = {
                "Error": {"Message": GROK_TEMPERATURE, "Code": "ValidationException"},
                "ResponseMetadata": {"HTTPStatusCode": 400},
            }

        self.assertEqual(bf.validation_message(_ClientError()), GROK_TEMPERATURE)


class TestDetectActions(unittest.TestCase):
    def test_temperature_rejection_drops_only_temperature(self):
        settings = {"temperature": 0.3, "max_tokens": 8192, "top_p": 0.9}
        actions = bf.detect_actions(GROK_TEMPERATURE, settings)
        self.assertEqual(actions, ["drop:temperature"])
        self.assertEqual(
            bf.apply_actions(settings, actions), {"max_tokens": 8192, "top_p": 0.9}
        )

    def test_extended_ttl_downgrades_the_cache_instead_of_disabling_it(self):
        settings = {
            "bedrock_cache_instructions": "1h",
            "bedrock_cache_tool_definitions": "1h",
            "temperature": 0.3,
        }
        actions = bf.detect_actions(NOVA_EXTENDED_TTL, settings)
        self.assertEqual(actions, [bf.CACHE_TTL_ACTION])
        self.assertEqual(
            bf.apply_actions(settings, actions),
            {
                "bedrock_cache_instructions": True,
                "bedrock_cache_tool_definitions": True,
                "temperature": 0.3,
            },
        )

    def test_caching_unsupported_removes_the_cache_hints(self):
        settings = {"bedrock_cache_instructions": True, "max_tokens": 4096}
        actions = bf.detect_actions(
            "This model does not support prompt caching", settings
        )
        self.assertEqual(actions, [bf.CACHE_OFF_ACTION])
        self.assertEqual(bf.apply_actions(settings, actions), {"max_tokens": 4096})

    def test_top_p_and_top_k_are_recognised_in_bedrocks_camel_case(self):
        self.assertEqual(
            bf.detect_actions("This model doesn't support the topP field", {"top_p": 1}),
            ["drop:top_p"],
        )
        self.assertEqual(
            bf.detect_actions("topK is not supported for this model", {"top_k": 5}),
            ["drop:top_k"],
        )

    def test_a_field_we_do_not_have_set_produces_no_action(self):
        # Retrying an identical request would just fail identically.
        self.assertEqual(bf.detect_actions(GROK_TEMPERATURE, {"max_tokens": 10}), [])

    def test_unrecognised_messages_produce_no_action(self):
        for message in (
            "Input is too long for requested model.",
            "The security token included in the request is invalid.",
            "Malformed input request: expected type: String, found: Integer.",
        ):
            self.assertEqual(bf.detect_actions(message, {"temperature": 0.3}), [], message)

    def test_never_drops_contractual_settings(self):
        # Even if Bedrock phrases a complaint about one of these, they are not
        # ours to remove — the caller asked for them.
        settings = {"max_tokens": 8192, "stop_sequences": ["x"], "tool_choice": "auto"}
        for message in (
            "This model doesn't support the max_tokens field",
            "stop_sequences is not supported for this model",
            "This model does not support tool_choice",
        ):
            self.assertEqual(bf.detect_actions(message, settings), [], message)

    def test_apply_actions_does_not_mutate_the_input(self):
        settings = {"temperature": 0.3}
        bf.apply_actions(settings, ["drop:temperature"])
        self.assertEqual(settings, {"temperature": 0.3})


class TestRetryLoop(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        bf.reset_learned()

    def tearDown(self):
        bf.reset_learned()

    async def test_retries_once_without_the_rejected_field(self):
        seen = []

        async def call(settings):
            seen.append(dict(settings or {}))
            if "temperature" in (settings or {}):
                raise _validation_error(GROK_TEMPERATURE)
            return "ok"

        result = await bf.run_with_field_fallback(
            "global.xai.grok-4.6", {"temperature": 0.3, "max_tokens": 100}, call
        )
        self.assertEqual(result, "ok")
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[1], {"max_tokens": 100})

    async def test_a_successful_call_is_never_retried(self):
        calls = []

        async def call(settings):
            calls.append(settings)
            return "ok"

        await bf.run_with_field_fallback("m", {"temperature": 0.3}, call)
        self.assertEqual(len(calls), 1)

    async def test_unrelated_errors_propagate_untouched_and_immediately(self):
        calls = []

        async def call(settings):
            calls.append(settings)
            raise RuntimeError("upstream is down")

        with self.assertRaises(RuntimeError):
            await bf.run_with_field_fallback("m", {"temperature": 0.3}, call)
        self.assertEqual(len(calls), 1, "a non-recoverable error must not be retried")

    async def test_throttling_is_left_to_the_callers_own_retry(self):
        calls = []

        async def call(settings):
            calls.append(settings)
            raise _validation_error("Rate exceeded", code="ThrottlingException")

        with self.assertRaises(ModelHTTPError):
            await bf.run_with_field_fallback("m", {"temperature": 0.3}, call)
        self.assertEqual(len(calls), 1)

    async def test_two_rejected_fields_are_stripped_in_sequence(self):
        async def call(settings):
            settings = settings or {}
            if "temperature" in settings:
                raise _validation_error(GROK_TEMPERATURE)
            if "top_p" in settings:
                raise _validation_error("This model doesn't support the topP field")
            return "ok"

        result = await bf.run_with_field_fallback(
            "m", {"temperature": 0.3, "top_p": 0.9, "max_tokens": 5}, call
        )
        self.assertEqual(result, "ok")

    async def test_the_attempt_count_is_capped(self):
        calls = []

        async def call(settings):
            calls.append(dict(settings or {}))
            # Keeps naming a *different* droppable field, so every attempt makes
            # progress and only the cap can stop it.
            for field in ("temperature", "top_p", "top_k", "seed"):
                if field in (settings or {}):
                    raise _validation_error(f"{field} is not supported for this model")
            return "ok"

        with self.assertRaises(ModelHTTPError):
            await bf.run_with_field_fallback(
                "m",
                {"temperature": 0.1, "top_p": 0.9, "top_k": 3, "seed": 1},
                call,
            )
        self.assertEqual(len(calls), bf.MAX_ATTEMPTS)

    async def test_the_rejection_is_remembered_for_the_next_call(self):
        seen = []

        async def call(settings):
            seen.append(dict(settings or {}))
            if "temperature" in (settings or {}):
                raise _validation_error(GROK_TEMPERATURE)
            return "ok"

        await bf.run_with_field_fallback("global.xai.grok-4.6", {"temperature": 0.3}, call)
        await bf.run_with_field_fallback("global.xai.grok-4.6", {"temperature": 0.3}, call)

        # First call: rejected, then retried. Second call: straight through.
        self.assertEqual(len(seen), 3)
        self.assertEqual(seen[2], {})

    async def test_what_one_model_rejects_does_not_affect_another(self):
        async def call(settings):
            if "temperature" in (settings or {}):
                raise _validation_error(GROK_TEMPERATURE)
            return "ok"

        await bf.run_with_field_fallback("global.xai.grok-4.6", {"temperature": 0.3}, call)
        self.assertEqual(bf.learned_actions("global.xai.grok-4.6"), ["drop:temperature"])
        self.assertEqual(bf.learned_actions("global.anthropic.claude-sonnet-5"), [])


class TestModelSubclass(unittest.TestCase):
    def test_it_subclasses_bedrock_converse_model_and_is_built_once(self):
        from pydantic_ai.models.bedrock import BedrockConverseModel

        cls = bf.resilient_model_class()
        self.assertTrue(issubclass(cls, BedrockConverseModel))
        self.assertIs(cls, bf.resilient_model_class())

    def test_it_overrides_both_request_paths(self):
        from pydantic_ai.models.bedrock import BedrockConverseModel

        cls = bf.resilient_model_class()
        self.assertIsNot(cls.request, BedrockConverseModel.request)
        self.assertIsNot(cls.request_stream, BedrockConverseModel.request_stream)


class TestModelSubclassEndToEnd(unittest.IsolatedAsyncioTestCase):
    """Drive the real subclass, with only the parent's transport stubbed out.

    This is what the AI agent node actually calls, so it catches a wiring
    mistake the helper-level tests above would miss.
    """

    def setUp(self):
        from pydantic_ai.providers.bedrock import BedrockProvider

        bf.reset_learned()
        # No network happens at construction; the credentials are never used.
        self.model = bf.build_model(
            model_name="global.xai.grok-4.6",
            provider=BedrockProvider(
                aws_access_key_id="AKIAFAKE",
                aws_secret_access_key="fake",
                region_name="us-east-1",
            ),
        )

    def tearDown(self):
        bf.reset_learned()

    async def test_request_recovers(self):
        from unittest.mock import patch

        from pydantic_ai.models.bedrock import BedrockConverseModel

        seen = []

        async def parent_request(inner_self, messages, model_settings, params):
            seen.append(dict(model_settings or {}))
            if "temperature" in (model_settings or {}):
                raise _validation_error(GROK_TEMPERATURE)
            return "RESPONSE"

        with patch.object(BedrockConverseModel, "request", parent_request):
            result = await self.model.request([], {"temperature": 0.3, "max_tokens": 100}, None)

        self.assertEqual(result, "RESPONSE")
        self.assertEqual(seen, [{"temperature": 0.3, "max_tokens": 100}, {"max_tokens": 100}])

    async def test_request_stream_recovers(self):
        from contextlib import asynccontextmanager
        from unittest.mock import patch

        from pydantic_ai.models.bedrock import BedrockConverseModel

        seen = []

        @asynccontextmanager
        async def parent_stream(inner_self, messages, model_settings, params, run_context=None):
            seen.append(dict(model_settings or {}))
            if "temperature" in (model_settings or {}):
                raise _validation_error(GROK_TEMPERATURE)
            yield "STREAM"

        with patch.object(BedrockConverseModel, "request_stream", parent_stream):
            async with self.model.request_stream(
                [], {"temperature": 0.3, "max_tokens": 100}, None
            ) as response:
                self.assertEqual(response, "STREAM")

        self.assertEqual(seen, [{"temperature": 0.3, "max_tokens": 100}, {"max_tokens": 100}])

    async def test_a_failure_while_consuming_the_stream_is_not_retried(self):
        from contextlib import asynccontextmanager
        from unittest.mock import patch

        from pydantic_ai.models.bedrock import BedrockConverseModel

        opened = []

        @asynccontextmanager
        async def parent_stream(inner_self, messages, model_settings, params, run_context=None):
            opened.append(dict(model_settings or {}))
            yield "STREAM"

        with patch.object(BedrockConverseModel, "request_stream", parent_stream):
            with self.assertRaises(ValueError):
                async with self.model.request_stream([], {"temperature": 0.3}, None):
                    # The model is already generating; re-issuing the call here
                    # would double-bill and duplicate output.
                    raise ValueError("consumer blew up")

        self.assertEqual(len(opened), 1)


if __name__ == "__main__":
    unittest.main()
