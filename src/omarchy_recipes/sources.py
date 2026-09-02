"""Where recipes come from, and how much that origin is trusted.

Milestone 2 lets an agent author recipes on the user's machine. A generated
recipe must not be able to pass itself off as one that shipped with the
project and was reviewed, so origin is tracked from the moment a recipe is
discovered rather than being asserted by the recipe's own metadata.

Layout:

    <engine root>/recipes/                       bundled
    ${XDG_CONFIG_HOME}/omarchy-recipes/recipes/
        local/                                   authored here, by the user or an agent
        community/                               pulled from someone else's collection

`OMARCHY_RECIPES_HOME` relocates the user workspace; tests use it so they never
read or write the developer's own recipes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Ordered most trusted first. Discovery walks them in this order, so a lower
# tier can never take an id that a higher tier already claimed.
BUNDLED = "bundled"
LOCAL = "local"
COMMUNITY = "community"
SOURCE_ORDER = (BUNDLED, LOCAL, COMMUNITY)

# What each origin means for the user, in one line the UI can show verbatim.
SOURCE_LABELS = {
    BUNDLED: "Shipped with omarchy-recipes",
    LOCAL: "Created on this machine",
    COMMUNITY: "From an external collection",
}

# Whether the project vouches for the recipe. Only bundled recipes went through
# review upstream; everything else is the user's own call. This is deliberately
# coarse — signing and review status are later milestones.
SOURCE_REVIEWED_UPSTREAM = {BUNDLED: True, LOCAL: False, COMMUNITY: False}


@dataclass(frozen=True)
class Source:
    name: str
    path: Path

    @property
    def label(self) -> str:
        return SOURCE_LABELS.get(self.name, self.name)

    @property
    def reviewed_upstream(self) -> bool:
        return SOURCE_REVIEWED_UPSTREAM.get(self.name, False)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": str(self.path),
            "label": self.label,
            "reviewed_upstream": self.reviewed_upstream,
            "exists": self.path.exists(),
        }


def workspace_root() -> Path:
    """User-writable root holding local and community recipes."""
    override = os.environ.get("OMARCHY_RECIPES_HOME")
    if override:
        return Path(override)
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "omarchy-recipes"


def sources(engine_root: Path) -> list[Source]:
    workspace = workspace_root()
    return [
        Source(BUNDLED, engine_root / "recipes"),
        Source(LOCAL, workspace / "recipes" / LOCAL),
        Source(COMMUNITY, workspace / "recipes" / COMMUNITY),
    ]


def source_for(name: str, engine_root: Path) -> Source:
    for source in sources(engine_root):
        if source.name == name:
            return source
    raise ValueError(f"unknown recipe source: {name!r}")


def ensure_workspace() -> Path:
    """Create the user workspace on demand.

    Called before writing a generated recipe, never during discovery: browsing
    recipes must not create directories as a side effect.
    """
    root = workspace_root()
    for name in (LOCAL, COMMUNITY):
        (root / "recipes" / name).mkdir(parents=True, exist_ok=True)
    return root
