"""Email integration: SMTP-first (AWS SES SMTP), IMAP optional, legacy records intact."""

import base64
import socketserver
import threading
from email.message import EmailMessage
from types import SimpleNamespace

import pytest

import autobotAI_integrations.integrations.email as email_mod
from autobotAI_integrations.integrations.email import IMAPService, smtp_security_for


class _SMTPHandler(socketserver.StreamRequestHandler):
    """Plain SMTP with AUTH PLAIN/LOGIN — enough for smtplib."""

    def _w(self, line):
        self.wfile.write((line + "\r\n").encode())

    def handle(self):
        srv = self.server
        self._w("220 fake ESMTP")
        while True:
            raw = self.rfile.readline()
            if not raw:
                return
            line = raw.decode().rstrip("\r\n")
            cmd = line.split(" ", 1)[0].upper()
            if cmd in ("EHLO", "HELO"):
                self._w("250-fake")
                self._w("250 AUTH PLAIN LOGIN")
            elif cmd == "AUTH":
                parts = line.split(" ")
                if parts[1].upper() == "PLAIN":
                    blob = parts[2] if len(parts) > 2 else None
                    if blob is None:
                        self._w("334 ")
                        blob = self.rfile.readline().decode().strip()
                    _, user, pwd = base64.b64decode(blob).decode().split("\0")
                else:  # LOGIN
                    self._w("334 VXNlcm5hbWU6")
                    user = base64.b64decode(self.rfile.readline().strip()).decode()
                    self._w("334 UGFzc3dvcmQ6")
                    pwd = base64.b64decode(self.rfile.readline().strip()).decode()
                srv.logins.append((user, pwd))
                if (user, pwd) == srv.creds:
                    self._w("235 ok")
                else:
                    self._w("535 Authentication Credentials Invalid")
            elif cmd == "MAIL":
                srv.envelope = {"from": line.split(":", 1)[1].strip().strip("<>").split(">")[0]}
                self._w("250 ok")
            elif cmd == "RCPT":
                srv.envelope.setdefault("to", []).append(line.split(":", 1)[1].strip().strip("<>"))
                self._w("250 ok")
            elif cmd == "DATA":
                self._w("354 go")
                data = []
                while True:
                    d = self.rfile.readline().decode()
                    if d in (".\r\n", ".\n"):
                        break
                    data.append(d)
                srv.messages.append((srv.envelope, "".join(data)))
                self._w("250 queued")
            elif cmd == "RSET" or cmd == "NOOP":
                self._w("250 ok")
            elif cmd == "QUIT":
                self._w("221 bye")
                return
            else:
                self._w("502 no")


@pytest.fixture
def smtp_server():
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _SMTPHandler)
    srv.daemon_threads = True
    srv.logins, srv.messages, srv.envelope = [], [], {}
    srv.creds = ("AKIASESSMTPUSER", "ses-smtp-secret")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


_BASE = {"userId": "t@pytest.com", "cspName": "email", "alias": "mail", "accountId": "acc"}


def _svc(**fields):
    return IMAPService(ctx=None, integration={**_BASE, **fields})


def _ses(server, **over):
    fields = {
        "smtp_host": "127.0.0.1",
        "smtp_port": str(server.server_address[1]),
        "smtp_security": "none",  # the fake has no TLS; TLS selection is tested separately
        "smtp_username": "AKIASESSMTPUSER",
        "smtp_password": "ses-smtp-secret",
        "from_address": "alerts@example.com",
    }
    fields.update(over)
    return _svc(**fields)


def _clients(svc, *names):
    creds = svc.generate_python_sdk_creds()
    task = SimpleNamespace(creds=creds, params=[], context={})
    defs = [SimpleNamespace(name=n) for n in names]
    return svc.build_python_exec_combinations_hook(task, defs)[0]["clients"]


# -- SES-style SMTP-only setup -------------------------------------------------


def test_ses_smtp_only_connection_test_passes_without_imap(smtp_server):
    assert _ses(smtp_server).is_active()["success"] is True
    assert smtp_server.logins == [("AKIASESSMTPUSER", "ses-smtp-secret")]


def test_bad_smtp_password_fails_the_connection_test(smtp_server):
    res = _ses(smtp_server, smtp_password="wrong")._test_integration()
    assert res["success"] is False
    assert "SMTP login failed (535)" in res["error"]


def test_ses_style_username_requires_a_from_address(smtp_server):
    res = _ses(smtp_server, from_address=None)._test_integration()
    assert res["success"] is False
    assert "From Address" in res["error"]


def test_nothing_configured_explains_what_to_enter():
    res = _svc()._test_integration()
    assert res["success"] is False and "SMTP host" in res["error"]


def test_smtp_client_fills_missing_from_and_skips_imap(smtp_server, monkeypatch):
    def no_imap(*a, **k):
        raise AssertionError("IMAP must not be opened for an SMTP-only action")

    monkeypatch.setattr(email_mod, "open_imap", no_imap)
    clients = _clients(_ses(smtp_server), "smtp_client")
    assert set(clients) == {"smtp_client"}

    msg = EmailMessage()  # action left From unset, like the library notify action
    msg["To"] = "ops@example.com"
    msg["Subject"] = "hi"
    msg.set_content("body")
    clients["smtp_client"].send_message(msg)
    clients["smtp_client"].sendmail("", ["ops@example.com"], "Subject: x\r\n\r\nraw")
    clients["smtp_client"].quit()

    (env1, data1), (env2, _) = smtp_server.messages
    assert env1["from"] == "alerts@example.com" and env1["to"] == ["ops@example.com"]
    assert "From: alerts@example.com" in data1
    assert env2["from"] == "alerts@example.com"


def test_explicit_from_is_kept(smtp_server):
    client = _clients(_ses(smtp_server), "smtp_client")["smtp_client"]
    msg = EmailMessage()
    msg["From"] = "other@example.com"
    msg["To"] = "ops@example.com"
    msg.set_content("x")
    client.send_message(msg)
    client.quit()
    assert smtp_server.messages[-1][0]["from"] == "other@example.com"


def test_imap_client_requested_without_imap_host_is_a_clear_error(smtp_server):
    with pytest.raises(ValueError, match="no IMAP host"):
        _clients(_ses(smtp_server), "imap_ssl_connection")


def test_sdk_envs_for_ses():
    envs = _svc(
        smtp_host="email-smtp.us-east-1.amazonaws.com",
        smtp_security="starttls",
        smtp_username="AKIA1",
        smtp_password="p",
        from_address="alerts@example.com",
    ).generate_python_sdk_creds().envs
    assert envs == {
        "SMTP_HOST": "email-smtp.us-east-1.amazonaws.com",
        "SMTP_PORT": "587",
        "SMTP_SECURITY": "starttls",
        "SMTP_USERNAME": "AKIA1",
        "SMTP_PASSWORD": "p",
        "SMTP_FROM": "alerts@example.com",
    }


# -- TLS mode selection --------------------------------------------------------


@pytest.mark.parametrize(
    "port, security, expected",
    [("587", None, "starttls"), ("465", None, "ssl"), ("2465", None, "ssl"),
     ("25", None, "starttls"), ("465", "starttls", "starttls"), ("25", "none", "none")],
)
def test_security_defaults_from_port(port, security, expected):
    assert smtp_security_for(port, security) == expected


def test_open_smtp_uses_starttls_on_587_and_ssl_on_465(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, **kw):
            calls.append(("plain", host, port))

        def ehlo(self):
            pass

        def starttls(self, context=None):
            calls.append(("starttls",))

        def login(self, u, p):
            calls.append(("login", u))

    class FakeSSL(FakeSMTP):
        def __init__(self, host, port, **kw):
            calls.append(("ssl", host, port))

    monkeypatch.setattr(email_mod, "_SMTP", FakeSMTP)
    monkeypatch.setattr(email_mod, "_SMTP_SSL", FakeSSL)
    email_mod.open_smtp("email-smtp.eu-west-1.amazonaws.com", "587", None, "AKIA", "p")
    assert calls == [("plain", "email-smtp.eu-west-1.amazonaws.com", 587), ("starttls",), ("login", "AKIA")]
    calls.clear()
    email_mod.open_smtp("smtp.example.com", "465", None, "u", "p")
    assert calls == [("ssl", "smtp.example.com", 465), ("login", "u")]


# -- records saved by the old IMAP-first form ------------------------------------


def test_legacy_record_keeps_shared_creds_guessed_host_and_465():
    envs = _svc(host="imap.gmail.com", username="me@gmail.com", password="app-pw").generate_python_sdk_creds().envs
    assert envs["IMAP_HOST"] == "imap.gmail.com" and envs["IMAP_PORT"] == "993"
    assert envs["SMTP_HOST"] == "smtp.gmail.com"
    assert (envs["SMTP_PORT"], envs["SMTP_SECURITY"]) == ("465", "ssl")
    assert (envs["SMTP_USERNAME"], envs["SMTP_PASSWORD"]) == ("me@gmail.com", "app-pw")
    assert envs["SMTP_FROM"] == "me@gmail.com"  # mailbox login is an address


def test_legacy_record_with_smtp_host_still_uses_465():
    envs = _svc(
        host="imap.example.com", smtp_host="mail.example.com", username="me@example.com", password="p"
    ).generate_python_sdk_creds().envs
    assert (envs["SMTP_HOST"], envs["SMTP_PORT"], envs["SMTP_SECURITY"]) == ("mail.example.com", "465", "ssl")


def test_legacy_record_connection_test_only_checks_imap(monkeypatch):
    seen = []
    monkeypatch.setattr(email_mod, "open_imap", lambda **k: seen.append(k) or SimpleNamespace(logout=lambda: None))
    monkeypatch.setattr(email_mod, "open_smtp", lambda **k: pytest.fail("legacy records were never SMTP-tested"))
    assert _svc(host="imap.example.com", username="u@example.com", password="p")._test_integration() == {"success": True}
    assert seen == [{"host": "imap.example.com", "port": "993", "username": "u@example.com", "password": "p"}]


def test_form_makes_imap_optional():
    fields = {f["name"]: f for f in IMAPService.get_forms()["children"]}
    assert not any(f.get("required") for f in fields.values())
    assert list(fields)[:6] == ["smtp_host", "smtp_port", "smtp_security", "smtp_username", "smtp_password", "from_address"]
