import uuid

from autobotAI_integrations import ConnectionTypes
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.integrations.aws import AWSIntegration
from autobotAI_integrations.payload_schema import Payload, PayloadTask, PayloadTaskContext

code = """
import traceback

def fetch(clients, test=False):
    s3_client = clients['s3']
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
        "access_key": "ASIAW74SAWUEOHOU35ST",
        "secret_key": "iWiBSg6GY9AL1WW0GMWV+qFU+yBHNiBXQrpDP6UT",
        "session_token": "IQoJb3JpZ2luX2VjEFcaCXVzLWVhc3QtMSJHMEUCIGHM/XjP7SqgvL+nEFzAipk4AppxAO/KbXVo276Fpp5NAiEA+93lJhIXm3t4nrslrsXiNvTHJc6Pq6oBNuP/uuFYqVYqgAMIbxAEGgw0ODA4MDU2OTY3NzYiDL10Oqaj5ZKodJf//yrdAgqGB+c1QttBDrZTMSRzQQXPtrSiY1qp8RaDLHxW2fTueVNiIihKMgeKzFYaK7rnbf8iD9JJhso5Gi4+m58qR8onHAoUmckXQMIYCilocrTaYusQ/EhepX4H3cewbNUgceymXbKsD+Bbwb6sAGSRTwBpCdIoBryJgjh/wgQslZgNzNdZwlO4A1WXIO/yHYGiEVG90lpjE2dAUuewgwn3lgXzRS2r4EVeww4LijuEYs9Hzo5jYvwe8/THO8ALowKoSg7evKFxAIpBEbsjTCkh1kDUtNj72NjcEIBaSu7RHODJ9JexkoB/rmAktie1g+gh52GkUn5eh2RTiPUDPqKs2S4IqzZOSgbwrcP8PT2HV/OcJV961nabwDbm07+gqFg0uMZtiyJN81Jg/nJacDkuwpcpZTmKmDFvBlEK5Rgldt2D412hXVBEmnesIPMtLNliuG9WiTxIAp2+CaLwpwYw9Ir/rwY6pgHP8uFLwwwo+MfZpIKKzd3BbPdJI2ou0lrtQYBbEe2V+sJoTR8aXj3l0fv3+6+ckQWJVd/eV/CQiV2erYzBCJEGMoIcl8JVX4YaxnrYvKW21Qxw+6o7sIdjNxu9O/FwqbAGisbNitm3M9XUUzYoR0/+YZ8bw6fLkYuz6yeEmECt7M2ZK3l5gvK6aGThJct6Z6Yg57yeinFYGRnYSmnF3xnW72DqmNPy",
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
        "tasks": [PayloadTask(**aws_task_dict)]
    }
    payload = Payload(**payload_dict)
    return payload


payload = generate_aws_python_sdk_payload()
# print(payload.tasks[0].model_dump())
# print(payload.model_dump_json(indent=2))
