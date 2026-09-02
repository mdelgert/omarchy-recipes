"""Offering a locally authored recipe back to the canonical collection.

The spec is firm about the shape of this: a contribution goes through a branch
and a pull request, never a direct write to the maintainer's main branch. That
is what keeps "let an agent write recipes" from turning into remote code
execution into the collection everyone else installs.

`prepare()` does everything that is safe to do without touching a remote:
validate, lint, check for duplicates, and build the branch name and pull
request body. `submit()` performs the git and `gh` steps. A caller that only
wants to show the user what would happen calls `prepare()` alone.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from . import lint as lint_mod
from . import sources as sources_mod
from .core import RecipeError, get_recipe, scan

PROTECTED_BRANCHES = {"main", "master"}
CLONE_TIMEOUT = 120
GH_TIMEOUT = 60
BRANCH_PREFIX = "recipe/"
GIT_TIMEOUT = 30


def _git(root: Path, *args: str) -> tuple[bool, str, str]:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=str(root), text=True, capture_output=True,
            check=False, timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, "", str(e)
    return proc.returncode == 0, proc.stdout.strip(), proc.stderr.strip()


def _gh(cwd: Path, *args: str, timeout: int = GH_TIMEOUT) -> tuple[bool, str, str]:
    try:
        proc = subprocess.run(
            ["gh", *args], cwd=str(cwd), text=True, capture_output=True,
            check=False, timeout=timeout,
        )
    except FileNotFoundError:
        return False, "", "the GitHub CLI (gh) is not installed"
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, "", str(e)
    return proc.returncode == 0, proc.stdout.strip(), proc.stderr.strip()


def remote_url(root: Path) -> str:
    ok, out, _err = _git(root, "remote", "get-url", "origin")
    return out.strip() if ok else ""


def branch_name(recipe_id: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", str(recipe_id or "").lower()).strip("-")
    if not slug:
        raise RecipeError("cannot build a branch name from an empty recipe id")
    return f"{BRANCH_PREFIX}{slug}"


def pull_request_body(recipe: Any, lint_report: dict[str, Any], testing: str = "") -> str:
    """The structured description the spec asks every recipe PR to carry."""
    warnings = [f"{f['rule']}: {f['message']}" for f in lint_report["findings"] if f["severity"] == lint_mod.WARNING]
    authoring = recipe.authoring or {}
    ai_line = "Yes" if authoring.get("generated_with_ai") else "No"
    reviewed_line = "Yes" if authoring.get("reviewed") else "Not yet"

    undo_text = {
        "restore": "Undo restores the exact prior state from the run's backup.",
        "command": "Undo runs an explicit inverse action.",
        "none": "This recipe declares no automatic undo.",
    }.get(recipe.undo, recipe.undo)

    return f"""## Recipe

Recipe ID: `{recipe.id}`

Title: {recipe.title}

Category: {recipe.category}

## Purpose

{recipe.description}

## Changes

Risk: {recipe.risk}. Privilege: {recipe.privilege}.

Parameters: {', '.join(f'`--{p.name}` ({p.type})' for p in recipe.parameters) or 'none'}

## Backup

Existing state is captured into the run's backup directory before modification,
via `recipe_backup_file` / `recipe_mark_absent`.

## Undo

{undo_text}

## Compatibility

Platform: {', '.join(recipe.platform) or 'linux'}

Distro: {', '.join(recipe.distro) or 'unspecified'}

## Testing

{testing or 'Describe how the recipe was tested.'}

## Conflicts

{chr(10).join('- ' + w for w in warnings) if warnings else 'No lint warnings outstanding.'}

## AI Generated

Was AI used to generate this recipe? {ai_line}

Human reviewed? {reviewed_line}
"""


def prepare(root: Path, recipe_id: str, *, testing: str = "") -> dict[str, Any]:
    """Everything that must be true before a contribution is worth opening."""
    recipe = get_recipe(root, recipe_id)
    blockers: list[str] = []

    if recipe.source == sources_mod.BUNDLED:
        blockers.append(f"{recipe.id} is already part of the bundled collection")

    report = lint_mod.lint(Path(recipe.path))
    if not report["ok"]:
        blockers.append(f"{report['errors']} lint error(s) must be fixed before contributing")

    # Duplicate detection, so the collection does not grow two recipes that do
    # the same thing under different names.
    existing, _problems = scan(root)
    keywords = [w for w in re.split(r"[^a-z0-9]+", recipe.title.lower()) if len(w) > 3]
    duplicates = []
    for other in existing:
        if other.id == recipe.id or other.source != sources_mod.BUNDLED:
            continue
        haystack = f"{other.id} {other.title} {other.description}".lower()
        if keywords and all(k in haystack for k in keywords):
            duplicates.append({"id": other.id, "title": other.title, "path": other.path})

    ok_git, current_branch, _err = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    target = branch_name(recipe.id)

    return {
        "recipe": recipe.to_dict(),
        "lint": report,
        "duplicates": duplicates,
        "branch": target,
        "current_branch": current_branch if ok_git else "",
        "pull_request_title": f"Add recipe: {recipe.title}",
        "pull_request_body": pull_request_body(recipe, report, testing),
        "blockers": blockers,
        # Duplicates do not block on their own; the spec wants the user asked,
        # not overruled.
        "ready": not blockers,
        "requires_user_decision": bool(duplicates),
    }


def open_pull_request(root: Path, recipe_id: str, *, testing: str = "") -> dict[str, Any]:
    """Branch, commit, push, and open the pull request.

    All of it happens in a throwaway clone rather than in the checkout the
    plugin is running from. Contributing a recipe must not leave the installed
    plugin sitting on a `recipe/...` branch with an extra commit — that is the
    sort of side effect that turns "I offered a recipe upstream" into "why is
    my plugin update failing".
    """
    plan = prepare(root, recipe_id, testing=testing)
    if not plan["ready"]:
        return {**plan, "submitted": False, "reason": "; ".join(plan["blockers"])}

    ok, _out, err = _gh(root, "auth", "status")
    if not ok:
        return {**plan, "submitted": False,
                "reason": f"GitHub CLI is not ready: {err or 'run `gh auth login`'}"}

    url = remote_url(root)
    if not url:
        return {**plan, "submitted": False, "reason": "could not determine the upstream repository"}

    recipe = get_recipe(root, recipe_id)
    source = Path(recipe.path)
    branch = plan["branch"]

    with tempfile.TemporaryDirectory(prefix="omarchy-recipes-contrib-") as tmp:
        work = Path(tmp) / "repo"
        try:
            proc = subprocess.run(["git", "clone", "--quiet", url, str(work)],
                                  text=True, capture_output=True, check=False, timeout=CLONE_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired) as e:
            return {**plan, "submitted": False, "reason": f"could not clone {url}: {e}"}
        if proc.returncode != 0:
            return {**plan, "submitted": False,
                    "reason": f"could not clone {url}: {proc.stderr.strip().splitlines()[:1]}"}

        ok, _out, err = _git(work, "checkout", "-b", branch)
        if not ok:
            return {**plan, "submitted": False, "reason": f"could not create branch {branch}: {err}"}

        destination = work / "recipes" / "community" / f"{recipe.id}.sh"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        destination.chmod(0o755)

        ok, _out, err = _git(work, "add", str(destination.relative_to(work)))
        if not ok:
            return {**plan, "submitted": False, "reason": f"could not stage the recipe: {err}"}

        ok, _out, err = _git(work, "commit", "-m", f"Add recipe: {recipe.title}")
        if not ok:
            return {**plan, "submitted": False, "reason": f"could not commit: {err}"}

        ok, _out, err = _git(work, "push", "-u", "origin", branch)
        if not ok:
            # No write access is the ordinary case for a contributor, and it
            # needs a fork rather than a retry. Say which it is.
            hint = ("you do not have push access; fork it first with "
                    "`gh repo fork --remote`, then contribute from that fork")
            return {**plan, "submitted": False,
                    "reason": f"could not push {branch}: {err}", "hint": hint}

        base = "main"
        ok, out, _err = _gh(work, "repo", "view", "--json", "defaultBranchRef",
                            "-q", ".defaultBranchRef.name")
        if ok and out.strip():
            base = out.strip()

        ok, out, err = _gh(work, "pr", "create", "--base", base, "--head", branch,
                           "--title", plan["pull_request_title"], "--body", plan["pull_request_body"])
        if not ok:
            return {**plan, "submitted": True, "pushed": True, "pull_request_url": "",
                    "branch": branch,
                    "reason": f"branch pushed, but the pull request could not be opened: {err}"}

        link = ""
        for line in out.splitlines():
            if line.strip().startswith("http"):
                link = line.strip()
                break

    return {**plan, "submitted": True, "pushed": True, "branch": branch,
            "base": base, "pull_request_url": link}


def submit(
    root: Path,
    recipe_id: str,
    *,
    testing: str = "",
    dry_run: bool = True,
    push: bool = False,
) -> dict[str, Any]:
    """Copy the recipe into the collection on a branch, and offer a PR.

    Defaults to a dry run: a contribution should be something the user reads
    before it happens, not something an agent completes on their behalf.
    """
    plan = prepare(root, recipe_id, testing=testing)
    if not plan["ready"]:
        return {**plan, "submitted": False, "reason": "; ".join(plan["blockers"])}

    recipe = get_recipe(root, recipe_id)
    destination = root / "recipes" / "community" / f"{recipe.id}.sh"
    steps = [
        f"git checkout -b {plan['branch']}",
        f"copy {recipe.path} -> {destination.relative_to(root)}",
        f"git add {destination.relative_to(root)}",
        f"git commit -m 'Add recipe: {recipe.title}'",
    ]
    if push:
        steps += [f"git push -u origin {plan['branch']}", "gh pr create --fill-first"]

    if dry_run:
        return {**plan, "submitted": False, "dry_run": True, "steps": steps, "destination": str(destination)}

    # Refuse to build a contribution on top of a protected branch: the whole
    # point is that this never becomes a direct write to main.
    if plan["current_branch"] in PROTECTED_BRANCHES and not plan["branch"]:
        return {**plan, "submitted": False, "reason": "refusing to commit directly to a protected branch"}
    if plan["branch"] in PROTECTED_BRANCHES:
        return {**plan, "submitted": False, "reason": f"refusing to use protected branch {plan['branch']}"}

    ok, _out, err = _git(root, "checkout", "-b", plan["branch"])
    if not ok and "already exists" not in err:
        return {**plan, "submitted": False, "reason": f"could not create branch: {err}"}

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(Path(recipe.path).read_bytes())
    destination.chmod(0o755)

    ok, _out, err = _git(root, "add", str(destination.relative_to(root)))
    if not ok:
        return {**plan, "submitted": False, "reason": f"could not stage the recipe: {err}"}
    ok, _out, err = _git(root, "commit", "-m", f"Add recipe: {recipe.title}")
    if not ok:
        return {**plan, "submitted": False, "reason": f"could not commit: {err}"}

    result = {**plan, "submitted": True, "steps": steps, "destination": str(destination), "pushed": False}
    if push:
        ok, _out, err = _git(root, "push", "-u", "origin", plan["branch"])
        if not ok:
            return {**result, "pushed": False, "reason": f"branch committed but push failed: {err}"}
        result["pushed"] = True
    return result
