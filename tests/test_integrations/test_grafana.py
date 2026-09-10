import pytest

from autobotAI_integrations.handlers.task_handler import handle_task
from autobotAI_integrations.integrations import integration_service_factory


class TestClassGrafana:
    def test_grafana_steampipe_task(
        self,
        get_keys,
        sample_integration_dict,
        sample_steampipe_task,
        test_result_format,
    ):
        tokens = {
            "host_url": get_keys["GRAFANA_URL"],
            "auth_key": get_keys["GRAFANA_AUTH"],
        }
        integration = sample_integration_dict("grafana", tokens)
        grafana_query = "select * from grafana_org"
        task = sample_steampipe_task(integration, query=grafana_query)
        result = handle_task(task)
        test_result_format(result)
        print(result.model_dump_json(indent=2))

    def test_integration_active(self, get_keys, sample_integration_dict):
        tokens = {
            "host_url": get_keys["GRAFANA_URL"],
            "auth_key": get_keys["GRAFANA_AUTH"],
        }
        integration = sample_integration_dict("grafana", tokens)
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert res["success"]
        tokens = {
            "host_url": get_keys["GRAFANA_URL"],
            "auth_key": get_keys["GRAFANA_AUTH"][:-3],
        }
        integration = sample_integration_dict("grafana", tokens)
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert not res["success"]

    def test_grafana_rest_api_actions(self):
        from autobotAI_integrations.integrations.grafana import GrafanaService
        actions = GrafanaService.get_all_rest_api_actions()
        assert len(actions) == 250, f"Expected 250 actions, got {len(actions)}"
        for action in actions:
            assert action.name, "Action name should not be empty"
            assert action.code.startswith("{base_url}/api/"), f"Unexpected code: {action.code}"
            assert action.integration_type == "grafana"
            # Verify parameters contain method
            methods = [p.values for p in action.parameters_definition if p.in_ == "method"]
            assert len(methods) == 1
            assert methods[0].upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]

    def test_grafana_mcp_server_actions(self):
        from autobotAI_integrations.integrations.grafana import GrafanaService
        mcp_actions = GrafanaService.get_all_mcp_server_actions()
        assert len(mcp_actions) == 2, f"Expected 2 MCP actions, got {len(mcp_actions)}"
        names = [a.name for a in mcp_actions]
        assert "Grafana Observability MCP Server" in names
        assert "Grafana Local MCP Server" in names
        for action in mcp_actions:
            assert action.integration_type == "grafana"
            assert action.transport == "streamable_http"

    def test_grafana_credentials_generation(self, sample_integration_dict):
        # Bearer token test
        integration = sample_integration_dict("grafana", {
            "host_url": "https://mygrafana.company.com:3000",
            "auth_key": "glsa_my_service_account_token",
        })
        service = integration_service_factory.get_service(None, integration)
        rest_creds = service.generate_rest_api_creds()
        assert rest_creds.base_url == "https://mygrafana.company.com:3000"
        assert rest_creds.headers.get("Authorization") == "Bearer glsa_my_service_account_token"

        mcp_creds = service.generate_mcp_creds()
        assert mcp_creds.headers.get("Authorization") == "Bearer glsa_my_service_account_token"

        # Basic auth test
        integration_basic = sample_integration_dict("grafana", {
            "host_url": "http://localhost:3000/",
            "auth_key": "admin:secret123",
        })
        service_basic = integration_service_factory.get_service(None, integration_basic)
        rest_creds_basic = service_basic.generate_rest_api_creds()
        assert rest_creds_basic.base_url == "http://localhost:3000"
        assert rest_creds_basic.headers.get("Authorization").startswith("Basic ")
        mcp_creds_basic = service_basic.generate_mcp_creds()
        assert mcp_creds_basic.headers.get("Authorization").startswith("Basic ")

        # Test stripping /api from host_url
        integration_api_suffix = sample_integration_dict("grafana", {
            "host_url": "http://localhost:3000/api",
            "auth_key": "admin:secret123",
        })
        service_api_suffix = integration_service_factory.get_service(None, integration_api_suffix)
        rest_creds_api_suffix = service_api_suffix.generate_rest_api_creds()
        assert rest_creds_api_suffix.base_url == "http://localhost:3000"

