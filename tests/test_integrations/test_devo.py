from unittest import mock

import pytest

from autobotAI_integrations import ConnectionInterfaces
from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.integrations.devo import DevoIntegration, DevoService


def _integration(**overrides):
    return DevoIntegration(
        **{
            "userId": "user123",
            "accountId": "acc123",
            "alias": "My Devo",
            "cspName": "devo",
            "token": "tok-123",
            **overrides,
        }
    )


class DummyPayloadTask:
    def __init__(self, executable, envs=None):
        self.executable = executable
        self.creds = mock.Mock(envs=envs)


def test_devo_registered_with_rest_api_only():
    service_cls = integration_service_factory.get_service_cls("devo")
    assert service_cls is DevoService
    assert service_cls.supported_connection_interfaces() == [
        ConnectionInterfaces.REST_API
    ]


def test_devo_token_excluded_from_serialization():
    assert "token" not in _integration().model_dump()


@pytest.mark.parametrize(
    "region,query_url,alerts_url",
    [
        ("us", "https://apiv2-us.devo.com", "https://api-us.devo.com"),
        ("eu", "https://apiv2-eu.devo.com", "https://api-eu.devo.com"),
        ("apac", "https://api-apac.devo.com", "https://api-apac.devo.com"),
    ],
)
def test_devo_rest_creds_follow_region(region, query_url, alerts_url):
    creds = DevoService({}, _integration(region=region)).generate_rest_api_creds()
    assert creds.base_url == query_url
    assert creds.envs == {"DEVO_ALERTS_API_URL": alerts_url}
    assert creds.headers["Authorization"] == "Bearer tok-123"
    assert creds.headers["standAloneToken"] == "tok-123"


def test_devo_custom_urls_strip_documented_suffixes():
    service = DevoService(
        {},
        _integration(
            query_api_url="https://apiv2-custom.devo.com/search/query/",
            alerts_api_url="https://api-custom.devo.com/alerts/v1",
        ),
    )
    creds = service.generate_rest_api_creds()
    assert creds.base_url == "https://apiv2-custom.devo.com"
    assert creds.envs["DEVO_ALERTS_API_URL"] == "https://api-custom.devo.com"


def test_devo_open_api_actions_parse():
    actions = DevoService.get_all_rest_api_actions()
    by_name = {a.name: a for a in actions}
    assert by_name["Run Query"].code == "{base_url}/search/query"
    assert (
        by_name["List Alert Definitions"].code
        == "https://{devo_alerts_host}/alerts/v1/alertDefinitions"
    )


def test_devo_alerts_paths_rewritten_to_alerts_host():
    service = DevoService({}, _integration(region="eu"))
    task = DummyPayloadTask(
        "https://{devo_alerts_host}/alerts/v1/alertDefinitions",
        envs={"DEVO_ALERTS_API_URL": "https://api-eu.devo.com"},
    )
    with mock.patch(
        "autobotAI_integrations.BaseService.execute_rest_api_task",
        return_value=([], []),
    ) as parent:
        service.execute_rest_api_task(task)
    parent.assert_called_once()
    assert task.executable == "https://api-eu.devo.com/alerts/v1/alertDefinitions"


def test_devo_query_paths_untouched():
    service = DevoService({}, _integration())
    task = DummyPayloadTask("{base_url}/search/query", envs={})
    with mock.patch(
        "autobotAI_integrations.BaseService.execute_rest_api_task",
        return_value=([], []),
    ):
        service.execute_rest_api_task(task)
    assert task.executable == "{base_url}/search/query"


def test_devo_test_integration_maps_auth_failure():
    service = DevoService({}, _integration())
    with mock.patch(
        "autobotAI_integrations.integrations.devo.requests.post",
        return_value=mock.Mock(status_code=401, text="unauthorized"),
    ) as post:
        result = service._test_integration()
    assert result["success"] is False
    assert "Authentication failed" in result["error"]
    assert post.call_args.args[0] == "https://apiv2-us.devo.com/search/query"


def test_devo_test_integration_success():
    service = DevoService({}, _integration())
    with mock.patch(
        "autobotAI_integrations.integrations.devo.requests.post",
        return_value=mock.Mock(status_code=200),
    ):
        assert service._test_integration() == {"success": True}
