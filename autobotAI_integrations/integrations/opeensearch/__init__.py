from enum import Enum
from typing import List, Optional, Type, Union

import boto3
from pydantic import Field, field_validator
from autobotAI_integrations import BaseService
from autobotAI_integrations.models import (
    BaseSchema,
    ConnectionInterfaces,
    IntegrationCategory,
    SDKClient,
    SDKCreds,
)
from autobotAI_integrations.payload_schema import PayloadTask
from autobotAI_integrations.utils.boto3_helper import Boto3Helper
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from utils.logging_config import logger


class OpensearchAuthTypes(Enum):
    AWS_CONFIG = "aws_config"
    DIRECT_AUTH = "direct_auth"


class AWSOpensearchType(Enum):
    AWS_OPENSEARCH_SERVICE = "aws_opensearch_service"
    OPENSEARCH_SERVERLESS = "opensearch_serverless"


class OpensearchIntegration(BaseSchema):
    host_url: str = Field(default=None, description="base url", exclude=True)

    # On-premise Opensearch
    port: int = 443
    username: Optional[str] = Field(default=None, exclude=True)
    password: Optional[str] = Field(default=None, exclude=True)

    # AWS Opensearch Service
    region: str
    opensearch_type: Optional[AWSOpensearchType] = None
    access_key: Optional[str] = Field(default=None, exclude=True)
    secret_key: Optional[str] = Field(default=None, exclude=True)
    session_token: Optional[str] = Field(default=None, exclude=True)
    account_id: Optional[str] = None
    roleArn: Optional[str] = None
    externalId: Optional[str] = None

    name: Optional[str] = "Opensearch"
    category: Optional[str] = IntegrationCategory.MONITORING_TOOLS.value
    description: Optional[str] = (
        "OpenSearch is a community-driven, open-source search and analytics suite, based on Elasticsearch and Kibana, designed for scalability and flexibility in search applications."
    )

    def use_dependency(self, dependency: dict):
        self.roleArn = dependency.get("roleArn")
        self.access_key = dependency.get("access_key")
        self.secret_key = dependency.get("secret_key")
        self.session_token = dependency.get("session_token")
        self.externalId = dependency.get("externalId")
        self.account_id = dependency.get("account_id")

    @field_validator("host_url", mode="before")
    @classmethod
    def validate_host_url(cls, host_url):
        return host_url.strip("/")


class OpensearchService(BaseService):
    def __init__(self, ctx: dict, integration: Union[OpensearchIntegration, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, OpensearchIntegration):
            integration = OpensearchIntegration(**integration)
        super().__init__(ctx, integration)

    def _get_aws_credentials(self, aws_client_name: str):
        if self.integration.roleArn not in ["None", None]:
            boto3_helper = Boto3Helper(
                self.ctx, integration=self.integration.dump_all_data()
            )
            return boto3_helper.get_session().get_credentials()
        else:
            return boto3.Session(
                aws_access_key_id=self.integration.access_key,
                aws_secret_access_key=self.integration.secret_key,
                region_name=self.integration.region,
                aws_session_token=self.integration.session_token,
            ).get_credentials()

    def _test_integration(self):
        try:
            logger.info(f"Initiating test for integration: {self.integration}")
            host = self.integration.host_url.split("://")[1]
            use_ssl = self.integration.host_url.split("://")[0] == "https"
            client = None
            if self.integration.auth_type == OpensearchAuthTypes.AWS_CONFIG.value:
                service = (
                    "es"
                    if AWSOpensearchType.AWS_OPENSEARCH_SERVICE.value
                    == self.integration.opensearch_type
                    else "aoss"
                )
                auth = AWSV4SignerAuth(
                    self._get_aws_credentials(),
                    self.integration.region,
                    service=service,
                )
                client = OpenSearch(
                    hosts=[{"host": host, "port": self.integration.port}],
                    http_auth=auth,
                    use_ssl=use_ssl,
                    verify_certs=use_ssl,
                    connection_class=RequestsHttpConnection,
                    pool_maxsize=20,
                )
            elif self.integration.auth_type == OpensearchAuthTypes.DIRECT_AUTH.value:
                auth = (self.integration.username, self.integration.password)
                client = OpenSearch(
                    hosts=[{"host": host, "port": self.integration.port}],
                    http_auth=auth,
                    use_ssl=use_ssl,
                    verify_certs=use_ssl,
                )
            else:
                return {"success": False, "error": "Invalid Authentication Method."}
            logger.info(str(client.info()))
        except Exception as e:
            logger.error(str(e))
            return {"success": False, "error": "Request failed with unexpected error"}

    def build_python_exec_combinations_hook(
        self, payload_task: PayloadTask, client_definitions: List[SDKClient]
    ) -> list:
        logger.info(f"Initiating test for integration: {self.integration}")
        host = payload_task.creds.envs.get("OPENSEARCH_HOST_URL").split("://")[1]
        use_ssl = (
            payload_task.creds.envs.get("OPENSEARCH_HOST_URL").split("://")[0]
            == "https"
        )
        client = None
        if self.integration.auth_type == OpensearchAuthTypes.AWS_CONFIG.value:
            service = (
                "es"
                if AWSOpensearchType.AWS_OPENSEARCH_SERVICE.value
                == self.integration.opensearch_type
                else "aoss"
            )
            credentials = boto3.Session(
                aws_access_key_id=payload_task.creds.envs.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=payload_task.creds.envs.get(
                    "AWS_SECRET_ACCESS_KEY"
                ),
                aws_session_token=payload_task.creds.envs.get("AWS_SESSION_TOKEN"),
            )
            auth = AWSV4SignerAuth(
                credentials, self.integration.region, service=service
            )
            client = OpenSearch(
                hosts=[{"host": host, "port": self.integration.port}],
                http_auth=auth,
                use_ssl=use_ssl,
                verify_certs=use_ssl,
                connection_class=RequestsHttpConnection,
                pool_maxsize=20,
            )
        elif self.integration.auth_type == OpensearchAuthTypes.DIRECT_AUTH.value:
            auth = (
                payload_task.creds.envs.get("OPENSEARCH_USERNAME"),
                payload_task.creds.envs.get("OPENSEARCH_PASSWORD"),
            )
            client = OpenSearch(
                hosts=[
                    {
                        "host": host,
                        "port": int(payload_task.creds.envs.get("OPENSEARCH_URL_PORT")),
                    }
                ],
                http_auth=auth,
                use_ssl=use_ssl,
                verify_certs=use_ssl,
            )
        return [
            {
                "clients": {
                    "opensearch": client,
                },
                "params": self.prepare_params(payload_task.params),
                "context": payload_task.context,
            }
        ]

    @staticmethod
    def get_forms():
        return {
            "label": "Opensearch",
            "type": "form",
            "children": [
                {
                    "label": "AWS Opensearch Integration",
                    "type": "form",
                    "formId": OpensearchAuthTypes.AWS_CONFIG.value,
                    "children": [
                        {
                            "name": "host_url",
                            "type": "text/url",
                            "label": "Host URL",
                            "placeholder": "Enter the host URL",
                            "required": True,
                        },
                        {
                            "name": "integration_id",
                            "type": "select",
                            "dataType": "integration",
                            "label": "Integration Id",
                            "placeholder": "Enter Integration Id",
                            "description": "Select Account you want to install this integration",
                            "required": True,
                        },
                        {
                            "name": "opensearch_type",
                            "type": "select",
                            "label": "Select OpenSearch Deployment Type",
                            "placeholder": "Choose your OpenSearch deployment",
                            "description": "Please select whether you are using Amazon OpenSearch Service or OpenSearch Serverless for your integration.",
                            "options": [
                                {
                                    "label": "Amazon OpenSearch Service",
                                    "value": "amazon_opensearch",
                                },
                                {
                                    "label": "OpenSearch Serverless",
                                    "value": "opensearch_serverless",
                                },
                            ],
                            "required": True,
                        },
                        {
                            "name": "region",
                            "type": "text",
                            "label": "Region",
                            "placeholder": "example: us-east-1",
                            "required": True,
                        },
                    ],
                },
                {
                    "label": "On-Premises Integration",
                    "type": "form",
                    "formId": OpensearchAuthTypes.DIRECT_AUTH.value,
                    "children": [
                        {
                            "name": "host_url",
                            "type": "text/url",
                            "label": "Host URL",
                            "placeholder": "Enter the host URL",
                            "required": True,
                        },
                        {
                            "name": "port",
                            "type": "number",
                            "label": "Port",
                            "placeholder": "Enter the port number (e.g., 9200)",
                            "required": True,
                        },
                        {
                            "name": "username",
                            "type": "text",
                            "label": "Username",
                            "placeholder": "Enter your username",
                            "required": False,
                        },
                        {
                            "name": "password",
                            "type": "text/password",
                            "label": "Password",
                            "placeholder": "Enter your password",
                            "required": False,
                        },
                        {
                            "name": "use_ssl",
                            "type": "checkbox",
                            "label": "Enable SSL/TLS Encryption",
                            "description": "Enable secure communication using SSL/TLS. Disable only for local or testing environments.",
                            "default": True,
                            "required": False,
                        },
                        {
                            "name": "verify_certs",
                            "type": "checkbox",
                            "label": "Verify SSL Certificates",
                            "description": "Ensure the server's SSL certificate is valid. Disable if using self-signed certificates or testing locally.",
                            "default": True,
                            "required": False,
                        },
                    ],
                },
            ],
        }

    @staticmethod
    def get_schema() -> Type[BaseSchema]:
        return OpensearchIntegration

    @classmethod
    def get_details(cls):
        details = super().get_details()
        details["preview"] = True
        return details

    @staticmethod
    def supported_connection_interfaces():
        return [
            ConnectionInterfaces.PYTHON_SDK,
        ]

    def generate_python_sdk_creds(self) -> SDKCreds:
        envs = {}
        if self.integration.auth_type == OpensearchAuthTypes.AWS_CONFIG.value:
            aws_creds = self._get_aws_credentials()
            envs = {
                "OPENSEARCH_HOST_URL": self.integration.host_url,
                "OPENSEARCH_URL_PORT": 443,
                "AWS_ACCESS_KEY_ID": aws_creds.access_key,
                "AWS_SECRET_ACCESS_KEY": aws_creds.secret_key,
                "AWS_SESSION_TOKEN": aws_creds.session_token,
            }
        else:
            envs = {
                "OPENSEARCH_HOST_URL": self.integration.host_url,
                "OPENSEARCH_URL_PORT": self.integration.port,
                "OPENSEARCH_USERNAME": self.integration.username,
                "OPENSEARCH_PASSWORD": self.integration.password,
            }
        return SDKCreds(envs=envs)