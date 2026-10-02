import pytest

from autobotAI_integrations.handlers.task_handler import handle_task
from autobotAI_integrations.integrations import integration_service_factory


class TestClassNewrelic:
    def test_newrelic_steampipe_task(
        self,
        get_keys,
        sample_integration_dict,
        sample_steampipe_task,
        test_result_format,
    ):
        tokens = {
            "api_key": get_keys["NEWRELIC_API_KEY"],
            "region": get_keys["NEWRELIC_REGION"]
        }
        integration = sample_integration_dict("newrelic", tokens)
        newrelic_query = "select * from newrelic_account"
        task = sample_steampipe_task(integration, query=newrelic_query)
        result = handle_task(task)
        test_result_format(result)

    def test_integration_active(self, get_keys, sample_integration_dict):
        tokens = {
            "api_key": get_keys["NEWRELIC_API_KEY"],
            "region": get_keys["NEWRELIC_REGION"],
        }
        integration = sample_integration_dict("newrelic", tokens)
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert res["success"]
        tokens = {
            "api_key": get_keys["NEWRELIC_API_KEY"][0:-3],
            "region": get_keys["NEWRELIC_REGION"],
        }
        integration = sample_integration_dict("newrelic", tokens)
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert not res["success"]

    def test_newrelic_mcp_server_actions(self):
        from autobotAI_integrations.integrations.newrelic import NewrelicService
        mcp_actions = NewrelicService.get_all_mcp_server_actions()
        assert len(mcp_actions) == 2, f"Expected 2 MCP actions, got {len(mcp_actions)}"
        names = [a.name for a in mcp_actions]
        assert "New Relic US MCP Server" in names
        assert "New Relic EU MCP Server" in names
        for action in mcp_actions:
            assert action.integration_type == "newrelic"
            assert action.transport == "streamable_http"
            assert action.code in ["https://mcp.newrelic.com/mcp/", "https://mcp.eu.newrelic.com/mcp/"]
            # Check Api-Key parameter definition
            param_names = [p.name for p in action.parameters_definition]
            assert "Api-Key" in param_names

    def test_newrelic_credentials_generation(self, sample_integration_dict):
        integration = sample_integration_dict("newrelic", {
            "api_key": "NRAK-MYNEWRELICUSERKEY123",
            "region": "us",
        })
        service = integration_service_factory.get_service(None, integration)
        mcp_creds = service.generate_mcp_creds()
        assert mcp_creds.headers.get("Api-Key") == "NRAK-MYNEWRELICUSERKEY123"

        # EU region test
        integration_eu = sample_integration_dict("newrelic", {
            "api_key": "NRAK-MYNEWRELICUSERKEYEU",
            "region": "eu",
        })
        service_eu = integration_service_factory.get_service(None, integration_eu)
        mcp_creds_eu = service_eu.generate_mcp_creds()
        assert mcp_creds_eu.headers.get("Api-Key") == "NRAK-MYNEWRELICUSERKEYEU"

