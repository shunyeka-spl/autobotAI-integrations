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
        self.creds = mock.Mock(envs=envs, headers={"Authorization": "Bearer tok-123"})


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
        ("us3", "https://api-us3.devo.com", "https://api-us3.devo.com"),
    ],
)
def test_devo_rest_creds_follow_region(region, query_url, alerts_url):
    creds = DevoService({}, _integration(region=region)).generate_rest_api_creds()
    assert creds.base_url == query_url
    assert creds.envs == {"DEVO_ALERTS_API_URL": alerts_url}
    # Query API token only; the Alerts API token is swapped in per call.
    assert creds.headers == {"Authorization": "Bearer tok-123"}


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


def test_devo_alerts_token_goes_into_envs_only_when_set():
    assert "DEVO_ALERTS_TOKEN" not in DevoService({}, _integration()).generate_rest_api_creds().envs
    creds = DevoService({}, _integration(alerts_token="alert-tok")).generate_rest_api_creds()
    assert creds.envs["DEVO_ALERTS_TOKEN"] == "alert-tok"


def test_devo_alerts_paths_use_alerts_host_and_standalone_token():
    service = DevoService({}, _integration(region="eu"))
    task = DummyPayloadTask(
        "https://{devo_alerts_host}/alerts/v1/alertDefinitions",
        envs={"DEVO_ALERTS_API_URL": "https://api-eu.devo.com", "DEVO_ALERTS_TOKEN": "alert-tok"},
    )
    with mock.patch(
        "autobotAI_integrations.BaseService.execute_rest_api_task",
        return_value=([], []),
    ) as parent:
        service.execute_rest_api_task(task)
    parent.assert_called_once()
    assert task.executable == "https://api-eu.devo.com/alerts/v1/alertDefinitions"
    assert task.creds.headers == {"standAloneToken": "alert-tok"}


def test_devo_alerts_paths_without_alerts_token_fail_clearly():
    service = DevoService({}, _integration())
    task = DummyPayloadTask(
        "https://{devo_alerts_host}/alerts/v1/alerts/list",
        envs={"DEVO_ALERTS_API_URL": "https://api-us.devo.com"},
    )
    with mock.patch("autobotAI_integrations.BaseService.execute_rest_api_task") as parent:
        results, errors = service.execute_rest_api_task(task)
    parent.assert_not_called()
    assert results == [] and "Alert API" in errors[0]["message"]


def test_devo_query_paths_untouched():
    service = DevoService({}, _integration())
    task = DummyPayloadTask("{base_url}/search/query", envs={})
    with mock.patch(
        "autobotAI_integrations.BaseService.execute_rest_api_task",
        return_value=([], []),
    ):
        service.execute_rest_api_task(task)
    assert task.executable == "{base_url}/search/query"
    assert task.creds.headers == {"Authorization": "Bearer tok-123"}


def _resp(status_code, body=None, text=""):
    return mock.Mock(status_code=status_code, json=mock.Mock(return_value=body), text=text)


def test_devo_test_integration_maps_auth_failure():
    service = DevoService({}, _integration())
    with mock.patch(
        "autobotAI_integrations.integrations.devo.requests.get",
        return_value=_resp(401, text="unauthorized"),
    ) as get:
        result = service._test_integration()
    assert result["success"] is False
    assert "Query API token rejected" in result["error"]
    assert get.call_args.args[0] == (
        "https://apiv2-us.devo.com/search/table/siem.logtrust.web.activity"
    )


def test_devo_test_integration_out_of_scope_table_hint():
    service = DevoService({}, _integration(test_table="my.app.table"))
    with mock.patch(
        "autobotAI_integrations.integrations.devo.requests.get",
        return_value=_resp(403, {"status": 403, "msg": "Access not allowed"}),
    ):
        result = service._test_integration()
    assert "my.app.table" in result["error"] and "Test Table" in result["error"]


def test_devo_test_integration_body_status_error():
    service = DevoService({}, _integration())
    with mock.patch(
        "autobotAI_integrations.integrations.devo.requests.get",
        return_value=_resp(200, {"status": 500, "error": "boom"}),
    ):
        result = service._test_integration()
    assert result["success"] is False and "boom" in result["error"]


def test_devo_test_integration_success_checks_alerts_token_when_set():
    service = DevoService({}, _integration(alerts_token="alert-tok"))
    with mock.patch(
        "autobotAI_integrations.integrations.devo.requests.get",
        side_effect=[_resp(200, {"status": 0, "object": []}), _resp(200, [])],
    ) as get:
        assert service._test_integration() == {"success": True}
    alerts_call = get.call_args_list[1]
    assert alerts_call.args[0] == "https://api-us.devo.com/alerts/v1/alertDefinitions"
    assert alerts_call.kwargs["headers"]["standAloneToken"] == "alert-tok"
    assert "Authorization" not in alerts_call.kwargs["headers"]


def test_devo_test_integration_skips_alerts_without_token():
    service = DevoService({}, _integration())
    with mock.patch(
        "autobotAI_integrations.integrations.devo.requests.get",
        return_value=_resp(200, {"status": 0, "object": []}),
    ) as get:
        assert service._test_integration() == {"success": True}
    assert get.call_count == 1


def test_devo_skip_test_makes_no_requests():
    service = DevoService({}, _integration(skip_test=True))
    with mock.patch("autobotAI_integrations.integrations.devo.requests.get") as get:
        assert service._test_integration() == {"success": True}
    get.assert_not_called()
