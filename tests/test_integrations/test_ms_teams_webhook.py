"""Teams webhook URL handling.

Office 365 Incoming Webhooks and Teams Workflows (Power Automate) URLs are
both accepted. Workflow URLs are posted as Adaptive Cards; a MessageCard is
dropped by the default "Post to a channel when a webhook request is received"
flow.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autobotAI_integrations.integrations.ms_teams import MsTeamsService
from autobotAI_integrations.integrations.ms_teams.webhook import (
    WorkflowConnectorCard,
    classify_teams_webhook,
    to_workflow_message,
)

LEGACY_URL = (
    "https://contoso.webhook.office.com/webhookb2/"
    "bc9fdbf4-8ce7-4c63-a6c5-2ce3c7a3f295@1943a128-2a2b-4f70-b73d-2134d1fca9b6/"
    "IncomingWebhook/469d969e6a52442085a2364e73c54212/"
    "75abd98f-93cc-4d82-9e50-176d8f2271de"
)

WORKFLOW_URL = (
    "https://default1f4beacdb7aa49b2aaa1b8525cb257.e0.environment.api.powerplatform.com:443"
    "/powerautomate/automations/direct/cu/06/workflows/"
    "e14ba1e47c204de68d8d45cdb363bef4/triggers/manual/paths/invoke"
    "?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=test-signature"
)

LOGIC_APP_URL = (
    "https://prod-00.westus.logic.azure.com:443/workflows/"
    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/triggers/manual/paths/invoke"
    "?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=test-signature"
)


def _svc(webhook, ctx=None):
    return MsTeamsService(
        ctx if ctx is not None else {},
        {
            "userId": "u-1",
            "cspName": "ms_teams",
            "alias": "teams",
            "webhook": webhook,
        },
    )


class TestClassifyTeamsWebhook:
    @pytest.mark.parametrize("url", [LEGACY_URL, LEGACY_URL + "?foo=1"])
    def test_legacy_incoming_webhook(self, url):
        assert classify_teams_webhook(url) == "connector"

    @pytest.mark.parametrize("url", [WORKFLOW_URL, LOGIC_APP_URL, "  " + WORKFLOW_URL + "  "])
    def test_workflow_webhook(self, url):
        assert classify_teams_webhook(url) == "workflow"

    @pytest.mark.parametrize(
        "url",
        [
            "",
            None,
            "https://example.com/hook",
            "http://prod-00.westus.logic.azure.com/workflows/abc/triggers/manual/paths/invoke?sig=x",
            WORKFLOW_URL.split("sig=")[0],
            "https://evil.logic.azure.com.attacker.test/workflows/abc/triggers/manual/paths/invoke?sig=x",
        ],
    )
    def test_rejects_other_urls(self, url):
        assert classify_teams_webhook(url) is None


class TestWorkflowMessage:
    def test_adaptive_card_envelope(self):
        message = to_workflow_message(
            {
                "title": "Approval",
                "text": "Please review<br><b>now</b>",
                "potentialAction": [
                    {
                        "@type": "ViewAction",
                        "name": "Open",
                        "target": ["https://example.com/approve"],
                    }
                ],
                "sections": [
                    {
                        "text": "ID : 1",
                        "facts": [{"name": "Region", "value": "us-east-1"}],
                    }
                ],
            }
        )
        card = message["attachments"][0]["content"]
        assert message["type"] == "message"
        assert message["attachments"][0]["contentType"] == "application/vnd.microsoft.card.adaptive"
        assert card["type"] == "AdaptiveCard"
        assert card["version"] == "1.2"
        texts = [block["text"] for block in card["body"] if block["type"] == "TextBlock"]
        assert "Approval" in texts
        assert "Please review\n**now**" in texts
        assert any(block["type"] == "FactSet" for block in card["body"])
        assert card["actions"][0]["url"] == "https://example.com/approve"


class TestMsTeamsService:
    def test_workflow_url_is_accepted_without_posting_on_background_check(self):
        with patch(
            "autobotAI_integrations.integrations.ms_teams.post_workflow_message"
        ) as post:
            result = _svc(WORKFLOW_URL).is_active()
        assert result["success"] is True
        post.assert_not_called()

    def test_user_test_posts_adaptive_card(self):
        ctx = SimpleNamespace(meta={"user_initiated_request": True})
        with patch(
            "autobotAI_integrations.integrations.ms_teams.post_workflow_message"
        ) as post:
            result = _svc(WORKFLOW_URL, ctx).is_active()
        assert result["success"] is True
        post.assert_called_once()
        assert post.call_args.args[0] == WORKFLOW_URL

    def test_user_test_reports_webhook_error(self):
        ctx = SimpleNamespace(meta={"user_initiated_request": True})
        with patch(
            "autobotAI_integrations.integrations.ms_teams.post_workflow_message",
            side_effect=Exception("Teams workflow webhook returned 401"),
        ):
            result = _svc(WORKFLOW_URL, ctx).is_active()
        assert result["success"] is False
        assert "401" in result["error"]

    def test_invalid_url_still_fails(self):
        result = _svc("https://example.com/not-teams").is_active()
        assert result["success"] is False

    def test_action_client_uses_workflow_card(self):
        service = _svc(WORKFLOW_URL)
        combinations = service.build_python_exec_combinations_hook(
            MagicMock(params=[], context={}),
            [MagicMock(import_library_names=["pymsteams"])],
        )
        assert isinstance(combinations[0]["clients"]["pymsteams"], WorkflowConnectorCard)


class TestWorkflowConnectorCard:
    def test_send_posts_adaptive_card_not_message_card(self):
        card = WorkflowConnectorCard(WORKFLOW_URL)
        card.title("Hello")
        card.text("From autobotAI")
        card.addLinkButton("Open", "https://example.com")

        response = MagicMock(status_code=202, text="")
        with patch(
            "autobotAI_integrations.integrations.ms_teams.webhook.requests.post",
            return_value=response,
        ) as post:
            assert card.send() is True

        sent = post.call_args.kwargs["json"]
        assert sent["type"] == "message"
        assert "@type" not in sent
        assert sent["attachments"][0]["content"]["type"] == "AdaptiveCard"
        assert post.call_args.args[0] == WORKFLOW_URL
