# Milestone 1 — Native Omarchy Recipe Browser

A working Omarchy `menu` plugin that discovers recipes through the
`omarchy-recipes` engine and renders them. No recipe is named in QML; adding a
recipe file makes it appear in the menu with its own controls, status, and undo
affordance without a UI change.

## What was implemented

### Frontend — `omarchy-plugin/`

| Milestone item | Where |
| --- | --- |
| Native Omarchy plugin menu | `Menu.qml`, layer-shell card following the built-in menu's conventions |
| Dynamic recipe discovery | `RecipeEngine.reload()` → `list --json` |
| Recipe categories | `RecipeModel.rowsFor()` groups the engine's sorted list |
| Search / filtering | type-to-filter over title, description, category, tags, id |
| Title and description | browse rows; descriptions shown while filtering, full text in detail |
| Recipe detail view | `RecipeDetail.qml` |
| Current status via `check` | run on selection; `@recipe.state` markers parsed by the engine |
| Generated parameter controls | `ParameterControl.qml`, chosen from `parameter.type` alone |
| Run/apply confirmation | `ConfirmDialog`, naming the recipe and warning on `undo=none` / `risk=high` |
| Execute through the runner | `run --json <id> --<param> <value>` as argv |
| stdout/stderr and success/failure | result banner, summary, and a "View log" pane |
| Execution history | `history --json`, newest first, with undone runs marked |
| Undo when supported | offered only when `status --json` reports `undo_available` |
| Refresh after apply/undo | `status`, `history`, and `check` are all re-read; nothing is inferred from an exit code |
| Missing dependencies / malformed recipes | runner resolution failure and per-recipe parse problems are shown in the menu |

The plugin also declares `bar-widget`, so a stateless bar icon (`BarWidget.qml`)
opens the same menu. That was added after the milestone review, because a
`menu`-kind plugin on its own has no launcher of any sort — no icon, no key, no
entry in the SUPER+SPACE menu — which made a working plugin feel like a broken
one.

Controls: `string` → text field, `integer` → bounded spin box, `boolean` →
toggle, `choice` → dropdown, `path` → wide text field, `secret` → masked field.
An unrecognised type falls back to a text field, so a recipe written against a
newer engine still renders and still round-trips through the validated argument
interface.

### Engine — `src/omarchy_recipes/`

The frontend needed things the engine could not yet answer cleanly, so the
engine grew rather than the QML:

- **JSON envelope.** Every `--json` response is `{"schemaVersion": 1, ...}`, and
  the plugin refuses a version it does not understand instead of half-reading it.
- **Tolerant discovery.** `scan()` returns parsed recipes plus a `problems` list.
  One malformed recipe reports itself and leaves the rest usable; `validate`
  stays strict and now exits 2 when anything is wrong.
- **Current-state protocol.** `check` reports state through `@recipe.state` /
  `@recipe.summary` markers (`recipe_state`, `recipe_summary` in
  `lib/recipe.sh`). The engine parses and strips them; recipes predating the
  protocol still report `unknown` with their first line of output.
- **`status`** — undo eligibility, run count, and last run, without executing
  anything. This is what keeps undo-eligibility logic out of QML.
- **`log`** — captured output of a recorded run, so the UI never reaches into
  the state directory.
- **Structured run results.** `execute()` returns a `RunResult`; `check`, `run`,
  and `undo` all accept `--json`.
- **Undo parameter replay.** `undo` re-validates and replays the source run's
  parameters, so a recipe whose target path is a parameter reverses the right
  file.
- **`OMARCHY_RECIPES_ROOT`** relocates the recipe tree, which is how the tests
  run against fixtures without touching the real one.

### Recipes

`example-numeric-setting` (integer with bounds), `example-feature-toggle`
(boolean + string + path), and `example-demo-report` (no parameters,
`undo=none`, second category) join the existing choice example. All write only
inside a demo directory under `XDG_CONFIG_HOME` and back up before writing.

## Architecture decisions

**The engine is the authoritative boundary.** QML issues argv-only process
calls and renders parsed JSON. It does not parse recipe files, validate
parameters, decide reversibility, or read the state directory. Where the
frontend needed a judgement, the engine learned to answer it (`status`, the
check-state protocol) rather than the judgement being reimplemented in
JavaScript.

**`menu` kind, not `bar-widget`.** The milestone's UX is a summoned, searchable,
keyboard-first card. That is what `menu` is, and it lets the plugin follow the
built-in Omarchy menu's surface conventions — same layer-shell setup, same
`Color.menu.*` roles, same type-to-filter behaviour.

**`RecipeModel.js` is a pure library.** Grouping, filtering, control selection,
argv building, and formatting live in a `.pragma library` file with no Omarchy
or Quickshell dependency. That is what makes `make test-qml` possible without a
running shell, and it keeps `Menu.qml` to layout and navigation.

**`check` is ephemeral.** A browser checks state every time a recipe is
selected. Recording those runs would bury the user's real history and grow the
state directory without bound, so `check` runs in a throwaway directory and is
not recorded.

**The installed plugin is self-contained.** `install.sh` copies the QML plus
`bin/`, `src/`, `lib/`, and `recipes/` into the plugin folder, so the plugin
finds its runner at `<plugin>/bin/omarchy-recipes` with nothing on `$PATH`.
Omarchy refuses a plugin folder containing symlinks, so a copy is the only
option; `$OMARCHY_RECIPES_BIN` overrides the runner while iterating.

**Card sizing is computed from the row model, not read back from the view.**
Asking the `ListView` how tall it is in order to size the card that sizes the
`ListView` is a binding loop; the browse height is measured from the row data
the same way the built-in menu does it.

**Discovery has a watchdog.** A process that cannot start never reports an exit,
which left the menu on "Loading recipes…" forever when no runner existed. Only
discovery is guarded (10s): every later call happens after a successful list,
which is proof the runner works, and an apply that takes minutes is legitimate.

## Security posture

- Parameter values travel as separate argv entries. No command string is built
  from metadata or user input anywhere in the plugin, and there is no `eval`.
  A unit test asserts that a value containing `;` and `&&` stays one argv entry.
- Recipe metadata and recipe output are untrusted: everything renders as
  `Text.PlainText`, and no recipe content is turned into QML or JavaScript.
- Selecting a recipe runs only `check`, which the recipe protocol requires to be
  non-mutating. Apply and Undo require an explicit, confirmed action.
- Runner resolution is an existence check, not a trial execution.
- `log --run` rejects a run id that would escape the state directory.
- Privilege elevation stays in the engine/recipe layer; the UI only displays
  what a recipe declares.

## Known limitations

- **Output is captured, not streamed.** A long-running recipe shows "Working…"
  until it exits. Streaming needs an engine change (line-by-line stdout) and is
  listed for Milestone 2.
- **Menu-kind QML is cached by the shell.** After `make plugin`, edited QML keeps
  running the previously compiled version until `omarchy-restart-shell`. Engine,
  recipe, and installed-`RecipeModel.js` changes are picked up on the next
  summon. This is Omarchy's plugin loader behaviour, not something the plugin can
  work around.
- **`secret` parameters render masked but are not yet safe.** The engine redacts
  them from run metadata, but full secret-safe logging is unfinished; recipes
  should not require secrets yet.
- **No user recipe directory.** Only the tree under the engine root is scanned.
- **Single-monitor surface.** The card maps on one output, matching the built-in
  menu; it is not mirrored to other outputs, and which output it picks is not
  necessarily the focused one.
- **The bar icon's click was not automated.** The icon renders and the command it
  issues is verified, but no pointer-injection tool exists on this machine, so
  the physical click path is the one step confirmed by hand rather than by a
  script.
- **UI refresh is verified at the contract layer.** Tests assert that `status`,
  `check`, and `history` report the reversed world after apply and undo — the
  exact reads the UI performs. The rendering of that refresh was verified by
  hand (see below), not by an automated GUI test.
- **`check` with a required parameter that has no default** reports the engine's
  validation error as the status until the field is filled. That is honest, but
  a friendlier "fill this in to check" state would be better.
- **A hung apply hangs the button.** Only discovery is watchdogged. If a recipe
  never exits, the detail view stays on "Working…" until the menu is closed.
  Streaming output (Milestone 2) is the right place to fix this properly.

## How to test

```bash
make check        # 27 engine tests, 18 QML logic tests, recipe validation
make test         # engine only
make test-qml     # RecipeModel.js only; no shell required
make lint-qml     # qmllint against the installed Omarchy shell types
```

The engine tests build a temporary root from `tests/fixtures/recipes/` with
`HOME`, `XDG_CONFIG_HOME`, and `XDG_STATE_HOME` redirected, so they never touch
real configuration. They cover multiple categories, malformed metadata, a
recipe with no parameters, integer/choice/boolean/path parameters, a failing
`check`, a failing `apply`, a successful apply, history, undo, undo parameter
replay, exact restore, and the refreshed status after each.

`qmllint` reports `unqualified` and `missing-property` warnings for the shell's
own singleton pattern and for `root.` access inside delegates; the built-in
Omarchy menu produces the same classes. Compare against it rather than expecting
zero output.

### Manual Omarchy testing

```bash
make plugin
omarchy plugin enable io.github.mdelgert.omarchy-recipes
omarchy-restart-shell                                    # required after QML changes
omarchy-shell shell toggle io.github.mdelgert.omarchy-recipes '{}'
```

1. **Browse.** Categories `Diagnostics` and `Examples` appear with their recipes.
   Type `numeric` — the list narrows and descriptions appear. `Esc` clears the
   filter, `Esc` again closes.
2. **Detail.** Open *Example numeric setting*. Status reads *Not configured*, a
   spin box shows `600` with its `60–7200` range, reversibility shows the two
   guarantees plus *Nothing to undo yet*, and *Undo last change* is disabled.
3. **Apply.** `Tab` to *Apply*, `Enter`. Confirm. Status flips to *Configured —
   600 seconds*, *Recipe completed successfully* appears with `unset → 600
   seconds`, undo becomes available, and the run shows up under History.
   `cat ~/.config/omarchy-recipes-demo/timeout.conf` shows `timeout=600`.
4. **Undo.** `Tab` to *Undo last change*, `Enter`, confirm. Status returns to
   *Not configured*, the file is gone, undo is disabled again, and History shows
   the undo plus the original apply marked `(undone)`.
5. **Other control types.** Open *Example feature toggle* for a toggle, a text
   field, and a path field; *Example configuration value* for a dropdown;
   *Report demo state* for a recipe with no parameters that correctly offers no
   undo.
6. **Malformed recipe.** Drop a `.sh` file with only `# @recipe.id broken` into
   the installed plugin's `recipes/` directory and summon the menu: it reports
   *1 recipe was skipped: … missing metadata* and still lists the others.
7. **Missing runner.** Rename the installed plugin's `bin/` directory and
   restart the shell: the menu reports *Recipe engine unavailable: the recipe
   engine could not be started or did not respond* and names the runner it fell
   back to, rather than sitting on "Loading recipes…" or claiming there are no
   recipes. Restore it with `make plugin`.

Open a specific recipe directly:

```bash
omarchy-shell shell toggle io.github.mdelgert.omarchy-recipes '{"recipe":"example-numeric-setting"}'
```

## Recommended Milestone 2 work

1. **Streaming output.** Emit recipe stdout line by line from the engine and
   render it live. This is the largest remaining gap for anything slower than
   the demo recipes, and it also unblocks a progress affordance.
2. **Preview / dry run.** A `preview` action alongside `check`/`apply` that
   reports what *would* change, surfaced as a diff above the Apply button. The
   vision document asks for it and the detail view has the room.
3. **User recipe directories.** Scan `~/.config/omarchy-recipes/recipes/` in
   addition to the engine root, with the source shown per recipe. Needed before
   anyone can keep their own recipes without editing this repository.
4. **Secret parameters.** Finish redaction end to end (never recorded, never
   logged, never replayed on undo) and then let recipes declare them honestly.
5. **A real recipe library.** The v0.3 roadmap items — hotkeys, power/idle,
   Docker, Samba — are what turn this from a demonstration into something worth
   opening daily. The browser is now the cheap part; each recipe is the work.
6. **Elevation UX.** `privilege: root` is descriptive only. Decide how a recipe
   requests elevation for a narrow command and how the menu should show it,
   keeping elevation in the recipe layer.
7. **Multi-select and grouped parameters.** `multichoice` and section grouping in
   the generated form, which the control map is already structured to absorb.
