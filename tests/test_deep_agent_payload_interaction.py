"""Contract test for the allow_user_interaction field on DeepAgentPayload.

This field is the cross-repo switch consumed by autobotAI-core (producer) and
autobotAI-agents (runtime). It must default to True (interactive) and be
distinct from `autonomous`.
"""

from autobotAI_integrations.deep_agent_schema import DeepAgentPayload


def _payload(**overrides):
    base = dict(job_id="j", tasks=[], user_prompt="hi")
    base.update(overrides)
    return DeepAgentPayload(**base)


def test_defaults_to_interactive():
    assert _payload().allow_user_interaction is True


def test_explicit_false_is_headless():
    assert _payload(allow_user_interaction=False).allow_user_interaction is False


def test_independent_of_autonomous():
    # The two flags are orthogonal: a headless run can still be autonomous,
    # and an interactive run can require approve-before-act.
    p = _payload(autonomous=False, allow_user_interaction=True)
    assert p.autonomous is False
    assert p.allow_user_interaction is True


def test_platform_catalog_defaults_to_empty_list():
    """Backward compatibility: platform_catalog is optional and defaults to []."""
    p = _payload()
    assert p.platform_catalog == []
    assert isinstance(p.platform_catalog, list)


def test_platform_catalog_accepts_list_of_dicts():
    """platform_catalog can hold a discovery catalog of capability dicts."""
    catalog = [
        {"slug": "feature_1", "name": "Feature 1", "description": "First feature", "enabled": True},
        {"slug": "feature_2", "name": "Feature 2", "description": "Second feature", "enabled": False},
    ]
    p = _payload(platform_catalog=catalog)
    assert p.platform_catalog == catalog


def test_platform_catalog_roundtrips_via_model_dump():
    """platform_catalog survives serialization and deserialization."""
    catalog = [
        {"slug": "auth", "name": "Authentication", "description": "User auth", "enabled": True},
    ]
    p = _payload(platform_catalog=catalog)
    dumped = p.model_dump()
    assert dumped["platform_catalog"] == catalog
    # Reconstruct from dump
    p2 = DeepAgentPayload(**dumped)
    assert p2.platform_catalog == catalog
