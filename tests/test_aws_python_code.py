import unittest
import dotenv
import os
from autobotAI_integrations import IntegrationSchema
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations import ConnectionInterfaces
from autobotAI_integrations.integrations.aws import AWSIntegration
from autobotAI_integrations.payload_schema import (
    Payload,
    PayloadTask,
    PayloadTaskContext,
    Param,
)
import uuid

dotenv.load_dotenv()

class TestAWSPythonCode(unittest.TestCase):
    def setUp(self):
        self.integration = {
            "userId": "amit@shunyeka.com*",
            "accountId": "175c0fa813244bc5a1aa6264e7ba20cc",
            "integrationState": "INACTIVE",
            "cspName": "aws",
            "access_key": os.environ.get("AWS_ACCESS_KEY_ID"),
            "secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
            "session_token": os.environ.get("AWS_SESSION_TOKEN"),
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
            "activeRegions": ["us-east-1", "ap-south-1"],
        }
        self.context = {
            "execution_details": {
                "execution_id": "660275c610755f71b634e572",
                "bot_id": "660274d5fa724e7537a4c0c5",
                "bot_name": "AWS Integrations-V2 Test",
                "node_name": "Python-Code-Executor",
                "caller": {"user_id": "amit@shunyeka.com", "root_user_id": "amit@shunyeka.com"},
            },
            "node_steps": {},
            "global_variables": {"default_aws_region": "us-east-1"},
        }
        self.aws_integration = AWSIntegration(**self.integration)
        self.aws_service = integration_service_factory.get_service(None, self.aws_integration)
        self.creds = self.aws_service.generate_python_sdk_creds()
    
    def run_payload_task(self, task):
        integration = IntegrationSchema.model_validate(task.context.integration)
        service = integration_service_factory.get_service(None, integration)
        return service.python_sdk_processor(payload_task=task)

    def test_single_python_code_task(self):
        code = """def executor(context):\n    return [{"success": "True"}]"""
        aws_python_task = {
            "task_id": uuid.uuid4().hex,
            "creds": self.creds,
            "connection_interface": ConnectionInterfaces.PYTHON_SDK,
            "executable": code,
            "clients": ["s3"],
            "node_details": {"filter_resources": False},
            "context": PayloadTaskContext(**self.context, **{"integration": self.integration}),
        }
        payload_dict = {
            "job_id": uuid.uuid4().hex,
            "tasks": [PayloadTask(**aws_python_task)],
        }
        payload = Payload(**payload_dict)
        output = self.run_payload_task(payload.tasks[0])
        self.assertTrue(output[0][0]["success"])
    
    def test_get_security_groups(self):
        code = """
def executor(context):
    ec2_client = context['clients']['ec2']
    groups = ec2_client.describe_security_groups()
    all_groups = groups['SecurityGroups']
    results = []
    for group in all_groups:
        group = {
            "name": group.get('GroupName', 'N/A'),
            "GroupId": group.get('GroupId', 'N/A'),
        }
        results.append(group)
    return [{"security_groups": results}]
"""
        aws_python_task = {
            "task_id": uuid.uuid4().hex,
            "creds": self.creds,
            "connection_interface": ConnectionInterfaces.PYTHON_SDK,
            "executable": code,
            "clients": ["ec2"],
            "node_details": {"filter_resources": False},
            "context": PayloadTaskContext(**self.context, **{"integration": self.integration}),
        }
        payload_dict = {
            "job_id": uuid.uuid4().hex,
            "tasks": [PayloadTask(**aws_python_task)],
        }
        payload = Payload(**payload_dict)
        # output = self.run_payload_task(payload.tasks[0])
        # self.assertEqual(type(output[0][0]["security_groups"]), list)
    
    def test_remove_security_group(self):
        code = """
def executor(context):
    ec2_client = context['clients']['ec2']
    
    params = context["params"]
    res = []
    for security_group in params['security_group']:
        try:
            response = ec2_client.delete_security_group(
                GroupId=security_group.get("id"),
                GroupName=security_group.get("name"),
            )
            res.append(response)
        except BaseException as e:
            res.append(e)
    return [{"results": res}]
"""
        test_security_groups = [
            {
                "id": "security_group_id",
                "name": "test_security_group",
                "region": "us-east-1",
                "integration_id": "",
                "integration_type": ""
            },
            {
                "id": "security_group_id",
                "name": "test_security_group",
                "region": "ap-south-1",
                "integration_id": "",
                "integration_type": ""
            },
            {
                "id": "security_group_id",
                "name": "test_group_2_do_not_use_it",
                "region": "ap-south-1",
                "integration_id": "",
                "integration_type": ""
            }
        ]
        param = {
            "type": "security_group",
            "name": "security_group",
            "values": test_security_groups,
            "filter_relevant_resources": True
        }
        aws_python_task = {
            "task_id": uuid.uuid4().hex,
            "creds": self.creds,
            "connection_interface": ConnectionInterfaces.PYTHON_SDK,
            "executable": code,
            "clients": ["ec2"],
            "params": [Param(**param)],
            "node_details": {"filter_resources": False},
            "context": PayloadTaskContext(**self.context, **{"integration": self.integration}),
        }
        payload_dict = {
            "job_id": uuid.uuid4().hex,
            "tasks": [PayloadTask(**aws_python_task)],
        }
        payload = Payload(**payload_dict)
        output = self.run_payload_task(payload.tasks[0])
        print(output)


if __name__ == "__main__":
    unittest.main()