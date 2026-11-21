import pytest
from unittest.mock import patch, MagicMock

from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.models import ConnectionInterfaces


class TestClassPrismaCloud:

    def test_prisma_cloud_interfaces(self):
        service_cls = integration_service_factory.get_service_cls("prisma_cloud")
        interfaces = service_cls.supported_connection_interfaces()
        assert ConnectionInterfaces.REST_API in interfaces
        assert ConnectionInterfaces.CLI in interfaces

    def test_prisma_cloud_rest_api_actions(self):
        service_cls = integration_service_factory.get_service_cls("prisma_cloud")
        actions = service_cls.get_all_rest_api_actions()
        assert len(actions) == 316, f"Expected 316 actions, got {len(actions)}"
        for action in actions:
            assert action.name, "Action name should not be empty"
            assert action.code.startswith("{base_url}/"), f"Unexpected code format: {action.code}"
            assert action.integration_type == "prisma_cloud"
            methods = [p.values for p in action.parameters_definition if p.in_ == "method"]
            assert len(methods) == 1
            assert methods[0].upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]

    def test_prisma_cloud_credentials_generation_default_url(self, sample_integration_dict):
        integration = sample_integration_dict("prisma_cloud", {
            "access_key_id": "test-access-key-id",
            "secret_key": "test-secret-key",
        })
        service = integration_service_factory.get_service(None, integration)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"token": "jwt-mock-token-xyz"}

        with patch("requests.post", return_value=mock_resp) as mock_post:
            creds = service.generate_rest_api_creds()
            mock_post.assert_called_once_with(
                "https://api.prismacloud.io/login",
                json={"username": "test-access-key-id", "password": "test-secret-key"},
                timeout=10,
            )
            assert creds.base_url == "https://api.prismacloud.io"
            assert creds.headers.get("x-redlock-auth") == "jwt-mock-token-xyz"

    def test_prisma_cloud_credentials_generation_custom_url(self, sample_integration_dict):
        integration = sample_integration_dict("prisma_cloud", {
            "url": "https://api2.prismacloud.io/",
            "access_key_id": "test-key",
            "secret_key": "test-secret",
        })
        service = integration_service_factory.get_service(None, integration)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"token": "jwt-token-eu"}

        with patch("requests.post", return_value=mock_resp) as mock_post:
            creds = service.generate_rest_api_creds()
            mock_post.assert_called_once_with(
                "https://api2.prismacloud.io/login",
                json={"username": "test-key", "password": "test-secret"},
                timeout=10,
            )
            assert creds.base_url == "https://api2.prismacloud.io"
            assert creds.headers.get("x-redlock-auth") == "jwt-token-eu"

    def test_prisma_cloud_test_integration(self, sample_integration_dict):
        integration = sample_integration_dict("prisma_cloud", {
            "url": "https://api.prismacloud.io",
            "access_key_id": "test-key",
            "secret_key": "test-secret",
        })
        service = integration_service_factory.get_service(None, integration)

        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200

        with patch("requests.post", return_value=mock_resp_ok):
            res = service._test_integration()
            assert res["success"] is True

        mock_resp_fail = MagicMock()
        mock_resp_fail.status_code = 401

        with patch("requests.post", return_value=mock_resp_fail):
            res = service._test_integration()
            assert res["success"] is False
            assert "401" in res["error"]
