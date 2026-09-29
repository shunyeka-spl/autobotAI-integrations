import pytest
from unittest.mock import MagicMock, patch
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.integrations.zoho_mcp import (
    ZohoMcpIntegration,
    ZohoMcpService,
    ZohoMcpAuthTypes,
)
from autobotAI_integrations.models import ConnectionInterfaces, IntegrationCategory


class TestClassZohoMcp:
    def test_factory_discovery(self):
        service_cls = integration_service_factory.get_service_cls("zoho_mcp")
        assert service_cls is ZohoMcpService

        metadata = integration_service_factory._get_metadata_for_type("zoho_mcp")
        assert metadata["name"] == "zoho_mcp"
        assert metadata["displayName"] == "Zoho MCP"
        assert metadata["category"] == IntegrationCategory.NOTIFICATIONS_AND_COMMUNICATIONS.value
        assert "mcp_server" in metadata["supported_interfaces"]

        service_details = integration_service_factory.get_service_details({"integration_type": "zoho_mcp"})
        assert len(service_details) == 1
        assert service_details[0]["displayName"] == "Zoho MCP"

    def test_schema_and_forms(self):
        forms = ZohoMcpService.get_forms()
        assert forms["label"] == "Zoho MCP"
        assert len(forms["children"]) == 1

        mcp_tab = forms["children"][0]
        assert mcp_tab["formId"] == ZohoMcpAuthTypes.SERVER_URL.value
        assert any(child["name"] == "server_url" for child in mcp_tab["children"])

        # Schema instantiation
        integration = ZohoMcpIntegration(
            userId="test_user",
            cspName="zoho_mcp",
            alias="test_zoho_mcp",
            server_url="https://autobot-zoho-server-60089064949.zohomcp.in/mcp/85a29b59632a2b826eacec06b2b4b44b/message",
            api_key="1001.sample_zapikey_token",
            category=IntegrationCategory.NOTIFICATIONS_AND_COMMUNICATIONS.value,
        )
        assert integration.name == "Zoho MCP"
        assert integration.base_url == "https://autobot-zoho-server-60089064949.zohomcp.in/mcp/85a29b59632a2b826eacec06b2b4b44b/message"
        assert integration.mcp_base_url == "https://autobot-zoho-server-60089064949.zohomcp.in/mcp/85a29b59632a2b826eacec06b2b4b44b/message"

    def test_mcp_credentials_generation(self, sample_integration_dict):
        integration_dict = sample_integration_dict(
            "zoho_mcp",
            {
                "server_url": "https://autobot-zoho-server-60089064949.zohomcp.in/mcp/85a29b59632a2b826eacec06b2b4b44b/message",
                "api_key": "1001.sample_zapikey_token",
            },
        )
        service = integration_service_factory.get_service(None, integration_dict)
        mcp_creds = service.generate_mcp_creds()
        assert mcp_creds.envs.get("ZOHO_MCP_URL") == "https://autobot-zoho-server-60089064949.zohomcp.in/mcp/85a29b59632a2b826eacec06b2b4b44b/message"
        assert mcp_creds.envs.get("ZOHO_MCP_TOKEN") == "1001.sample_zapikey_token"
        assert mcp_creds.headers.get("Authorization") == "Zoho-oauthtoken 1001.sample_zapikey_token"
        assert mcp_creds.headers.get("apikey") == "1001.sample_zapikey_token"
        assert mcp_creds.headers.get("zapikey") == "1001.sample_zapikey_token"

    def test_mcp_server_actions_discovery(self):
        service_cls = integration_service_factory.get_service_cls("zoho_mcp")
        assert ConnectionInterfaces.MCP_SERVER in service_cls.supported_connection_interfaces()

        mcp_actions = service_cls.get_all_mcp_server_actions()
        assert len(mcp_actions) == 3
        mcp_names = [a.name for a in mcp_actions]
        assert "Zoho MCP All Tools" in mcp_names
        assert "Zoho Cliq Messaging Tools" in mcp_names
        assert "Zoho Organization Tools" in mcp_names

    @patch("requests.post")
    def test_connection_test_rpc_success(self, mock_post, sample_integration_dict):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"jsonrpc": "2.0", "result": {"tools": []}}
        mock_post.return_value = mock_resp

        integration = sample_integration_dict(
            "zoho_mcp",
            {
                "server_url": "https://autobot-zoho-server-60089064949.zohomcp.in/mcp/85a29b59632a2b826eacec06b2b4b44b/message",
                "api_key": "1001.sample_zapikey_token",
            },
        )
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert res["success"] is True

    @patch("requests.get")
    @patch("requests.post")
    def test_connection_test_get_fallback_success(self, mock_post, mock_get, sample_integration_dict):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 405
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get.return_value = mock_get_resp

        integration = sample_integration_dict(
            "zoho_mcp",
            {
                "server_url": "https://autobot-zoho-server-60089064949.zohomcp.in/mcp/85a29b59632a2b826eacec06b2b4b44b/message",
            },
        )
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert res["success"] is True
