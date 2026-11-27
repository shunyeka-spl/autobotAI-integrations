import pytest
from autobotAI_integrations.integrations.proofpoint_itm import ProofpointITMIntegration, ProofpointITMService

def test_proofpoint_itm_schema_validation():
    # Valid data
    data = {
        "base_url": "https://tenant.itmsaas.proofpoint.com",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "alias": "proofpoint_itm_alias",
        "userId": "test_user",
        "cspName": "aws"
    }
    integration = ProofpointITMIntegration(**data)
    assert integration.base_url == "https://tenant.itmsaas.proofpoint.com"
    assert integration.client_id == "test_client_id"
    assert integration.client_secret == "test_client_secret"
    assert integration.alias == "proofpoint_itm_alias"
    assert integration.name == "Endpoint DLP"
    assert integration.category == "security_tools"

def test_proofpoint_itm_service_metadata():
    forms = ProofpointITMService.get_forms()
    assert "children" in forms
    # verify the fields are generated
    field_names = [f["name"] for f in forms["children"]]
    assert "base_url" in field_names
    assert "client_id" in field_names
    assert "client_secret" in field_names

    interfaces = ProofpointITMService.supported_connection_interfaces()
    assert "REST_API" in [i.name for i in interfaces]
    assert "PYTHON_SDK" in [i.name for i in interfaces]


def test_proofpoint_itm_python_sdk_task(
    sample_integration_dict, sample_python_task, test_result_format
):
    from autobotAI_integrations.handlers.task_handler import handle_task

    integration = sample_integration_dict(
        "proofpoint_itm",
        {
            "base_url": "https://persistentindia.explore.proofpoint.com",
            "client_id": "pp-client-id",
            "client_secret": "pp-client-secret",
        },
    )
    service = ProofpointITMService(None, integration)
    creds = service.generate_python_sdk_creds()
    assert creds.envs["PROOFPOINT_ITM_CLIENT_ID"] == "pp-client-id"
    assert creds.envs["PROOFPOINT_ITM_CLIENT_SECRET"] == "pp-client-secret"

    details = ProofpointITMService.get_details()
    assert any(c["name"] == "proofpoint_itm" for c in details["clients"])

    code = """
def executor(context):
    client = context["clients"]["proofpoint_itm"]
    return {
        "base_url": client.base_url,
        "client_id": client.client_id,
        "client_secret": client.client_secret,
    }
"""
    task = sample_python_task(integration, code=code, clients=["proofpoint_itm"])
    result = handle_task(task)
    test_result_format(result)
    assert result.resources[0]["client_id"] == "pp-client-id"
    assert result.resources[0]["client_secret"] == "pp-client-secret"
