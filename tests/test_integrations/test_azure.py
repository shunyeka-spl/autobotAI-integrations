from autobotAI_integrations.handlers.task_handler import handle_task
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.integrations.azure import AzureIntegration, AzureService

azure_python_code = """
def executor(context):
    client = context["clients"]["ResourceManagementClient"]
    results = []
    for group in client.resource_groups.list():
        results.append(
            {
                "id": group.id,
                "name": group.name,
                "location": group.location,
            }
        )
    if not results:
        results.append({"subscription_id": client.subscription_id})
    return results
"""


def _tokens(get_keys, include_subscription=True):
    tokens = {
        "tenant_id": get_keys["AZURE_TENANT_ID"],
        "client_id": get_keys["AZURE_CLIENT_ID"],
        "client_secret": get_keys["AZURE_CLIENT_SECRET"],
    }
    if include_subscription and get_keys.get("AZURE_SUBSCRIPTION_ID"):
        tokens["subscription_id"] = get_keys["AZURE_SUBSCRIPTION_ID"]
    return tokens


class TestClassAzure:
    def test_azure_steampipe_task(
        self,
        get_keys,
        sample_integration_dict,
        sample_steampipe_task,
        test_result_format,
    ):
        integration = sample_integration_dict("azure", _tokens(get_keys))
        task = sample_steampipe_task(
            integration,
            query="select subscription_id, display_name, state from azure_subscription",
        )
        result = handle_task(task)
        test_result_format(result)

    def test_azure_python_task(
        self, get_keys, sample_integration_dict, sample_python_task, test_result_format
    ):
        integration = sample_integration_dict("azure", _tokens(get_keys))
        task = sample_python_task(
            integration,
            code=azure_python_code,
            clients=["ResourceManagementClient"],
        )
        result = handle_task(task)
        dumped = result.model_dump() if not isinstance(result, dict) else result
        if dumped.get("errors"):
            raise AssertionError(dumped["errors"][0].get("message", dumped["errors"]))
        test_result_format(result)

    def test_integration_active(self, get_keys, sample_integration_dict):
        integration = sample_integration_dict("azure", _tokens(get_keys))
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert res["success"], res.get("error")

        bad_tokens = _tokens(get_keys)
        bad_tokens["client_secret"] = bad_tokens["client_secret"][:-2]
        bad_integration = sample_integration_dict("azure", bad_tokens)
        bad_service = integration_service_factory.get_service(None, bad_integration)
        res = bad_service.is_active()
        assert not res["success"]

    def test_subscription_id_optional(self):
        integration = AzureIntegration(
            userId="test-user",
            cspName="azure",
            alias="test-azure",
            tenant_id="tenant",
            client_id="client",
            client_secret="secret",
        )
        assert integration.subscription_id is None
        service = AzureService(None, integration)
        creds = service._temp_credentials()
        assert "AZURE_SUBSCRIPTION_ID" not in creds
        assert creds["AZURE_TENANT_ID"] == "tenant"

        with_subscription = AzureIntegration(
            userId="test-user",
            cspName="azure",
            alias="test-azure",
            tenant_id="tenant",
            client_id="client",
            client_secret="secret",
            subscription_id="sub-123",
        )
        assert with_subscription.accountId == "sub-123"
        creds = AzureService(None, with_subscription)._temp_credentials()
        assert creds["AZURE_SUBSCRIPTION_ID"] == "sub-123"

    def test_get_forms_subscription_optional(self):
        forms = AzureService.get_forms()
        subscription_field = next(
            field for field in forms["children"] if field["name"] == "subscription_id"
        )
        assert subscription_field["required"] is False
