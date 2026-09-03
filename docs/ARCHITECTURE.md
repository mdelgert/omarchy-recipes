# Architecture

## Boundaries

### Recipe content

Bash files under `recipes/` contain metadata and implement a tiny protocol:

```text
recipe.sh check [parameters]
recipe.sh apply [parameters]
recipe.sh undo
```

`check` must not mutate state. `apply` makes the desired change. `undo` uses the source run supplied by the engine when a previous successful apply is available.

### Engine

The dependency-free Python code under `src/omarchy_recipes/` owns:

- discovery
- metadata parsing
- parameter validation
- normalized JSON output
- process execution
- state/run directories
- stdout/stderr capture
- history
- selecting the source run for undo

It must not contain Omarchy UI logic.

### Bash helper library

`lib/recipe.sh` owns safe primitives useful to recipe authors:

- fail/message helpers
- exact file backup preserving metadata via `cp -a`
- restore from the engine-provided source run
- argument parsing helpers
- atomic file replacement helper

The helper library must remain small. Recipe authors should still be able to understand what changes a recipe performs by reading the recipe itself.

### Frontends

Frontends consume the engine's JSON interface. The initial CLI is authoritative;
TUI and QML call the engine rather than reparsing recipe headers independently.

## Machine-readable interface

Every `--json` response is a JSON object stamped with the contract version:

```json
{ "schemaVersion": 1, "...": "payload" }
```

A frontend checks `schemaVersion` before trusting the rest, so the engine can
add fields without a client silently misreading a new shape. On failure the
same envelope carries `error` and the process exits non-zero.

| Command | Payload keys | Notes |
| --- | --- | --- |
| `list --json` | `recipes`, `problems` | sorted by category then title |
| `info --json <id>` | `recipe` | normalized metadata only |
| `status --json <id>` | `status` | undo eligibility + last run; executes nothing |
| `check --json <id> [--p v]` | `run` | non-mutating; leaves no run directory |
| `run --json <id> [--p v]` | `run` | apply; records a run |
| `undo --json <id>` | `run` | undo; records a run |
| `history --json [<id>] [--limit n]` | `runs` | newest first |
| `log --json <id> [--run <run-id>]` | `run`, `stdout`, `stderr` | captured output of one run |
| `validate --json` | `recipes`, `problems`, `ok` | exits 2 when a recipe is malformed |
| `agent providers --json` | `providers`, `default`, `model` | `default`/`model` are the *resolved* choice, not just what is installed |
| `config show --json` | `config` | the whole settings file |

`--json` must precede the recipe id for `check`, `run`, and `undo`, because
everything after the id is the recipe's own parameter list. Passing it later is
refused with an explanatory error rather than guessed at.

`config get` and `config set` are deliberately outside the envelope: they print
a bare JSON value and a one-line confirmation respectively, so they compose with
`$(...)` in a shell without a JSON parser. `config show --json` is the form a
frontend consumes.

Engine environment overrides:

| Variable | Effect |
| --- | --- |
| `OMARCHY_RECIPES_ROOT` | directory the `recipes/` tree is read from; relocates the engine, not a recipe-source feature |
| `OMARCHY_RECIPES_HOME` | user workspace: the recipe collections *and* `config.json` |
| `OMARCHY_RECIPES_AGENT` | agent provider; outranks the config file, for scripting and CI |
| `OMARCHY_RECIPES_MODEL` | agent model; outranks the config file, for scripting and CI |

### Tolerant discovery

`scan()` returns the recipes that parsed plus a `problems` list. One malformed
recipe reports itself and leaves the rest usable, which is what keeps a browser
from going blank because of one bad file. `validate` is the strict view of the
same scan and fails when any problem exists.

### Current-state protocol

`check` reports state by writing markers to stdout:

```text
@recipe.state configured
@recipe.summary 600 seconds
```

`lib/recipe.sh` provides `recipe_state` and `recipe_summary` for this. The
engine parses the markers, strips them from the text it hands a frontend, and
keeps the raw stream in the run log. States: `configured`, `not-configured`,
`partial`, `unsupported`, `unknown`, `error` (a non-zero exit is always
`error`). A recipe that emits no marker reports `unknown` with its first line of
output as the summary, so recipes written before the protocol still work.

`check` runs in a throwaway working directory and is not recorded in history: a
frontend checks state every time a recipe is selected, and that must not
accumulate state or bury the user's real history.

### Undo parameter replay

`undo` re-validates and replays the parameter values recorded by the source
apply run. A recipe whose target path or resource is chosen by a parameter can
only reverse the right thing if undo sees the values the apply used. Secret
values are never recorded and so are never replayed; values that no longer
validate are dropped so undo falls back to the recipe's own defaults.

## Config layout

```text
${XDG_CONFIG_HOME:-~/.config}/omarchy-recipes/
├── config.json
└── recipes/
    ├── local/
    └── community/
```

`config.json` holds authoring settings only — which agent provider to use, and
per provider which model:

```json
{"agent": {"provider": "copilot", "models": {"claude": null, "copilot": null, "codex": null}}}
```

`null` means "not configured": the engine falls back to the first installed
provider, and lets each provider choose its own model. Resolution order is
flag > environment variable > this file > fallback, for both.

No secret ever goes in this file. `claude`, `copilot`, and `codex` each own
their own login state; the engine stores a provider name and a model name and
nothing else, which is what keeps the file safe to copy between machines or
paste into a bug report.

`OMARCHY_RECIPES_HOME` relocates this whole directory, which is how the tests
avoid reading or writing a developer's real settings.

## State layout

```text
${XDG_STATE_HOME:-~/.local/state}/omarchy-recipes/
└── runs/
    └── <recipe-id>/
        └── <timestamp>-<random>/
            ├── run.json
            ├── stdout.log
            ├── stderr.log
            └── backup/
```

An `undo` execution gets its own run directory and points to the source apply run in `run.json`.

## Environment passed to recipes

```text
OMARCHY_RECIPES_ROOT
OMARCHY_RECIPES_LIB
OMARCHY_RECIPES_RUN_DIR
OMARCHY_RECIPES_BACKUP_DIR
OMARCHY_RECIPES_SOURCE_RUN_DIR   # undo only
OMARCHY_RECIPES_RECIPE_ID
```

Recipes must not guess state directories.

## Security model

Recipes are executable code. Metadata is not a sandbox.

Key rules:

1. Never build a command string from user values and feed it to `eval`.
2. Parameters are passed as argv, not concatenated shell.
3. QML should never directly execute recipe body text.
4. Elevation belongs inside narrowly scoped recipe commands, not around the whole runner.
5. Secret parameters must eventually be flagged and excluded from run metadata/logging.
6. Collection trust/signing is a future concern but should remain visible in the roadmap.

Omarchy's plugin documentation notes that plugins run unsandboxed inside the long-running shell with the user's permissions. This is another reason to keep the runner boundary explicit and avoid embedding arbitrary shell logic in QML.

## Exit semantics

- `0` = operation succeeded
- `2` = the engine refused the request (unknown recipe, invalid parameter, malformed metadata)
- other non-zero = the recipe itself failed; the value is the recipe's exit code

## Omarchy frontend

`omarchy-plugin/` holds the native menu. Its layering is:

```text
Menu.qml            surface, navigation, keys, confirmation
  RecipeDetail.qml  generated form, status, actions, output, history
  ParameterControl.qml   one control per declared parameter type
RecipeEngine.qml    every engine call; the only place that talks to the runner
RecipeModel.js      pure presentation helpers (grouping, filtering, formatting)
```

`RecipeModel.js` has no Omarchy or Quickshell dependency, which is what lets
`make test-qml` cover the frontend's decisions without a running shell.

The QML layer never parses a recipe file, decides reversibility, validates a
parameter, or reads the state directory. Parameter values travel to the runner
as argv entries; no command string is built from metadata or user input, and
nothing from a recipe is evaluated as QML or JavaScript. See
`docs/OMARCHY_PLUGIN.md` for installation and manual testing.
