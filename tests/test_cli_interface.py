"""CLI connection interface: specs, sessions and the types metadata flag."""

import json
import os

import pytest

from autobotAI_integrations.cli import CLISession, CLISpec
from autobotAI_integrations.integrations import integration_service_factory as factory
from autobotAI_integrations.integrations.gcp import GCPCredentials

CLI_TYPES = {"aws": "aws", "azure": "az", "gcp": "gcloud"}


@pytest.mark.parametrize("integration_type,binary", CLI_TYPES.items())
def test_cli_types_expose_a_spec(integration_type, binary):
    spec = factory.get_service_cls(integration_type).cli_spec()
    assert isinstance(spec, CLISpec)
    assert spec.binary == binary
    assert factory._get_metadata_for_type(integration_type)["cli"] == spec.public_dict()


def test_declaring_the_interface_is_not_enough():
    # kubernetes lists ConnectionInterfaces.CLI but implements no CLI.
    assert "cli" in factory._get_metadata_for_type("kubernetes")["supported_interfaces"]
    assert factory._get_metadata_for_type("kubernetes")["cli"] is None


def test_aws_session_disables_ambient_creds(tmp_path):
    cls = factory.get_service_cls("aws")
    session = cls.prepare_cli_session(
        {"AWS_ACCESS_KEY_ID": "AKIA1", "AWS_SECRET_ACCESS_KEY": "s3cret-value"},
        {"activeRegions": ["eu-west-1"]},
        str(tmp_path),
    )
    assert session.error is None
    assert session.env["AWS_REGION"] == "eu-west-1"
    assert session.env["AWS_EC2_METADATA_DISABLED"] == "true"
    assert session.env["AWS_CONFIG_FILE"].startswith(str(tmp_path))
    assert "s3cret-value" in session.secrets
    # An explicit region wins over the configured one.
    assert cls.prepare_cli_session(
        {"AWS_ACCESS_KEY_ID": "a", "AWS_SECRET_ACCESS_KEY": "b"}, {}, str(tmp_path), region="ap-south-1"
    ).env["AWS_REGION"] == "ap-south-1"


def test_aws_session_without_creds_errors(tmp_path):
    session = factory.get_service_cls("aws").prepare_cli_session({}, {}, str(tmp_path))
    assert isinstance(session, CLISession) and session.error


def test_azure_session_logs_in_and_defaults_subscription(tmp_path):
    envs = {
        "AZURE_TENANT_ID": "t",
        "AZURE_CLIENT_ID": "c",
        "AZURE_CLIENT_SECRET": "azure-secret",
        "AZURE_SUBSCRIPTION_ID": "sub-1",
    }
    cls = factory.get_service_cls("azure")
    session = cls.prepare_cli_session(envs, {}, str(tmp_path), argv=["vm", "list"])
    assert session.setup_commands[0][0] == "login"
    assert session.extra_args == ["--subscription", "sub-1"]
    assert "AZURE_CLIENT_SECRET" not in session.env
    assert cls.prepare_cli_session(
        envs, {}, str(tmp_path), argv=["vm", "list", "--subscription", "other"]
    ).extra_args == []


def test_gcp_session_writes_private_key_file(tmp_path):
    sa = dict(
        type="service_account", project_id="proj", private_key_id="k",
        private_key="-----BEGIN PRIVATE KEY-----abc", client_email="sa@proj",
        client_id="1", auth_uri="a", token_uri="t",
        auth_provider_x509_cert_url="c", client_x509_cert_url="d",
    )
    raw = json.dumps(GCPCredentials(**sa).model_dump_json())
    session = factory.get_service_cls("gcp").prepare_cli_session(
        {"GOOGLE_APPLICATION_CREDENTIALS": raw}, {}, str(tmp_path)
    )
    key = session.env["CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"]
    assert oct(os.stat(key).st_mode & 0o777) == "0o600"
    assert json.load(open(key))["type"] == "service_account"
    assert session.env["CLOUDSDK_CORE_PROJECT"] == "proj"
    assert sa["private_key"] in session.secrets
