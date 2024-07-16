from typing import List, Type, Union

from autobotAI_integrations.models import *
from autobotAI_integrations import (
    BaseSchema,
    BaseService,
    ConnectionInterfaces,
)
import requests


class NewrelicIntegrations(BaseSchema):
    api_key: Optional[str] = Field(default=None, exclude=True)
    region: Optional[str] = Field(default="us", exclude=False)

    category: Optional[str] = IntegrationCategory.MONITORING_TOOLS.value
    description: Optional[str] = (
        "New Relic is a SaaS providing Monitoring, Alerting, Dashboards for applications, infrastructure, etc."
    )


class NewrelicService(BaseService):

    def __init__(self, ctx: dict, integration: Union[NewrelicIntegrations, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, NewrelicIntegrations):
            integration = NewrelicIntegrations(**integration)
        super().__init__(ctx, integration)


    def _test_integration(self) -> dict:
     try:
        api_key = self.integration.api_key
        headers = {"X-Api-Key": api_key}
        url = "https://api.newrelic.com/v2/applications.json"
        response = requests.get(url, headers=headers)

        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.content}")

        if response.status_code == 200:
            try:
                response_data = response.json()
                if "applications" in response_data:
                    return {"success": True}
                else:
                    return {"success": False, "error": "Unexpected response format"}
            except ValueError:
                return {"success": False, "error": "Invalid JSON response"}
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
            "label": "Newrelic",
            "type": "form",
            "children": [
                {
                    "name": "api_key",
                    "type": "text/password",
                    "label": "API Key",
                    "placeholder": "Enter the Newrelic API Key",
                    "required": True,
                },
                {
                    "name": "region",
                    "type": "text",
                    "label": "Region",
                    "placeholder": "'us' or 'eu',default:'us'",
                    "required": True,
                },
            ],
        }

    @staticmethod
    def get_schema() -> Type[BaseSchema]:
        return NewrelicIntegrations

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
            "NEW_RELIC_API_KEY": self.integration.api_key,
            "NEW_RELIC_REGION": self.integration.region,
        }
        conf_path = "~/.steampipe/config/newrelic.spc"
        config = """connection "newrelic" {
  plugin = "newrelic"
}
"""
        return SteampipeCreds(
            envs=creds,
            plugin_name="newrelic",
            connection_name="newrelic",
            conf_path=conf_path,
            config=config,
        )
