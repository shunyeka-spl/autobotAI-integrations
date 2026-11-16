"""Offline tests for the Cymulate integration. Dummy credentials only."""

import json
from pathlib import Path

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from autobotAI_integrations.integrations import integration_service_factory
from autobotAI_integrations.integrations.cymulate import (
    CYMULATE_API_URLS,
    CymulateIntegration,
    CymulateService,
    ENVIRONMENTS_PATH,
    TOKEN_PATH,
)
from autobotAI_integrations.models import ConnectionInterfaces, SDKClient

DUMMY_API_TOKEN = "dummy-cymulate-token"
DUMMY_CLIENT_ID = "a" * 24
DUMMY_CLIENT_SECRET = "dummy-client-secret"
DUMMY_ACCESS_TOKEN = "dummy-access-token"
US_API = "https://api.us-app.cymulate.com"
EU_API = "https://api.app.cymulate.com"
MCP_URL = "https://mcp.cymulate.example/mcp"

EXPECTED_OPERATION_IDS = {
    "listEnvironments",
    "getAllAssessmentStatuses",
    "listConnectedIntegrations",
    "listConnectedAgents",
    "listAllAgents",
    "searchFindings",
    "getFindingsFilters",
    "getFindingInfo",
    "getFindingMitigations",
    "getEndpointSecurityStatus",
    "getImmediateThreatsStatus",
    "getImmediateThreatsResults",
    "listLaunchedAssessments",
}


def _integration(sample_integration_dict, **tokens):
    payload = {
        "auth_type": "oauth_client",
        "api_url": US_API,
        "client_id": DUMMY_CLIENT_ID,
        "client_secret": DUMMY_CLIENT_SECRET,
    }
    payload.update(tokens)
    return sample_integration_dict("cymulate", payload)


def _service(sample_integration_dict, **tokens):
    return integration_service_factory.get_service(
        None, _integration(sample_integration_dict, **tokens)
    )


class _Response:
    def __init__(self, status_code, is_redirect=False, payload=None):
        self.status_code = status_code
        self.is_redirect = is_redirect
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class TestCymulateOffline:
    def test_factory_registration(self):
        assert integration_service_factory.get_service_cls("cymulate") is CymulateService

    def test_schema_with_dummy_creds(self, sample_integration_dict):
        integration = CymulateIntegration(**_integration(sample_integration_dict))
        assert integration.auth_type == "oauth_client"
        assert integration.client_id == DUMMY_CLIENT_ID
        assert integration.client_secret == DUMMY_CLIENT_SECRET
        assert integration.api_url == US_API
        assert integration.name == "Cymulate"
        assert integration.category == "security_tools"
        assert integration.mcp_url is None
        assert integration.ignore_ssl is False

    def test_api_token_excluded_from_dump(self, sample_integration_dict):
        integration = CymulateIntegration(**_integration(sample_integration_dict))
        dumped = integration.model_dump()
        assert "api_token" not in dumped
        assert "client_id" not in dumped
        assert "client_secret" not in dumped
        serialized = json.dumps(dumped)
        assert DUMMY_API_TOKEN not in serialized
        assert DUMMY_CLIENT_SECRET not in serialized
        assert DUMMY_ACCESS_TOKEN not in serialized

    def test_api_token_schema(self, sample_integration_dict):
        integration = CymulateIntegration(
            **_integration(
                sample_integration_dict,
                auth_type="api_token",
                api_token=DUMMY_API_TOKEN,
                client_id=None,
                client_secret=None,
            )
        )
        assert integration.uses_api_token()
        assert integration.api_token == DUMMY_API_TOKEN
        assert integration.client_id is None
        dumped = integration.model_dump()
        assert "api_token" not in dumped
        assert DUMMY_API_TOKEN not in json.dumps(dumped)

    def test_empty_token_rejected(self, sample_integration_dict):
        with pytest.raises(ValidationError):
            CymulateIntegration(**_integration(sample_integration_dict, client_secret=""))
        with pytest.raises(ValidationError):
            CymulateIntegration(**_integration(sample_integration_dict, client_id="not-a-hex-id"))
        with pytest.raises(ValidationError):
            CymulateIntegration(
                **_integration(
                    sample_integration_dict,
                    auth_type="api_token",
                    api_token="  ",
                    client_id=None,
                    client_secret=None,
                )
            )

    def test_api_url_rejects_unsafe_urls(self, sample_integration_dict):
        for bad in (
            "http://api.us-app.cymulate.com",
            "https://10.0.0.5",
            "https://localhost",
            "https://user:secret@api.us-app.cymulate.com",
        ):
            with pytest.raises(ValidationError):
                CymulateIntegration(**_integration(sample_integration_dict, api_url=bad))

    def test_custom_https_api_url_accepted(self, sample_integration_dict):
        integration = CymulateIntegration(
            **_integration(
                sample_integration_dict,
                api_url="https://api.customer.example/",
            )
        )
        assert integration.api_url == "https://api.customer.example"

    def test_known_regional_urls_accepted(self, sample_integration_dict):
        for url in CYMULATE_API_URLS:
            integration = CymulateIntegration(
                **_integration(sample_integration_dict, api_url=url + "/")
            )
            assert integration.api_url == url

    def test_mcp_url_rejects_private_hosts(self, sample_integration_dict):
        for bad in ("http://mcp.example/mcp", "https://127.0.0.1/mcp", "https://10.1.1.1/mcp"):
            with pytest.raises(ValidationError):
                CymulateIntegration(**_integration(sample_integration_dict, mcp_url=bad))

    def test_forms(self):
        form = CymulateService.get_forms()
        assert form["label"] == "Cymulate"
        tabs = form["children"]
        assert [tab["formId"] for tab in tabs] == ["api_token", "oauth_client"]
        assert all(tab["type"] == "form" for tab in tabs)
        api_token_tab = tabs[0]["children"]
        oauth_tab = tabs[1]["children"]
        assert [field["name"] for field in api_token_tab] == [
            "api_url",
            "api_token",
            "mcp_url",
            "ignore_ssl",
        ]
        assert [field["name"] for field in oauth_tab] == [
            "api_url",
            "client_id",
            "client_secret",
            "ignore_ssl",
        ]
        assert api_token_tab[0]["type"] == "text/url"
        assert "options" not in api_token_tab[0]
        assert api_token_tab[1]["type"] == "text/password"
        assert oauth_tab[1]["type"] == "text"
        assert oauth_tab[1]["required"] is True
        assert oauth_tab[2]["type"] == "text/password"

    def test_supported_interfaces(self):
        assert CymulateService.supported_connection_interfaces() == [
            ConnectionInterfaces.REST_API,
            ConnectionInterfaces.PYTHON_SDK,
            ConnectionInterfaces.MCP_SERVER,
        ]
        assert CymulateService._rest_api_supported()
        assert CymulateService._python_sdk_supported()
        assert CymulateService._mcp_server_supported()

    def test_rest_creds_use_oauth_bearer(self, sample_integration_dict, monkeypatch):
        def fake_token(api_url, client_id, client_secret, *, verify):
            assert api_url == EU_API
            assert client_id == DUMMY_CLIENT_ID
            assert client_secret == DUMMY_CLIENT_SECRET
            assert verify is False
            return DUMMY_ACCESS_TOKEN

        monkeypatch.setattr(
            "autobotAI_integrations.integrations.cymulate.fetch_access_token",
            fake_token,
        )
        creds = _service(
            sample_integration_dict, api_url=EU_API, ignore_ssl=True
        ).generate_rest_api_creds()
        assert creds.base_url == EU_API
        assert creds.headers["Authorization"] == f"Bearer {DUMMY_ACCESS_TOKEN}"
        assert creds.headers["Accept"] == "application/json"
        assert creds.verify_ssl is False
        assert "x-token" not in creds.headers

    def test_rest_creds_use_api_token(self, sample_integration_dict, monkeypatch):
        def fail_token(*args, **kwargs):
            raise AssertionError("OAuth token exchange was called")

        monkeypatch.setattr(
            "autobotAI_integrations.integrations.cymulate.fetch_access_token",
            fail_token,
        )
        creds = _service(
            sample_integration_dict,
            auth_type="api_token",
            api_token=DUMMY_API_TOKEN,
            client_id=None,
            client_secret=None,
            api_url=EU_API,
        ).generate_rest_api_creds()
        assert creds.base_url == EU_API
        assert creds.headers["x-token"] == DUMMY_API_TOKEN
        assert creds.headers["Accept"] == "application/json"
        assert "Authorization" not in creds.headers

    def test_python_sdk_rejects_api_token(self, sample_integration_dict):
        service = _service(
            sample_integration_dict,
            auth_type="api_token",
            api_token=DUMMY_API_TOKEN,
            client_id=None,
            client_secret=None,
        )
        with pytest.raises(ValueError, match="OAuth client"):
            service.generate_python_sdk_creds()

    def test_python_sdk_uses_official_oauth_client(self, sample_integration_dict, monkeypatch):
        constructed = {}

        class FakeOAuthClient:
            def __init__(self, client_id, client_secret, base_url):
                constructed.update(
                    client_id=client_id,
                    client_secret=client_secret,
                    base_url=base_url,
                )

        fake_module = SimpleNamespace(CymulateOAuth2Client=FakeOAuthClient)
        monkeypatch.setattr(
            "autobotAI_integrations.integrations.cymulate.importlib.import_module",
            lambda name, package=None: fake_module,
        )

        service = _service(sample_integration_dict, api_url=EU_API)
        creds = service.generate_python_sdk_creds()
        assert creds.envs == {
            "CYMULATE_API_URL": EU_API,
            "CYMULATE_CLIENT_ID": DUMMY_CLIENT_ID,
            "CYMULATE_CLIENT_SECRET": DUMMY_CLIENT_SECRET,
        }
        clients = CymulateService.get_all_python_sdk_clients()
        assert clients[0]["name"] == "cymulate"
        assert clients[0]["import_library_names"] == ["cymulate_oauth2_client"]
        assert clients[0]["pip_package_names"] == ["cymulate-oauth2-client"]
        combo = service.build_python_exec_combinations_hook(
            SimpleNamespace(creds=creds, params=[], context={}),
            [SDKClient(**clients[0])],
        )
        assert combo[0]["clients"]["cymulate"].__class__ is FakeOAuthClient
        assert constructed == {
            "client_id": DUMMY_CLIENT_ID,
            "client_secret": DUMMY_CLIENT_SECRET,
            "base_url": EU_API,
        }

    def test_mcp_creds_and_actions(self, sample_integration_dict, monkeypatch):
        service_cls = integration_service_factory.get_service_cls("cymulate")
        actions = service_cls.get_all_mcp_server_actions()
        assert {action.name for action in actions} == {
            "Cymulate All",
            "Cymulate Findings",
            "Cymulate Assessments",
            "Cymulate Agents and Environments",
        }
        for action in actions:
            assert action.code == "{base_url}"
            assert action.executable_type == "mcp_server"

        calls = {"count": 0}

        def fake_token(*args, **kwargs):
            calls["count"] += 1
            return DUMMY_ACCESS_TOKEN

        monkeypatch.setattr(
            "autobotAI_integrations.integrations.cymulate.fetch_access_token",
            fake_token,
        )
        oauth_with_mcp = _service(
            sample_integration_dict, mcp_url=MCP_URL
        ).generate_mcp_creds()
        assert oauth_with_mcp.url is None
        assert oauth_with_mcp.headers == {}
        assert calls["count"] == 0

        token_service = _service(
            sample_integration_dict,
            auth_type="api_token",
            api_token=DUMMY_API_TOKEN,
            client_id=None,
            client_secret=None,
        )
        without_mcp = token_service.generate_mcp_creds()
        assert without_mcp.url is None
        assert without_mcp.headers == {}
        assert calls["count"] == 0

        with_mcp = _service(
            sample_integration_dict,
            auth_type="api_token",
            api_token=DUMMY_API_TOKEN,
            client_id=None,
            client_secret=None,
            mcp_url=MCP_URL + "/",
            ignore_ssl=True,
        ).generate_mcp_creds()
        assert with_mcp.url == MCP_URL
        assert with_mcp.headers == {"x-token": DUMMY_API_TOKEN}
        assert "Authorization" not in with_mcp.headers
        assert with_mcp.envs == {"MCP_BASE_URL": MCP_URL}
        assert with_mcp.ignore_ssl is True
        assert calls["count"] == 0

    def test_open_api_actions(self):
        import autobotAI_integrations.integrations.cymulate as pkg

        spec_path = Path(pkg.__file__).parent / "open_api.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        assert spec["servers"][0]["url"] == "{base_url}"
        found = {
            op["operationId"]
            for path_item in spec["paths"].values()
            for op in path_item.values()
            if isinstance(op, dict) and "operationId" in op
        }
        assert found == EXPECTED_OPERATION_IDS

        actions = CymulateService.get_all_rest_api_actions()
        assert len(actions) == len(EXPECTED_OPERATION_IDS)
        by_name = {action.name: action for action in actions}
        assert by_name["Get all environments"].code == "{base_url}/v1/environments"
        assert by_name["Search findings"].code == "{base_url}/msfinding/api/v2/search"

    def test_connection_check_success_with_dummy_client(self, sample_integration_dict, monkeypatch):
        seen = {}

        def fake_post(url, data=None, headers=None, timeout=None, verify=None, allow_redirects=None):
            seen["post"] = {
                "url": url,
                "data": data,
                "timeout": timeout,
                "verify": verify,
                "allow_redirects": allow_redirects,
            }
            return _Response(200, payload={"access_token": DUMMY_ACCESS_TOKEN})

        def fake_get(url, headers=None, timeout=None, verify=None, allow_redirects=None):
            seen["get"] = {
                "url": url,
                "headers": headers,
                "timeout": timeout,
                "verify": verify,
                "allow_redirects": allow_redirects,
            }
            return _Response(200)

        monkeypatch.setattr(
            "autobotAI_integrations.integrations.cymulate.requests.post", fake_post
        )
        monkeypatch.setattr(
            "autobotAI_integrations.integrations.cymulate.requests.get", fake_get
        )
        result = _service(sample_integration_dict).is_active()
        assert result == {"success": True}
        assert seen["post"]["url"] == f"{US_API}{TOKEN_PATH}"
        assert seen["post"]["data"]["client_id"] == DUMMY_CLIENT_ID
        assert seen["post"]["data"]["client_secret"] == DUMMY_CLIENT_SECRET
        assert seen["post"]["data"]["grant_type"] == "client_credentials"
        assert seen["post"]["allow_redirects"] is False
        assert seen["get"]["url"] == f"{US_API}{ENVIRONMENTS_PATH}"
        assert seen["get"]["headers"]["Authorization"] == f"Bearer {DUMMY_ACCESS_TOKEN}"
        assert "x-token" not in seen["get"]["headers"]
        assert seen["get"]["verify"] is True
        assert seen["get"]["allow_redirects"] is False
        assert seen["get"]["timeout"] == 15

    def test_connection_check_success_with_api_token(self, sample_integration_dict, monkeypatch):
        seen = {}

        def fail_post(*args, **kwargs):
            raise AssertionError("OAuth token exchange was called")

        def fake_get(url, headers=None, timeout=None, verify=None, allow_redirects=None):
            seen.update(
                url=url,
                headers=headers,
                timeout=timeout,
                verify=verify,
                allow_redirects=allow_redirects,
            )
            return _Response(200)

        monkeypatch.setattr(
            "autobotAI_integrations.integrations.cymulate.requests.post", fail_post
        )
        monkeypatch.setattr(
            "autobotAI_integrations.integrations.cymulate.requests.get", fake_get
        )
        result = _service(
            sample_integration_dict,
            auth_type="api_token",
            api_token=DUMMY_API_TOKEN,
            client_id=None,
            client_secret=None,
        ).is_active()
        assert result == {"success": True}
        assert seen["url"] == f"{US_API}{ENVIRONMENTS_PATH}"
        assert seen["headers"]["x-token"] == DUMMY_API_TOKEN
        assert "Authorization" not in seen["headers"]
        assert seen["allow_redirects"] is False
        assert DUMMY_API_TOKEN not in json.dumps(result)

    def test_connection_check_rejects_dummy_client(self, sample_integration_dict, monkeypatch):
        monkeypatch.setattr(
            "autobotAI_integrations.integrations.cymulate.requests.post",
            lambda *args, **kwargs: _Response(401),
        )
        def fail_get(*args, **kwargs):
            raise AssertionError("API was called")

        monkeypatch.setattr(
            "autobotAI_integrations.integrations.cymulate.requests.get",
            fail_get,
        )
        result = _service(sample_integration_dict).is_active()
        assert result["success"] is False
        assert DUMMY_CLIENT_SECRET not in result["error"]
        assert DUMMY_ACCESS_TOKEN not in result["error"]

    def test_connection_check_does_not_follow_redirects(
        self, sample_integration_dict, monkeypatch
    ):
        monkeypatch.setattr(
            "autobotAI_integrations.integrations.cymulate.requests.post",
            lambda *args, **kwargs: _Response(302, is_redirect=True),
        )
        def fail_get(*args, **kwargs):
            raise AssertionError("API was called")

        monkeypatch.setattr(
            "autobotAI_integrations.integrations.cymulate.requests.get",
            fail_get,
        )
        result = _service(sample_integration_dict).is_active()
        assert result["success"] is False
        assert "302" in result["error"]
        assert DUMMY_CLIENT_SECRET not in result["error"]
