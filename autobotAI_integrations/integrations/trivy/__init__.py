from typing import List, Type, Union

from autobotAI_integrations.models import *
from autobotAI_integrations import (
    BaseSchema,
    BaseService,
    ConnectionInterfaces,
)
import requests


class TrivyIntegrations(BaseSchema):
    category: Optional[str] = IntegrationCategory.SECURITY_TOOLS.value
    description: Optional[str] = (
        "Trivy is a comprehensive open-source vulnerability scanner for container images, file systems, and Git repositories, designed to identify and mitigate security risks."
    )


class TrivyService(BaseService):

    def __init__(self, ctx: dict, integration: Union[TrivyIntegrations, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, TrivyIntegrations):
            integration = TrivyIntegrations(**integration)
        super().__init__(ctx, integration)

    def _test_integration(self) -> dict:
        try:
            # TODO: replace with actual API
            response = requests.get("https://api.example.com")
            if response.status_code == 200:
                return {"success": True}
            else:
                return {
                "success": False,
                "error": f"API request failed. Status code: {response.status_code}",
            }
        except requests.exceptions.ConnectionError as e:
            return {"success": False, "error": "Connection is unreachable"}

    @staticmethod
    def get_forms():
        return {
            "label": "Trivy",
            "type": "form",
            "children": [],
        }

    @staticmethod
    def get_schema() -> Type[BaseSchema]:
        return TrivyIntegrations

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
        conf_path = "~/.steampipe/config/trivy.spc"
        config = """connection "trivy" {
  plugin = "trivy"
}
"""
        return SteampipeCreds(
            envs={},
            plugin_name="trivy",
            connection_name="trivy",
            conf_path=conf_path,
            config=config,
        )
