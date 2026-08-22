import traceback

import pytest
from pydantic import ValidationError

from autobotAI_integrations.handlers.task_handler import handle_task
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.integrations.azure_devops import (
    AzureDevOpsIntegration,
    AzureDevOpsService,
)

azure_devops_python_code = """
def executor(context):
    connection = context["clients"]["azure_devops"]
    core_client = connection.clients.get_core_client()

    results = []
    projects = core_client.get_projects(top=10)
    if projects:
        for project in projects:
            results.append({
                "project_id": project.id,
                "project_name": project.name,
                "state": str(project.state) if project.state else None,
                "visibility": str(project.visibility) if project.visibility else None,
            })

    return results
"""


# ---------------------------------------------------------------------------
# Schema / unit tests (no live credentials needed)
# ---------------------------------------------------------------------------

def test_azure_devops_pat_required():
    """Verify personal_access_token is required for AzureDevOpsIntegration."""
    with pytest.raises(ValidationError):
        AzureDevOpsIntegration(userId="test-user", organization="myorg")

    with pytest.raises(ValidationError):
        AzureDevOpsIntegration(userId="test-user", organization="myorg", personal_access_token="")

    integration = AzureDevOpsIntegration(
        userId="test-user",
        organization="myorg",
        personal_access_token="test_pat_token_12345",
    )
    assert integration.personal_access_token == "test_pat_token_12345"


def test_azure_devops_get_forms_pat_required():
    """Verify get_forms marks personal_access_token as required."""
    forms = AzureDevOpsService.get_forms()
    pat_field = next(
        f for f in forms["children"] if f["name"] == "personal_access_token"
    )
    assert pat_field["required"] is True


# ---------------------------------------------------------------------------
# Live integration tests (require .env with AZURE_DEVOPS_PAT + AZURE_DEVOPS_ORG)
# ---------------------------------------------------------------------------

class TestClassAzureDevOps:
    def test_azure_devops_python_task(
        self, get_keys, sample_integration_dict, sample_python_task, test_result_format
    ):
        tokens = {
            "personal_access_token": get_keys["AZURE_DEVOPS_PAT"],
            "organization": get_keys["AZURE_DEVOPS_ORG"],
        }
        integration = sample_integration_dict("azure_devops", tokens)
        task = sample_python_task(
            integration, code=azure_devops_python_code, clients=["azure_devops"]
        )
        result = handle_task(task)
        test_result_format(result)

    def test_integration_active(self, get_keys, sample_integration_dict):
        tokens = {
            "personal_access_token": get_keys["AZURE_DEVOPS_PAT"],
            "organization": get_keys["AZURE_DEVOPS_ORG"],
        }
        integration = sample_integration_dict("azure_devops", tokens)
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert res["success"]

        # Invalid PAT should fail
        tokens_bad = {
            "personal_access_token": get_keys["AZURE_DEVOPS_PAT"][:-2] + "xx",
            "organization": get_keys["AZURE_DEVOPS_ORG"],
        }
        integration_bad = sample_integration_dict("azure_devops", tokens_bad)
        service_bad = integration_service_factory.get_service(None, integration_bad)
        res_bad = service_bad.is_active()
        assert not res_bad["success"]

    def test_actions_generation(self, get_keys):
        service = integration_service_factory.get_service_cls("azure_devops")
        actions = service.get_all_rest_api_actions()
        for action in actions:
            assert action.name is not None
            assert action.name.strip() != ""
            print(action.model_dump_json(indent=2))
        assert len(actions) > 0

    # "List Projects"
    def test_actions_run(
        self, get_keys, sample_restapi_task, test_result_format, sample_integration_dict
    ):
        tokens = {
            "personal_access_token": get_keys["AZURE_DEVOPS_PAT"],
            "organization": get_keys["AZURE_DEVOPS_ORG"],
        }
        integration = sample_integration_dict("azure_devops", tokens)
        service = integration_service_factory.get_service(None, integration)
        actions = service.get_all_rest_api_actions()
        for action in actions:
            if action.name == "List Projects":
                try:
                    task = sample_restapi_task(
                        integration, action.code, action.parameters_definition
                    )
                    result = handle_task(task)
                    print(result.model_dump_json(indent=2))
                    test_result_format(result)
                except Exception as e:
                    traceback.print_exc()
                    assert False, f"List Projects action failed: {e}"
                break
