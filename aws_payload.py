import json
import uuid
from typing import List, Optional, Any

from pydantic import BaseModel

from autobotAI_integrations import BaseSchema, BaseCreds, ConnectionTypes
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.integrations.aws import AWSIntegration


class PayloadTask(BaseModel):
    creds: BaseCreds
    connection_type: str
    executable: str
    params: Optional[Any] = None
    context: Optional[dict] = None


class Payload(BaseModel):
    job_id: str
    tasks: List[PayloadTask]


def generate_aws_payload() -> Payload:
    connection_type = "steampipe"
    aws_integration = AWSIntegration(**{
        "userId": "amit@shunyeka.com*",
        "accountId": "175c0fa813244bc5a1aa6264e7ba20cc*",
        "integrationState": "INACTIVE",
        "cspName": "aws*",
        "acccess_key": "ahudfuusdfj",
        "secret_key": "ahudfuusdfj",
        "session_token": "abkfhlksf",
        "session_token": "abc",
        "alias": "test-gitlab-integrationsv2*",
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
        "activeRegions": [],
    })
    aws_service = integration_service_factory.get_service("aws", None, aws_integration)
    creds = aws_service.generate_steampipe_creds()
    aws_task_dict = {
        "creds": creds,
        "connection_type": ConnectionTypes.STEAMPIPE,
        "executable": "select * from aws.s3_buckets",
        "context": {}
    }
    payload_dict = {
        "job_id": uuid.uuid4().hex,
        "tasks": [PayloadTask(**aws_task_dict)]
    }
    payload = Payload(**payload_dict)
    return payload


payload = generate_aws_payload()
print(payload.tasks[0].model_dump())
print(payload.model_dump())
