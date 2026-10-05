import time
from typing import Optional, Type, Union
from urllib.parse import urlparse

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
# host naming is not uniform across regions (APAC has no apiv2- host).
# https://docs.devo.com/space/latest/95128301/Query+API+requests
DEVO_REGION_ENDPOINTS = {
    "us": ("https://apiv2-us.devo.com", "https://api-us.devo.com"),
    "eu": ("https://apiv2-eu.devo.com", "https://api-eu.devo.com"),
    "ca": ("https://apiv2-ca.devo.com", "https://api-ca.devo.com"),
    "es": ("https://apiv2-es.devo.com", "https://api-es.devo.com"),
    "apac": ("https://api-apac.devo.com", "https://api-apac.devo.com"),
}

# open_api.json addresses Alerts API paths as https://{devo_alerts_host}/...
# because the generic REST executor only knows a single base_url.
ALERTS_HOST_PLACEHOLDER = "{devo_alerts_host}"


class DevoIntegration(BaseSchema):
    region: Optional[str] = Field(default="us")
    query_api_url: Optional[str] = Field(
        default=None,
        description="Overrides the region's Query API URL (e.g. https://apiv2-us.devo.com)",
    )
    alerts_api_url: Optional[str] = Field(
        default=None,
        description="Overrides the region's Alerts API URL (e.g. https://api-us.devo.com)",
    )
    token: Optional[str] = Field(default=None, exclude=True)

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
        if url.endswith("/alerts/v1"):
            url = url[: -len("/alerts/v1")]
        return url

    def _auth_headers(self) -> dict:
        return {
            # Query API authenticates with a bearer token, the Alerts API with
            # the standAloneToken header; the same domain token works for both.
            "Authorization": f"Bearer {self.integration.token}",
            "standAloneToken": str(self.integration.token),
        }

    def _test_integration(self) -> dict:
        try:
            now = int(time.time())
            response = requests.post(
                f"{self._query_api_url()}/search/query",
                headers={"Content-Type": "application/json", **self._auth_headers()},
                json={
                    # Devo's own audit table exists in every domain.
                    "query": "from siem.logtrust.web.activity select eventdate",
                    "from": now - 300,
                    "to": now,
                    "limit": 1,
                    "mode": {"type": "json"},
                },
                timeout=30,
            )
            if response.status_code == 200:
                return {"success": True}
            if response.status_code in (401, 403):
                return {
                    "success": False,
                    "error": "Authentication failed. Verify the token is valid, not expired, "
                    "and has Query API permissions.",
                }
            return {
                "success": False,
                "error": f"Request failed with status code {response.status_code}: "
                f"{response.text[:300]}",
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Connection is unreachable. Verify the region / Query API URL.",
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
                        {"label": "Spain", "value": "es"},
                        {"label": "APAC", "value": "apac"},
                    ],
                    "default": "us",
                },
                {
                    "name": "token",
                    "type": "text/password",
                    "label": "API Token",
                    "placeholder": "Enter your Devo authentication token",
                    "description": "Token from Administration → Credentials → Tokens. Grant Query API "
                    "access to the tables you want to search; alert management also needs "
                    "Alerts API permissions.",
                    "help_url": "https://docs.devo.com/space/latest/94763701/Security+credentials",
                    "help_url_text": "Get API Token ↗",
                    "required": True,
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
        return RestAPICreds(
            base_url=self._query_api_url(),
            token=self.integration.token,
            headers=self._auth_headers(),
            envs={"DEVO_ALERTS_API_URL": self._alerts_api_url()},
        )

    def execute_rest_api_task(self, payload_task: PayloadTask):
        executable = getattr(payload_task, "executable", None)
        if executable and ALERTS_HOST_PLACEHOLDER in executable:
            alerts_url = (payload_task.creds.envs or {}).get(
                "DEVO_ALERTS_API_URL"
            ) or self._alerts_api_url()
            payload_task.executable = executable.replace(
                ALERTS_HOST_PLACEHOLDER, urlparse(alerts_url).netloc
            )
        return super().execute_rest_api_task(payload_task)
