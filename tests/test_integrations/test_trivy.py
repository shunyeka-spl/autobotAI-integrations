import pytest

from autobotAI_integrations.handlers.task_handler import handle_task
from autobotAI_integrations.integrations import integration_service_factory


class TestClassTrivy:
    def test_trivy_steampipe_task(
        self,
        get_keys,
        sample_integration_dict,
        sample_steampipe_task,
        test_result_format,
    ):
        tokens = {}
        integration = sample_integration_dict("trivy", tokens)
        trivy_query = "select * from trivy_scan_vulnerability where artifact_type = 'container_image' and artifact_name = 'turbot/steampipe'"
        task = sample_steampipe_task(integration, query=trivy_query)
        result = handle_task(task)
        test_result_format(result)

    def test_integration_active(self, get_keys, sample_integration_dict):
        tokens = {}
        integration = sample_integration_dict("trivy", tokens)
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert res["success"]

    def test_trivy_interfaces(self):
        service_cls = integration_service_factory.get_service_cls("trivy")
        interfaces = service_cls.supported_connection_interfaces()
        from autobotAI_integrations.models import ConnectionInterfaces
        assert ConnectionInterfaces.MCP_SERVER in interfaces
        assert ConnectionInterfaces.STEAMPIPE in interfaces

    def test_trivy_mcp_server_actions(self):
        from autobotAI_integrations.integrations.trivy import TrivyService
        mcp_actions = TrivyService.get_all_mcp_server_actions()
        assert len(mcp_actions) == 1, f"Expected 1 MCP action, got {len(mcp_actions)}"
        action = mcp_actions[0]
        assert action.name == "Trivy Security Scanner MCP Server"
        assert action.integration_type == "trivy"
        assert action.transport == "streamable_http"
        assert action.code == "http://localhost:8080"

    def test_trivy_credentials_generation(self, sample_integration_dict):
        integration = sample_integration_dict("trivy", {})
        service = integration_service_factory.get_service(None, integration)
        mcp_creds = service.generate_mcp_creds()
        assert mcp_creds is not None
        assert isinstance(mcp_creds.headers, dict)

