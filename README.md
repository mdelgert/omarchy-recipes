# omarchy-recipes

A self-describing, reversible recipe runner for Omarchy and Linux workstations.

`omarchy-recipes` turns reusable Bash setup/configuration scripts into discoverable **recipes**. Each recipe declares its title, description, category, parameters, privilege needs, compatibility, and undo capability in structured comments. The runner discovers recipes dynamically, validates input, records execution history, provides backup/restore helpers, and exposes the same recipe collection to CLI/TUI/Omarchy frontends.

> The script is the source of truth. Add a recipe file; frontends discover it without UI code changes.

## Why this exists

Workstation setup tends to become a collection of repeated one-off commands: install Docker, configure Samba, change power settings, add hotkeys, tune screen locking, mount a NAS, and so on. Those commands are often rewritten by people or AI, are hard to audit later, and rarely have a reliable undo path.

A recipe is expected to follow a lifecycle:

**inspect → backup → apply → verify → record**

and, when reversible:

**locate prior run → undo/restore → verify**

## Status

This repository is a **starter/reference implementation**. The core CLI, metadata parser, validation, history model, backup helpers, example recipe, tests, and Omarchy plugin integration plan are included. The richer native Omarchy GUI is deliberately kept as a thin scaffold so agents can build it against the current Quattro plugin APIs rather than hard-coding UI assumptions into the core engine.

## Quick start

```bash
./bin/omarchy-recipes list
./bin/omarchy-recipes list --json
./bin/omarchy-recipes info example-config-value
./bin/omarchy-recipes check example-config-value
./bin/omarchy-recipes run example-config-value --value balanced
./bin/omarchy-recipes history example-config-value
./bin/omarchy-recipes undo example-config-value
```

State is stored under:

```text
${XDG_STATE_HOME:-~/.local/state}/omarchy-recipes/
```

User recipe directories can be added later; the starter scans the repository `recipes/` tree.

## Recipe example

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

# @recipe.id example-config-value
# @recipe.title Example configuration value
# @recipe.description Demonstrates metadata, parameters, backup, apply, check, and undo.
# @recipe.category Examples
# @recipe.platform linux
# @recipe.privilege user
# @recipe.undo restore
# @recipe.risk low
# @param value choice required=true default=balanced choices=performance,balanced,powersave label="Mode"

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

case "${1:-}" in
  check) ... ;;
  apply) ... ;;
  undo)  ... ;;
  *) recipe_die "expected check|apply|undo" ;;
esac
```

See [`docs/RECIPE_SPEC.md`](docs/RECIPE_SPEC.md) for the full starter contract.

## Repository map

```text
bin/omarchy-recipes              CLI entry point
src/omarchy_recipes/             dependency-free Python engine
lib/recipe.sh                    Bash authoring/backup helpers
recipes/                         dynamically discovered recipes
docs/VISION.md                   the larger product idea; do not shrink this
/docs/ARCHITECTURE.md             component boundaries and lifecycle
/docs/RECIPE_SPEC.md              metadata + execution protocol
/docs/OMARCHY_PLUGIN.md           Omarchy/Quattro integration notes
skills/recipe-authoring/SKILL.md  rules for AI agents writing recipes
AGENTS.md                         project-wide instructions for coding agents
.github/copilot-instructions.md   concise Copilot instructions
omarchy-plugin/                   native plugin scaffold
schemas/recipe.schema.json        normalized metadata schema
/tests/                           unit/integration starter tests
```

## Design principles

1. **Self-describing** — metadata lives with executable logic.
2. **Reversible by default** — exact prior state beats guessed defaults.
3. **Idempotent where practical** — re-running should not accumulate damage.
4. **Frontend-neutral** — CLI, TUI and GUI consume the same normalized model.
5. **Least privilege** — elevate only the exact operation that requires it.
6. **Observable** — every run has status, parameters, output and timestamps.
7. **AI-authorable, human-auditable** — the skill defines safe conventions.
8. **Portable collections** — recipes should eventually be shareable as Git repositories.

## Inspiration

The metadata approach intentionally takes inspiration from `argc`, which defines Bash CLI behavior through structured comments. The runner/task concepts also borrow ideas from `just`, while state/idempotence ideas are influenced by chezmoi. We do not need to clone any of them: this project adds the workstation-oriented reversible lifecycle and generated UI model.

- argc: https://github.com/sigoden/argc
- just: https://github.com/casey/just
- chezmoi: https://github.com/twpayne/chezmoi
- Gum (possible TUI frontend): https://github.com/charmbracelet/gum
- Omarchy plugin docs: https://plugins.omarchy.org/develop.html

## Development

```bash
python -m unittest discover -s tests -v
./bin/omarchy-recipes validate
```

No third-party Python packages are required for the starter engine.

## License

MIT. See `LICENSE`.
