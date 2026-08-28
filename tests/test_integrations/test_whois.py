import pytest

from autobotAI_integrations.handlers.task_handler import handle_task
from autobotAI_integrations.integrations import integration_service_factory


class TestClassWhois:
    def test_whois_steampipe_task(
        self,
        get_keys,
        sample_integration_dict,
        sample_steampipe_task,
        test_result_format,
    ):
        tokens = {}
        integration = sample_integration_dict("whois", tokens)
        whois_query = "select * from whois_domain where domain = 'steampipe.io'"
        task = sample_steampipe_task(integration, query=whois_query)
        result = handle_task(task)
        test_result_format(result)

    def test_actions_generation(self):
        service = integration_service_factory.get_service_cls("whois")
        actions = service.get_all_rest_api_actions()
        assert len(actions) == 5
        action_names = [a.name for a in actions]
        assert "Lookup domain RDAP WHOIS record" in action_names
        assert "Lookup IP address RDAP WHOIS record" in action_names
        assert "Lookup Autonomous System Number ASN RDAP WHOIS record" in action_names
        assert "Lookup entity contact RDAP record" in action_names
        assert "Lookup nameserver RDAP record" in action_names


    def test_integration_active(self, get_keys, sample_integration_dict):
        tokens = {}
        integration = sample_integration_dict("whois", tokens)
        service = integration_service_factory.get_service(None, integration)
        res = service.is_active()
        assert res["success"]

