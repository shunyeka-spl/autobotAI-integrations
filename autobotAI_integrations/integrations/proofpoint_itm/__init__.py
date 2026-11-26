import requests
from typing import List, Optional, Type, Union
from urllib.parse import urlparse
from pydantic import Field

from autobotAI_integrations import (
    BaseSchema,
    BaseService,
    ConnectionInterfaces,
    PayloadTask,
    RestAPICreds,
    SDKClient,
    SDKCreds,
)
from autobotAI_integrations.models import IntegrationCategory

class ProofpointITMIntegration(BaseSchema):
    base_url: Optional[str] = Field(default=None, exclude=True, description="Proofpoint ITM Base URL (e.g., https://tenant.itmsaas.proofpoint.com)")
    client_id: Optional[str] = Field(default=None, exclude=True, description="Proofpoint ITM API Client ID")
    client_secret: Optional[str] = Field(default=None, exclude=True, description="Proofpoint ITM API Client Secret")

    name: str = "Endpoint DLP"
    category: Optional[str] = IntegrationCategory.SECURITY_TOOLS.value
    description: Optional[str] = (
        "DLP (Data Loss Prevention) and Insider Threat Management (ITM) integration for pulling user activity, "
        "alerts, and endpoint data protection incidents."
    )

class ProofpointITMService(BaseService):
    def __init__(self, ctx: dict, integration: Union[ProofpointITMIntegration, dict]):
        if not isinstance(integration, ProofpointITMIntegration):
            integration = ProofpointITMIntegration(**integration)
        super().__init__(ctx, integration)

    def _get_access_token(self) -> str:
        """
        Fetches the OAuth 2.0 Bearer token from Proofpoint ITM SaaS.
        """
        token_url = f"{self.integration.base_url.rstrip('/')}/v2/oauth/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.integration.client_id,
            "client_secret": self.integration.client_secret
        }
        
        response = requests.post(
            token_url,
            data=payload,
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("access_token", "")
        else:
            raise Exception(f"Failed to fetch Proofpoint ITM token: {response.text}")

    def _test_integration(self) -> dict:
        """
        Strictly tests the integration by fetching an OAuth token and attempting a lightweight API call.
        """
        try:
            # 1. Test token generation
            token = self._get_access_token()
            if not token:
                return {"success": False, "error": "Token generation succeeded but access_token was missing in response."}

            # 2. Test a lightweight ITM API endpoint to verify scopes
            test_url = f"{self.integration.base_url.rstrip('/')}/v2/alerts?limit=1"
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            }
            
            response = requests.get(test_url, headers=headers, timeout=10)
            
            if response.status_code in (200, 201):
                return {"success": True}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
            
        except Exception as e:
            return {"success": False, "error": f"Proofpoint ITM integration test failed: {str(e)}"}

    @classmethod
    def get_details(cls):
        details = super().get_details()
        details["preview"] = True
        return details

    @staticmethod
    def get_forms():
        return {
            "label": "Endpoint DLP",
            "type": "form",
            "children": [
                {
                    "name": "base_url",
                    "type": "text",
                    "label": "Base URL",
                    "placeholder": "Enter your ITM SaaS URL (e.g. https://<tenant>.itmsaas.proofpoint.com)",
                    "required": True,
                },
                {
                    "name": "client_id",
                    "type": "text",
                    "label": "Client ID",
                    "placeholder": "Enter your Proofpoint ITM API Client ID",
                    "required": True,
                    "help_url": "https://www.proofpoint.com/us/products/information-protection/endpoint-dlp",
                    "help_url_text": "Proofpoint ITM Docs ↗",
                },
                {
                    "name": "client_secret",
                    "type": "text/password",
                    "label": "Client Secret",
                    "placeholder": "Enter your Proofpoint ITM API Client Secret",
                    "required": True,
                }
            ],
        }

    @staticmethod
    def get_schema(ctx=None) -> Type[BaseSchema]:
        return ProofpointITMIntegration

    @staticmethod
    def supported_connection_interfaces():
        return [
            ConnectionInterfaces.REST_API,
            ConnectionInterfaces.PYTHON_SDK,
        ]

    def generate_rest_api_creds(self) -> RestAPICreds:
        """
        Generates REST API credentials dynamically before the workflow triggers an action.
        """
        # Fetch a fresh token before running the REST API actions
        token = self._get_access_token()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        return RestAPICreds(
            base_url=self.integration.base_url.rstrip("/"),
            headers=headers
        )

    def generate_python_sdk_creds(self) -> SDKCreds:
        return SDKCreds(
            envs={
                "PROOFPOINT_ITM_BASE_URL": (self.integration.base_url or "").rstrip("/"),
                "PROOFPOINT_ITM_CLIENT_ID": self.integration.client_id or "",
                "PROOFPOINT_ITM_CLIENT_SECRET": self.integration.client_secret or "",
            }
        )

    def build_python_exec_combinations_hook(
        self, payload_task: PayloadTask, client_definitions: List[SDKClient]
    ) -> list:
        envs = payload_task.creds.envs or {}
        base_url = envs.get("PROOFPOINT_ITM_BASE_URL", "").rstrip("/")
        client_id = envs.get("PROOFPOINT_ITM_CLIENT_ID", "")
        client_secret = envs.get("PROOFPOINT_ITM_CLIENT_SECRET", "")

        session = requests.Session()
        session.base_url = base_url
        session.client_id = client_id
        session.client_secret = client_secret
        session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        parsed_url = urlparse(base_url)
        host = (parsed_url.hostname or "").lower()
        if (
            parsed_url.scheme == "https"
            and host.endswith(".itmsaas.proofpoint.com")
            and client_id
            and client_secret
        ):
            resp = requests.post(
                f"{base_url}/v2/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                timeout=10,
                allow_redirects=False,
            )
            if resp.ok and resp.json().get("access_token"):
                session.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"

        return [
            {
                "clients": {"proofpoint_itm": session},
                "params": self.prepare_params(payload_task.params),
                "context": payload_task.context,
            }
        ]
