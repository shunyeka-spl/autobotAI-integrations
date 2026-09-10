from typing import List, Optional, Type, Union

from pydantic import Field
from autobotAI_integrations import (
    BaseSchema,
    BaseService,
    ConnectionInterfaces,
)
import requests

from autobotAI_integrations.models import (
    IntegrationCategory,
    SteampipeCreds,
    RestAPICreds,
    MCPCreds,
)


class GrafanaIntegrations(BaseSchema):
    host_url: Optional[str] = None
    auth_key: Optional[str] = Field(default=None, exclude=True)

    category: Optional[str] = IntegrationCategory.MONITORING_TOOLS.value
    description: Optional[str] = (
        "Grafana is an open-source observability platform for querying, visualizing, and alerting on metrics, logs, and traces."
    )


    @property
    def base_url(self) -> str:
        return self.host_url


class GrafanaService(BaseService):

    def __init__(self, ctx: dict, integration: Union[GrafanaIntegrations, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, GrafanaIntegrations):
            integration = GrafanaIntegrations(**integration)
        super().__init__(ctx, integration)

    def _test_integration(self) -> dict:
        try:
            url = (self.integration.host_url or "").rstrip("/")
            if url.endswith("/api"):
                url = url[:-4].rstrip("/")
            test_url = f"{url}/api/user"

            headers = {}
            auth = None
            if self.integration.auth_key:
                if ":" in self.integration.auth_key:
                    parts = self.integration.auth_key.split(":", 1)
                    auth = (parts[0], parts[1])
                else:
                    headers["Authorization"] = f"Bearer {self.integration.auth_key}"

            response = requests.get(test_url, headers=headers, auth=auth, timeout=15)
            if response.status_code == 200:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": f"Request failed with status code: {response.status_code}",
                }
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Connection is unreachable"}
        except Exception as e:
            return {"success": False, "error": f"Request failed with error: {str(e)}"}

    @staticmethod
    def get_forms():
        return {
            "label": "Grafana",
            "type": "form",
            "children": [
                {
                    "name": "host_url",
                    "label": "Host URL",
                    "type": "text",
                    "placeholder": "grafana host url",
                    "required": True,
                },
                {
                    "name": "auth_key",
                    "label": "Auth Key",
                    "type": "text/password",
                    "placeholder": "Service account token or username:password",
                    "required": True,
                    "help_url": "https://grafana.com/docs/grafana/latest/administration/service-accounts/",
                    "help_url_text": "Create Service Account ↗",
                },
            ],
        }

    @staticmethod
    def get_schema(ctx=None) -> Type[BaseSchema]:
        return GrafanaIntegrations

    @classmethod
    def get_details(cls):
        return {
            "clients": [],
            "supported_executor": "ecs",
            "compliance_supported": False,
            "supported_interfaces": cls.supported_connection_interfaces(),
        }

    @staticmethod
    def supported_connection_interfaces():
        return [
            ConnectionInterfaces.STEAMPIPE,
            ConnectionInterfaces.REST_API,
            ConnectionInterfaces.CLI,
            ConnectionInterfaces.MCP_SERVER,
        ]

    def generate_steampipe_creds(self) -> SteampipeCreds:
        creds = {
            "GRAFANA_URL": self.integration.host_url,
            "GRAFANA_AUTH": self.integration.auth_key,
        }
        conf_path = "~/.steampipe/config/grafana.spc"
        config = """connection "grafana" {
  plugin = "grafana"
}
"""
        return SteampipeCreds(
            envs=creds,
            plugin_name="grafana",
            connection_name="grafana",
            conf_path=conf_path,
            config=config,
        )

    def generate_rest_api_creds(self) -> RestAPICreds:
        headers = {}
        if self.integration.auth_key:
            if ":" in self.integration.auth_key:
                import base64
                token = base64.b64encode(self.integration.auth_key.encode()).decode()
                headers["Authorization"] = f"Basic {token}"
            else:
                headers["Authorization"] = f"Bearer {self.integration.auth_key}"
        base_url = (self.integration.host_url or "").rstrip("/")
        if base_url.endswith("/api"):
            base_url = base_url[:-4].rstrip("/")
        return RestAPICreds(
            base_url=base_url,
            headers=headers,
        )

    def generate_mcp_creds(self) -> MCPCreds:
        headers = {}
        if self.integration.auth_key:
            if ":" in self.integration.auth_key:
                import base64
                token = base64.b64encode(self.integration.auth_key.encode()).decode()
                headers["Authorization"] = f"Basic {token}"
            else:
                headers["Authorization"] = f"Bearer {self.integration.auth_key}"
        return MCPCreds(
            headers=headers,
        )
