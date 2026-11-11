"""CLI connection interface: how an integration exposes its vendor CLI.

An integration opts in by implementing three hooks on its service class:

- ``cli_spec()`` (classmethod) returns a ``CLISpec``: the binary, how to filter
  output, which subcommands/flags are off limits. ``None`` (the default) means
  the integration has no CLI; declaring ``ConnectionInterfaces.CLI`` alone is
  not enough.
- ``generate_cli_creds()`` returns ``CLICreds`` whose ``envs`` carry the
  credentials. Core calls it while building the agent payload.
- ``prepare_cli_session()`` (classmethod) turns those envs into a
  ``CLISession`` for one command: the child environment, any login step, args
  to append, and the secret values to redact from output. The agent calls it
  for every run, inside a fresh per-run HOME it deletes afterwards.

The agent owns execution (no shell, environment built from scratch, fan-out,
redaction); the integration owns everything vendor specific. Adding a CLI for
another integration is these three hooks plus installing the binary in the
agent images.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CLISpec(BaseModel):
    binary: str
    display_name: str
    # One realistic command (without the binary) shown to the model.
    example: str = ""
    # How to narrow output, since there is no shell to pipe through.
    filter_hint: str = ""
    # Leading subcommands that would print, mint or replace credentials.
    blocked_subcommands: List[List[str]] = Field(default_factory=list)
    blocked_flags: List[str] = Field(default_factory=list)
    # Global options that take a value and may precede the subcommand, so the
    # value is not taken for the first subcommand when checking the block list.
    global_value_flags: List[str] = Field(default_factory=list)
    # True when the agent may fan a command out across regions.
    supports_regions: bool = False

    def public_dict(self) -> Dict[str, Any]:
        """What the integration-types API exposes to the UI."""
        return {"binary": self.binary, "display_name": self.display_name}


class CLISession(BaseModel):
    env: Dict[str, str] = Field(default_factory=dict)
    # Commands (args after the binary) to run first, e.g. a service-principal
    # login. A non-zero exit fails the run.
    setup_commands: List[List[str]] = Field(default_factory=list)
    # Appended to the user's command, e.g. a default --subscription.
    extra_args: List[str] = Field(default_factory=list)
    # Values to mask in anything returned to the model.
    secrets: List[str] = Field(default_factory=list)
    # Set instead of the above when the session cannot be prepared.
    error: Optional[str] = None


def has_flag(argv: List[str], flag: str) -> bool:
    return any(t == flag or t.startswith(flag + "=") for t in argv)


def integration_field(integration: Any, field: str, default: Any = None) -> Any:
    if integration is None:
        return default
    if isinstance(integration, dict):
        return integration.get(field, default)
    return getattr(integration, field, default)
