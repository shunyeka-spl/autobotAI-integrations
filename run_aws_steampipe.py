from autobotAI_integrations import IntegrationSchema
from autobotAI_integrations.integrations import integration_service_factory
from aws_payload import generate_aws_steampipe_payload

import os

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

steampipe_payload = generate_aws_steampipe_payload(aws_json)

output_path = os.path.join(os.getcwd(), "aws_s3_buckets.json")

for task in steampipe_payload.tasks:
    integration = IntegrationSchema.model_validate(task.context.integration)
    service = integration_service_factory.get_service(None, integration)
    service.execute_steampipe_task(task, job_type="query", output_path=output_path)
