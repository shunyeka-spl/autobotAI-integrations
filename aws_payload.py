import uuid

from autobotAI_integrations import ConnectionTypes
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.integrations.aws import AWSIntegration
from autobotAI_integrations.payload_schema import Payload, PayloadTask

aws_json = {
    "userId": "amit@shunyeka.com*",
    "accountId": "175c0fa813244bc5a1aa6264e7ba20cc",
    "integrationState": "INACTIVE",
    "cspName": "aws*",
    "acccess_key": "hkags",
    "secret_key": "hkhkjgv",
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
def generate_aws_payload(aws_json) -> Payload:
    aws_integration = AWSIntegration(**aws_json)
    aws_service = integration_service_factory.get_service("aws", None, aws_integration)
    creds = aws_service.generate_steampipe_creds()
    aws_task_dict = {
        "taskId": uuid.uuid4().hex,
        "creds": creds,
        "connection_type": ConnectionTypes.STEAMPIPE,
        "executable": "select * from aws_s3_bucket",
        "context": {},
        "interation_specific_details": {}
    }
    payload_dict = {
        "job_id": uuid.uuid4().hex,
        "tasks": [PayloadTask(**aws_task_dict)]
    }
    payload = Payload(**payload_dict)
    return payload


payload = generate_aws_payload(aws_json)
# print(payload.tasks[0].model_dump())
# print(payload.model_dump_json(indent=2))
