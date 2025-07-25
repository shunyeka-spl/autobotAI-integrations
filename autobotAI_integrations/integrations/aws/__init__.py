import traceback
from typing import Type, Union
from enum import Enum

import uuid
import boto3
import pydash
from botocore.exceptions import ClientError
from pydantic import Field, model_validator
import os

from autobotAI_integrations import BaseService, list_of_unique_elements, PayloadTask, Param
from autobotAI_integrations.models import *
from autobotAI_integrations.utils.boto3_helper import Boto3Helper
from autobotAI_integrations.utils.logging_config import logger


class Forms:
    pass


class AWSSDKClient(SDKClient):
    is_regional: bool

class AWSAuthTypes(str, Enum):
    IAM_ROLE_INTEGRaTION = "iam_role_integration"
    ACCESS_KEY_INTEGRATION = "access_key_integration"


class AWSIntegration(BaseSchema):
    # TODO: Add validation for role_arn and access keys
    access_key: Optional[str] = Field(default=None, exclude=True)
    secret_key: Optional[str] = Field(default=None, exclude=True)
    session_token: Optional[str] = Field(default=None, exclude=True)
    account_id: Optional[str] = None
    roleArn: Optional[str] = None
    externalId: Optional[str] = None
    activeRegions: Optional[list] = None

    name: Optional[str] = "AWS"
    category: Optional[str] = IntegrationCategory.CLOUD_SERVICES_PROVIDERS.value
    description: Optional[str] = (
        """The world's most comprehensive and mature cloud computing platform, offering a vast range of on-demand compute, storage, database, networking, analytics, and machine learning services."""
    )

    def __init__(self, **kwargs):
        if not kwargs.get("accountId"):
            kwargs["accountId"] = str(uuid.uuid4().hex)
        super().__init__(**kwargs)

    @model_validator(mode="before")
    @classmethod
    def resource_type_validator(cls, values: Any) -> Any:
        if values.get("accountId", None):
            values["accountId"] = str(values["accountId"])
        return values


class AWSService(BaseService):

    def __init__(self, ctx: dict, integration: Union[AWSIntegration, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, AWSIntegration):
            integration = AWSIntegration(**integration)
        super().__init__(ctx, integration)

    def _get_aws_client(self, aws_client_name: str):
        if self.integration.roleArn not in ["None", None]:
            boto3_helper = Boto3Helper(
                self.ctx, integration=self.integration.dump_all_data()
            )
            return boto3_helper.get_client(aws_client_name)
        else:
            return boto3.client(
                aws_client_name,
                aws_access_key_id=str(self.integration.access_key),
                aws_secret_access_key=str(self.integration.secret_key),
                aws_session_token=(
                    str(self.integration.session_token)
                    if self.integration.session_token not in [None, "None"]
                    else None
                ),
            )

    def _test_integration(self) -> dict:
        try:
            sts_client = self._get_aws_client("sts")
            ec2_client = self._get_aws_client("ec2")
            identity_data = sts_client.get_caller_identity()
            account_id = str(identity_data["Account"])
            self.integration.account_id = account_id
            self.integration.activeRegions = [
                region["RegionName"]
                for region in ec2_client.describe_regions()["Regions"]
            ]
            return {"success": True}
        except ClientError as e:
            logger.debug(e.response)
            logger.debug(traceback.format_exc())
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_forms():
        return {
            "label": "AWS",
            "type": "form",
            "children": [
                {
                    "label": "IAM Role Integration",
                    "type": "form",
                    "formId": AWSAuthTypes.IAM_ROLE_INTEGRaTION.value,
                    "children": [
                        {
                            "name": "roleArn",
                            "type": "text",
                            "label": "IAM Role ARN",
                            "placeholder": "Enter IAM role ARN",
                            "required": True
                        }
                    ]
                },
                {
                    "label": "AccessKey / SecretKey Integration",
                    "type": "form",
                    "formId": AWSAuthTypes.ACCESS_KEY_INTEGRATION.value,
                    "children": [
                        {
                            "name": "access_key",
                            "type": "text",
                            "label": "Access Key",
                            "placeholder": "Enter your AWS access key",
                            "required": True
                        },
                        {
                            "name": "secret_key",
                            "type": "text/password",
                            "label": "Secret Key",
                            "placeholder": "Enter your AWS secret key",
                            "required": True
                        }
                    ]
                }
            ]
        }

    def get_integration_specific_details(self) -> dict:
        try:
            ec2_client = self._get_aws_client('ec2')
            regions = [region['RegionName'] for region in ec2_client.describe_regions()["Regions"]]
            return {
                "integration_id": self.integration.accountId,
                "activeRegions": regions
            }
        except Exception as e:
            logger.warn("Details cannot be fetched")
            return {
                "error": "Details cannot be fetched"
            }

    @staticmethod
    def get_schema() -> Type[BaseSchema]:
        return AWSIntegration

    @classmethod
    def get_details(cls):
        return {
            "clients": list_of_unique_elements(cls.get_all_python_sdk_clients()),
            "supported_executor": "ecs",
            "compliance_supported": True,
            "supported_interfaces": cls.supported_connection_interfaces(),
            "python_code_sample": cls.get_code_sample()
        }

    def generate_steampipe_creds(self) -> SteampipeCreds:
        creds = {k: v for k, v in self._temp_credentials().items() if v}
        conf_path = "~/.steampipe/config/aws.spc"
        config = """connection "aws" {
  plugin = "aws"
  regions = ["*"]
  ignore_error_codes = ["InvalidClientTokenId", "InvalidToken", "AccessDenied", "AccessDeniedException", "NotAuthorized", "UnauthorizedOperation", "UnrecognizedClientException", "AuthorizationError"]
}
"""
        return SteampipeCreds(envs=creds, plugin_name="aws", connection_name="aws",
                              conf_path=conf_path, config=config)

    def build_python_exec_combinations_hook(self, payload_task: PayloadTask,
                                            client_definitions: List[SDKClient]) -> list:
        built_clients = {
            "global": {},
            "regional": {

            }
        }
        global_clients = pydash.filter_(client_definitions, lambda x: x.is_regional is False)
        regional_clients = pydash.filter_(client_definitions, lambda x: x.is_regional is True)
        creds = {
            "aws_access_key_id": payload_task.creds.envs["AWS_ACCESS_KEY_ID"],
            "aws_secret_access_key": payload_task.creds.envs["AWS_SECRET_ACCESS_KEY"],            
        }
        if payload_task.creds.envs.get("AWS_SESSION_TOKEN"):
            creds["aws_session_token"] = payload_task.creds.envs.get("AWS_SESSION_TOKEN")
        if global_clients:
            for client in global_clients:
                built_clients["global"][client.name] = boto3.client(client.name, **creds)
        if regional_clients:
            active_regions = self.integration.activeRegions
            if not active_regions:
                active_regions = self.get_integration_specific_details()["available_regions"]
                logger.info("Active Regions: %s", active_regions)
            for region in active_regions:
                built_clients["regional"].setdefault(region, {})
                for client in regional_clients:
                    try:
                        built_clients["regional"][region][client.name] = boto3.client(client.name, region_name=region,
                                                                                      **creds)
                    except ImportError:
                        logger.exception(f"Failed create client for {client['name']}")
        combinations = []
        if built_clients["regional"]:
            for region in built_clients["regional"]:
                this_params = self.filer_combo_params(payload_task.params, region)
                execute_for_this_region = True
                for param in this_params:
                    if param["filter_relevant_resources"] and param["required"] and not param["values"]:
                        execute_for_this_region = False
                        break
                if not execute_for_this_region:
                    continue
                combo = {"metadata": {
                    "region": region
                }, "clients": {**built_clients["global"], **built_clients["regional"][region]},
                    "params": self.prepare_params(this_params),
                    "context": payload_task.context}
                combinations.append(combo)
        else:
            combo = {"metadata": {
                "region": "global"
            }, "clients": {**built_clients["global"]},
                "params": self.prepare_params(self.filer_combo_params(payload_task.params, "global")),
                "context": payload_task.context}
            combinations.append(combo)
        return combinations

    def filer_combo_params(self, params: List[Param], region):
        filtered_params = []
        for param in params:
            if not param.filter_relevant_resources or not param.values or not isinstance(param.values, list):
                filtered_params.append(param.model_dump())
            else:
                filtered_values = []
                for value in param.values:
                    if isinstance(value, dict) and "region" in value:
                        if value.get("region") == region:
                            filtered_values.append(value)
                    else:
                        filtered_values.append(value)
                filtered_params.append({**param.model_dump(), "values": filtered_values})
        return filtered_params

    def generate_python_sdk_creds(self, requested_clients=None) -> SDKCreds:
        creds = self._temp_credentials()
        return SDKCreds(envs=creds)

    @staticmethod
    def supported_connection_interfaces():
        return [ConnectionInterfaces.REST_API, ConnectionInterfaces.CLI, ConnectionInterfaces.PYTHON_SDK,
                ConnectionInterfaces.STEAMPIPE]

    def generate_cli_creds(self) -> CLICreds:
        raise NotImplementedError()

    def _temp_credentials(self):
        if self.integration.roleArn not in ["None", None]:
            boto3_helper = Boto3Helper(
                self.ctx, integration=self.integration.model_dump()
            )
            return {
                "AWS_ACCESS_KEY_ID": boto3_helper.get_access_key(),
                "AWS_SECRET_ACCESS_KEY": boto3_helper.get_secret_key(),
                "AWS_SESSION_TOKEN": boto3_helper.get_session_token(),
            }
        else:
            creds = {
                "AWS_ACCESS_KEY_ID": str(self.integration.access_key),
                "AWS_SECRET_ACCESS_KEY": str(self.integration.secret_key),
            }
            if self.integration.session_token not in [None, "None"]:
                creds["AWS_SESSION_TOKEN"] = str(self.integration.session_token)
            return creds
