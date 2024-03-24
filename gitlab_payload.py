import uuid

from autobotAI_integrations import ConnectionTypes
from autobotAI_integrations.integrations.gitlab import GitlabIntegration
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.payload_schema import Payload, PayloadTask


gitlab_json = {
    "userId": "amit@shunyeka.com*",
    "accountId": "175c0fa813244bc5a1aa6264e7ba20cc*",
    "integrationState": "INACTIVE",
    "cspName": "gitlab*",
    "alias": "test-gitlab-integrationsv2*",
    "connection_type": "DIRECT",
    "token": "xyz",
    "base_url": "xyz",
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
    gitlab_integration = GitlabIntegration(**gitlab_json)
    gitlab_service = integration_service_factory.get_service('gitlab', None, gitlab_integration)
    creds = gitlab_service.generate_steampipe_creds()
    gitlab_task_dict = {
        "taskId": uuid.uuid4().hex,
        "creds": creds,
        "connection_type": ConnectionTypes.STEAMPIPE,
        "executable": "select * from git_branch",
        "context": {},
        "interation_specific_details": {}
    }
    payload_dict = {
        "job_id": uuid.uuid4().hex,
        "tasks": [PayloadTask(**gitlab_task_dict)]
    }
    payload = Payload(**payload_dict)
    return payload

payload = generate_gitlab_payload()

print(payload.model_dump_json(indent=2))
