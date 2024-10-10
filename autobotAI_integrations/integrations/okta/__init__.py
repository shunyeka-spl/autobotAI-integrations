import importlib
from typing import List, Optional, Union

from pydantic import Field

from autobotAI_integrations import (
    BaseSchema,
    SteampipeCreds,
    RestAPICreds,
    SDKCreds,
    CLICreds,
    BaseService,
    ConnectionInterfaces,
    PayloadTask,
    SDKClient,
)

from autobotAI_integrations.models import IntegrationCategory
import requests

# demeg63111@hraifi.com
# @Password123


class OktaIntegration(BaseSchema):
    host_url: str
    token: Optional[str] = Field(default=None, exclude=True)

    category: Optional[str] = IntegrationCategory.MONITORING_TOOLS.value
    description: Optional[str] = (
        "Okta is the leading independent identity provider. The Okta Identity enables organizations to securely connect the right people to the right technologies at the right time."
    )


class OktaService(BaseService):

    def __init__(self, ctx: dict, integration: Union[OktaIntegration, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, OktaIntegration):
            integration = OktaIntegration(**integration)
        super().__init__(ctx, integration)

    def _test_integration(self):
        try:
            response = requests.get(self.integration.host_url)
            if response.status_code == 200:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": f"Request failed with status code: {response.status_code}",
                }
        except requests.exceptions.ConnectionError as e:
            return {"success": False, "error": "Connection is Unreachable"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_forms():
        return {
            "label": "Okta",
            "type": "form",
            "children": [
                {
                    "name": "host_url",
                    "type": "text/url",
                    "label": "Okta Host URL",
                    "placeholder": "Enter HOST URL",
                    "required": True,
                }
            ],
        }

    @staticmethod
    def get_schema():
        return OktaIntegration

    @staticmethod
    def supported_connection_interfaces():
        return [
            ConnectionInterfaces.REST_API,
            ConnectionInterfaces.CLI,
            ConnectionInterfaces.PYTHON_SDK,
            ConnectionInterfaces.STEAMPIPE,
        ]

    def build_python_exec_combinations_hook(
        self, payload_task: PayloadTask, client_definitions: List[SDKClient]
    ) -> list:
        okta = importlib.import_module(
            client_definitions[0].import_library_names[0], package=None
        )

        return [
            {
                "clients": {
                    "okta_api_client": okta.OktaConnect(
                        url=payload_task.creds.envs["OKTA_URL"], disable_ssl=True
                    ),
                },
                "params": self.prepare_params(payload_task.params),
                "context": payload_task.context,
            }
        ]

    def generate_steampipe_creds(self) -> SteampipeCreds:
        envs = {
            "OKTA_URL": self.integration.host_url,
        }
        conf_path = "~/.steampipe/config/okta.spc"
        config = """connection "okta" {
  plugin = "okta"
  # metrics = [".+"]
}"""
        return SteampipeCreds(
            envs=envs,
            plugin_name="okta",
            connection_name="okta",
            conf_path=conf_path,
            config=config,
        )

    def generate_rest_api_creds(self) -> RestAPICreds:
        pass

    def generate_python_sdk_creds(self) -> SDKCreds:
        envs = {"OKTA_URL": self.integration.host_url}
        return SDKCreds(envs=envs)

    def generate_cli_creds(self) -> CLICreds:
        pass
