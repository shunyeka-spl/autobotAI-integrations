import importlib
import json
from typing import Type, Union
from autobotAI_integrations.models import *
from autobotAI_integrations import (
    BaseSchema,
    BaseService,
    ConnectionInterfaces,
)
import requests

from autobotAI_integrations.payload_schema import PayloadTask
from autobotAI_integrations.utils import list_of_unique_elements


class SplunkIntegration(BaseSchema):
    username: Optional[str] = Field(default=None, exclude=True)
    password: Optional[str] = Field(default=None, exclude=True)

    category: Optional[str] = IntegrationCategory.SECURITY_TOOLS.value
    description: Optional[str] = (
        "Splunk software is used for searching, monitoring and analyzing log data."
    )


class SplunkService(BaseService):

    def __init__(self, ctx: dict, integration: Union[SplunkIntegration, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, SplunkIntegration):
            integration = SplunkIntegration(**integration)
        super().__init__(ctx, integration)

    def _test_integration(self) -> dict:
        try:
        
            response = requests.get("https://api.splunk.com/2.0/rest/login/splunk", auth=(self.integration.username, self.integration.password))
            
            if response.status_code == 200:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": f"Error: API request failed. Status code: {response.status_code}",
                }
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Connection is unreachable"}
        
    @staticmethod
    def get_forms():
        return {
            "label": "Splunk",
            "type": "form",
            "children": [
                {
                    "name": "username",
                    "type": "text",
                    "label": "Username",
                    "placeholder": "Enter your Splunk Username",
                    "required": True,
                },
                {
                    "name": "password",
                    "type": "text/password",
                    "label": "Password",
                    "placeholder": "Enter your Splunk Password",
                    "required": True,
                },
            ],
        }

    @staticmethod
    def get_schema() -> Type[BaseSchema]:
        return SplunkIntegration

    @classmethod
    def get_details(cls):
        return {
            "clients": list_of_unique_elements(cls.get_all_python_sdk_clients()),
            "supported_executor": "ecs",
            "compliance_supported": False,
            "supported_interfaces": cls.supported_connection_interfaces(),
            "python_code_sample": cls.get_code_sample(),
        }

    @staticmethod
    def supported_connection_interfaces():
        return [
            ConnectionInterfaces.STEAMPIPE,
            ConnectionInterfaces.REST_API,
            ConnectionInterfaces.PYTHON_SDK
        ]

    def generate_steampipe_creds(self) -> SteampipeCreds:
        creds = {
            "SPLUNK_USERNAME": str(self.integration.username),
            "SPLUNK_PASSWORD": str(self.integration.password)
        }
        conf_path = "~/.steampipe/config/splunk.spc"
        config = """connection "splunk" {
  plugin = "splunk"
}
"""
        return SteampipeCreds(
            envs=creds,
            plugin_name="splunk",
            connection_name="splunk",
            conf_path=conf_path,
            config=config,
        )

    def build_python_exec_combinations_hook(
        self, payload_task: PayloadTask, client_definitions: List[SDKClient]
    ) -> list:
        Splunk = importlib.import_module(
            client_definitions[0].import_library_names[0], package=None
        )

        return [
            {
                "clients": {
                    "Splunk": Splunk.Splunk(
                        payload_task.creds.envs.get("SPLUNK_USERNAME"),
                        payload_task.creds.envs.get("SPLUNK_PASSWORD")
                    )
                },
                "params": self.prepare_params(payload_task.params),
                "context": payload_task.context,
            }
        ]

    def generate_python_sdk_creds(self, requested_clients=None) -> SDKCreds:
        creds = {
            "SPLUNK_USERNAME": str(self.integration.username),
            "SPLUNK_PASSWORD": str(self.integration.password),
        }
        return SDKCreds(envs=creds)


