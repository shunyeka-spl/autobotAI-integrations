import importlib
import smtplib
from typing import List, Optional, Union

from pydantic import Field

from autobotAI_integrations import (
    BaseSchema,
    SteampipeCreds,
    RestAPICreds,
    SDKCreds,
    CLICreds,
    BaseService,
    ConnectionInterfaces,
    PayloadTask,
    SDKClient,
)

from autobotAI_integrations.models import IntegrationCategory
import imaplib
import socket
import ssl

_TIMEOUT_SECONDS = 15
_SMTP_SECURITY = ("starttls", "ssl", "none")


def _clean(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text != "None" else None


def smtp_security_for(port, security=None) -> str:
    """'ssl' (implicit TLS), 'starttls' or 'none'. Defaults from the port."""
    sec = (_clean(security) or "").lower()
    if sec in _SMTP_SECURITY:
        return sec
    return "ssl" if str(port) in ("465", "2465") else "starttls"


class DefaultFromSMTPMixin:
    """Fill a missing From with the integration's sender address.

    Providers like AWS SES only accept mail from a verified identity, and the
    SMTP username (an IAM key id for SES) is not an email address. Actions
    written against the old IMAP-first integration often leave From unset.
    """

    default_from: Optional[str] = None

    def send_message(self, msg, from_addr=None, to_addrs=None, *args, **kwargs):
        if self.default_from and not (msg.get("From") or msg.get("Sender")):
            msg["From"] = self.default_from
        return super().send_message(msg, from_addr, to_addrs, *args, **kwargs)

    def sendmail(self, from_addr, to_addrs, msg, *args, **kwargs):
        if not _clean(from_addr) and self.default_from:
            from_addr = self.default_from
        return super().sendmail(from_addr, to_addrs, msg, *args, **kwargs)


class _SMTP(DefaultFromSMTPMixin, smtplib.SMTP):
    pass


class _SMTP_SSL(DefaultFromSMTPMixin, smtplib.SMTP_SSL):
    pass


def open_smtp(host, port, security, username=None, password=None, from_address=None):
    """Connected (and logged-in when credentials are given) SMTP client."""
    port = int(port or 587)
    security = smtp_security_for(port, security)
    context = ssl.create_default_context()
    if security == "ssl":
        client = _SMTP_SSL(host, port, timeout=_TIMEOUT_SECONDS, context=context)
    else:
        client = _SMTP(host, port, timeout=_TIMEOUT_SECONDS)
        if security == "starttls":
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
    client.default_from = _clean(from_address)
    if username and password:
        client.login(username, password)
    return client


def open_imap(host, port, username, password):
    port = int(port or 993)
    if port == 143:
        client = imaplib.IMAP4(host, port, timeout=_TIMEOUT_SECONDS)
        client.starttls(ssl_context=ssl.create_default_context())
    else:
        client = imaplib.IMAP4_SSL(host, port, timeout=_TIMEOUT_SECONDS)
    client.login(username, password)
    return client


class IMAPIntegration(BaseSchema):
    """Email over SMTP (sending) and optionally IMAP (reading).

    Field names are kept from the original IMAP-first integration so stored
    records keep working: ``host``/``port`` are the IMAP side, ``username`` /
    ``password`` are shared unless ``smtp_username``/``smtp_password`` are set.
    """

    # Sending (SMTP)
    smtp_host: Optional[str] = None
    smtp_port: Optional[str] = None
    smtp_security: Optional[str] = None
    smtp_username: Optional[str] = Field(default=None, exclude=True)
    smtp_password: Optional[str] = Field(default=None, exclude=True)
    from_address: Optional[str] = None
    # Reading (IMAP), optional
    host: Optional[str] = None
    port: Optional[str] = Field(default="993")
    username: Optional[str] = Field(default=None, exclude=True)
    password: Optional[str] = Field(default=None, exclude=True)

    category: Optional[str] = IntegrationCategory.NOTIFICATIONS_AND_COMMUNICATIONS.value
    description: Optional[str] = (
        "Send email over SMTP (AWS SES, Microsoft 365, Gmail, SendGrid, your own "
        "relay) and optionally read a mailbox over IMAP."
    )


class IMAPService(BaseService):
    # Same generous 1 MB cap as AWS SES with HTML-formatted footers.
    notification_body_limit = {"max_bytes": 1_000_000, "format": "html"}

    def __init__(self, ctx: dict, integration: Union[IMAPIntegration, dict]):
        """
        Integration should have all the data regarding the integration
        """
        if not isinstance(integration, IMAPIntegration):
            integration = IMAPIntegration(**integration)
        super().__init__(ctx, integration)

    # -- resolved settings --------------------------------------------------

    def _smtp_settings(self, legacy_host_fallback: bool = True) -> Optional[dict]:
        i = self.integration
        host = _clean(i.smtp_host)
        if not host and legacy_host_fallback and _clean(i.host):
            # Records from the IMAP-first form: guess smtp.<domain>.
            host = _clean(i.host).replace("imap", "smtp")
        if not host:
            return None
        port = _clean(i.smtp_port)
        security = (_clean(i.smtp_security) or "").lower() or None
        if not port:
            # Records saved before smtp_port/smtp_security existed always used
            # implicit TLS on 465; new records pick security in the form.
            port = "587" if security in ("starttls", "none") else "465"
        username = _clean(i.smtp_username) or _clean(i.username)
        sender = _clean(i.from_address)
        if not sender and username and "@" in username:
            sender = username  # mailbox logins (Gmail, M365) are addresses
        return {
            "host": host,
            "port": port,
            "security": smtp_security_for(port, security),
            "username": username,
            "password": _clean(i.smtp_password) or _clean(i.password),
            "from_address": sender,
        }

    def _imap_settings(self) -> Optional[dict]:
        i = self.integration
        if not _clean(i.host):
            return None
        return {
            "host": _clean(i.host),
            "port": _clean(i.port) or "993",
            "username": _clean(i.username),
            "password": _clean(i.password),
        }

    def _test_integration(self):
        smtp = self._smtp_settings(legacy_host_fallback=False)
        imap = self._imap_settings()
        if not smtp and not imap:
            return {"success": False, "error": "Enter an SMTP host (to send) or an IMAP host (to read)."}
        if smtp:
            if not smtp["from_address"] or "@" not in smtp["from_address"]:
                return {
                    "success": False,
                    "error": (
                        "Set a From Address to send email: the SMTP username is not an "
                        "email address (for AWS SES the sender must be a verified identity)."
                    ),
                }
            try:
                client = open_smtp(**smtp)
                client.quit()
            except smtplib.SMTPAuthenticationError as e:
                return {"success": False, "error": f"SMTP login failed ({e.smtp_code}): check the SMTP username and password."}
            except (socket.timeout, TimeoutError, ConnectionError, OSError, smtplib.SMTPException) as e:
                return {
                    "success": False,
                    "error": f"Could not connect to SMTP {smtp['host']}:{smtp['port']} ({smtp['security']}): {e}",
                }
        if imap:
            try:
                client = open_imap(**imap)
                client.logout()
            except Exception as e:
                return {"success": False, "error": f"IMAP {imap['host']}:{imap['port']} failed: {e}"}
        return {"success": True}

    @staticmethod
    def get_forms():
        return {
            "label": "Email",
            "type": "form",
            "children": [
                {
                    "name": "smtp_host",
                    "type": "text",
                    "label": "SMTP Host",
                    "placeholder": "email-smtp.us-east-1.amazonaws.com",
                    "description": "Server used to send email. For AWS SES: email-smtp.<region>.amazonaws.com. Leave empty if you only read mail over IMAP.",
                    "required": False,
                },
                {
                    "name": "smtp_port",
                    "type": "text",
                    "label": "SMTP Port",
                    "placeholder": "587",
                    "description": "587 (STARTTLS, default), 465 (SSL/TLS), or 25/2587/2465.",
                    "required": False,
                },
                {
                    "name": "smtp_security",
                    "type": "select",
                    "label": "SMTP Security",
                    "required": False,
                    "options": [
                        {"label": "STARTTLS (port 587)", "value": "starttls"},
                        {"label": "SSL/TLS (port 465)", "value": "ssl"},
                        {"label": "None (trusted relay only)", "value": "none"},
                    ],
                    "default": "starttls",
                },
                {
                    "name": "smtp_username",
                    "type": "text",
                    "label": "SMTP Username",
                    "placeholder": "AWS SES SMTP username (AKIA...)",
                    "description": "For AWS SES use the SMTP credentials from the SES console, not your IAM access key.",
                    "required": False,
                },
                {
                    "name": "smtp_password",
                    "type": "text/password",
                    "label": "SMTP Password",
                    "required": False,
                },
                {
                    "name": "from_address",
                    "type": "text",
                    "label": "From Address",
                    "placeholder": "alerts@example.com",
                    "description": "Sender used when a message has no From. Required for sending; for AWS SES it must be a verified identity.",
                    "required": False,
                },
                {
                    "name": "host",
                    "type": "text",
                    "label": "IMAP Host (optional)",
                    "placeholder": "imap.example.com",
                    "description": "Only needed to read a mailbox (inventory, mail-reading actions).",
                    "required": False,
                },
                {
                    "name": "port",
                    "type": "text",
                    "label": "IMAP Port",
                    "placeholder": "993",
                    "description": "993 (SSL, default) or 143 (STARTTLS).",
                    "required": False,
                },
                {
                    "name": "username",
                    "type": "text",
                    "label": "IMAP Username",
                    "placeholder": "user@example.com",
                    "description": "Also used for SMTP when SMTP Username is empty.",
                    "required": False,
                },
                {
                    "name": "password",
                    "type": "text/password",
                    "label": "IMAP Password",
                    "description": "Also used for SMTP when SMTP Password is empty.",
                    "required": False,
                },
            ],
        }

    @staticmethod
    def get_schema(ctx=None):
        return IMAPIntegration

    @staticmethod
    def supported_connection_interfaces():
        return [
            ConnectionInterfaces.PYTHON_SDK,
            ConnectionInterfaces.STEAMPIPE,
        ]

    def build_python_exec_combinations_hook(
        self, payload_task: PayloadTask, client_definitions: List[SDKClient]
    ) -> list:
        envs = payload_task.creds.envs
        wanted = {client.name for client in client_definitions}
        clients = {}
        if "imap_ssl_connection" in wanted:
            if not envs.get("IMAP_HOST"):
                raise ValueError("This Email integration has no IMAP host; add one to read mail.")
            clients["imap_ssl_connection"] = open_imap(
                envs["IMAP_HOST"],
                envs.get("IMAP_PORT"),
                envs.get("IMAP_USERNAME"),
                envs.get("IMAP_PASSWORD"),
            )
        if "smtp_client" in wanted:
            if not envs.get("SMTP_HOST"):
                raise ValueError("This Email integration has no SMTP host; add one to send mail.")
            clients["smtp_client"] = open_smtp(
                envs["SMTP_HOST"],
                envs.get("SMTP_PORT"),
                envs.get("SMTP_SECURITY"),
                envs.get("SMTP_USERNAME"),
                envs.get("SMTP_PASSWORD"),
                envs.get("SMTP_FROM"),
            )
        return [
            {
                "clients": clients,
                "params": self.prepare_params(payload_task.params),
                "context": payload_task.context,
            }
        ]

    def generate_steampipe_creds(self) -> SteampipeCreds:
        envs = {
            "IMAP_HOST": self.integration.host,
            "IMAP_PORT": self.integration.port,
            "IMAP_LOGIN": self.integration.username,
            "IMAP_PASSWORD": self.integration.password,
        }
        conf_path = "~/.steampipe/config/imap.spc"
        config = """connection "imap" {
  plugin   = "imap"
}"""
        return SteampipeCreds(
            envs=envs,
            plugin_name="imap",
            connection_name="imap",
            conf_path=conf_path,
            config=config,
        )

    def generate_python_sdk_creds(self) -> SDKCreds:
        envs = {}
        imap = self._imap_settings()
        if imap:
            envs.update(
                {
                    "IMAP_HOST": imap["host"],
                    "IMAP_PORT": imap["port"],
                    "IMAP_USERNAME": imap["username"],
                    "IMAP_PASSWORD": imap["password"],
                }
            )
        smtp = self._smtp_settings()
        if smtp:
            envs.update(
                {
                    "SMTP_HOST": smtp["host"],
                    "SMTP_PORT": smtp["port"],
                    "SMTP_SECURITY": smtp["security"],
                    "SMTP_USERNAME": smtp["username"],
                    "SMTP_PASSWORD": smtp["password"],
                    "SMTP_FROM": smtp["from_address"],
                }
            )
        return SDKCreds(envs={k: v for k, v in envs.items() if v is not None})
