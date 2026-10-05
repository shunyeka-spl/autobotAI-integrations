from typing import Optional, Type, Union
from urllib.parse import quote, urlparse

import requests
from pydantic import Field

from autobotAI_integrations import (
    BaseSchema,
    BaseService,
    ConnectionInterfaces,
)
from autobotAI_integrations.models import IntegrationCategory, RestAPICreds
from autobotAI_integrations.payload_schema import PayloadTask

# Devo serves the Query API and the Alerts API from different hosts, and the
# host naming is not uniform across regions (APAC/US3 have no apiv2- host).
# Query API: https://docs.devo.com/space/latest/95128275/Query+API
# Alerts API: https://docs.devo.com/space/latest/95128644/Alerts+API
DEVO_REGION_ENDPOINTS = {
    "us": ("https://apiv2-us.devo.com", "https://api-us.devo.com"),
    "eu": ("https://apiv2-eu.devo.com", "https://api-eu.devo.com"),
    "ca": ("https://apiv2-ca.devo.com", "https://api-ca.devo.com"),
    "apac": ("https://api-apac.devo.com", "https://api-apac.devo.com"),
    "us3": ("https://api-us3.devo.com", "https://api-us3.devo.com"),
}

# open_api.json addresses Alerts API paths as https://{devo_alerts_host}/...
# because the generic REST executor only knows a single base_url.
ALERTS_HOST_PLACEHOLDER = "{devo_alerts_host}"

DEFAULT_TEST_TABLE = "siem.logtrust.web.activity"


class DevoIntegration(BaseSchema):
    region: Optional[str] = Field(default="us")
    # Devo tokens are typed: a "Query API" token cannot call the Alerts API and
    # an "Alert API" token cannot query data, so each API gets its own token.
    token: Optional[str] = Field(default=None, exclude=True)
    alerts_token: Optional[str] = Field(default=None, exclude=True)
    test_table: Optional[str] = Field(default=DEFAULT_TEST_TABLE)
    query_api_url: Optional[str] = Field(
        default=None,
        description="Overrides the region's Query API URL (e.g. https://apiv2-us.devo.com)",
    )
    alerts_api_url: Optional[str] = Field(
        default=None,
        description="Overrides the region's Alerts API URL (e.g. https://api-us.devo.com)",
    )

    name: Optional[str] = "Devo"
    category: Optional[str] = IntegrationCategory.SECURITY_TOOLS.value
    description: Optional[str] = (
        "Devo is a cloud-native SIEM and security data analytics platform for "
        "real-time log search, threat detection and alerting."
    )


class DevoService(BaseService):
    def __init__(self, ctx: dict, integration: Union[DevoIntegration, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, DevoIntegration):
            integration = DevoIntegration(**integration)
        super().__init__(ctx, integration)

    def _region_endpoints(self):
        region = str(self.integration.region or "us").strip().lower()
        return DEVO_REGION_ENDPOINTS.get(region, DEVO_REGION_ENDPOINTS["us"])

    def _query_api_url(self) -> str:
        url = self.integration.query_api_url or self._region_endpoints()[0]
        # Users often paste the full documented endpoint (.../search/query).
        url = url.strip().rstrip("/")
        for suffix in ("/search/query", "/search"):
            if url.endswith(suffix):
                url = url[: -len(suffix)]
                break
        return url

    def _alerts_api_url(self) -> str:
        url = self.integration.alerts_api_url or self._region_endpoints()[1]
        url = url.strip().rstrip("/")
        for suffix in ("/alerts/v1", "/alerts"):
            if url.endswith(suffix):
                url = url[: -len(suffix)]
                break
        return url

    def _test_query_token(self) -> Optional[str]:
        table = (self.integration.test_table or DEFAULT_TEST_TABLE).strip()
        response = requests.get(
            f"{self._query_api_url()}/search/table/{quote(table, safe='')}",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.integration.token}",
            },
            timeout=30,
        )
        body = _json_or_none(response)
        # Devo reports errors both as HTTP codes and as a non-zero "status".
        if response.status_code == 200 and not _devo_error_status(body):
            return None
        if response.status_code == 401:
            return "Query API token rejected. Verify it is a valid, enabled 'Query API' token."
        message = _devo_error_message(body) or response.text[:300]
        if response.status_code == 403 or "not allowed" in message.lower():
            return (
                f"Query API token cannot access table '{table}': {message}. Set 'Test Table' "
                "to a table inside the token's target tables."
            )
        return f"Query API request failed ({response.status_code}): {message}"

    def _test_alerts_token(self) -> Optional[str]:
        response = requests.get(
            f"{self._alerts_api_url()}/alerts/v1/alertDefinitions",
            headers={
                "Content-Type": "application/json",
                "standAloneToken": str(self.integration.alerts_token),
            },
            params={"page": 0, "size": 1},
            timeout=30,
        )
        if response.status_code == 200:
            return None
        if response.status_code in (401, 403):
            return (
                "Alerts API token rejected. Verify it is an 'Alert API' token and its user "
                "has the Alert configuration and Triggered alerts permissions."
            )
        return f"Alerts API request failed ({response.status_code}): {response.text[:300]}"

    def _test_integration(self) -> dict:
        try:
            error = self._test_query_token()
            if not error and self.integration.alerts_token:
                error = self._test_alerts_token()
            if error:
                return {"success": False, "error": error}
            return {"success": True}
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Connection is unreachable. Verify the region / API URLs.",
            }
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @staticmethod
    def get_forms():
        return {
            "label": "Devo",
            "type": "form",
            "children": [
                {
                    "name": "region",
                    "type": "select",
                    "label": "Region",
                    "placeholder": "Select your Devo cloud region",
                    "description": "Region of your Devo domain; sets the Query and Alerts API endpoints.",
                    "required": True,
                    "options": [
                        {"label": "USA", "value": "us"},
                        {"label": "Europe", "value": "eu"},
                        {"label": "Canada", "value": "ca"},
                        {"label": "Asia-Pacific (APAC)", "value": "apac"},
                        {"label": "US3", "value": "us3"},
                    ],
                    "default": "us",
                },
                {
                    "name": "token",
                    "type": "text/password",
                    "label": "Query API Token",
                    "placeholder": "Enter your Devo Query API token",
                    "description": "Administration → Credentials → Tokens → Create token, type 'Query API'. "
                    "Its target tables limit which tables can be searched.",
                    "help_url": "https://docs.devo.com/space/latest/94763821/Authentication+tokens",
                    "help_url_text": "Get API Token ↗",
                    "required": True,
                },
                {
                    "name": "alerts_token",
                    "type": "text/password",
                    "label": "Alert API Token (optional)",
                    "placeholder": "Enter your Devo Alert API token",
                    "description": "Separate token of type 'Alert API'. Required only for alert "
                    "definition and triggered alert actions.",
                    "help_url": "https://docs.devo.com/space/latest/127762507/Authorizing+Alerts+API+requests",
                    "help_url_text": "Get Alert API Token ↗",
                    "required": False,
                },
                {
                    "name": "test_table",
                    "type": "text",
                    "label": "Test Table",
                    "placeholder": DEFAULT_TEST_TABLE,
                    "description": "Table used to validate the Query API token. Must be inside the "
                    "token's target tables.",
                    "required": False,
                    "default": DEFAULT_TEST_TABLE,
                },
                {
                    "name": "query_api_url",
                    "type": "text/url",
                    "label": "Query API URL (optional)",
                    "placeholder": "https://apiv2-us.devo.com",
                    "description": "Only needed if your domain uses a non-standard Query API endpoint.",
                    "required": False,
                },
                {
                    "name": "alerts_api_url",
                    "type": "text/url",
                    "label": "Alerts API URL (optional)",
                    "placeholder": "https://api-us.devo.com",
                    "description": "Only needed if your domain uses a non-standard Alerts API endpoint.",
                    "required": False,
                },
            ],
        }

    @staticmethod
    def get_schema(ctx=None) -> Type[BaseSchema]:
        return DevoIntegration

    @classmethod
    def get_details(cls):
        return super().get_details()

    @staticmethod
    def supported_connection_interfaces():
        # Devo publishes no MCP server (checked docs.devo.com and DevoInc on
        # GitHub); add ConnectionInterfaces.MCP_SERVER once one exists.
        return [ConnectionInterfaces.REST_API]

    def generate_rest_api_creds(self) -> RestAPICreds:
        envs = {"DEVO_ALERTS_API_URL": self._alerts_api_url()}
        if self.integration.alerts_token:
            envs["DEVO_ALERTS_TOKEN"] = str(self.integration.alerts_token)
        return RestAPICreds(
            base_url=self._query_api_url(),
            token=self.integration.token,
            headers={"Authorization": f"Bearer {self.integration.token}"},
            envs=envs,
        )

    def execute_rest_api_task(self, payload_task: PayloadTask):
        executable = getattr(payload_task, "executable", None)
        if executable and ALERTS_HOST_PLACEHOLDER in executable:
            envs = payload_task.creds.envs or {}
            alerts_token = envs.get("DEVO_ALERTS_TOKEN") or self.integration.alerts_token
            if not alerts_token:
                return [], [
                    {
                        "message": "This Devo action uses the Alerts API, which needs an "
                        "'Alert API' token. Add one to the integration's Alert API Token field."
                    }
                ]
            alerts_url = envs.get("DEVO_ALERTS_API_URL") or self._alerts_api_url()
            payload_task.executable = executable.replace(
                ALERTS_HOST_PLACEHOLDER, urlparse(alerts_url).netloc
            )
            # The Alerts API authenticates with standAloneToken only; never send
            # the Query API bearer token to it.
            payload_task.creds.headers = {"standAloneToken": str(alerts_token)}
        return super().execute_rest_api_task(payload_task)


def _json_or_none(response):
    try:
        return response.json()
    except Exception:
        return None


def _devo_error_status(body) -> bool:
    return isinstance(body, dict) and body.get("status") not in (None, 0)


def _devo_error_message(body) -> str:
    if not isinstance(body, dict):
        return ""
    for key in ("msg", "error"):
        if body.get(key):
            return str(body[key])
    obj = body.get("object")
    if isinstance(obj, list) and obj:
        return str(obj[0])
    return ""
