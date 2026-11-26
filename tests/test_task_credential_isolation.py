"""A task's credentials must not outlive the task in the worker process.

Live incident (2026-11-17): python_sdk_processor copied each task's
``creds.envs`` into ``os.environ`` and never removed them. The action task
processor is a warm Lambda that runs every tenant's tasks one after another, so
a tenant's code could read the AWS credentials of whichever tenant ran before
it. These tests replay that sequence.
"""
import os
import sys
import types
from unittest import mock

import pytest

from autobotAI_integrations import base
from autobotAI_integrations.base import BaseService, task_environment

TENANT_A = {
    "AWS_ACCESS_KEY_ID": "ASIATENANTA000000000",
    "AWS_SECRET_ACCESS_KEY": "tenant-a-secret",
    "AWS_SESSION_TOKEN": "tenant-a-token",
}


@pytest.fixture(autouse=True)
def _clean_env():
    saved = dict(os.environ)
    for key in TENANT_A:
        os.environ.pop(key, None)
    yield
    os.environ.clear()
    os.environ.update(saved)


def test_credentials_visible_only_inside_the_task():
    with task_environment(TENANT_A):
        assert os.environ["AWS_ACCESS_KEY_ID"] == TENANT_A["AWS_ACCESS_KEY_ID"]
    for key in TENANT_A:
        assert key not in os.environ


def test_restores_previous_values_and_drops_task_additions():
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["AWS_ACCESS_KEY_ID"] = "ASIAPLATFORM00000000"
    with task_environment({**TENANT_A, "AWS_REGION": "eu-west-1"}):
        os.environ["LEFT_BEHIND_BY_TASK_CODE"] = "x"
        os.environ.pop("AWS_REGION")
    assert os.environ["AWS_REGION"] == "us-east-1"
    assert os.environ["AWS_ACCESS_KEY_ID"] == "ASIAPLATFORM00000000"
    assert "LEFT_BEHIND_BY_TASK_CODE" not in os.environ
    assert "AWS_SESSION_TOKEN" not in os.environ


def test_restores_even_when_the_task_raises():
    with pytest.raises(RuntimeError):
        with task_environment(TENANT_A):
            raise RuntimeError("task failed")
    assert "AWS_ACCESS_KEY_ID" not in os.environ


def test_boto3_default_session_is_dropped_on_both_sides():
    fake_boto3 = types.SimpleNamespace(DEFAULT_SESSION="tenant-a-session")
    with mock.patch.dict(sys.modules, {"boto3": fake_boto3}):
        with task_environment(TENANT_A):
            assert fake_boto3.DEFAULT_SESSION is None
            fake_boto3.DEFAULT_SESSION = "created-by-task-code"
        assert fake_boto3.DEFAULT_SESSION is None


def test_next_tenant_cannot_see_previous_tenant_credentials():
    """Replays the warm-worker sequence: tenant A's task, then tenant B's."""
    seen = {}

    def run(self, payload_task):
        seen[payload_task.name] = {k: os.environ.get(k) for k in TENANT_A}
        return [], []

    def task(name, envs):
        creds = types.SimpleNamespace(envs=envs)
        return types.SimpleNamespace(name=name, creds=creds)

    service = BaseService.__new__(BaseService)
    with mock.patch.object(BaseService, "_python_sdk_processor", run):
        service.python_sdk_processor(task("tenant-a", TENANT_A))
        service.python_sdk_processor(task("tenant-b", {}))

    assert seen["tenant-a"] == TENANT_A
    assert seen["tenant-b"] == {k: None for k in TENANT_A}


def test_steampipe_config_is_removed_when_the_run_fails():
    service = BaseService.__new__(BaseService)
    creds = types.SimpleNamespace(plugin_name="aws", config="connection {}", envs={})
    payload_task = types.SimpleNamespace(creds=creds, executable="DROP everything")
    with mock.patch.object(base.subprocess, "run"), \
            mock.patch.object(BaseService, "set_steampipe_spc_config") as set_cfg, \
            mock.patch.object(BaseService, "clear_steampipe_spc_config") as clear_cfg:
        with pytest.raises(ValueError):
            service.execute_steampipe_task(payload_task)
    set_cfg.assert_called_once()
    clear_cfg.assert_called_once_with(plugin_name="aws")


def test_steampipe_config_contents_are_not_logged(tmp_path):
    service = BaseService.__new__(BaseService)
    with mock.patch.object(BaseService, "_get_steampipe_config_path", return_value=str(tmp_path / "aws.spc")), \
            mock.patch.object(base, "logger") as log:
        service.set_steampipe_spc_config("access_key = \"AKIASECRET\"", "aws")
    logged = " ".join(str(c) for c in log.method_calls)
    assert "AKIASECRET" not in logged
