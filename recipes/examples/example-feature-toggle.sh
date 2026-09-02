#!/usr/bin/env bash
set -Eeuo pipefail

# @recipe.id example-feature-toggle
# @recipe.title Example feature toggle
# @recipe.description Safe demonstration of boolean, string, and path parameters written to a demo file.
# @recipe.category Examples
# @recipe.platform linux,omarchy
# @recipe.privilege user
# @recipe.undo restore
# @recipe.risk low
# @recipe.tags example,toggle
# @param enabled boolean default=true label="Enable demo feature" description="Whether the demo feature is switched on"
# @param note string default="hello" label="Note" description="Free-text note stored beside the toggle"
# @param directory path required=true default="~/.config/omarchy-recipes-demo" label="Demo directory" description="Directory the demo file is written to"

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

action="${1:-}"
shift || true
recipe_parse_args "$@"

# Only ~ and ~/... are expanded; nothing here is passed through a shell, so a
# parameter value can never turn into shell syntax.
expand_home() {
  local raw="$1"
  case "$raw" in
    "~") printf '%s' "$HOME" ;;
    "~/"*) printf '%s/%s' "$HOME" "${raw#\~/}" ;;
    *) printf '%s' "$raw" ;;
  esac
}

directory="$(expand_home "${RECIPE_ARG_DIRECTORY:-${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-recipes-demo}")"
target="$directory/feature.conf"

case "$action" in
  check)
    if [[ -f "$target" ]]; then
      recipe_state configured "$(head -n 1 -- "$target")"
    else
      recipe_state not-configured "No demo feature file at $target"
    fi
    ;;

  apply)
    enabled="${RECIPE_ARG_ENABLED:-true}"
    case "$enabled" in true|false) ;; *) recipe_die "enabled must be true or false" ;; esac
    note="${RECIPE_ARG_NOTE:-}"
    case "$note" in *$'\n'*) recipe_die "note must be a single line" ;; esac

    desired="enabled=$enabled note=$note"
    if [[ -f "$target" ]] && [[ "$(head -n 1 -- "$target")" == "$desired" ]]; then
      recipe_summary "Already configured: $desired"
      recipe_note "Already configured"
      exit 0
    fi

    if [[ -e "$target" || -L "$target" ]]; then
      recipe_backup_file "$target"
    else
      recipe_mark_absent "$target"
    fi
    printf '%s\n' "$desired" | recipe_atomic_write "$target"
    [[ "$(head -n 1 -- "$target")" == "$desired" ]] || recipe_die "verification failed"
    recipe_summary "$desired"
    recipe_note "Configured $target"
    ;;

  undo)
    recipe_restore_file "$target"
    recipe_summary "Restored previous demo feature state"
    recipe_note "Restored prior state for $target"
    ;;

  *) recipe_die "expected action check|apply|undo" ;;
esac
