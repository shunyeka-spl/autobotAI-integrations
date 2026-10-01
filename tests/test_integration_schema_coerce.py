from boto3.dynamodb.types import Binary

from autobotAI_integrations.integration_schema import IntegrationSchema

BASE = {"userId": "root@x.com", "accountId": "acc-1", "cspName": "aws", "alias": "prod"}


def test_binary_utf8_value_is_decoded():
    model = IntegrationSchema(**BASE, arn=Binary(b"arn:autobotai:integration/prod"))
    assert model.arn == "arn:autobotai:integration/prod"


def test_undecodable_binary_becomes_none_instead_of_raising():
    # Previously: TypeError: __str__ returned non-string (type bytes)
    model = IntegrationSchema(**BASE, arn=Binary(b"\x8d\x86\xedF\x00\xff"))
    assert model.arn is None


def test_raw_bytes_are_decoded():
    model = IntegrationSchema(**BASE, lastUsed=b"2026-10-01T00:00:00")
    assert model.lastUsed == "2026-10-01T00:00:00"


def test_non_str_values_still_coerced():
    model = IntegrationSchema(**{**BASE, "accountId": 123456789012})
    assert model.accountId == "123456789012"
