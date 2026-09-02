# omarchy-recipes

A self-describing, reversible recipe runner for Omarchy and Linux workstations,
with a native Omarchy plugin for browsing, running, and authoring recipes.

Reusable setup and configuration scripts become discoverable **recipes**. Each
one declares its title, parameters, privilege needs, and undo capability in its
own header, so the menu is generated from the recipes themselves — add a recipe
file and it appears, with the right controls, current state, and an Undo button.

Describe a change in plain language and an agent will draft one for you, after
checking it against what is already configured on your machine. Nothing runs
until you have read it and pressed Apply.

## Install

```bash
omarchy plugin add https://github.com/mdelgert/omarchy-recipes.git --enable
```

That clones the repository into `~/.config/omarchy/plugins/`, validates it, and
offers to enable it. When it asks for a bar section, pick one — that is where
the recipe icon lands.

Open it from the bar icon, or:

```bash
omarchy-shell shell toggle io.github.mdelgert.omarchy-recipes '{}'
```

Optionally bind a key in `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + SHIFT + R", "Recipes",
  "omarchy-shell shell toggle io.github.mdelgert.omarchy-recipes '{}'")
```

Update later with:

```bash
omarchy plugin update io.github.mdelgert.omarchy-recipes
omarchy-restart-shell     # only needed when the plugin's QML changed
```

> A freshly installed third-party plugin lists as `disabled` until enabled, and
> a plugin enabled *without* a section stays out of the bar. If there is no
> icon:
> ```bash
> omarchy plugin disable io.github.mdelgert.omarchy-recipes
> omarchy plugin enable io.github.mdelgert.omarchy-recipes right
> ```

## Remove

**Undo anything you applied first** — undo works from the recorded run history,
so reverse your changes while the engine is still installed:

The runner lives inside the plugin, so call it by path (or use the menu's Undo
button, which does the same thing):

```bash
cd ~/.config/omarchy/plugins/io.github.mdelgert.omarchy-recipes
./bin/omarchy-recipes history            # what has been applied
./bin/omarchy-recipes undo <recipe-id>   # for each one you want reversed
```

Then:

```bash
omarchy plugin disable io.github.mdelgert.omarchy-recipes   # off, still installed
omarchy plugin remove io.github.mdelgert.omarchy-recipes --yes
```

`remove` disables it first. A plugin added with `omarchy plugin add` is a git
clone and is deleted outright; one copied in by `install.sh` is moved to a
hidden backup beside it, which you can delete too:

```bash
rm -rf ~/.config/omarchy/plugins/.io.github.mdelgert.omarchy-recipes.bak.*
```

Your own recipes and run history live outside the plugin folder and survive it.
Remove them only if you want them gone:

```bash
rm -rf ~/.config/omarchy-recipes                                 # your recipes
rm -rf "${XDG_STATE_HOME:-$HOME/.local/state}/omarchy-recipes"   # run history + backups
rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-recipes-demo"  # example recipes' demo files
```

Finally, drop the keybinding from `~/.config/hypr/bindings.lua`.

## Requirements

- Linux with Bash 5 and Python 3.9+ (Arch/Omarchy ship both). The engine has no
  third-party Python dependencies.
- For the native menu: Omarchy with its Quickshell-based shell running.
- For `make test-qml` / `make lint-qml`: the Qt 6 tools in `/usr/lib/qt6/bin`,
  which an Omarchy install already has.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `omarchy plugin list` does not show the plugin | The shell has not rescanned. Run `omarchy-shell shell rescanPlugins`. |
| The plugin lists as `disabled` | Third-party plugins start disabled. Run `omarchy plugin enable io.github.mdelgert.omarchy-recipes right`. |
| `omarchy plugin add` says the id is already used | It is already installed. Use `omarchy plugin update <id>`, or remove it first. |
| No bar icon, but the plugin is enabled | It was enabled without a section, so it is not in the bar layout. `omarchy plugin disable` it, then `omarchy plugin enable <id> right`. |
| The bar icon is missing after a QML change | The shell caches plugin QML. Run `omarchy-restart-shell`. |
| Nothing happens on `toggle` | The plugin is disabled, or the shell is not running. Check `omarchy-shell shell ping`. |
| *Recipe engine unavailable* in the menu | The runner was not found or would not start. Re-run `make plugin`, or set `OMARCHY_RECIPES_BIN` to an `omarchy-recipes` that works. |
| *N recipes were skipped* in the menu | A recipe's metadata is malformed. Run `./bin/omarchy-recipes validate` for the exact reason. |
| QML edits do not take effect | The shell caches a menu plugin's compiled QML. Run `omarchy-restart-shell`. |
| A recipe has no Undo button | The recipe declares `undo: none`, or nothing has been applied yet. The detail view says which. |

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
[`docs/milestones/MILESTONE-1-REPORT.md`](docs/milestones/MILESTONE-1-REPORT.md) for what the first milestone delivered and
where the edges still are.

## Using the menu

### Opening it

| | |
| --- | --- |
| **Bar icon** | Click the 📖 book icon in the bar |
| **Keybinding** | Whatever you bound in [Install](#install) |
| **Command** | `omarchy-shell shell toggle io.github.mdelgert.omarchy-recipes '{}'` |

Open straight into one recipe by passing its id:

```bash
omarchy-shell shell toggle io.github.mdelgert.omarchy-recipes '{"recipe":"example-numeric-setting"}'
```

### Keys

| Key | In the list | In a recipe |
| --- | --- | --- |
| type | filters recipes | goes to the focused control |
| `↑` `↓` | move the cursor | — |
| `Enter` | open the recipe | activate the focused button |
| `Tab` | — | move between controls and buttons |
| `Ctrl+N` | create a recipe | — |
| `Esc` | clear the filter, then close | back to the list |
| `F5` | reload recipes | reload and re-check |

Runner resolution and the development loop:
[`docs/OMARCHY_PLUGIN.md`](docs/OMARCHY_PLUGIN.md).

### Create a recipe by describing it

Press `Ctrl+N` in the menu, or from the command line:

```bash
./bin/omarchy-recipes agent providers                      # claude, codex
./bin/omarchy-recipes agent plan "Add a hotkey Super+Alt+Y that opens Firefox"
```

The agent inspects the machine, declares what it would touch, and the engine
checks that against reality — a shortcut that is already bound stops the flow
until you choose what to do. Then it writes the recipe, the engine lints it, and
you read the Bash before it is saved. Nothing is applied until you press Apply.

Authoring commands, used by the recipe-authoring agent so it never needs a shell
of its own:

```bash
./bin/omarchy-recipes sources                      # collections and their trust level
./bin/omarchy-recipes inspect --json keybindings   # read-only view of the machine
echo '{"resources":[{"type":"keybinding","value":"SUPER + RETURN"}]}' \
  | ./bin/omarchy-recipes conflicts --json         # exits 3 when the user must decide
./bin/omarchy-recipes lint --json < draft.sh       # static and AI-safety checks
./bin/omarchy-recipes create my-recipe < draft.sh  # save to the local collection
./bin/omarchy-recipes contribute my-recipe         # dry-run pull request plan
```

Each response is an object stamped `{"schemaVersion": 1, ...}`. For `check`,
`run`, and `undo`, `--json` goes before the recipe id — everything after the id
is the recipe's own parameter list. The full contract is in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

State is stored under:

```text
${XDG_STATE_HOME:-~/.local/state}/omarchy-recipes/
```

Recipes are discovered from three collections, in trust order:

```text
<checkout>/recipes/                           bundled    reviewed upstream
~/.config/omarchy-recipes/recipes/local/      local      written here, by you or an agent
~/.config/omarchy-recipes/recipes/community/  community  from another collection
```

A local or community recipe can never take an id a bundled one already claimed.
`OMARCHY_RECIPES_ROOT` points the engine at a different checkout;
`OMARCHY_RECIPES_HOME` relocates the user workspace.

## Command line

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

### Running the engine outside Omarchy

The plugin ships the engine, so `omarchy plugin add` is all most people need.
To use the CLI on its own, or to work on the project:

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

### Installing the plugin from a working copy

When you are changing the code, install the working tree instead — uncommitted
changes and all:

```bash
./omarchy-plugin/install.sh                                # or: make plugin
omarchy plugin enable io.github.mdelgert.omarchy-recipes right
omarchy-restart-shell
```

`install.sh` mirrors the repository into the plugin directory, so an install
from git and an install from a working copy are the same layout. After a
`git pull`, re-run `make plugin`.

`omarchy-restart-shell` restarts the desktop shell (brief bar flicker; your
windows and Hyprland are untouched). It is required after a QML change, because
the shell caches a menu plugin's compiled QML for the life of the process.
Engine, recipe, and `RecipeModel.js` changes are picked up on the next summon.

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
skills/recipe-contribution/SKILL.md  how an agent contributes a recipe upstream
AGENTS.md                         project-wide instructions for coding agents
schemas/recipe.schema.json        normalized metadata schema
tests/                            engine tests, fixtures, QML logic tests
docs/tasks/                       backlog: one file per assignable task, see docs/AGENT_WORKFLOW.md
docs/milestones/                  milestone specs (MILESTONE-N-SPEC.md) and reports (MILESTONE-N-REPORT.md)
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

## Inspiration

The metadata approach intentionally takes inspiration from `argc`, which defines Bash CLI behavior through structured comments. The runner/task concepts also borrow ideas from `just`, while state/idempotence ideas are influenced by chezmoi. We do not need to clone any of them: this project adds the workstation-oriented reversible lifecycle and generated UI model.

- argc: https://github.com/sigoden/argc
- just: https://github.com/casey/just
- chezmoi: https://github.com/twpayne/chezmoi
- Gum (possible TUI frontend): https://github.com/charmbracelet/gum
- Omarchy plugin docs: https://plugins.omarchy.org/develop.html

## License

MIT. See `LICENSE`.
