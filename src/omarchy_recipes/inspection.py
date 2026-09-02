"""Read-only inspection of the machine, for conflict detection.

The authoring agent needs to know what is already configured before it proposes
a recipe. It gets that from here rather than by running its own shell commands,
which is what keeps the security boundary in the spec honest: the agent reads
structured facts, and only the recipe runner changes anything.

Every inspector:

* runs a fixed argv — nothing here is built from a caller's input
* only reads; no inspector installs, writes, starts, or stops anything
* reports `available: false` with a reason instead of raising, so "I could not
  look" is never mistaken for "there is nothing there"
* is bounded by a timeout, because a wedged command must not hang a UI
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

COMMAND_TIMEOUT = 5

# Hyprland reports a keybinding's modifiers as a bitmask. Ordered most
# significant first so a decoded combo reads the way a user would write it.
HYPR_MODMASK = ((64, "SUPER"), (8, "ALT"), (4, "CTRL"), (1, "SHIFT"))


@dataclass
class DomainResult:
    """What one inspector found, or why it could not look."""

    name: str
    available: bool = True
    items: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "available": self.available, "items": self.items, "error": self.error}


def _run(argv: list[str]) -> tuple[bool, str, str]:
    """Run a fixed argv and report success, stdout, and a reason on failure."""
    try:
        proc = subprocess.run(
            argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=COMMAND_TIMEOUT,
        )
    except FileNotFoundError:
        return False, "", f"{argv[0]} is not installed"
    except subprocess.TimeoutExpired:
        return False, "", f"{argv[0]} did not respond within {COMMAND_TIMEOUT}s"
    except OSError as e:
        return False, "", f"could not run {argv[0]}: {e}"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        return False, "", detail[0] if detail else f"{argv[0]} exited {proc.returncode}"
    return True, proc.stdout, ""


def decode_hypr_modmask(mask: int) -> list[str]:
    return [name for bit, name in HYPR_MODMASK if mask & bit]


def normalize_keybinding(combo: str) -> str:
    """Canonical form of a shortcut so equivalent spellings compare equal.

    `SUPER+Return`, `super + return`, and `Mod4 + Enter` all name the same key,
    and a conflict check that missed that would be worse than no check at all.
    """
    text = str(combo or "").strip()
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r"[+\s]+", text) if p.strip()]
    aliases = {
        "MOD4": "SUPER", "LOGO": "SUPER", "META": "SUPER", "WIN": "SUPER", "SUPER_L": "SUPER",
        "CONTROL": "CTRL", "MOD1": "ALT",
        "ENTER": "RETURN", "ESC": "ESCAPE", "SPACEBAR": "SPACE",
    }
    mods: list[str] = []
    keys: list[str] = []
    for part in parts:
        upper = aliases.get(part.upper(), part.upper())
        if upper in {"SUPER", "ALT", "CTRL", "SHIFT"}:
            if upper not in mods:
                mods.append(upper)
        else:
            keys.append(upper)
    ordered = [m for _bit, m in HYPR_MODMASK if m in mods]
    return " + ".join(ordered + keys)


# ---------------------------------------------------------------- inspectors


def inspect_keybindings() -> DomainResult:
    ok, out, err = _run(["hyprctl", "-j", "binds"])
    if not ok:
        return DomainResult("keybindings", available=False, error=err)
    try:
        binds = json.loads(out)
    except ValueError:
        return DomainResult("keybindings", available=False, error="hyprctl returned unreadable JSON")
    items = []
    for bind in binds:
        if not isinstance(bind, dict):
            continue
        key = str(bind.get("key") or "")
        if not key:
            continue
        combo = normalize_keybinding(" + ".join(decode_hypr_modmask(int(bind.get("modmask") or 0)) + [key]))
        items.append({
            "combo": combo,
            "description": str(bind.get("description") or ""),
            "dispatcher": str(bind.get("dispatcher") or ""),
            "submap": str(bind.get("submap") or ""),
        })
    return DomainResult("keybindings", items=items)


def inspect_packages() -> DomainResult:
    ok, out, err = _run(["pacman", "-Qq"])
    if not ok:
        return DomainResult("packages", available=False, error=err)
    return DomainResult("packages", items=[{"name": line.strip()} for line in out.splitlines() if line.strip()])


def inspect_services() -> DomainResult:
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for scope, argv in (
        ("system", ["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--plain", "--no-pager"]),
        ("user", ["systemctl", "--user", "list-units", "--type=service", "--all", "--no-legend", "--plain", "--no-pager"]),
    ):
        ok, out, err = _run(argv)
        if not ok:
            errors.append(f"{scope}: {err}")
            continue
        for line in out.splitlines():
            fields = line.split()
            if len(fields) < 4 or not fields[0].endswith(".service"):
                continue
            items.append({"name": fields[0], "scope": scope, "load": fields[1], "active": fields[2], "sub": fields[3]})
    if not items and errors:
        return DomainResult("services", available=False, error="; ".join(errors))
    return DomainResult("services", items=items, error="; ".join(errors))


def inspect_ports() -> DomainResult:
    ok, out, err = _run(["ss", "-tulnH"])
    if not ok:
        return DomainResult("ports", available=False, error=err)
    items = []
    for line in out.splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        protocol = fields[0]
        local = fields[4]
        # Split host:port from the right so IPv6 literals survive intact.
        host, _, port = local.rpartition(":")
        if not port.isdigit():
            continue
        items.append({"port": int(port), "protocol": protocol, "address": host})
    return DomainResult("ports", items=items)


def inspect_mounts() -> DomainResult:
    try:
        raw = Path("/proc/mounts").read_text()
    except OSError as e:
        return DomainResult("mounts", available=False, error=f"could not read /proc/mounts: {e}")
    items = []
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        # /proc/mounts octal-escapes spaces and friends in the path.
        target = fields[1].encode().decode("unicode_escape")
        items.append({"target": target, "source": fields[0], "fstype": fields[2]})
    return DomainResult("mounts", items=items)


def inspect_containers() -> DomainResult:
    ok, out, err = _run(["docker", "ps", "-a", "--format", "{{json .}}"])
    if not ok:
        return DomainResult("containers", available=False, error=err)
    items = []
    for line in out.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        items.append({"name": str(row.get("Names") or ""), "image": str(row.get("Image") or ""), "status": str(row.get("Status") or "")})
    return DomainResult("containers", items=items)


# Names whose values must never be echoed into an agent prompt or a log.
SECRET_ENV_RE = re.compile(r"(TOKEN|SECRET|PASSWORD|PASSWD|APIKEY|API_KEY|CREDENTIAL|PRIVATE_KEY|SESSION)", re.IGNORECASE)


def inspect_environment() -> DomainResult:
    items = []
    for name in sorted(os.environ):
        secret = bool(SECRET_ENV_RE.search(name))
        items.append({"name": name, "value": "<redacted>" if secret else os.environ[name], "secret": secret})
    return DomainResult("environment", items=items)


# Files an Omarchy user is expected to edit. Which of these exist decides where
# a recipe should write, and it differs between Omarchy releases: a recipe that
# appends a keybinding to `bindings.conf` on a machine using `bindings.lua`
# writes to a file nothing reads. The agent must be told, not left to guess.
USER_CONFIG_CANDIDATES = (
    ("hypr-bindings", "~/.config/hypr/bindings.lua"),
    ("hypr-bindings-legacy", "~/.config/hypr/bindings.conf"),
    ("hypr-main", "~/.config/hypr/hyprland.lua"),
    ("hypr-main-legacy", "~/.config/hypr/hyprland.conf"),
    ("hypr-monitors", "~/.config/hypr/monitors.lua"),
    ("hypr-input", "~/.config/hypr/input.lua"),
    ("hypr-looknfeel", "~/.config/hypr/looknfeel.lua"),
    ("hypr-autostart", "~/.config/hypr/autostart.lua"),
    ("omarchy-menu-extension", "~/.config/omarchy/extensions/omarchy-menu.jsonc"),
    ("omarchy-shell", "~/.config/omarchy/shell.json"),
)


def inspect_config_files() -> DomainResult:
    items = []
    for name, raw in USER_CONFIG_CANDIDATES:
        path = Path(os.path.expanduser(raw))
        items.append({
            "name": name,
            "path": str(path),
            "exists": path.is_file(),
            "format": "lua" if path.suffix == ".lua" else path.suffix.lstrip(".") or "text",
        })
    return DomainResult("config-files", items=items)


INSPECTORS: dict[str, Callable[[], DomainResult]] = {
    "config-files": inspect_config_files,
    "keybindings": inspect_keybindings,
    "packages": inspect_packages,
    "services": inspect_services,
    "ports": inspect_ports,
    "mounts": inspect_mounts,
    "containers": inspect_containers,
    "environment": inspect_environment,
}


def inspect(domains: list[str] | None = None) -> dict[str, DomainResult]:
    """Snapshot the requested domains, or all of them.

    New domains are added by putting a function in INSPECTORS; nothing else in
    the engine, and nothing in the frontend, has to change.
    """
    wanted = domains or list(INSPECTORS)
    unknown = [d for d in wanted if d not in INSPECTORS]
    if unknown:
        raise ValueError(f"unknown inspection domain(s): {', '.join(sorted(unknown))}")
    return {name: INSPECTORS[name]() for name in wanted}


def config_option(key: str) -> DomainResult:
    """Read one Hyprland option. Separate from `inspect` because it is a lookup.

    The key is validated rather than trusted: it reaches an argv, so it can
    never become a second command, but a malformed key should still be a clear
    error instead of a confusing hyprctl failure.
    """
    if not re.fullmatch(r"[A-Za-z0-9_:.\-]+", str(key or "")):
        return DomainResult("config", available=False, error=f"invalid option name: {key!r}")
    ok, out, err = _run(["hyprctl", "-j", "getoption", key])
    if not ok:
        return DomainResult("config", available=False, error=err)
    # hyprctl answers an unknown key with plain text on a zero exit, so a JSON
    # decode failure here usually means "no such option", not a broken hyprctl.
    # Saying so is the difference between a useful answer and a shrug.
    text = out.strip()
    if text.lower().startswith("no such option"):
        return DomainResult("config", available=False, error=f"{key} is not a Hyprland option")
    try:
        data = json.loads(text)
    except ValueError:
        return DomainResult("config", available=False,
                            error=f"hyprctl gave an unreadable answer for {key}: {text[:80]}")
    return DomainResult("config", items=[{"key": key, **{k: v for k, v in data.items() if k != "set"}}])
