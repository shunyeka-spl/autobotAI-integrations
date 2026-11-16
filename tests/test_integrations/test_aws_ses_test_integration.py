"""AWS SES integration test: passes only when SES can actually send."""

from botocore.exceptions import ClientError

from autobotAI_integrations.integrations.aws_ses import AwsSesService


class _Sts:
    def get_caller_identity(self):
        return {"Account": "123456789012"}


class _Sesv2:
    def __init__(self, identities=(), account=None, error_code=None):
        self.identities = list(identities)
        self.account = account if account is not None else {
            "SendingEnabled": True, "ProductionAccessEnabled": True,
        }
        self.error_code = error_code

    def list_email_identities(self, **kwargs):
        if self.error_code:
            raise ClientError({"Error": {"Code": self.error_code, "Message": "no"}},
                              "ListEmailIdentities")
        return {"EmailIdentities": self.identities}

    def get_account(self):
        return self.account


def _ident(name, kind="EMAIL_ADDRESS", status="SUCCESS", sending=True):
    return {"IdentityName": name, "IdentityType": kind,
            "VerificationStatus": status, "SendingEnabled": sending}


def _service(sesv2, **fields):
    svc = AwsSesService({}, {
        "userId": "root@acme.com", "cspName": "aws_ses", "alias": "ses",
        "region": "us-east-1", "roleArn": "arn:aws:iam::1:role/x",
        "externalId": "ext", **fields,
    })
    svc._get_aws_client = lambda name: {"sts": _Sts(), "sesv2": sesv2}[name]
    return svc


def test_fails_without_any_verified_identity():
    sesv2 = _Sesv2([_ident("a@acme.com", status="PENDING"),
                    _ident("acme.com", kind="DOMAIN", sending=False)])
    result = _service(sesv2)._test_integration()
    assert result["success"] is False
    assert "no verified sender" in result["error"]
    assert "us-east-1" in result["error"]


def test_passes_with_a_verified_domain_and_lists_it():
    result = _service(_Sesv2([_ident("Acme.com", kind="DOMAIN")]))._test_integration()
    assert result["success"] is True
    assert result["verified_identities"] == {"domains": ["acme.com"], "emails": []}
    assert result["warnings"] == []


def test_sandbox_is_a_warning_not_a_failure():
    sesv2 = _Sesv2([_ident("ops@acme.com")],
                   account={"SendingEnabled": True, "ProductionAccessEnabled": False})
    result = _service(sesv2)._test_integration()
    assert result["success"] is True
    assert "sandbox" in result["warnings"][0]


def test_paused_sending_fails():
    sesv2 = _Sesv2([_ident("ops@acme.com")], account={"SendingEnabled": False})
    assert _service(sesv2)._test_integration()["success"] is False


def test_from_address_must_be_covered():
    sesv2 = _Sesv2([_ident("acme.com", kind="DOMAIN")])
    assert _service(sesv2, from_address="alerts@acme.com")._test_integration()["success"]
    result = _service(sesv2, from_address="me@other.io")._test_integration()
    assert result["success"] is False
    assert "me@other.io" in result["error"]


def test_access_denied_names_the_missing_permission():
    result = _service(_Sesv2(error_code="AccessDeniedException"))._test_integration()
    assert result["success"] is False
    assert "ses:ListEmailIdentities" in result["error"]
