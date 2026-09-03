"""Persistent settings for the recipe-authoring agent.

The engine's one configuration file. It records which AI provider the authoring
agent should use and, per provider, which model — the two things a user would
otherwise have to repeat on every `agent plan` / `agent draft` call, or pin into
an environment variable.

NEVER PUT A SECRET IN THIS FILE. No API key, token, or password belongs here,
and no field for one should be added. `claude`, `copilot`, and `codex` each own
their own login and auth state; this file only ever holds a provider name and a
model name. That is what keeps it safe to read, diff, copy between machines, and
paste into a bug report.

This is authoring configuration only. It has no bearing on what a recipe does
when it runs.

The file lives beside the user's recipe collections, in the workspace root that
`sources.workspace_root()` already defines:

    ${XDG_CONFIG_HOME:-~/.config}/omarchy-recipes/config.json

`OMARCHY_RECIPES_HOME` relocates it, exactly as it relocates the collections, so
tests never read or write the developer's own settings.
"""

from __future__ import annotations

import copy
import json
from typing import Any
from pathlib import Path

from . import sources as sources_mod
from .core import RecipeError

# What a key may be, for error messages and for rejecting anything else.
KNOWN_KEYS = "agent.provider, agent.models.<provider>"


def _default_config() -> dict[str, Any]:
    """The config as it ships.

    `models` gets one slot per registered provider, derived from the provider
    registry rather than hardcoded, so adding a provider stays what the design
    promises: one adapter function plus one registry entry in `agent.py`.

    Both `provider` and every model default to null, meaning "not configured".
    Null is not the same as a choice: it is what lets the engine fall back to
    the first installed provider, and lets each provider pick its own default
    model. Defaulting `provider` to a literal "claude" here would quietly make
    that fallback unreachable and break machines that have codex but not claude.
    """
    from . import agent as agent_mod

    return {
        "agent": {
            "provider": None,
            "models": {name: None for name in agent_mod.PROVIDER_ARGV},
        }
    }


def config_path() -> Path:
    """Where the config file lives.

    Resolved on every call rather than cached, so a test that redirects
    `OMARCHY_RECIPES_HOME` is honoured without having to reimport this module.
    """
    return sources_mod.workspace_root() / "config.json"


def load() -> dict[str, Any]:
    """Read the config, filling in anything the file does not mention.

    A missing file is not an error — it is the ordinary state before the user
    has configured anything. A file that exists but cannot be read or parsed
    *is* an error: silently falling back to defaults there would hide a typo and
    leave the user wondering why their setting had no effect.
    """
    path = config_path()
    if not path.exists():
        return _default_config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise RecipeError(f"cannot read {path}: {e}") from e
    except ValueError as e:
        raise RecipeError(f"{path} is not valid JSON: {e}") from e
    return _merge_with_defaults(data)


def _merge_with_defaults(data: dict[str, Any]) -> dict[str, Any]:
    """Overlay a stored config onto the defaults.

    Deep-copied first: the defaults are a fresh structure every time, so a
    caller mutating what it gets back can never edit the next caller's view.
    """
    result = _default_config()
    if not isinstance(data, dict):
        return result
    agent = data.get("agent")
    if isinstance(agent, dict):
        models = agent.get("models")
        result["agent"].update({k: v for k, v in agent.items() if k != "models"})
        if isinstance(models, dict):
            result["agent"]["models"].update(models)
    return result


def save(data: dict[str, Any]) -> None:
    """Write the config, creating the workspace directory if needed."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _normalize(key_path: str) -> str:
    """Accept `agent.model.<provider>` as an alias for `agent.models.<provider>`.

    Both spellings read naturally and confusing them is the obvious mistake to
    make, so neither is worth an error.
    """
    if key_path == "agent.model" or key_path.startswith("agent.model."):
        return "agent.models" + key_path[len("agent.model"):]
    return key_path


def get(key_path: str) -> Any:
    """Read one value by dotted path, e.g. `agent.provider`."""
    keys = _normalize(key_path).split(".")
    current: Any = load()
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            raise RecipeError(f"unknown config key: {key_path!r}; known keys are {KNOWN_KEYS}")
        current = current[key]
    return current


def set_value(key_path: str, value: Any) -> None:
    """Write one value by dotted path, rejecting anything not in the schema.

    Validation happens before the file is touched, so a rejected `set` leaves
    the existing config exactly as it was.
    """
    normalized = _normalize(key_path)
    keys = normalized.split(".")

    def unknown() -> RecipeError:
        return RecipeError(f"unknown config key: {key_path!r}; known keys are {KNOWN_KEYS}")

    if keys[0] != "agent" or len(keys) < 2:
        raise unknown()
    if keys[1] == "provider":
        if len(keys) != 2:
            raise unknown()
        # null clears the setting and restores the "first installed" fallback.
        if value is not None:
            _validate_provider(str(value))
    elif keys[1] == "models":
        if len(keys) != 3:
            raise RecipeError(
                f"use 'agent.models.<provider>' to set a model, e.g. agent.models.claude"
            )
        _validate_provider(keys[2])
    else:
        raise unknown()

    data = load()
    current = data
    for key in keys[:-1]:
        current = current.setdefault(key, {})
    current[keys[-1]] = value
    save(data)


def _validate_provider(name: str) -> None:
    """Reject a provider the engine has no adapter for."""
    from . import agent as agent_mod

    if name not in agent_mod.PROVIDER_ARGV:
        raise RecipeError(
            f"unknown provider {name!r}; available: {', '.join(sorted(agent_mod.PROVIDER_ARGV))}"
        )
