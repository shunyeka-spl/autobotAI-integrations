import os
import uuid

from autobotAI_integrations import ConnectionTypes
from autobotAI_integrations.integrations.gitlab import GitlabIntegration
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.payload_schema import Payload, PayloadTask

code = """
import traceback

def execute(context):
    print("in execute")
    gl = context["clients"]['gitlab']    
    gl.auth()
    current_user = gl.user
    print(current_user)
    group = gl.groups.get(84577768)    
    pj = []
    for project in group.projects.list(iterator=True):
        print(project)
        pj.append(project.asdict())

    return pj
"""

gitlab_json = {
    "userId": "amit@shunyeka.com*",
    "accountId": "175c0fa813244bc5a1aa6264e7ba20cc*",
    "integrationState": "INACTIVE",
    "cspName": "gitlab",
    "alias": "test-gitlab-integrationsv2*",
    "connection_type": "DIRECT",
    "token": os.environ["GITLAB_TOKEN"],
    "base_url": "https://gitlab.com/",
    "groups": ["gitlab", "shunyeka", "integrations-v2"],
    "agent_ids": [],
    "accessToken": "",
    "createdAt": "2024-02-26T13:38:59.978056",
    "updatedAt": "2024-02-26T13:38:59.978056",
    "indexFailures": 0,
    "isUnauthorized": False,
    "lastUsed": None,
    "resource_type": "integration",
    "activeRegions": [],
}

def generate_gitlab_payload() -> Payload:
    integration = GitlabIntegration(**gitlab_json)
    service = integration_service_factory.get_service(None, integration)
    creds = service.generate_python_sdk_creds()
    task_dict = {
        "taskId": uuid.uuid4().hex,
        "creds": creds,
        "connection_type": ConnectionTypes.PYTHON_SDK,
        "executable": code,
        "clients": ["gitlab"],
        "context": {
            "integration": integration
        }
    }
    payload_dict = {
        "job_id": uuid.uuid4().hex,
        "tasks": [PayloadTask(**task_dict, node_details={
            "filter_resources": True
        }, resources=[{
            "id": "1",
            "name": "amit"
        }])]
    }
    payload = Payload(**payload_dict)
    return payload
