import contextvars
import importlib
import re
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


API_TOKEN_HEADER = "Netskope-Api-Token"
MCP_HOST = "https://mcp-preview.goskope.com"
_TENANT_SUFFIXES = (".goskope.com", ".goskope.us", ".govskope.com")
_HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)+$")
_ACCESS_CODE_RE = re.compile(r"^[A-Za-z0-9]{6}$")
TEST_PATH = "/api/v2/events/data/alert"

_secrets_omitted = contextvars.ContextVar("netskope_secrets_omitted", default=False)


def api_token_headers(api_token: str) -> dict:
    return {
        API_TOKEN_HEADER: api_token,
        "Accept": "application/json",
    }


def normalize_tenant(value: str) -> str:
    """Return the tenant hostname, such as mycompany.goskope.com."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A Netskope tenant hostname is required")
    raw = value.strip().rstrip("/")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.port not in (None, 443)
        or parsed.path not in ("", "/")
    ):
        raise ValueError("Tenant must be an https Netskope hostname")
    if not any(host.endswith(suffix) for suffix in _TENANT_SUFFIXES) or not _HOST_RE.match(host):
        raise ValueError("Tenant must be a Netskope hostname such as mycompany.goskope.com")
    return host


def tenant_base_url(tenant: str) -> str:
    return f"https://{normalize_tenant(tenant)}"


def tenant_mcp_slug(tenant: str) -> str:
    """Map mytenant.goskope.com to mytenant, and eurocorp.eu.goskope.com to eurocorp_eu."""
    host = normalize_tenant(tenant)
    for suffix in _TENANT_SUFFIXES:
        if host.endswith(suffix):
            slug = host[: -len(suffix)].replace(".", "_")
            if slug and re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug):
                return slug
    raise ValueError("Tenant hostname cannot be used for the MCP server URL")


def mcp_server_url(tenant: str, access_code: str) -> str:
    if not isinstance(access_code, str) or not _ACCESS_CODE_RE.fullmatch(access_code):
        raise ValueError("MCP access code must be 6 letters or digits")
    return f"{MCP_HOST}/{tenant_mcp_slug(tenant)}/{access_code}/mcp"


class NetskopeIntegration(BaseSchema):
    tenant: str
    api_token: Optional[str] = Field(default=None, exclude=True)
    mcp_access_code: Optional[str] = Field(default=None, exclude=True)
    ignore_ssl: bool = False

    name: Optional[str] = "Netskope"
    category: Optional[str] = IntegrationCategory.SECURITY_TOOLS.value
    description: Optional[str] = (
        "Netskope security cloud for alerts, events, incidents, policy, "
        "and private access through the REST API v2, Python SDK, and MCP server."
    )

    @model_validator(mode="before")
    @classmethod
    def note_omitted_secrets(cls, values):
        if isinstance(values, dict):
            _secrets_omitted.set("api_token" not in values)
        else:
            _secrets_omitted.set(False)
        return values

    @field_validator("tenant")
    @classmethod
    def validate_tenant(cls, value: str) -> str:
        return normalize_tenant(value)

    @field_validator("api_token")
    @classmethod
    def validate_api_token(cls, value: Optional[str]) -> Optional[str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if not isinstance(value, str) or any(char in value for char in "\r\n"):
            raise ValueError("A non-empty API token is required")
        return value.strip()

    @field_validator("mcp_access_code")
    @classmethod
    def validate_mcp_access_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        cleaned = value.strip()
        if not _ACCESS_CODE_RE.fullmatch(cleaned):
            raise ValueError("MCP access code must be 6 letters or digits")
        return cleaned

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

    @model_validator(mode="after")
    def require_api_token(self):
        if not _secrets_omitted.get() and not self.api_token:
            raise ValueError("API token is required")
        return self


class NetskopeService(BaseService):
    def __init__(self, ctx: dict, integration: Union[NetskopeIntegration, dict]):
        if not isinstance(integration, NetskopeIntegration):
            integration = NetskopeIntegration(**integration)
        super().__init__(ctx, integration)

    def _test_integration(self) -> dict:
        url = f"{tenant_base_url(self.integration.tenant)}{TEST_PATH}"
        try:
            response = requests.get(
                url,
                params={"limit": 1},
                headers=api_token_headers(self.integration.api_token),
                timeout=15,
                verify=not self.integration.ignore_ssl,
                allow_redirects=False,
            )
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request to Netskope timed out"}
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Unable to reach the Netskope tenant. Check the tenant hostname.",
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        if response.status_code == 200:
            return {"success": True}
        if response.is_redirect:
            return {
                "success": False,
                "error": f"Netskope API returned redirect status {response.status_code}",
            }
        if response.status_code in (401, 403):
            return {
                "success": False,
                "error": "Invalid API token or insufficient permissions.",
            }
        return {
            "success": False,
            "error": f"Request failed with status code: {response.status_code}",
        }

    @staticmethod
    def get_forms():
        return {
            "label": "Netskope",
            "type": "form",
            "children": [
                {
                    "name": "tenant",
                    "type": "text",
                    "label": "Tenant hostname",
                    "placeholder": "mycompany.goskope.com",
                    "description": (
                        "Netskope tenant hostname. "
                        "Standard tenants use mycompany.goskope.com. "
                        "Regional tenants use a name such as eurocorp.eu.goskope.com."
                    ),
                    "required": True,
                    "help_url": "https://docs.netskope.com/en/rest-api-v2-overview-312207",
                    "help_url_text": "REST API docs ↗",
                },
                {
                    "name": "api_token",
                    "type": "text/password",
                    "label": "API Token",
                    "placeholder": "Enter the REST API v2 token",
                    "description": (
                        "Token from Settings → Tools → REST API v2. "
                        "Sent as the Netskope-Api-Token header for REST, "
                        "used by the Python SDK, and sent as a Bearer token to the MCP server."
                    ),
                    "required": True,
                    "help_url": "https://docs.netskope.com/en/rest-api-v2-overview-312207",
                    "help_url_text": "REST API docs ↗",
                },
                {
                    "name": "mcp_access_code",
                    "type": "text/password",
                    "label": "MCP Access Code",
                    "placeholder": "6-character access code",
                    "description": (
                        "Access code for the hosted Netskope MCP server. "
                        "Leave blank to use the REST API and Python SDK only."
                    ),
                    "required": False,
                    "help_url": "https://docs.netskope.com/en/netskope-copilot-for-mcp-server",
                    "help_url_text": "Netskope MCP ↗",
                },
                {
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
                },
            ],
        }

    @staticmethod
    def get_schema(ctx=None):
        return NetskopeIntegration

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
        envs = payload_task.creds.envs or {}
        tenant = envs.get("NETSKOPE_TENANT")
        api_token = envs.get("NETSKOPE_API_TOKEN")
        if not tenant or not api_token:
            raise ValueError("The Netskope Python SDK requires the tenant and API token")
        selected = [client for client in (client_definitions or []) if client.name == "netskope"]
        library = (
            selected[0].import_library_names[0]
            if selected and selected[0].import_library_names
            else "netskope"
        )
        sdk = importlib.import_module(library, package=None)
        client = sdk.NetskopeClient(
            tenant=tenant,
            api_token=api_token,
            verify=not self.integration.ignore_ssl,
        )
        return [
            {
                "clients": {"netskope": client},
                "params": self.prepare_params(payload_task.params),
                "context": payload_task.context,
            }
        ]

    def generate_rest_api_creds(self) -> RestAPICreds:
        if not self.integration.api_token:
            raise ValueError("The Netskope REST API requires an API token")
        return RestAPICreds(
            base_url=tenant_base_url(self.integration.tenant),
            headers=api_token_headers(self.integration.api_token),
            verify_ssl=not self.integration.ignore_ssl,
        )

    def generate_python_sdk_creds(self) -> SDKCreds:
        return SDKCreds(
            envs={
                "NETSKOPE_TENANT": normalize_tenant(self.integration.tenant),
                "NETSKOPE_API_TOKEN": self.integration.api_token or "",
            }
        )

    def generate_mcp_creds(self) -> MCPCreds:
        access_code = self.integration.mcp_access_code
        if not access_code or not self.integration.api_token:
            return MCPCreds(
                url=None,
                headers={},
                envs={},
                ignore_ssl=self.integration.ignore_ssl,
            )
        url = mcp_server_url(self.integration.tenant, access_code)
        return MCPCreds(
            url=url,
            headers={"Authorization": f"Bearer {self.integration.api_token}"},
            envs={"MCP_BASE_URL": url},
            ignore_ssl=self.integration.ignore_ssl,
        )
