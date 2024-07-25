from typing import List, Type, Union, Optional
from autobotAI_integrations.models import *
from autobotAI_integrations import (
    BaseSchema,
    BaseService,
    ConnectionInterfaces,
)
import requests

class PaloAltoIntegrations(BaseSchema):
    # TODO: Add API Key Set up and Use Username,Password to generate API key, Optimize for API key
    username: Optional[str] = Field(default=None, exclude=False)
    password: Optional[str] = Field(default=None, exclude=False)
    api_key: Optional[str] = Field(default=None, exclude=False)
    host_url: Optional[str] = Field(default=None, exclude=False)

    category: Optional[str] = IntegrationCategory.SECURITY_TOOLS.value
    description: Optional[str] = (
        "Palo Alto Networks provides advanced firewalls and cloud-based security solutions."
    )

class PaloAltoService(BaseService):

    def __init__(self, ctx: dict, integration: Union[PaloAltoIntegrations, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, PaloAltoIntegrations):
            integration = PaloAltoIntegrations(**integration)
        super().__init__(ctx, integration)

    def _test_integration(self) -> dict:
        try:
            response = requests.get(
                f"{self.integration.host_url}/api/?type=keygen&user={self.integration.username}&password={self.integration.password}",
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": f"API request failed. Status code: {response.status_code}",
                }
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Connection is unreachable"}

    @staticmethod
    def get_forms():
        return {
            "label": "Palo Alto",
            "type": "form",
            "children": [
                {
                    "name": "username",
                    "type": "text",
                    "label": "Username",
                    "placeholder": "Enter the Palo Alto Username",
                    "required": True,
                },
                {
                    "name": "password",
                    "type": "password",
                    "label": "Password",
                    "placeholder": "Enter the Palo Alto Password",
                    "required": True,
                },
                {
                    "name": "host_url",
                    "type": "text",
                    "label": "Host URL",
                    "placeholder": "Enter the Palo Alto API Host URL",
                    "required": True,
                },
            ],
        }

    @staticmethod
    def get_schema() -> Type[BaseSchema]:
        return PaloAltoIntegrations

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
        ]

    def generate_steampipe_creds(self) -> SteampipeCreds:
        creds = {
            "PANOS_USERNAME": self.integration.username,
            "PANOS_PASSWORD": self.integration.password,
            "PANOS_HOSTNAME": self.integration.host_url,
        }
        conf_path = "~/.steampipe/config/panos.spc"
        config = """connection "palo_alto" {
  plugin = "panos"
}
"""
        return SteampipeCreds(
            envs=creds,
            plugin_name="panos",
            connection_name="panos",
            conf_path=conf_path,
            config=config,
        )