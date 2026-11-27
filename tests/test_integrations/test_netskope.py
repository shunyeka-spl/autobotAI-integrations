import pytest
from pydantic import ValidationError

from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.integrations.netskope import NetskopeIntegration
from autobotAI_integrations.models import ConnectionInterfaces


def _integration(sample_integration_dict, **extra):
    payload = {
        "tenant": "mycompany.goskope.com",
        "api_token": "test-token",
    }
    payload.update(extra)
    return sample_integration_dict("netskope", payload)


class TestClassNetskope:
    def test_actions_generation(self):
        service = integration_service_factory.get_service_cls("netskope")
        actions = service.get_all_rest_api_actions()
        assert len(actions) > 200
        codes = []
        for action in actions:
            assert action.name
            assert action.name.strip()
            assert action.code.startswith("{base_url}/api/v2/")
            assert "/:" not in action.code
            codes.append(action.code)

        publisher = next(
            action
            for action in actions
            if action.code == "{base_url}/api/v2/infrastructure/publishers/{publisher_id}"
        )
        path_names = {
            param.name for param in publisher.parameters_definition if param.in_ == "path"
        }
        assert path_names == {"publisher_id"}

        userlist = next(
            action for action in actions if action.code == "{base_url}/api/v2/adem/userlist"
        )
        starttime = next(
            param
            for param in userlist.parameters_definition
            if param.name == "starttime" and param.in_ == "query"
        )
        assert starttime.required is True
        assert starttime.params_type == "integer"

    def test_mcp_server(self):
        service_cls = integration_service_factory.get_service_cls("netskope")
        assert ConnectionInterfaces.MCP_SERVER in service_cls.supported_connection_interfaces()
        assert ConnectionInterfaces.REST_API in service_cls.supported_connection_interfaces()
        assert ConnectionInterfaces.PYTHON_SDK in service_cls.supported_connection_interfaces()
        actions = service_cls.get_all_mcp_server_actions()
        assert {action.name for action in actions} == {
            "Netskope All",
            "Netskope Events",
            "Netskope Incidents",
            "Netskope Policy",
            "Netskope Users",
            "Netskope DEM",
        }
        for action in actions:
            assert action.code == "{base_url}"
            assert action.executable_type == "mcp_server"

    def test_rest_api_creds(self, sample_integration_dict):
        service = integration_service_factory.get_service(
            None,
            _integration(
                sample_integration_dict,
                tenant="https://eurocorp.eu.goskope.com/",
            ),
        )
        creds = service.generate_rest_api_creds()
        assert creds.base_url == "https://eurocorp.eu.goskope.com"
        assert creds.headers["Netskope-Api-Token"] == "test-token"
        assert creds.headers["Accept"] == "application/json"
        assert "Authorization" not in creds.headers
        assert creds.verify_ssl is True

    def test_python_sdk_creds(self, sample_integration_dict):
        service = integration_service_factory.get_service(
            None, _integration(sample_integration_dict)
        )
        creds = service.generate_python_sdk_creds()
        assert creds.envs["NETSKOPE_TENANT"] == "mycompany.goskope.com"
        assert creds.envs["NETSKOPE_API_TOKEN"] == "test-token"
        clients = service.get_all_python_sdk_clients()
        assert clients[0]["name"] == "netskope"
        assert "netskope-py-sdk" in clients[0]["pip_package_names"]

    def test_mcp_creds(self, sample_integration_dict):
        service = integration_service_factory.get_service(
            None,
            _integration(
                sample_integration_dict,
                tenant="plm-sspm.de.goskope.com",
                mcp_access_code="ab12CD",
            ),
        )
        creds = service.generate_mcp_creds()
        assert creds.url == "https://mcp-preview.goskope.com/plm-sspm_de/ab12CD/mcp"
        assert creds.headers["Authorization"] == "Bearer test-token"
        assert "Netskope-Api-Token" not in creds.headers

        rest_only = integration_service_factory.get_service(
            None, _integration(sample_integration_dict)
        )
        empty = rest_only.generate_mcp_creds()
        assert empty.url is None
        assert empty.headers == {}

    def test_tenant_and_secret_validation(self, sample_integration_dict):
        with pytest.raises(ValidationError):
            NetskopeIntegration(**_integration(sample_integration_dict, tenant="https://evil.example"))
        with pytest.raises(ValidationError):
            NetskopeIntegration(
                **_integration(sample_integration_dict, tenant="http://169.254.169.254")
            )
        with pytest.raises(ValidationError):
            NetskopeIntegration(
                **_integration(sample_integration_dict, api_token="tok\nen")
            )
        with pytest.raises(ValidationError):
            NetskopeIntegration(
                **_integration(sample_integration_dict, mcp_access_code="abc/12")
            )

    def test_integration_active_skips_without_token(self, get_keys, sample_integration_dict):
        token = get_keys.get("NETSKOPE_API_TOKEN")
        tenant = get_keys.get("NETSKOPE_TENANT")
        if not token or not tenant:
            pytest.skip("NETSKOPE_API_TOKEN or NETSKOPE_TENANT is not set in .env")
        service = integration_service_factory.get_service(
            None,
            sample_integration_dict(
                "netskope", {"tenant": tenant, "api_token": token}
            ),
        )
        assert service.is_active()["success"]
