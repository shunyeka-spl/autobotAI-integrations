from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.models import ConnectionInterfaces


GATED_INTERFACE_CHECKS = {
    ConnectionInterfaces.REST_API: "_rest_api_supported",
    ConnectionInterfaces.MCP_SERVER: "_mcp_server_supported",
    ConnectionInterfaces.PYTHON_SDK: "_python_sdk_supported",
}


class TestSupportedConnectionInterfaces:
    def test_hardcoded_lists_only_declare_available_gated_interfaces(self):
        mismatches = []
        for name in integration_service_factory.list_integration_module_names():
            service_cls = integration_service_factory.get_service_cls(name)
            declared = service_cls.supported_connection_interfaces()
            for interface, check_name in GATED_INTERFACE_CHECKS.items():
                if interface in declared and not getattr(service_cls, check_name)():
                    mismatches.append(
                        f"{name} declares {interface.value} but {check_name} is false"
                    )
        assert mismatches == [], (
            "Hardcoded supported_connection_interfaces() listed an interface "
            "the integration cannot run. REST_API needs open_api.json and "
            "generate_rest_api_creds; MCP_SERVER needs mcp_servers.json and "
            "generate_mcp_creds (autobotAI is exempt from mcp_servers.json because "
            "its MCP details come from the internal backend); PYTHON_SDK needs the "
            "and python_sdk_clients.yml. Failures:\n" + "\n".join(mismatches)
        )

    def test_capability_helpers_match_integration_artifacts(self):
        gitlab = integration_service_factory.get_service_cls("gitlab")
        assert gitlab._rest_api_supported()
        assert gitlab._mcp_server_supported()
        assert gitlab._python_sdk_supported()

        openai = integration_service_factory.get_service_cls("openai")
        assert not openai._rest_api_supported()
        assert openai._python_sdk_supported()

        autobotai = integration_service_factory.get_service_cls("autobotai")
        assert autobotai._rest_api_supported()
        assert autobotai._mcp_server_supported()

        python_svc = integration_service_factory.get_service_cls("python")
        assert python_svc._python_sdk_supported()
        assert not python_svc._rest_api_supported()
