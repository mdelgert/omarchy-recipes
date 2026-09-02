"""Configuration management for agent providers and models.

Stores persistent settings for which AI provider and model the recipe authoring
agent uses. Never stores secrets — provider CLIs own their auth/login state.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from .core import RecipeError

DEFAULT_CONFIG = {
    "agent": {
        "provider": "claude",
        "models": {"claude": None, "copilot": None, "codex": None},
    }
}


def config_path() -> Path:
    """Get the path to the config file.

    Respects OMARCHY_RECIPES_HOME for tests, falling back to XDG_CONFIG_HOME.
    This always computes the path fresh rather than caching it.
    """
    # Always compute fresh to respect test environment changes
    override = os.environ.get("OMARCHY_RECIPES_HOME")
    if override:
        base = Path(override)
    else:
        xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        base = xdg / "omarchy-recipes"
    return base / "config.json"


def load() -> dict[str, Any]:
    """Load config from disk, returning defaults if not found or corrupt."""
    path = config_path()
    if not path.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        # Merge with defaults to ensure all expected keys exist
        return _merge_with_defaults(data)
    except (OSError, ValueError) as e:
        raise RecipeError(f"cannot read config: {e}") from e


def _merge_with_defaults(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge config with defaults to handle schema evolution."""
    result = copy.deepcopy(DEFAULT_CONFIG)
    if not isinstance(data, dict):
        return result
    if "agent" in data and isinstance(data["agent"], dict):
        result["agent"].update(data["agent"])
        if "models" in data["agent"] and isinstance(data["agent"]["models"], dict):
            result["agent"]["models"].update(data["agent"]["models"])
    return result


def save(data: dict[str, Any]) -> None:
    """Write config to disk."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def get(key_path: str) -> Any:
    """Get a config value by dotted path (e.g. "agent.provider")."""
    data = load()
    keys = key_path.split(".")
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            raise RecipeError(f"config key not found: {key_path}")
        current = current[key]
    return current


def set_value(key_path: str, value: Any) -> None:
    """Set a config value by dotted path, validating known keys."""
    data = load()
    keys = key_path.split(".")

    # Validate the path and value
    if len(keys) == 1:
        raise RecipeError(f"cannot set top-level key {keys[0]!r}")

    if keys[0] == "agent":
        if keys[1] == "provider":
            _validate_provider(value)
        elif keys[1] == "models":
            if len(keys) < 3:
                raise RecipeError("use 'agent.models.<provider>' to set a model")
            provider = keys[2]
            _validate_provider(provider)
        else:
            raise RecipeError(f"unknown config key: agent.{keys[1]!r}")
    else:
        raise RecipeError(f"unknown config key: {keys[0]!r}")

    # Navigate to the parent and set the value
    current = data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value
    save(data)


def _validate_provider(name: str) -> None:
    """Ensure the provider name is known."""
    from . import agent as agent_mod
    valid = set(agent_mod.PROVIDER_ARGV.keys())
    if name not in valid:
        raise RecipeError(
            f"unknown provider {name!r}; available: {', '.join(sorted(valid))}"
        )
