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

Frontends consume `omarchy-recipes list --json` and `info --json`.

The initial CLI is authoritative. TUI and QML should call the engine rather than reparsing recipe headers independently.

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

Starter convention:

- `0` = operation succeeded
- non-zero = failed

For `check`, stdout should be concise human-readable text today. A future protocol can add structured JSON state without breaking the basic command shape.
