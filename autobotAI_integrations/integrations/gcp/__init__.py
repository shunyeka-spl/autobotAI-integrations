import uuid
from typing import List, Optional, Type, Union
import importlib
from pathlib import Path
import json

from pydantic import BaseModel, ConfigDict, Field, field_validator
from functools import wraps

from autobotAI_integrations import list_of_unique_elements

from autobotAI_integrations import BaseSchema, SteampipeCreds, SDKCreds, CLICreds, \
    BaseService, ConnectionInterfaces, PayloadTask, SDKClient

from autobotAI_integrations.models import IntegrationCategory
import os
import pydantic


class GCPCredentials(BaseModel):
    model_config = ConfigDict(frozen=True)

    type_: str = Field(alias="type", serialization_alias="type")
    project_id: str
    private_key_id: str
    private_key: str
    client_email: str
    client_id: str
    auth_uri: str
    token_uri: str
    auth_provider_x509_cert_url: str
    client_x509_cert_url: str

    def model_dump(self, **kwargs):
        return super().model_dump(by_alias=True, **kwargs)

    def model_dump_json(self, **kwargs):
        return super().model_dump_json(by_alias=True, **kwargs)


class GCPIntegration(BaseSchema):
    # TODO: Integration Credential Field Optimization,
    account_id: Optional[str] = uuid.uuid4().hex
    credentials: Optional[GCPCredentials] = Field(default=None, exclude=True)

    name: Optional[str] = "GCP"
    category: Optional[str] = IntegrationCategory.CLOUD_SERVICES_PROVIDERS.value
    description: Optional[str] = (
        "GCP is Google Cloud Platform, a suite of cloud computing services offered by Google."
    )

    def __init__(self, **kwargs):
        if kwargs.get("credentials"):
            creds = kwargs.get("credentials")
            if isinstance(kwargs.get('credentials'), str):
                creds = json.loads(creds)
            try:
                kwargs["credentials"] = GCPCredentials(**creds)
            except pydantic.ValidationError as e:
                # generating custom error message
                errors = [err_str for err_str in str(e).split("\n") if not err_str.startswith(' ')]
                raise ValueError("Validation error for fields: {}".format(errors[1:]))
        if not kwargs.get("accountId"):
            kwargs["accountId"] = str(creds.get("project_id"))
        super().__init__(**kwargs)

    @field_validator('credentials', mode='before')
    @classmethod
    def validate_credentials(cls, credentials) -> GCPCredentials:
        if isinstance(credentials, dict):
            return GCPCredentials(**credentials)
        if isinstance(credentials, str):
            try:
                return GCPCredentials(**json.loads(credentials))  # Parse JSON string
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(f"Invalid JSON format in 'credentials': {e}")
        return credentials


class GCPService(BaseService):

    def __init__(self, ctx: dict, integration: Union[GCPIntegration, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, GCPIntegration):
            integration = GCPIntegration(**integration)
        super().__init__(ctx, integration)

    def _test_integration(self) -> dict:
        try:
            from google.cloud.storage import Client as StorageClient # type: ignore
            from google.oauth2.service_account import Credentials # type: ignore
            from google.api_core.exceptions import Forbidden, BadRequest # type: ignore
            from google.auth.exceptions import RefreshError # type: ignore

            gcp_creds = self.integration.credentials.model_dump()
            scopes = ["https://www.googleapis.com/auth/cloud-platform"]
            try:
                credentials = Credentials.from_service_account_info(gcp_creds, scopes=scopes)
            except:
                return {
                    "success": False,
                    "error": "Invalid credentials provided. Please check your service account keys and try again.",
                }
            client = StorageClient(credentials=credentials)
            try:
                buckets = client.list_buckets()
                print("Buckets: ")
                for bucket in buckets:
                    print(bucket.name)
                return {"success": True}
            except BadRequest as e:
                return {
                    "success": False,
                    "error": "Bad request: Please check the project ID and request parameters.",
                }
            except Forbidden:
                return {
                    "success": False,
                    "error": "Permission denied. Please ensure the service account has the storage.buckets.list permission.",
                }
            except RefreshError:
                return {
                    "success": False,
                    "error": "Invalid or expired credentials. Please check your service account keys (client email)  and try again.",
                }
        except Exception as e:
            return {"success": False, "error": f"Unexpected Error: {str(e)}"}

    @staticmethod
    def get_forms():
        return {
            "label": "GCP",
            "type": "form",
            "children": [
                {
                    "name": "credentials",
                    "type": "json",
                    "label": "Credentials JSON",
                    "placeholder": "Enter the Credentials In JSON Format",
                    "required": True,
                }
            ],
        }

    @staticmethod
    def get_schema() -> Type[BaseSchema]:
        return GCPIntegration

    @classmethod
    def get_details(cls):
        return {
            "clients": list_of_unique_elements(cls.get_all_python_sdk_clients()),
            "supported_executor": "ecs",
            "compliance_supported": True,
            "supported_interfaces": cls.supported_connection_interfaces(),
            "python_code_sample": cls.get_code_sample(),
        }

    def generate_steampipe_creds(self) -> SteampipeCreds:
        creds = self._temp_credentials()
        conf_path = "~/.steampipe/config/gcp.spc"
        config = """connection "gcp" {
  plugin    = "gcp"

  ignore_error_codes = ["401", "403"]
}
"""
        return SteampipeCreds(
            envs=creds, plugin_name="gcp", connection_name="gcp", conf_path=conf_path, config=config,
        )

    def build_python_exec_combinations_hook(
            self, payload_task: PayloadTask, client_definitions: List[SDKClient]
    ) -> list:
        from google.oauth2 import service_account # type: ignore
        clients_classes = dict()
        credentials_dict = GCPCredentials.model_validate_json(
            json.loads(payload_task.creds.envs["GOOGLE_APPLICATION_CREDENTIALS"])
        ).model_dump()

        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        for client in client_definitions:
            try:
                client_module = importlib.import_module(client.module, package=None)
                if not client.class_name:
                    # NOTE: Preventing the import of module as much as possible to reduce complexity
                    try:
                        name, version = client.name.split("_", 1)
                        clients_classes[client.name] = client_module.build(
                            serviceName=name,
                            version=version,
                            credentials=credentials,
                        )
                    except ValueError as e:
                        clients_classes[client.name] = client_module
                    continue
                if hasattr(client_module, client.class_name):
                    cls = getattr(client_module, client.class_name)
                    try:
                        clients_classes[client.name] = cls(
                            project=payload_task.creds.envs["CLOUDSDK_CORE_PROJECT"],
                            credentials=credentials
                        )
                    except TypeError:
                        clients_classes[client.name] = cls(
                            credentials=credentials,
                        )
            except BaseException as e:
                print(e)
                continue
        return [
            {
                "clients": clients_classes,
                "params": self.prepare_params(payload_task.params),
                "context": payload_task.context
            }
        ]

    def generate_python_sdk_creds(self, requested_clients=None) -> SDKCreds:
        envs = self._temp_credentials()
        return SDKCreds(creds={}, envs=envs)

    @staticmethod
    def supported_connection_interfaces():
        return [
            ConnectionInterfaces.REST_API,
            ConnectionInterfaces.CLI,
            ConnectionInterfaces.PYTHON_SDK,
            ConnectionInterfaces.STEAMPIPE,
        ]

    def generate_cli_creds(self) -> CLICreds:
        raise NotImplementedError()

    def _temp_credentials(self):
        return {
            "CLOUDSDK_CORE_PROJECT": self.integration.credentials.project_id,
            "GOOGLE_APPLICATION_CREDENTIALS": json.dumps(self.integration.credentials.model_dump_json())
        }

    @staticmethod
    def manage_creds_path(func):
        @wraps(func)
        def wrapper(self, payload_task: PayloadTask, *args, **kwargs):
            try:
                home_dir = Path.home()
                credentials_dict = GCPCredentials.model_validate_json(
                    json.loads(payload_task.creds.envs["GOOGLE_APPLICATION_CREDENTIALS"])
                ).model_dump()
                file_path = os.path.join(home_dir, f"gcp_credentials_{str(uuid.uuid4().hex)}.json")
                with open(file_path, "w") as f:
                    f.write(json.dumps(credentials_dict))

                payload_task.creds.envs["GOOGLE_APPLICATION_CREDENTIALS"] = file_path
                result = func(self, payload_task, *args, **kwargs)  # Call the original function
            finally:
                try:
                    os.remove(file_path)
                except BaseException as e:
                    print(e)
            return result
        return wrapper

    @manage_creds_path
    def execute_steampipe_task(self, payload_task: PayloadTask):
        return super().execute_steampipe_task(payload_task)
