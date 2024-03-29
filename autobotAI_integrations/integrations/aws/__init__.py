import traceback
from typing import Type, List, Optional

import boto3
import pydash
from botocore.exceptions import ClientError
from pydantic import Field

from autobotAI_integrations import BaseService, list_of_unique_elements,PayloadTask
from autobotAI_integrations.models import *
from autobotAI_integrations.utils import boto3_helper
from autobotAI_integrations.utils.boto3_helper import Boto3Helper

import inspect
import platform
import os


class Forms:
    pass


class AWSSDKClient(SDKClient):
    is_regional: bool


class AWSIntegration(BaseSchema):
    # TODO: Add validation for role_arn and access keys
    access_key: Optional[str] = Field(default=None, exclude=True)
    secret_key: Optional[str] = Field(default=None, exclude=True)
    session_token: Optional[str] = Field(default=None, exclude=True)
    account_id: str = None
    role_arn: Optional[str] = None
    activeRegions: Optional[list] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class AWSService(BaseService):

    def __init__(self, ctx: dict, integration: AWSIntegration):
        """
        Integration should have all the data regarding the integration
        """
        super().__init__(ctx, integration)

    def _test_integration(self, integration: dict) -> dict:
        try:
            boto3_helper = Boto3Helper(self.ctx, integration=integration)
            boto3_helper.get_client("ec2")
            return {'success': True}
        except ClientError as e:
            print(traceback.format_exc())
            return {'success': False, 'error': traceback.format_exc()}

    def get_forms(self):
        return {
            "access_secret_form": {
                "fields": [
                    {
                        "name": "access_key",
                        "type": "text",
                        "label": "Access Key",
                        "placeholder": "Enter your AWS access key",
                        "required": True
                    },
                    {
                        "name": "secret_key",
                        "type": "password",
                        "label": "Secret Key",
                        "placeholder": "Enter your AWS secret key",
                        "required": True
                    }
                ],
                "submit_label": "Submit"
            },
            "iam_role_form": {
                "fields": [
                    {
                        "name": "roleArn",
                        "type": "text",
                        "label": "IAM Role ARN",
                        "placeholder": "Enter IAM role ARN",
                        "required": True
                    }
                ],
                "submit_label": "Submit"
            }
        }

    @staticmethod
    def get_schema() -> Type[BaseSchema]:
        return AWSIntegration

    @classmethod
    def get_details(cls):
        return {
            "automation_code": "",
            "fetcher_code": "",
            "automation_supported": ["communication", 'mutation'],
            "clients": list_of_unique_elements(cls.get_all_python_sdk_clients()),
            "supported_executor": "ecs",
            "compliance_supported": False
        }

    def generate_steampipe_creds(self) -> SteampipeCreds:
        creds = self._temp_credentials()
        conf_path = "~/.steampipe/config/aws.spc"
        return SteampipeCreds(envs=creds, plugin_name="aws", connection_name="aws",
                              conf_path=conf_path)

    def build_python_exec_combinations_hook(self, payload_task: PayloadTask, client_definitions: List[SDKClient]) -> list:
        built_clients = {
            "global": {},
            "regional": {

            }
        }
        global_clients = pydash.filter_(client_definitions, lambda x: x.is_regional is False)
        regional_clients = pydash.filter_(client_definitions, lambda x: x.is_regional is True)
        if global_clients:
            for client in global_clients:
                built_clients["global"].append(boto3.client(client.name))
        for region in self.integration.activeRegions:
            built_clients["regional"].setdefault(region, {})
            for client in regional_clients:
                try:
                    built_clients["regional"][region][client.name] = boto3.client(client.name, region_name=region)
                except ImportError:
                    print(f"Failed create client for {client['name']}")
        combinations = []
        if built_clients["regional"]:
            for region in built_clients["regional"]:
                combo = {
                    "metadata": {
                        "region": region
                    },
                    "clients": {**built_clients["global"], **built_clients["regional"][region]}
                }
                resources = []
                if payload_task.node_details.get("filter_resources"):
                    for resource in payload_task.resources:
                        if resource.get("integration_type") == self.get_integration_type():
                            if resource.get("region") == region:
                                resources.append(resource)
                else:
                    resources = payload_task.resources
                combo["resources"] = resources
                combo["params"] = payload_task.params
                combo["context"] = payload_task.context
                combinations.append(combo)
        return combinations

    def generate_python_sdk_creds(self, requested_clients=None) -> SDKCreds:
        creds = self._temp_credentials()
        clients = self.get_all_python_sdk_clients()
        package_names = None
        return SDKCreds(library_names=[], clients=[], envs=creds, package_names=package_names)

    @staticmethod
    def supported_connection_interfaces():
        return [ConnectionInterfaces.REST_API, ConnectionInterfaces.CLI, ConnectionInterfaces.PYTHON_SDK, ConnectionInterfaces.STEAMPIPE]

    def generate_cli_creds(self) -> CLICreds:
        raise NotImplementedError()

    def _temp_credentials(self):
        if self.integration.role_arn:
            return {
                "AWS_ACCESS_KEY_ID": self.ctx.integration_context.boto3_helper.get_access_key(),
                "AWS_SECRET_ACCESS_KEY": self.ctx.integration_context.boto3_helper.get_secret_key(),
                "AWS_SESSION_TOKEN": self.ctx.integration_context.boto3_helper.get_session_token(),
            }
        else:
            return {
                "AWS_ACCESS_KEY_ID": self.integration.access_key,
                "AWS_SECRET_ACCESS_KEY": self.integration.secret_key,
                "AWS_SESSION_TOKEN": self.integration.session_token,
            }
