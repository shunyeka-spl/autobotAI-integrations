import pytest

from autobotAI_integrations.handlers.task_handler import handle_task
from autobotAI_integrations.integrations import integration_service_factory

azure_entra_id_python_code = """
# Import your modules here
import json
import asyncio

# **Security Note:** Client-related modules should not be directly imported here.
# Instead, they are passed as arguments and retrieved from a secure configuration.


def executor(context):
    async def me(client):
        res = []
        users = await client.users.get()
        if users and users.value:
            for user in users.value:
                res.append({
                    "id": user.id,
                    "displayName": user.display_name,
                    "userPrincipalName": user.user_principal_name
                })
        return res
    clients = context["clients"]
    client = clients["msgraph"]
    return asyncio.run(me(client))
"""


class TestClassAzure_entra_id:
    def test_azure_entra_id_steampipe_task(
        self,
        get_keys,
        sample_integration_dict,
        sample_steampipe_task,
        test_result_format,
    ):
        tokens = {
            "tenant_id": get_keys["AZURE_TENANT_ID"],
            "client_id": get_keys["AZURE_CLIENT_ID"],
            "client_secret": get_keys["AZURE_CLIENT_SECRET"]
        }
        integration = sample_integration_dict("azure_entra_id", tokens)
        azure_entra_id_query = "select * from azuread_user"
        task = sample_steampipe_task(integration, query=azure_entra_id_query)
        result = handle_task(task)
        test_result_format(result)
        print(result.model_dump_json(indent=2))

    def test_azure_entra_id_python_task(
        self, get_keys, sample_integration_dict, sample_python_task, test_result_format
    ):
        tokens = {
            "tenant_id": get_keys["AZURE_TENANT_ID"],
            "client_id": get_keys["AZURE_CLIENT_ID"],
            "client_secret": get_keys["AZURE_CLIENT_SECRET"],
        }
        integration = sample_integration_dict("azure_entra_id", tokens)
        task = sample_python_task(
            integration, code=azure_entra_id_python_code, clients=["msgraph"]
        )
        result = handle_task(task)
        test_result_format(result)
        print(result.model_dump_json(indent=2))

    def test_integration_active(self, get_keys, sample_integration_dict):
        tokens = {
            "tenant_id": get_keys["AZURE_TENANT_ID"],
            "client_id": get_keys["AZURE_CLIENT_ID"],
            "client_secret": get_keys["AZURE_CLIENT_SECRET"],
        }
        integration = sample_integration_dict("azure_entra_id", tokens)
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        print(res)
        assert res["success"]
        tokens = {
            "tenant_id": get_keys["AZURE_TENANT_ID"],
            "client_id": get_keys["AZURE_CLIENT_ID"],
            # Invalid secret
            "client_secret": get_keys["AZURE_CLIENT_SECRET"][:-2],
        }
        integration = sample_integration_dict("azure_entra_id", tokens)
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert not res["success"]
