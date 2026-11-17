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


def test_verified_domain_covers_subdomain_senders():
    sesv2 = _Sesv2([_ident("acme.com", kind="DOMAIN")])
    assert _service(sesv2, from_address="Alerts@Mail.Acme.com")._test_integration()["success"]
    # A look-alike domain is not covered.
    assert not _service(sesv2, from_address="a@notacme.com")._test_integration()["success"]


def test_verified_address_matches_case_insensitively():
    sesv2 = _Sesv2([_ident("Ops@Other.io")])
    assert _service(sesv2, from_address="ops@other.io")._test_integration()["success"]


def test_access_denied_names_the_missing_permission():
    result = _service(_Sesv2(error_code="AccessDeniedException"))._test_integration()
    assert result["success"] is False
    assert "ses:ListEmailIdentities" in result["error"]


def test_new_integration_runs_the_checks_by_default():
    svc = _service(_Sesv2())
    assert svc.integration.skip_test is False
    assert svc._test_integration()["success"] is False


def test_stored_integration_without_the_field_skips_the_checks():
    """Backward compatibility: records saved before skip_test existed."""
    svc = _service(_Sesv2(), createdAt="2026-01-01T00:00:00")
    assert svc.integration.skip_test is True
    result = svc._test_integration()
    assert result["success"] is True
    assert "skipped" in result["warnings"][0]


def test_explicit_skip_test_wins_over_the_default():
    assert _service(_Sesv2(), createdAt="2026-01-01", skip_test=False).integration.skip_test is False
    assert _service(_Sesv2(), skip_test="true").integration.skip_test is True
    assert _service(_Sesv2(), skip_test="false").integration.skip_test is False


def test_skip_makes_no_aws_calls():
    svc = _service(_Sesv2(), skip_test=True)
    svc._get_aws_client = lambda name: (_ for _ in ()).throw(AssertionError(name))
    assert svc._test_integration()["success"] is True
