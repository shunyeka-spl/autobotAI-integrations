import importlib
from enum import Enum
from typing import List, Optional, Union
from urllib.parse import urlparse

import requests
from pydantic import Field, field_validator, model_validator

from autobotAI_integrations import (
    BaseSchema,
    BaseService,
    ConnectionInterfaces,
    PayloadTask,
    RestAPICreds,
    SDKClient,
    SDKCreds,
)
from autobotAI_integrations.models import IntegrationCategory, MCPCreds

# Public Cymulate API hosts. API token covers REST and MCP. OAuth covers REST and the SDK.
CYMULATE_API_URLS = (
    "https://api.us-app.cymulate.com",
    "https://api.app.cymulate.com",
    "https://us-api.cymulate.com",
    "https://api.cymulate.com",
)
DEFAULT_API_URL = CYMULATE_API_URLS[0]
ENVIRONMENTS_PATH = "/v2/threats"
TOKEN_PATH = "/oauth2/token"
_BLOCKED_MCP_HOSTS = {"localhost", "metadata.google.internal", "169.254.169.254"}


class CymulateAuthTypes(str, Enum):
    API_TOKEN = "api_token"
    OAUTH_CLIENT = "oauth_client"


class TokenExchangeError(Exception):
    """OAuth token exchange failed. The message must not include secrets."""


def api_token_headers(api_token: str) -> dict:
    return {
        "x-token": api_token,
        "Accept": "application/json",
    }


def bearer_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }


def fetch_access_token(
    api_url: str, client_id: str, client_secret: str, *, verify: bool
) -> str:
    """Exchange the OAuth client for an access token. Does not follow redirects."""
    response = requests.post(
        f"{api_url}{TOKEN_PATH}",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "audience": "cymulate.com",
            "issuer": "cymulate.com",
        },
        headers={"Accept": "application/json"},
        timeout=15,
        verify=verify,
        allow_redirects=False,
    )
    if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
        raise TokenExchangeError(
            f"Cymulate token endpoint returned redirect status {response.status_code}"
        )
    if response.status_code in (401, 403):
        raise TokenExchangeError("Invalid client id or client secret.")
    if response.status_code != 200:
        raise TokenExchangeError(
            f"Token request failed with status code: {response.status_code}"
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise TokenExchangeError("Cymulate token response was not JSON") from exc
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if (
        not isinstance(token, str)
        or not token.strip()
        or any(char in token for char in "\r\n")
    ):
        raise TokenExchangeError("Cymulate token response did not include an access token")
    return token.strip()


def _normalize_https_url(value: Optional[str], *, required: bool) -> Optional[str]:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValueError("An https URL is required")
        return None
    raw = str(value).strip().rstrip("/")
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise ValueError("URL must be https and must not include credentials")
    if host in _BLOCKED_MCP_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError("URL host is not allowed")
    try:
        import ipaddress

        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ValueError("URL host is not allowed")
    return raw


class CymulateIntegration(BaseSchema):
    auth_type: Optional[str] = None
    api_url: str = Field(default=DEFAULT_API_URL)
    api_token: Optional[str] = Field(default=None, exclude=True)
    client_id: Optional[str] = Field(default=None, exclude=True)
    client_secret: Optional[str] = Field(default=None, exclude=True)
    mcp_url: Optional[str] = None
    ignore_ssl: bool = False

    name: Optional[str] = "Cymulate"
    category: Optional[str] = IntegrationCategory.SECURITY_TOOLS.value
    description: Optional[str] = (
        "Cymulate exposure validation platform for breach and attack simulation, "
        "findings, agents, and assessment status."
    )

    @field_validator("api_token", "client_secret")
    @classmethod
    def validate_secret(cls, value: Optional[str]) -> Optional[str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if not isinstance(value, str) or any(char in value for char in "\r\n"):
            raise ValueError("A non-empty secret is required")
        return value.strip()

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, value: Optional[str]) -> Optional[str]:
        # CymulateOAuth2Client accepts only a 24-character hex ObjectId.
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if not isinstance(value, str):
            raise ValueError("client_id must be a 24-character hexadecimal id")
        cleaned = value.strip()
        if len(cleaned) != 24 or any(char not in "0123456789abcdefABCDEF" for char in cleaned):
            raise ValueError("client_id must be a 24-character hexadecimal id")
        return cleaned

    @model_validator(mode="after")
    def validate_selected_auth(self):
        allowed = {
            CymulateAuthTypes.API_TOKEN.value,
            CymulateAuthTypes.OAUTH_CLIENT.value,
        }
        if self.auth_type not in (None, "") and self.auth_type not in allowed:
            raise ValueError("Unknown Cymulate auth type")
        if not self.auth_type:
            if self.client_id and self.client_secret and not self.api_token:
                self.auth_type = CymulateAuthTypes.OAUTH_CLIENT.value
            else:
                self.auth_type = CymulateAuthTypes.API_TOKEN.value
        if self.auth_type == CymulateAuthTypes.API_TOKEN.value and not self.api_token:
            raise ValueError("API token is required")
        if self.auth_type == CymulateAuthTypes.OAUTH_CLIENT.value and (
            not self.client_id or not self.client_secret
        ):
            raise ValueError("Client id and client secret are required")
        return self

    def uses_api_token(self) -> bool:
        return self.auth_type == CymulateAuthTypes.API_TOKEN.value

    @field_validator("api_url")
    @classmethod
    def validate_api_url(cls, value: str) -> str:
        return _normalize_https_url(value, required=True)

    @field_validator("mcp_url")
    @classmethod
    def validate_mcp_url(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_https_url(value, required=False)

    @field_validator("ignore_ssl", mode="before")
    @classmethod
    def validate_ignore_ssl(cls, ignore_ssl) -> bool:
        if isinstance(ignore_ssl, bool):
            return ignore_ssl
        if isinstance(ignore_ssl, str):
            if ignore_ssl.lower() == "true":
                return True
            if ignore_ssl.lower() == "false":
                return False
        raise ValueError("Invalid ignore_ssl passed !")


class CymulateService(BaseService):
    def __init__(self, ctx: dict, integration: Union[CymulateIntegration, dict]):
        if not isinstance(integration, CymulateIntegration):
            integration = CymulateIntegration(**integration)
        super().__init__(ctx, integration)

    def _access_token(self) -> str:
        return fetch_access_token(
            self.integration.api_url,
            self.integration.client_id,
            self.integration.client_secret,
            verify=not self.integration.ignore_ssl,
        )

    def _test_integration(self) -> dict:
        verify = not self.integration.ignore_ssl
        if self.integration.uses_api_token():
            headers = api_token_headers(self.integration.api_token)
        else:
            try:
                headers = bearer_headers(self._access_token())
            except TokenExchangeError as exc:
                return {"success": False, "error": str(exc)}
            except requests.exceptions.Timeout:
                return {"success": False, "error": "Request to Cymulate timed out"}
            except requests.exceptions.ConnectionError:
                return {
                    "success": False,
                    "error": "Unable to reach the Cymulate API. Check the regional API URL.",
                }
            except Exception as exc:
                return {"success": False, "error": str(exc)}

        url = f"{self.integration.api_url}{ENVIRONMENTS_PATH}"
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=15,
                verify=verify,
                allow_redirects=False,
            )
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request to Cymulate timed out"}
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Unable to reach the Cymulate API. Check the regional API URL.",
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        if response.status_code == 200:
            return {"success": True}
        if response.is_redirect:
            return {
                "success": False,
                "error": f"Cymulate API returned redirect status {response.status_code}",
            }
        if response.status_code in (401, 403):
            if self.integration.uses_api_token():
                return {
                    "success": False,
                    "error": "Invalid API token or insufficient permissions.",
                }
            return {
                "success": False,
                "error": "Invalid client id or client secret.",
            }
        return {
            "success": False,
            "error": f"Request failed with status code: {response.status_code}",
        }

    @staticmethod
    def get_forms():
        api_url = {
            "name": "api_url",
            "type": "text/url",
            "label": "API URL",
            "placeholder": "https://api.us-app.cymulate.com",
            "default_value": DEFAULT_API_URL,
            "description": (
                "Cymulate API host for this tenant. "
                "US: https://api.us-app.cymulate.com. "
                "EU: https://api.app.cymulate.com."
            ),
            "required": True,
        }
        ignore_ssl = {
            "name": "ignore_ssl",
            "type": "select",
            "label": "Ignore SSL",
            "placeholder": "default: 'False'",
            "description": "Select whether to ignore SSL certificate validation.",
            "options": [
                {"label": "True", "value": True},
                {"label": "False", "value": False},
            ],
            "required": False,
        }
        return {
            "label": "Cymulate",
            "type": "form",
            "children": [
                {
                    "label": "API Token",
                    "type": "form",
                    "formId": CymulateAuthTypes.API_TOKEN.value,
                    "children": [
                        {**api_url},
                        {
                            "name": "api_token",
                            "type": "text/password",
                            "label": "API Token",
                            "placeholder": "Enter the Cymulate API token",
                            "description": (
                                "API token from Settings → Cymulate API. "
                                "Sent as the x-token header for the REST API and the MCP server."
                            ),
                            "required": True,
                            "help_url": "https://api.cymulate.com/docs",
                            "help_url_text": "API docs ↗",
                        },
                        {
                            "name": "mcp_url",
                            "type": "text/url",
                            "label": "MCP Server URL",
                            "placeholder": "https://your-cymulate-mcp.example/mcp",
                            "description": (
                                "Streamable HTTP endpoint of the Cymulate MCP server. "
                                "The API token is sent as the x-token header. "
                                "Leave blank to use the REST API only."
                            ),
                            "required": False,
                            "help_url": "https://cymulate.com/blog/mcp-server-and-claude-plugin/",
                            "help_url_text": "Cymulate MCP ↗",
                        },
                        {**ignore_ssl},
                    ],
                },
                {
                    "label": "OAuth Client",
                    "type": "form",
                    "formId": CymulateAuthTypes.OAUTH_CLIENT.value,
                    "children": [
                        {**api_url},
                        {
                            "name": "client_id",
                            "type": "text",
                            "label": "Client ID",
                            "placeholder": "24-character client id",
                            "description": (
                                "OAuth client id for the official Python SDK and the REST API. "
                                "Must be a 24-character hexadecimal id."
                            ),
                            "required": True,
                            "help_url": "https://github.com/cymulate-ltd/oauth2-client",
                            "help_url_text": "Python SDK ↗",
                        },
                        {
                            "name": "client_secret",
                            "type": "text/password",
                            "label": "Client Secret",
                            "placeholder": "Enter the client secret",
                            "description": (
                                "OAuth client secret. Used with the client id for "
                                "the Python SDK and the REST API."
                            ),
                            "required": True,
                            "help_url": "https://github.com/cymulate-ltd/oauth2-client",
                            "help_url_text": "Python SDK ↗",
                        },
                        {**ignore_ssl},
                    ],
                },
            ],
        }

    @staticmethod
    def get_schema(ctx=None):
        return CymulateIntegration

    @staticmethod
    def supported_connection_interfaces():
        return [
            ConnectionInterfaces.REST_API,
            ConnectionInterfaces.PYTHON_SDK,
            ConnectionInterfaces.MCP_SERVER,
        ]

    def build_python_exec_combinations_hook(
        self, payload_task: PayloadTask, client_definitions: List[SDKClient]
    ) -> list:
        sdk = importlib.import_module(
            client_definitions[0].import_library_names[0], package=None
        )
        envs = payload_task.creds.envs
        client_id = envs.get("CYMULATE_CLIENT_ID")
        client_secret = envs.get("CYMULATE_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise ValueError("The Cymulate Python SDK requires the OAuth client")
        return [
            {
                "clients": {
                    "cymulate": sdk.CymulateOAuth2Client(
                        client_id=client_id,
                        client_secret=client_secret,
                        base_url=envs["CYMULATE_API_URL"],
                    )
                },
                "params": self.prepare_params(payload_task.params),
                "context": payload_task.context,
            }
        ]

    def generate_rest_api_creds(self) -> RestAPICreds:
        if self.integration.uses_api_token():
            headers = api_token_headers(self.integration.api_token)
        else:
            headers = bearer_headers(self._access_token())
        return RestAPICreds(
            base_url=self.integration.api_url,
            headers=headers,
            verify_ssl=not self.integration.ignore_ssl,
        )

    def generate_python_sdk_creds(self) -> SDKCreds:
        if self.integration.uses_api_token():
            raise ValueError("The Cymulate Python SDK requires the OAuth client")
        return SDKCreds(
            envs={
                "CYMULATE_API_URL": self.integration.api_url,
                "CYMULATE_CLIENT_ID": self.integration.client_id,
                "CYMULATE_CLIENT_SECRET": self.integration.client_secret,
            }
        )

    def generate_mcp_creds(self) -> MCPCreds:
        mcp_url = self.integration.mcp_url if self.integration.uses_api_token() else None
        if not mcp_url:
            return MCPCreds(
                url=None,
                headers={},
                envs={},
                ignore_ssl=self.integration.ignore_ssl,
            )
        return MCPCreds(
            url=mcp_url,
            headers={"x-token": self.integration.api_token},
            envs={"MCP_BASE_URL": mcp_url},
            ignore_ssl=self.integration.ignore_ssl,
        )
