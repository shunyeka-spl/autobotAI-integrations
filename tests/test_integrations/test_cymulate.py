import traceback
import pytest

from autobotAI_integrations.handlers.task_handler import handle_task
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.models import ConnectionInterfaces

US_API = "https://api.us-app.cymulate.com"


def _tokens(get_keys, *, valid=True):
    token = get_keys.get("CYMULATE_API_TOKEN") or get_keys.get("api_token")
    if not token:
        pytest.skip("CYMULATE_API_TOKEN or api_token is not set in .env")
    if not valid:
        token = token[:-2]
    return {
        "auth_type": "api_token",
        "api_token": token,
        "api_url": get_keys.get("CYMULATE_API_URL") or US_API,
    }


class TestClassCymulate:
    def test_integration_active(self, get_keys, sample_integration_dict):
        integration = sample_integration_dict("cymulate", _tokens(get_keys))
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert res["success"]

        integration = sample_integration_dict("cymulate", _tokens(get_keys, valid=False))
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert not res["success"]

    def test_actions_generation(self):
        service = integration_service_factory.get_service_cls("cymulate")
        actions = service.get_all_rest_api_actions()
        for action in actions:
            assert action.name is not None
            assert action.name.strip() != ""
        assert len(actions) > 0

    def test_mcp_server(self):
        service_cls = integration_service_factory.get_service_cls("cymulate")
        assert ConnectionInterfaces.MCP_SERVER in service_cls.supported_connection_interfaces()
        actions = service_cls.get_all_mcp_server_actions()
        assert {action.name for action in actions} == {
            "Cymulate All",
            "Cymulate Findings",
            "Cymulate Assessments",
            "Cymulate Agents and Environments",
        }
        for action in actions:
            assert action.code == "{base_url}"
            assert action.executable_type == "mcp_server"

    def test_rest_api_creds_generation(self, get_keys, sample_integration_dict):
        tokens = _tokens(get_keys)
        service = integration_service_factory.get_service(
            None, sample_integration_dict("cymulate", tokens)
        )
        creds = service.generate_rest_api_creds()
        assert creds.base_url == tokens["api_url"].rstrip("/")
        assert creds.headers["x-token"] == tokens["api_token"]
        assert "Authorization" not in creds.headers

    def test_action_run(
        self, get_keys, sample_restapi_task, test_result_format, sample_integration_dict
    ):
        """Execute REST API action: Get Immediate Threats assessment status (GET /v1/immediate-threats/status)."""
        tokens = _tokens(get_keys)
        integration = sample_integration_dict("cymulate", tokens)
        service = integration_service_factory.get_service(None, integration)
        actions = service.get_all_rest_api_actions()

        target_action = None
        for action in actions:
            if action.name == "Get Immediate Threats assessment status":
                target_action = action
                break

        assert target_action is not None, (
            "Action 'Get immediate threats status' not found in Cymulate REST API actions. "
            f"Available: {[a.name for a in actions]}"
        )

        try:
            task = sample_restapi_task(
                integration, target_action.code, target_action.parameters_definition
            )
            result = handle_task(task)
            test_result_format(result)
        except Exception:
            traceback.print_exc()
            raise
