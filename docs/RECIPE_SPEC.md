# Recipe Specification (starter v0.1)

The metadata grammar is intentionally simple and inspired by comment-driven tools such as `argc`.

## Required metadata

```bash
# @recipe.id unique-kebab-case-id
# @recipe.title Human readable title
# @recipe.description One-line description
# @recipe.category Category name
```

## Recommended metadata

```bash
# @recipe.platform linux,omarchy
# @recipe.distro arch
# @recipe.privilege user
# @recipe.undo restore
# @recipe.risk low
# @recipe.tags docker,development
```

Allowed starter values:

- privilege: `user`, `mixed`, `root`
- undo: `restore`, `command`, `none`
- risk: `low`, `medium`, `high`

`root` is descriptive only in v0.1. The runner does not automatically sudo the entire recipe.

## Parameters

One parameter is declared per line:

```bash
# @param timeout integer required=true default=600 min=60 max=7200 label="Screen timeout" description="Seconds before display timeout"
# @param mode choice required=true default=balanced choices=performance,balanced,powersave label="Power mode"
# @param enabled boolean default=true label="Enable feature"
# @param path path required=true label="Configuration directory"
```

Syntax:

```text
@param <name> <type> key=value key="quoted value" ...
```

Starter types:

- `string`
- `integer`
- `boolean`
- `choice`
- `path`
- `secret` (reserved; parser accepts it, but secret-safe logging is not complete yet)

Supported properties:

- `required=true|false`
- `default=<value>`
- `label=<text>`
- `description=<text>`
- `choices=a,b,c`
- `min=<integer>`
- `max=<integer>`

Unknown properties are retained in normalized metadata so the schema can evolve.

## Execution protocol

Every recipe accepts an action as argv[1]:

```text
check
apply
undo
```

Parameters are passed after the action as long options:

```text
./recipe.sh apply --timeout 600 --mode balanced
```

A recipe can use `recipe_parse_args "$@"` from `lib/recipe.sh`, which exposes values as `RECIPE_ARG_<NAME>` with names normalized to uppercase underscores.

Example:

```bash
case "${1:-}" in
  check)
    shift
    recipe_parse_args "$@"
    ;;
  apply)
    shift
    recipe_parse_args "$@"
    timeout="$RECIPE_ARG_TIMEOUT"
    ;;
  undo)
    recipe_restore_file "$HOME/.config/example.conf"
    ;;
esac
```

## Backup contract

Before modifying an existing file:

```bash
recipe_backup_file "$target"
```

The helper stores the file under the current run's backup directory using a path-safe encoding and writes a small index entry. `recipe_restore_file` finds the matching backup in `OMARCHY_RECIPES_SOURCE_RUN_DIR`.

If a file did not previously exist, call:

```bash
recipe_mark_absent "$target"
```

before creating it. Undo can then remove the newly-created file with:

```bash
recipe_restore_file "$target"
```

The helper distinguishes "was absent" from "backup missing".

## Authoring requirements

Read `skills/recipe-authoring/SKILL.md`. The important guarantees are:

- inspect before modifying
- backup before modifying
- preserve exact prior state
- idempotent where practical
- validate user input
- minimize privilege
- check must be non-mutating
- verify after apply/undo when possible
- no `eval` on user input
