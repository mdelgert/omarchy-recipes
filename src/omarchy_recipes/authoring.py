"""Saving a drafted recipe into the user's own collection.

This is the only way a generated recipe reaches the disk. The agent hands over
text; the engine decides whether it is allowed to become a file. Everything the
spec asks for at this step happens here and not in the frontend:

* the draft is linted before it is written, and errors refuse the write
* it lands in the user's local collection, never among the bundled recipes
* provenance is stamped by the engine, so "an agent wrote this" is recorded by
  the thing that knows it rather than claimed by the file itself
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from . import lint as lint_mod
from . import sources as sources_mod
from .core import ID_RE, RecipeError, parse_recipe

PROVENANCE_KEYS = ("generated-with-ai", "reviewed")


def _strip_provenance(text: str) -> str:
    """Remove any provenance the draft declared about itself.

    A recipe does not get to assert that it was human-reviewed. The engine
    stamps these, so whatever the draft claimed is dropped first.
    """
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            body = stripped.lstrip("#").strip()
            if any(body.startswith(f"@recipe.{key} ") for key in PROVENANCE_KEYS):
                continue
        kept.append(line)
    return "\n".join(kept)


def _stamp_provenance(text: str, generated_with_ai: bool, reviewed: bool) -> str:
    """Insert provenance directly after the last @recipe.* metadata line."""
    lines = _strip_provenance(text).splitlines()
    stamp = [
        f"# @recipe.generated-with-ai {'true' if generated_with_ai else 'false'}",
        f"# @recipe.reviewed {'true' if reviewed else 'false'}",
    ]
    last_meta = -1
    for index, line in enumerate(lines):
        if line.strip().startswith("#") and "@recipe." in line:
            last_meta = index
    if last_meta < 0:
        # No metadata block to attach to; the lint pass will reject this draft
        # anyway, so leave the text alone rather than inventing a header.
        return "\n".join(lines) + "\n"
    lines[last_meta + 1:last_meta + 1] = stamp
    return "\n".join(lines) + "\n"


def draft_report(text: str) -> dict[str, Any]:
    """Lint a draft that is not on disk yet.

    Used for the preview step: the user sees the generated Bash and its findings
    before anything is written.
    """
    with tempfile.TemporaryDirectory(prefix="omarchy-recipes-draft-") as tmp:
        path = Path(tmp) / "draft.sh"
        path.write_text(text)
        report = lint_mod.lint(path)
    report["path"] = "<draft>"
    return report


def save(
    root: Path,
    recipe_id: str,
    text: str,
    *,
    generated_with_ai: bool = True,
    reviewed: bool = False,
    overwrite: bool = False,
    allow_warnings: bool = True,
) -> dict[str, Any]:
    """Validate a draft and, if it passes, write it to the local collection."""
    rid = str(recipe_id or "").strip()
    if not ID_RE.match(rid):
        raise RecipeError(f"invalid recipe id {rid!r}; use lowercase letters, digits, and hyphens")

    stamped = _stamp_provenance(text, generated_with_ai=generated_with_ai, reviewed=reviewed)
    report = draft_report(stamped)
    if report["errors"]:
        return {"saved": False, "reason": "the draft has errors that must be fixed first", "lint": report}
    if report["warnings"] and not allow_warnings:
        return {"saved": False, "reason": "the draft has warnings and warnings were not allowed", "lint": report}

    # The id in the file has to be the id being saved, or discovery and the
    # filename would disagree the first time someone looks for it.
    with tempfile.TemporaryDirectory(prefix="omarchy-recipes-draft-") as tmp:
        probe = Path(tmp) / "draft.sh"
        probe.write_text(stamped)
        parsed = parse_recipe(probe)
    if parsed.id != rid:
        raise RecipeError(f"draft declares @recipe.id {parsed.id!r} but is being saved as {rid!r}")

    sources_mod.ensure_workspace()
    target = sources_mod.source_for(sources_mod.LOCAL, root).path / f"{rid}.sh"
    if target.exists() and not overwrite:
        raise RecipeError(f"{target} already exists; pass --overwrite to replace it")

    # Write via a temporary file in the same directory so a failure part-way
    # cannot leave a half-written recipe that discovery would then try to parse.
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=f".{rid}.", suffix=".sh")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(stamped)
        os.chmod(tmp_name, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        os.replace(tmp_name, target)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise

    saved = parse_recipe(target)
    saved.source = sources_mod.LOCAL
    return {"saved": True, "path": str(target), "recipe": saved.to_dict(), "lint": report}
