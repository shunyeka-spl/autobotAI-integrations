from autobotAI_integrations import IntegrationSchema
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations import ConnectionInterfaces
from autobotAI_integrations.integrations.aws import AWSIntegration
from autobotAI_integrations.payload_schema import Payload, PayloadTask, PayloadTaskContext, \
    ExecutionDetails, Caller
import os, uuid

from dotenv import load_dotenv
load_dotenv()

access_key = os.getenv("access_key")
secret_key = os.getenv("secret_key")

aws_json = {
    "userId": "amit@shunyeka.com*",
    "accountId": "175c0fa813244bc5a1aa6264e7ba20cc",
    "integrationState": "INACTIVE",
    "cspName": "aws",
    "access_key": access_key,
    "secret_key": secret_key,
    "session_token": "",
    "alias": "test-aws-integrationsv2",
    "connection_type": "DIRECT",
    "groups": ["aws", "shunyeka", "integrations-v2"],
    "agent_ids": [],
    "accessToken": "",
    "createdAt": "2024-02-26T13:38:59.978056",
    "updatedAt": "2024-02-26T13:38:59.978056",
    "indexFailures": 0,
    "isUnauthorized": False,
    "lastUsed": None,
    "resource_type": "integration",
    "activeRegions": [
        'us-east-1',
        'ap-south-1'
    ],
}

aws_config_str = """
connection "aws" {
  plugin = "aws"
  #default_region = "eu-west-2"

  #profile = "myprofile"

  #max_error_retry_attempts = 9

  #min_error_retry_delay = 25

  #ignore_error_codes = ["AccessDenied", "AccessDeniedException", "NotAuthorized", "UnauthorizedOperation", "UnrecognizedClientException", "AuthorizationError"]

  #endpoint_url = "http://localhost:4566"

  # Set to `true` to force S3 requests to use path-style addressing,
  # i.e., `http://s3.amazonaws.com/BUCKET/KEY`. By default, the S3 client
  # will use virtual hosted bucket addressing when possible (`http://BUCKET.s3.amazonaws.com/KEY`).
  #s3_force_path_style = false
}
"""

def generate_aws_steampipe_payload() -> Payload:
    aws_integration = AWSIntegration(**aws_json)
    aws_service = integration_service_factory.get_service(None, aws_integration)
    creds = aws_service.generate_steampipe_creds()
    creds.config=aws_config_str
    aws_task_dict = {
        "task_id": uuid.uuid4().hex,
        "creds": creds,
        "connection_interface": ConnectionInterfaces.STEAMPIPE,
        "executable": "select * from aws_s3_bucket",
        "context": PayloadTaskContext(
            integration=aws_integration,
            global_variables={},
            integration_variables={},
            integration_group_vars={},
            execute_details=ExecutionDetails(
                execution_id="lsahlkwa",
                bot_id="akjflk",
                bot_name="lhfskah",
                node_name="lskahf",
                caller=Caller(
                    user_id="ljfa",
                    root_user_id="jflfhls"
                )
            ),
            node_steps={}
        ),
    }
    payload_dict = {
        "job_id": uuid.uuid4().hex,
        "tasks": [PayloadTask(**aws_task_dict)]
    }
    payload = Payload(**payload_dict)
    return payload

steampipe_payload = generate_aws_steampipe_payload()

for task in steampipe_payload.tasks:
    integration = IntegrationSchema.model_validate(task.context.integration)
    service = integration_service_factory.get_service(None, integration)
    output = service.execute_steampipe_task(task, job_type="query")
    # print(output)
