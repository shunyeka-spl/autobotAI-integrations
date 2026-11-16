import pytest

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
