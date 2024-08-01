from typing import List, Type, Union, Optional

from autobotAI_integrations.models import *
from autobotAI_integrations import (
    BaseSchema,
    BaseService,
    ConnectionInterfaces,
)
import requests


class IPinfoIntegrations(BaseSchema):
    category: Optional[str] = IntegrationCategory.SECURITY_TOOLS.value
    description: Optional[str] = (
        "ipinfo.io is an API for IP address information (e.g. location)."
    )


class IPinfoService(BaseService):

    def __init__(self, ctx: dict, integration: Union[IPinfoIntegrations, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, IPinfoIntegrations):
            integration = IPinfoIntegrations(**integration)
        super().__init__(ctx, integration)

    def _test_integration(self) -> dict:
        try:
            response = requests.get("https://ipinfo.io/ip")
            return {"success": response.status_code == 200}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_forms():
        return {
            "label": "IPinfo",
            "type": "form",
            "children": [
                {
                    "label": "API Key",
                    "type": "text",
                    "name": "api_key",
                    "required": True,
                }
            ],
        }

    @staticmethod
    def get_schema() -> Type[BaseSchema]:
        return IPinfoIntegrations

    @classmethod
    def get_details(cls):
        return {
            "clients": ["requests"],
            "supported_executor": "http",
            "compliance_supported": False,
            "supported_interfaces": cls.supported_connection_interfaces(),
        }

    @staticmethod
    def supported_connection_interfaces():
        return [
            ConnectionInterfaces.REST_API,
            ConnectionInterfaces.CLI,
        ]

    def generate_steampipe_creds(self) -> SteampipeCreds:
        conf_path = "~/.steampipe/config/ipinfo.spc"
        config = """connection "ipinfo" {
  plugin = "ipinfo"
}
"""
        return SteampipeCreds(
            envs={},
            plugin_name="ipinfo",
            connection_name="ipinfo",
            conf_path=conf_path,
            config=config,
        )
