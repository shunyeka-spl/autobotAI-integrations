import traceback
from typing import Type, Union

import boto3
from botocore.exceptions import ClientError
from pydantic import Field

from autobotAI_integrations import (
    BaseService,
    list_of_unique_elements,
    PayloadTask,
    Param,
)
from autobotAI_integrations.models import *
from autobotAI_integrations.utils.boto3_helper import Boto3Helper


class AwsSecurityLakeIntegration(BaseSchema):
    region: str
    access_key: Optional[str] = Field(default=None, exclude=True)
    secret_key: Optional[str] = Field(default=None, exclude=True)
    session_token: Optional[str] = Field(default=None, exclude=True)
    account_id: Optional[str] = None
    roleArn: Optional[str] = None
    externalId: Optional[str] = None

    name: Optional[str] = "AWS Security Lake"
    category: Optional[str] = IntegrationCategory.SECURITY_TOOLS.value
    description: Optional[str] = "AWS Security Lake centralizes security data from across AWS accounts, AWS services, and on-premises."

    def use_dependency(self, dependency: dict):
        self.roleArn = dependency.get("roleArn")
        self.access_key = dependency.get("access_key")
        self.secret_key = dependency.get("secret_key")
        self.session_token = dependency.get("session_token")
        self.externalId = dependency.get("externalId")
        self.account_id = dependency.get("account_id")


class AwsSecurityLakeService(BaseService):

    def __init__(self, ctx: dict, integration: Union[AwsSecurityLakeIntegration, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, AwsSecurityLakeIntegration):
            integration = AwsSecurityLakeIntegration(**integration)
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
            securitylake_client = self._get_aws_client("securitylake")
            response = securitylake_client.list_subscribers()
            sts_client = self._get_aws_client("sts")
            identity_data = sts_client.get_caller_identity()
            account_id = str(identity_data["Account"])
            self.integration.account_id = account_id
            return {"success": True}
        except ClientError as e:
            print(traceback.format_exc())
            return {"success": False, "error": e}

    def get_integration_specific_details(self) -> dict:
        try:
            ec2_client = self._get_aws_client("ec2")
            regions = [
                region["RegionName"]
                for region in ec2_client.describe_regions()["Regions"]
            ]
            # Fetching the model
            return {
                "integration_id": self.integration.accountId,
                "available_regions": regions,
            }
        except Exception as e:
            return {"error": "Details can not be fetched"}

    @staticmethod
    def get_forms():
        return {
            "label": "AWS Security Lake",
            "type": "form",
            "children": [
                {
                    "name": "roleArn",
                    "type": "text",
                    "label": "IAM Role ARN",
                    "placeholder": "Enter IAM role ARN",
                    "required": True,
                },
                {
                    "name": "region",
                    "type": "select",
                    "label": "Region",
                    "placeholder": "Select Region",
                    "required": True,
                },
            ],
        }

    @staticmethod
    def get_schema() -> Type[BaseSchema]:
        return AwsSecurityLakeIntegration

    @classmethod
    def get_details(cls):
        return {
            "clients": list_of_unique_elements(cls.get_all_python_sdk_clients()),
            "supported_executor": "ecs",
            "compliance_supported": False,
            "supported_interfaces": cls.supported_connection_interfaces(),
            "python_code_sample": cls.get_code_sample(),
            "preview": True,
        }

    def build_python_exec_combinations_hook(
        self, payload_task: PayloadTask, client_definitions: List[SDKClient]
    ) -> list:
        creds = {
            "aws_access_key_id": payload_task.creds.envs["AWS_ACCESS_KEY_ID"],
            "aws_secret_access_key": payload_task.creds.envs["AWS_SECRET_ACCESS_KEY"],
        }
        if payload_task.creds.envs.get("AWS_SESSION_TOKEN"):
            creds["aws_session_token"] = payload_task.creds.envs.get(
                "AWS_SESSION_TOKEN"
            )
        return [
            {
                "metadata": {"region": self.integration.region},
                "clients": {
                    "securitylake": boto3.client(
                        "securitylake", region_name=self.integration.region, **creds
                    )
                },
                "params": self.prepare_params(
                    self.filer_combo_params(
                        payload_task.params, self.integration.region
                    )
                ),
                "context": payload_task.context,
            }
        ]

    def filer_combo_params(self, params: List[Param], region):
        filtered_params = []
        for param in params:
            if (
                not param.filter_relevant_resources
                or not param.values
                or not isinstance(param.values, list)
            ):
                filtered_params.append(param)
            else:
                filtered_values = []
                for value in param.values:
                    if isinstance(value, dict) and "region" in value:
                        if value.get("region") == region:
                            filtered_values.append(value)
                    else:
                        filtered_values.append(value)
                filtered_params.append({"name": param.name, "values": filtered_values})
        return filtered_params

    def generate_python_sdk_creds(self, requested_clients=None) -> SDKCreds:
        creds = self._temp_credentials()
        return SDKCreds(envs=creds)

    @staticmethod
    def supported_connection_interfaces():
        return [ConnectionInterfaces.PYTHON_SDK]

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
