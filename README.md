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

The engine and the native Omarchy browser both work. The CLI, metadata parser,
validation, current-state protocol, history model, backup/undo helpers, example
recipes, tests, and the Omarchy `menu` plugin are all in place. See
[`MILESTONE-1.md`](MILESTONE-1.md) for what the first milestone delivered and
where the edges still are.

## Requirements

- Linux with Bash 5 and Python 3.9+ (Arch/Omarchy ship both). The engine has no
  third-party Python dependencies.
- For the native menu: Omarchy with its Quickshell-based shell running.
- For `make test-qml` / `make lint-qml`: the Qt 6 tools in `/usr/lib/qt6/bin`,
  which an Omarchy install already has.

## Install

```bash
git clone https://github.com/mdelgert/omarchy-recipes.git
cd omarchy-recipes
./bin/omarchy-recipes list
```

That is the whole engine install — it runs from the checkout. To call it from
anywhere without the path, add it to `PATH` (adjust the clone location):

```bash
mkdir -p ~/.local/bin
cp -r ~/omarchy-recipes ~/.local/share/omarchy-recipes
printf '#!/usr/bin/env bash\nexec "$HOME/.local/share/omarchy-recipes/bin/omarchy-recipes" "$@"\n' \
  > ~/.local/bin/omarchy-recipes
chmod +x ~/.local/bin/omarchy-recipes
```

A wrapper rather than a symlink: `bin/omarchy-recipes` locates `src/`, `lib/`,
and `recipes/` relative to itself, so it has to keep sitting inside the checkout.

## Quick start

```bash
./bin/omarchy-recipes list
./bin/omarchy-recipes info example-config-value
./bin/omarchy-recipes check example-config-value
./bin/omarchy-recipes run example-config-value --value balanced
./bin/omarchy-recipes history example-config-value
./bin/omarchy-recipes undo example-config-value
```

Every command also speaks JSON, which is what the frontends consume:

```bash
./bin/omarchy-recipes list --json                 # recipes + any that failed to parse
./bin/omarchy-recipes info --json example-config-value
./bin/omarchy-recipes status --json example-config-value    # undo eligibility; runs nothing
./bin/omarchy-recipes check --json example-config-value
./bin/omarchy-recipes run --json example-config-value --value balanced
./bin/omarchy-recipes history --json example-config-value --limit 20
./bin/omarchy-recipes log --json example-config-value
```

Each response is an object stamped `{"schemaVersion": 1, ...}`. For `check`,
`run`, and `undo`, `--json` goes before the recipe id — everything after the id
is the recipe's own parameter list. The full contract is in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

State is stored under:

```text
${XDG_STATE_HOME:-~/.local/state}/omarchy-recipes/
```

The engine scans the repository `recipes/` tree. `OMARCHY_RECIPES_ROOT` points it
at a different checkout; user recipe directories are still to come.

## Omarchy menu

The menu lists every discovered recipe by category, filters as you type, and
opens a detail view generated from the recipe's own metadata: current state from
`check`, a control per declared parameter, what the recipe promises about
reversal, a confirmed Apply, the run's output, its history, and Undo when the
engine says one is available. Adding a recipe never requires a UI change.

### Enable it

```bash
./omarchy-plugin/install.sh                                # or: make plugin
omarchy plugin enable io.github.mdelgert.omarchy-recipes right
```

1. **`install.sh`** copies `omarchy-plugin/` plus `bin/`, `src/`, `lib/`, and
   `recipes/` into `~/.config/omarchy/plugins/io.github.mdelgert.omarchy-recipes/`,
   validates the manifest and the recipes, and reloads the shell. The copy is
   self-contained, so the plugin finds its runner without anything on `PATH`.
   A copy rather than a symlink because Omarchy refuses a plugin folder
   containing one.
2. **`omarchy plugin enable`** is required — a freshly installed third-party
   plugin lists as `disabled` until you enable it. The trailing `right` places
   the bar icon in the right-hand section (`left`, `center`, and `right` all
   work).

Confirm it loaded:

```bash
omarchy plugin list | grep omarchy-recipes
# io.github.mdelgert.omarchy-recipes enabled third-party menu,bar-widget Omarchy Recipes
```

> If the plugin was previously enabled **without** a section, `enable <id> right`
> will not move it into the bar. Disable it first, then enable it with the
> section:
> ```bash
> omarchy plugin disable io.github.mdelgert.omarchy-recipes
> omarchy plugin enable io.github.mdelgert.omarchy-recipes right
> ```

### Three ways to open it

| | |
| --- | --- |
| **Bar icon** | Click the 📖 book icon in the bar |
| **Keybinding** | See below — not set up by default |
| **Command** | `omarchy-shell shell toggle io.github.mdelgert.omarchy-recipes '{}'` |

### Bind it to a key

The bar icon works out of the box; a keybinding is optional and is **not** set
up for you. Add this to `~/.config/hypr/bindings.lua` (`SUPER + SHIFT + R` is
unused by Omarchy's defaults; check yours with `omarchy menu keybindings --print`):

```lua
o.bind("SUPER + SHIFT + R", "Recipes",
  "omarchy-shell shell toggle io.github.mdelgert.omarchy-recipes '{}'")
```

Open a specific recipe directly by passing its id:

```bash
omarchy-shell shell toggle io.github.mdelgert.omarchy-recipes '{"recipe":"example-numeric-setting"}'
```

### Update it

```bash
git pull
make plugin              # reinstall into the plugin directory
omarchy-restart-shell    # only needed when the plugin's QML changed
```

`omarchy-restart-shell` restarts the desktop shell (brief bar flicker; your
windows and Hyprland are untouched). It is required after a QML change because
the shell caches a menu plugin's compiled QML for the life of the process.
Engine, recipe, and `RecipeModel.js` changes are picked up on the next summon.

Keys, runner resolution, and the development loop:
[`docs/OMARCHY_PLUGIN.md`](docs/OMARCHY_PLUGIN.md).

## Uninstall

**Undo anything you applied first.** Undo works from the recorded run history,
so reverse your changes while the engine is still installed:

```bash
./bin/omarchy-recipes history                       # what has been applied
./bin/omarchy-recipes undo <recipe-id>              # for each one you want reversed
```

Remove the Omarchy plugin:

```bash
omarchy plugin disable io.github.mdelgert.omarchy-recipes   # keep it installed, just off
omarchy plugin remove io.github.mdelgert.omarchy-recipes --yes
```

`remove` disables the plugin and moves its folder to a hidden backup beside it,
`~/.config/omarchy/plugins/.io.github.mdelgert.omarchy-recipes.bak.<timestamp>`.
Delete that too if you want it gone:

```bash
rm -rf ~/.config/omarchy/plugins/.io.github.mdelgert.omarchy-recipes.bak.*
```

Then remove the rest:

```bash
rm -rf "${XDG_STATE_HOME:-$HOME/.local/state}/omarchy-recipes"   # run history + backups
rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-recipes-demo"  # example recipes' demo files
rm -f  ~/.local/bin/omarchy-recipes                              # only if you made the wrapper
rm -rf ~/.local/share/omarchy-recipes                            # only if you copied it there
```

Deleting the state directory throws away every recorded run and its backups,
which is what undo restores from. Do it last.

Finally, drop the keybinding from `~/.config/hypr/bindings.lua` and delete the
repository checkout.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `omarchy plugin list` does not show the plugin | The shell has not rescanned. Run `omarchy-shell shell rescanPlugins`. |
| The plugin lists as `disabled` | Third-party plugins start disabled. Run `omarchy plugin enable io.github.mdelgert.omarchy-recipes right`. |
| No bar icon, but the plugin is enabled | It was enabled without a section, so it is not in the bar layout. `omarchy plugin disable` it, then `omarchy plugin enable <id> right`. |
| The bar icon is missing after a QML change | The shell caches plugin QML. Run `omarchy-restart-shell`. |
| Nothing happens on `toggle` | The plugin is disabled, or the shell is not running. Check `omarchy-shell shell ping`. |
| *Recipe engine unavailable* in the menu | The runner was not found or would not start. Re-run `make plugin`, or set `OMARCHY_RECIPES_BIN` to an `omarchy-recipes` that works. |
| *N recipes were skipped* in the menu | A recipe's metadata is malformed. Run `./bin/omarchy-recipes validate` for the exact reason. |
| QML edits do not take effect | The shell caches a menu plugin's compiled QML. Run `omarchy-restart-shell`. |
| A recipe has no Undo button | The recipe declares `undo: none`, or nothing has been applied yet. The detail view says which. |

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
  check) recipe_state configured "mode=balanced" ;;   # or: recipe_state not-configured "..."
  apply) ... ;;
  undo)  ... ;;
  *) recipe_die "expected check|apply|undo" ;;
esac
```

See [`docs/RECIPE_SPEC.md`](docs/RECIPE_SPEC.md) for the full starter contract.

## Repository map

```text
bin/omarchy-recipes               CLI entry point
src/omarchy_recipes/              dependency-free Python engine
lib/recipe.sh                     Bash authoring/backup/state helpers
recipes/                          dynamically discovered recipes
omarchy-plugin/                   native Omarchy menu plugin + bar icon
docs/VISION.md                    the larger product idea; do not shrink this
docs/ARCHITECTURE.md              component boundaries, JSON contract, lifecycle
docs/RECIPE_SPEC.md               metadata + execution protocol
docs/OMARCHY_PLUGIN.md            Omarchy plugin integration and testing
skills/recipe-authoring/SKILL.md  rules for AI agents writing recipes
AGENTS.md                         project-wide instructions for coding agents
schemas/recipe.schema.json        normalized metadata schema
tests/                            engine tests, fixtures, QML logic tests
MILESTONE-1.md                    what the native browser milestone delivered
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
make check       # engine tests + QML logic tests + recipe validation
make test        # Python engine tests only
make test-qml    # RecipeModel.js unit tests (qmltestrunner, no shell needed)
make lint-qml    # qmllint against the installed Omarchy shell types
make plugin      # install the Omarchy plugin from this working tree
```

No third-party Python packages are required for the engine. The QML targets need
Qt 6 tools (`/usr/lib/qt6/bin`), which an Omarchy install already has.

## License

MIT. See `LICENSE`.
