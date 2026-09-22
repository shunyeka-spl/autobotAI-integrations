import pytest

from autobotAI_integrations.handlers.task_handler import handle_task
from autobotAI_integrations.integrations import integration_service_factory

class TestClassIPinfo:
    def test_integration_interfaces(self):
        service_cls = integration_service_factory.get_service_cls("ipinfo")
        interfaces = service_cls.supported_connection_interfaces()
        from autobotAI_integrations.models import ConnectionInterfaces
        assert ConnectionInterfaces.REST_API in interfaces
        assert ConnectionInterfaces.STEAMPIPE in interfaces
        assert ConnectionInterfaces.MCP_SERVER in interfaces

    def test_actions_generation(self):
        service_cls = integration_service_factory.get_service_cls("ipinfo")
        actions = service_cls.get_all_rest_api_actions()
        assert len(actions) == 48
        for action in actions:
            assert action.name is not None
            assert action.name.strip() != ""
            assert action.code is not None
            assert action.code.startswith("https://ipinfo.io")
            assert action.integration_type == "ipinfo"
            assert len(action.parameters_definition) > 0

    def test_mcp_server(self, sample_integration_dict):
        service_cls = integration_service_factory.get_service_cls("ipinfo")
        actions = service_cls.get_all_mcp_server_actions()
        assert len(actions) == 7
        expected_names = {
            "IPinfo All Tools",
            "IPinfo Lookup",
            "IPinfo Geolocate",
            "IPinfo ASN",
            "IPinfo Privacy Check",
            "IPinfo Residential Proxy Check",
            "IPinfo Quota Check",
        }
        assert {action.name for action in actions} == expected_names
        for action in actions:
            assert action.code == "https://mcp.ipinfo.io/"
            assert action.executable_type == "mcp_server"
            assert action.transport == "streamable_http"

        integration = sample_integration_dict("ipinfo", {"token": "dummy_test_token"})
        service = integration_service_factory.get_service(None, integration)
        mcp_creds = service.generate_mcp_creds()
        assert mcp_creds.headers.get("Authorization") == "Bearer dummy_test_token"

    def test_rest_api_creds(self, sample_integration_dict):
        integration = sample_integration_dict("ipinfo", {"token": "dummy_test_token"})
        service = integration_service_factory.get_service(None, integration)
        rest_creds = service.generate_rest_api_creds()
        assert rest_creds.base_url == "https://ipinfo.io"
        assert rest_creds.headers.get("Authorization") == "Bearer dummy_test_token"

    def test_rest_api_run(self, sample_integration_dict, sample_restapi_task, test_result_format):
        # ipinfo answers an unauthenticated lookup, so this needs no token.
        integration = sample_integration_dict("ipinfo", {})
        service = integration_service_factory.get_service(None, integration)
        actions = service.get_all_rest_api_actions()
        lookup_action = next(a for a in actions if a.code == "https://ipinfo.io/{ip}")

        from autobotAI_integrations.payload_schema import OpenAPIPathParams
        params = [
            OpenAPIPathParams(name="method", in_="method", values="GET", type="str", version=2),
            OpenAPIPathParams(name="ip", in_="path", values="8.8.8.8", type="string", version=2),
        ]
        task = sample_restapi_task(integration, lookup_action.code, params)
        result = handle_task(task)
        test_result_format(result)
        assert len(result.errors) == 0
        assert len(result.resources) > 0
        assert result.resources[0].get("ip") == "8.8.8.8"
        assert result.resources[0].get("country") == "US"

