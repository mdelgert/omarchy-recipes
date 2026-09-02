"""Does the change a recipe wants to make collide with something already here?

The authoring agent declares the resources it intends to touch *before* it
writes a recipe, and this module answers against real inspection data. That
ordering is the point: the spec requires conflicts to be surfaced and resolved
by the user, not discovered after a recipe has already overwritten a binding.

A claim is a small dict naming one resource:

    {"type": "keybinding", "value": "SUPER + RETURN"}
    {"type": "package", "name": "docker"}
    {"type": "port", "port": 8080, "protocol": "tcp"}

Adding a resource type means adding a checker to CHECKERS. Nothing in the CLI
or the frontend needs to know the list.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import inspection
from .inspection import DomainResult

# What the caller should do about a finding.
CONFLICT = "conflict"   # something is already there
CLEAR = "clear"         # nothing in the way
UNKNOWN = "unknown"     # could not determine; never report this as clear

# How much a conflict matters. `block` means do not proceed without the user
# choosing; `warn` means proceed but say so.
BLOCK = "block"
WARN = "warn"
INFO = "info"


@dataclass
class Finding:
    resource: dict[str, Any]
    status: str = CLEAR
    detail: str = ""
    severity: str = INFO
    # Concrete choices to offer the user. The spec is explicit that the agent
    # must not silently pick one.
    resolutions: list[str] = field(default_factory=list)
    existing: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "status": self.status,
            "detail": self.detail,
            "severity": self.severity,
            "resolutions": self.resolutions,
            "existing": self.existing,
        }


class Snapshot:
    """Inspection data, fetched once per domain and only when a checker asks.

    Checking one package should not shell out for keybindings, containers, and
    every systemd unit on the machine. Tests construct this with canned data.
    """

    def __init__(self, preloaded: dict[str, DomainResult] | None = None):
        self._cache: dict[str, DomainResult] = dict(preloaded or {})

    def domain(self, name: str) -> DomainResult:
        if name not in self._cache:
            self._cache[name] = inspection.INSPECTORS[name]()
        return self._cache[name]


def field(resource: dict[str, Any], *names: str) -> Any:
    """First present field, falling back to a generic `value`.

    Callers are often models, which reasonably reach for `value` when the
    schema said `path`. Returning "could not check: no path given" for a claim
    that plainly names a path would be a checker failing, not a caller failing.
    """
    for name in names:
        got = resource.get(name)
        if got not in (None, ""):
            return got
    return resource.get("value")


def expand_path(raw: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(str(raw or "")))).resolve(strict=False)


def _unknown(resource: dict[str, Any], reason: str) -> Finding:
    return Finding(
        resource=resource,
        status=UNKNOWN,
        severity=WARN,
        detail=f"could not check: {reason}",
        resolutions=["proceed-anyway", "cancel"],
    )


# ------------------------------------------------------------------ checkers


def check_keybinding(resource: dict[str, Any], snapshot: Snapshot, root: Path) -> Finding:
    combo = inspection.normalize_keybinding(field(resource, "value", "combo", "keybinding", "key") or "")
    if not combo:
        return _unknown(resource, "no shortcut given")
    domain = snapshot.domain("keybindings")
    if not domain.available:
        return _unknown(resource, domain.error)
    matches = [b for b in domain.items if b["combo"] == combo]
    if not matches:
        return Finding(resource=resource, status=CLEAR, detail=f"{combo} is unused")
    described = matches[0].get("description") or matches[0].get("dispatcher") or "another action"
    return Finding(
        resource=resource,
        status=CONFLICT,
        severity=BLOCK,
        detail=f"{combo} is already assigned to {described}",
        resolutions=["replace-existing", "choose-another-shortcut", "cancel"],
        existing=matches,
    )


def check_file(resource: dict[str, Any], snapshot: Snapshot, root: Path) -> Finding:
    raw = field(resource, "path", "target", "file") or ""
    if not raw:
        return _unknown(resource, "no path given")
    path = expand_path(raw)
    if not path.exists() and not path.is_symlink():
        return Finding(resource=resource, status=CLEAR, detail=f"{path} does not exist yet")
    kind = "directory" if path.is_dir() else "file"
    return Finding(
        resource=resource,
        status=CONFLICT,
        # A recipe that backs up before writing is the normal, correct case, so
        # an existing file is a warning to be acknowledged, not a blocker.
        severity=WARN,
        detail=f"{path} already exists ({kind}); it must be backed up before modification",
        resolutions=["modify-with-backup", "choose-another-path", "cancel"],
        existing=[{"path": str(path), "kind": kind}],
    )


def check_package(resource: dict[str, Any], snapshot: Snapshot, root: Path) -> Finding:
    name = str(field(resource, "name", "package") or "").strip()
    if not name:
        return _unknown(resource, "no package name given")
    domain = snapshot.domain("packages")
    if not domain.available:
        return _unknown(resource, domain.error)
    if any(item["name"] == name for item in domain.items):
        return Finding(
            resource=resource,
            status=CONFLICT,
            severity=INFO,
            detail=f"{name} is already installed; undo must not remove a package the recipe did not install",
            resolutions=["use-existing", "reinstall", "cancel"],
            existing=[{"name": name}],
        )
    return Finding(resource=resource, status=CLEAR, detail=f"{name} is not installed")


def check_service(resource: dict[str, Any], snapshot: Snapshot, root: Path) -> Finding:
    name = str(field(resource, "name", "service", "unit") or "").strip()
    if not name:
        return _unknown(resource, "no service name given")
    if not name.endswith(".service"):
        name += ".service"
    domain = snapshot.domain("services")
    if not domain.available:
        return _unknown(resource, domain.error)
    matches = [item for item in domain.items if item["name"] == name]
    if not matches:
        return Finding(resource=resource, status=CLEAR, detail=f"{name} is not present")
    state = matches[0].get("active", "unknown")
    return Finding(
        resource=resource,
        status=CONFLICT,
        severity=WARN,
        detail=f"{name} already exists and is {state}; undo must restore its previous enabled/running state",
        resolutions=["reconfigure-existing", "choose-another-name", "cancel"],
        existing=matches,
    )


def check_port(resource: dict[str, Any], snapshot: Snapshot, root: Path) -> Finding:
    raw = field(resource, "port")
    try:
        port = int(raw)
    except (TypeError, ValueError):
        return _unknown(resource, f"invalid port: {raw!r}")
    protocol = str(resource.get("protocol") or "").lower()
    domain = snapshot.domain("ports")
    if not domain.available:
        return _unknown(resource, domain.error)
    matches = [
        item for item in domain.items
        if item["port"] == port and (not protocol or item["protocol"].startswith(protocol))
    ]
    if not matches:
        return Finding(resource=resource, status=CLEAR, detail=f"port {port} is free")
    return Finding(
        resource=resource,
        status=CONFLICT,
        severity=BLOCK,
        detail=f"port {port} is already in use",
        resolutions=["choose-another-port", "stop-existing-listener", "cancel"],
        existing=matches,
    )


def check_mount(resource: dict[str, Any], snapshot: Snapshot, root: Path) -> Finding:
    raw = field(resource, "path", "target", "mount") or ""
    if not raw:
        return _unknown(resource, "no mount point given")
    target = str(expand_path(raw))
    domain = snapshot.domain("mounts")
    if not domain.available:
        return _unknown(resource, domain.error)
    matches = [item for item in domain.items if item["target"] == target]
    if not matches:
        return Finding(resource=resource, status=CLEAR, detail=f"{target} is not a mount point")
    return Finding(
        resource=resource,
        status=CONFLICT,
        severity=BLOCK,
        detail=f"{target} already has {matches[0]['source']} mounted on it",
        resolutions=["choose-another-mount-point", "replace-existing-mount", "cancel"],
        existing=matches,
    )


def check_container(resource: dict[str, Any], snapshot: Snapshot, root: Path) -> Finding:
    name = str(field(resource, "name", "container") or "").strip()
    if not name:
        return _unknown(resource, "no container name given")
    domain = snapshot.domain("containers")
    if not domain.available:
        return _unknown(resource, domain.error)
    matches = [item for item in domain.items if item["name"] == name]
    if not matches:
        return Finding(resource=resource, status=CLEAR, detail=f"no container named {name}")
    return Finding(
        resource=resource,
        status=CONFLICT,
        severity=BLOCK,
        detail=f"a container named {name} already exists ({matches[0]['status']})",
        resolutions=["choose-another-name", "replace-existing-container", "cancel"],
        existing=matches,
    )


def check_environment(resource: dict[str, Any], snapshot: Snapshot, root: Path) -> Finding:
    name = str(field(resource, "name", "variable") or "").strip()
    if not name:
        return _unknown(resource, "no variable name given")
    domain = snapshot.domain("environment")
    matches = [item for item in domain.items if item["name"] == name]
    if not matches:
        return Finding(resource=resource, status=CLEAR, detail=f"{name} is not set in this session")
    return Finding(
        resource=resource,
        status=CONFLICT,
        severity=WARN,
        detail=f"{name} is already set in this session",
        resolutions=["replace-existing", "choose-another-name", "cancel"],
        existing=matches,
    )


def check_config(resource: dict[str, Any], snapshot: Snapshot, root: Path) -> Finding:
    key = str(field(resource, "key", "option", "name") or "").strip()
    if not key:
        return _unknown(resource, "no option name given")
    domain = inspection.config_option(key)
    if not domain.available:
        return _unknown(resource, domain.error)
    current = domain.items[0] if domain.items else {}
    return Finding(
        resource=resource,
        status=CONFLICT,
        severity=INFO,
        detail=f"{key} is currently configured; the previous value must be restorable",
        resolutions=["replace-existing", "cancel"],
        existing=[current],
    )


def check_recipe(resource: dict[str, Any], snapshot: Snapshot, root: Path) -> Finding:
    """Duplicate-recipe detection.

    The spec would rather the user ran or improved an existing recipe than
    accumulated a second one that does the same thing, so a match here is a
    genuine finding and not just an id collision.
    """
    from .core import scan  # imported here to keep module import order simple

    wanted_id = str(field(resource, "id", "recipe_id") or "").strip()
    keywords = [k.lower() for k in (resource.get("keywords") or []) if str(k).strip()]
    recipes, _problems = scan(root)

    if wanted_id:
        exact = [r for r in recipes if r.id == wanted_id]
        if exact:
            r = exact[0]
            return Finding(
                resource=resource,
                status=CONFLICT,
                severity=BLOCK,
                detail=f"a recipe with id {wanted_id!r} already exists ({r.source}): {r.title}",
                resolutions=["run-existing", "improve-existing", "choose-another-id"],
                existing=[{"id": r.id, "title": r.title, "source": r.source, "path": r.path}],
            )

    if keywords:
        similar = []
        for r in recipes:
            haystack = " ".join([r.id, r.title, r.description, " ".join(r.tags)]).lower()
            if all(k in haystack for k in keywords):
                similar.append({"id": r.id, "title": r.title, "source": r.source, "path": r.path})
        if similar:
            return Finding(
                resource=resource,
                status=CONFLICT,
                severity=WARN,
                detail=f"{len(similar)} existing recipe(s) already cover this: "
                       + ", ".join(s["id"] for s in similar[:3]),
                resolutions=["run-existing", "improve-existing", "create-alternative"],
                existing=similar,
            )

    return Finding(resource=resource, status=CLEAR, detail="no equivalent recipe found")


CHECKERS: dict[str, Callable[[dict[str, Any], Snapshot, Path], Finding]] = {
    "keybinding": check_keybinding,
    "file": check_file,
    "package": check_package,
    "service": check_service,
    "port": check_port,
    "mount": check_mount,
    "container": check_container,
    "environment": check_environment,
    "config": check_config,
    "recipe": check_recipe,
}


def check(resources: list[dict[str, Any]], root: Path, snapshot: Snapshot | None = None) -> dict[str, Any]:
    """Check every claimed resource and summarize what the user must decide."""
    snap = snapshot or Snapshot()
    findings: list[Finding] = []
    for resource in resources or []:
        kind = str(resource.get("type") or "").strip()
        checker = CHECKERS.get(kind)
        if checker is None:
            findings.append(Finding(
                resource=resource,
                status=UNKNOWN,
                severity=WARN,
                detail=f"unknown resource type {kind!r}; supported: {', '.join(sorted(CHECKERS))}",
                resolutions=["proceed-anyway", "cancel"],
            ))
            continue
        findings.append(checker(resource, snap, root))

    conflicts = [f for f in findings if f.status == CONFLICT]
    blocking = [f for f in conflicts if f.severity == BLOCK]
    return {
        "findings": [f.to_dict() for f in findings],
        "conflicts": len(conflicts),
        "blocking": len(blocking),
        # The one field a caller must honor: no recipe may be generated or
        # applied while this is true without the user resolving the conflicts.
        "requires_user_decision": bool(blocking),
        "supported_types": sorted(CHECKERS),
    }
