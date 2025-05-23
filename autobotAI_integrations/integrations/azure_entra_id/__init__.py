import importlib
from typing import List, Optional, Type, Union
from pydantic import Field
import requests

from autobotAI_integrations import BaseService, list_of_unique_elements, PayloadTask

from autobotAI_integrations.models import (
    BaseSchema,
    CLICreds,
    ConnectionInterfaces,
    IntegrationCategory,
    RestAPICreds,
    SDKClient,
    SDKCreds,
    SteampipeCreds,
)


class AzureEntraIdIntegration(BaseSchema):
    tenant_id: Optional[str] = Field(default=None, exclude=True)
    client_id: Optional[str] = Field(default=None, exclude=True)
    client_secret: Optional[str] = Field(default=None, exclude=True)

    name: Optional[str] = "Azure Entra ID"
    category: Optional[str] = IntegrationCategory.CLOUD_SERVICES_PROVIDERS.value
    description: Optional[str] = (
        "Azure Active Directory is Microsoft's cloud-based identity and access management service, which helps your employees sign in and access resources"
    )


class AzureEntraIdService(BaseService):
    def __init__(self, ctx: dict, integration: Union[AzureEntraIdIntegration, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, AzureEntraIdIntegration):
            integration = AzureEntraIdIntegration(**integration)
        super().__init__(ctx, integration)

    def _test_integration(self) -> dict:
        try:
            url = f"https://login.microsoftonline.com/{self.integration.tenant_id}/oauth2/v2.0/token"
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            data = {
                "client_id": self.integration.client_id,
                "scope": "https://graph.microsoft.com/.default",
                "client_secret": self.integration.client_secret,
                "grant_type": "client_credentials",
            }

            response = requests.post(url, headers=headers, data=data)
            if response.status_code == 200:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": f"Request failed with status code: {response.status_code}",
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_forms():
        return {
            "label": "Azure Entra Id",
            "type": "form",
            "children": [
                {
                    "name": "tenant_id",
                    "type": "text",
                    "label": "Tenant ID",
                    "placeholder": "Enter your Azure tenant ID",
                    "required": True,
                },
                {
                    "name": "client_id",
                    "type": "text",
                    "label": "Client ID",
                    "placeholder": "Enter your Azure application client ID",
                    "required": True,
                },
                {
                    "name": "client_secret",
                    "type": "text/password",
                    "label": "Client Secret",
                    "placeholder": "Enter your Azure Application Client Secret",
                    "required": True,
                },
            ],
        }

    @staticmethod
    def get_schema() -> Type[BaseSchema]:
        return AzureEntraIdIntegration

    @classmethod
    def get_details(cls):
        return {
            "clients": list_of_unique_elements(cls.get_all_python_sdk_clients()),
            "supported_executor": "ecs",
            "compliance_supported": False,
            "supported_interfaces": cls.supported_connection_interfaces(),
            "python_code_sample": cls.get_code_sample(),
        }

    def generate_steampipe_creds(self) -> SteampipeCreds:
        creds = self._temp_credentials()
        conf_path = "~/.steampipe/config/azuread.spc"
        config = """connection "azuread" {
  plugin = "azuread"
}"""
        return SteampipeCreds(
            envs=creds,
            plugin_name="azuread",
            connection_name="azuread",
            conf_path=conf_path,
            config=config,
        )

    def build_python_exec_combinations_hook(
        self, payload_task: PayloadTask, client_definitions: List[SDKClient]
    ) -> list:
        from azure.identity import ClientSecretCredential
        credential = ClientSecretCredential(
            tenant_id=payload_task.creds.envs.get("AZURE_TENANT_ID"),
            client_id=payload_task.creds.envs.get("AZURE_CLIENT_ID"),
            client_secret=payload_task.creds.envs.get("AZURE_CLIENT_SECRET"),
        )
        scopes = ["https://graph.microsoft.com/.default"]
        clients_classes = {}
        for client in client_definitions:
            try:
                client_module = importlib.import_module(client.module, package=None)
                if hasattr(client_module, client.class_name):
                    cls = getattr(client_module, client.class_name)
                    try:
                        clients_classes[client.name] = cls(
                            credentials=credential, scopes=scopes
                        )
                    except BaseException:
                        clients_classes[client.name] = cls(credentials=credential)
            except BaseException as e:
                print(e)
                continue
        return [
            {
                "clients": clients_classes,
                "params": self.prepare_params(payload_task.params),
                "context": payload_task.context,
            }
        ]

    def generate_python_sdk_creds(self, requested_clients=None) -> SDKCreds:
        creds = self._temp_credentials()
        return SDKCreds(envs=creds)

    @staticmethod
    def supported_connection_interfaces():
        return [
            ConnectionInterfaces.REST_API,
            ConnectionInterfaces.CLI,
            ConnectionInterfaces.PYTHON_SDK,
            # ConnectionInterfaces.STEAMPIPE,
        ]

    def generate_cli_creds(self) -> CLICreds:
        raise NotImplementedError()

    def _temp_credentials(self):
        return {
            "AZURE_TENANT_ID": self.integration.tenant_id,
            "AZURE_CLIENT_ID": self.integration.client_id,
            "AZURE_CLIENT_SECRET": self.integration.client_secret,
        }
    
    def generate_rest_api_creds(self) -> RestAPICreds:
        try:
            url = f"https://login.microsoftonline.com/{self.integration.tenant_id}/oauth2/v2.0/token"
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            data = {
                "client_id": self.integration.client_id,
                "scope": "https://graph.microsoft.com/.default",
                "client_secret": self.integration.client_secret,
                "grant_type": "client_credentials",
            }
            response = requests.post(url, headers=headers, data=data).json()
            return RestAPICreds(
                base_url="https://graph.microsoft.com",
                headers={"Authorization": f"Bearer {response.get('access_token')}"},
            )
        except Exception as e:
            raise Exception(f"Error while generating rest api creds: {e}")

