#!/usr/bin/env bash
set -Eeuo pipefail

# @recipe.id example-config-value
# @recipe.title Example configuration value
# @recipe.description Safe demonstration of metadata, typed input, backup, history, and exact undo.
# @recipe.category Examples
# @recipe.platform linux,omarchy
# @recipe.privilege user
# @recipe.undo restore
# @recipe.risk low
# @recipe.tags example,configuration
# @param value choice required=true default=balanced choices=performance,balanced,powersave label="Mode" description="Example mode written to a harmless demo configuration file"

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

target="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-recipes-demo/settings.conf"

action="${1:-}"
shift || true
recipe_parse_args "$@"

case "$action" in
  check)
    if [[ -f "$target" ]]; then
      recipe_state configured "$(cat -- "$target")"
    else
      recipe_state not-configured "No demo configuration file yet"
    fi
    ;;

  apply)
    value="${RECIPE_ARG_VALUE:?missing --value}"
    case "$value" in performance|balanced|powersave) ;; *) recipe_die "invalid mode" ;; esac

    if [[ -f "$target" ]] && [[ "$(cat -- "$target")" == "mode=$value" ]]; then
      recipe_note "Already configured: mode=$value"
      exit 0
    fi

    if [[ -e "$target" || -L "$target" ]]; then
      recipe_backup_file "$target"
    else
      recipe_mark_absent "$target"
    fi
    printf 'mode=%s\n' "$value" | recipe_atomic_write "$target"
    [[ "$(cat -- "$target")" == "mode=$value" ]] || recipe_die "verification failed"
    recipe_note "Configured $target: mode=$value"
    ;;

  undo)
    recipe_restore_file "$target"
    recipe_note "Restored prior state for $target"
    ;;

  *) recipe_die "expected action check|apply|undo" ;;
esac
