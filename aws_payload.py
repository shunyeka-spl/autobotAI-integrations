import uuid

import yaml

from autobotAI_integrations import ConnectionTypes
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.integrations.aws import AWSIntegration
from autobotAI_integrations.payload_schema import Payload, PayloadTask, PayloadTaskContext

code = """
import traceback

def execute(context):
    s3_client = context["clients"]['s3']
    aws_response = s3_client.list_buckets()

    return_list = []
    for bucket in aws_response['Buckets']:
        bucket_region = s3_client.get_bucket_location(Bucket=bucket['Name']).get('LocationConstraint', 'us-east-1')
        if not bucket_region:
            bucket_region = 'us-east-1'
        if bucket_region != s3_client.meta.region_name:
            continue
        item_object = {
            'id': bucket['Name'],
            'name': bucket['Name']
        }
        return_list.append(item_object)

    return return_list
"""


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


def generate_aws_steampipe_payload() -> Payload:
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
        "taskId": uuid.uuid4().hex,
        "creds": creds,
        "connection_type": ConnectionTypes.STEAMPIPE,
        "executable": "select * from aws_s3_bucket",
        "context": {},
        "executable": "select * from aws.s3_buckets",
        "context": PayloadTaskContext(integration=aws_integration),
    }
    payload_dict = {
        "job_id": uuid.uuid4().hex,
        "tasks": [PayloadTask(**aws_task_dict)]
    }
    payload = Payload(**payload_dict)
    return payload


def generate_aws_python_sdk_payload() -> Payload:
    aws_integration = AWSIntegration(**{
        "userId": "amit@shunyeka.com*",
        "accountId": "175c0fa813244bc5a1aa6264e7ba20cc*",
        "integrationState": "INACTIVE",
        "cspName": "aws",
        "access_key": "ASIAW74SAWUEJKES5QAJ",
        "secret_key": "6DAcFeLTS1ETwkFrMmv7GllCXnSx/X3iD7bxR4VD",
        "session_token": "IQoJb3JpZ2luX2VjEF8aCXVzLWVhc3QtMSJHMEUCIDYPU0Q8UHyUNv+1Ja4yEwk9fTiUa4i8g42h8IqS4RFbAiEAjPK4XOTjVDl3wxwVDtsYyi+wskF7wiHWXnoJPlZeIYgqgAMIeBAEGgw0ODA4MDU2OTY3NzYiDHTsJetOdQ5/3iv8TCrdAjYGhoJ2dckhlhYEbA/jd8vjLhvKASt4U61RmMSncpnZST6tYDngFBOKZnjzSpTySKIxQ+AU1OU0mul2ayu11HHJQjfyG+JgxmD7RC/VyVbiHaKbv376DMXWEOmY+GBJOtGDeK2THMfpq1AVcfE+h3mexmCizbtMzHxg0JWxJnV+67FtXXH6ot0IeIlrOurfxmTX1d0I90yuex2JPisTnMqZMjQLaXygNrHqVPibC1hayikMTYhab2RH9gYi53Z0nGj/0QBVta1N5H9ZsQnCGl44FNFOHB8j8ypXw4HBXgVNeUaTex3wwk07PF5+/lg1yKYLHqfjCVvRKfOszuKOd+16ECi2yIjLOCTHks1OoNW5EEIF97sI5EvJwjPprlnLS309W1rPPEzwH5TuyMWpOPtCFC+ZgeW8IrPAzMYRyTbpLBgau9qMjS4UgmbBKx2uVVPlFvg9YwlKfMG7F0AwoPWAsAY6pgEMlAhdQug1PjVRKGgo+NSFvhh5+PPnRuAqbZ/h6/w+f70FwSeO+diH3m+PI2yKVukdK9fxYq8GtD6dWiax82FXSz62W9sWanzmIfny7FUrZC5OImjcG/3r3dHzHjMoL9xLL9rjjzjW1wumDcWmIMgvE1KfRQDf+GspX9nvt6aanucpgt2fzi7pg4t8bHk+0ySACY6to7SKGs24J4aXjUtYFFEjZmWt",
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
        "activeRegions": ["ap-south-1", "us-east-1"],
    })
    aws_service = integration_service_factory.get_service(None, aws_integration)
    creds = aws_service.generate_steampipe_creds()
    aws_task_dict = {
        "taskId": uuid.uuid4().hex,
        "creds": creds,
        "connection_type": ConnectionTypes.PYTHON_SDK,
        "executable": code,
        "clients": ["s3"],
        "context": {
            "integration": aws_integration
        }
    }
    payload_dict = {
        "job_id": uuid.uuid4().hex,
        "tasks": [PayloadTask(**aws_task_dict, node_details={
            "filter_resources": True
        }, resources=[{
            "id": "1",
            "name": "amit"
        }])]
    }
    payload = Payload(**payload_dict)
    return payload


payload_output = generate_aws_python_sdk_payload()
# print(payload.tasks[0].model_dump())
# print(payload.model_dump_json(indent=2))
