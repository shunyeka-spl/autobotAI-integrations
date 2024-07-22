import pytest

from autobotAI_integrations.handlers.task_handler import handle_task
from autobotAI_integrations.integrations import integration_service_factory


class TestClassPaloAlto:
    def test_palo_alto_steampipe_task(
        self,
        get_keys,
        sample_integration_dict,
        sample_steampipe_task,
        test_result_format,
    ):
        tokens = {
            "username": get_keys["PANOS_USERNAME"],
            "password": get_keys["PANOS_PASSWORD"],
            "host_url": get_keys["PANOS_HOSTNAME"]
        }
        integration = sample_integration_dict("paloalto", tokens)
        palo_alto_query = "select * from palo_alto_account"  
        task = sample_steampipe_task(integration, query=palo_alto_query)
        result = handle_task(task)
        test_result_format(result)

    def test_integration_active(self, get_keys, sample_integration_dict):
        tokens = {
            "username": get_keys["PANOS_USERNAME"],
            "password": get_keys["PANOS_PASSWORD"],
            "host_url": get_keys["PANOS_HOSTNAME"],
        }
        integration = sample_integration_dict("paloalto", tokens)
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert res["success"]

        # Test with invalid API key
        tokens["api_key"] = get_keys["PANOS_API_KEY"][0:-3]  
        integration = sample_integration_dict("paloalto", tokens)
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert not res["success"]