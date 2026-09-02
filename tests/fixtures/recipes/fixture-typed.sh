#!/usr/bin/env bash
set -Eeuo pipefail

# Test fixture: exercises every starter parameter type through the real
# execution path. Writes only inside XDG_CONFIG_HOME, which the tests point at
# a temporary directory.

# @recipe.id fixture-typed
# @recipe.title Typed parameters
# @recipe.description Fixture covering integer, choice, boolean, string, and path parameters.
# @recipe.category Fixtures
# @recipe.privilege user
# @recipe.undo restore
# @recipe.risk low
# @param timeout integer required=true default=600 min=60 max=7200 label="Timeout"
# @param mode choice required=true default=balanced choices=performance,balanced,powersave label="Mode"
# @param enabled boolean default=true label="Enabled"
# @param note string default="none" label="Note"
# @param directory path required=true label="Target directory"

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

action="${1:-}"
shift || true
recipe_parse_args "$@"

target="${RECIPE_ARG_DIRECTORY:-${XDG_CONFIG_HOME:?}/fixture}/typed.conf"

case "$action" in
  check)
    if [[ -f "$target" ]]; then
      recipe_state configured "$(cat -- "$target")"
    else
      recipe_state not-configured "nothing written yet"
    fi
    ;;
  apply)
    desired="timeout=${RECIPE_ARG_TIMEOUT} mode=${RECIPE_ARG_MODE} enabled=${RECIPE_ARG_ENABLED} note=${RECIPE_ARG_NOTE}"
    if [[ -e "$target" || -L "$target" ]]; then
      recipe_backup_file "$target"
    else
      recipe_mark_absent "$target"
    fi
    printf '%s\n' "$desired" | recipe_atomic_write "$target"
    recipe_summary "$desired"
    recipe_note "wrote $target"
    ;;
  undo)
    recipe_restore_file "$target"
    recipe_summary "restored"
    ;;
  *) recipe_die "expected action check|apply|undo" ;;
esac
