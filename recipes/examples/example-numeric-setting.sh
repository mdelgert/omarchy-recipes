#!/usr/bin/env bash
set -Eeuo pipefail

# @recipe.id example-numeric-setting
# @recipe.title Example numeric setting
# @recipe.description Safe demonstration of a bounded integer parameter with backup and exact undo.
# @recipe.category Examples
# @recipe.platform linux,omarchy
# @recipe.privilege user
# @recipe.undo restore
# @recipe.risk low
# @recipe.tags example,numeric
# @param timeout integer required=true default=600 min=60 max=7200 label="Screen timeout" description="Seconds written to a harmless demo configuration file"

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

target="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-recipes-demo/timeout.conf"

action="${1:-}"
shift || true
recipe_parse_args "$@"

current_value() {
  [[ -f "$target" ]] || return 1
  sed -n 's/^timeout=\([0-9]\{1,\}\)$/\1/p' -- "$target" | head -n 1
}

case "$action" in
  check)
    if value="$(current_value)" && [[ -n "$value" ]]; then
      recipe_state configured "$value seconds"
    else
      recipe_state not-configured "No demo timeout configured"
    fi
    ;;

  apply)
    timeout="${RECIPE_ARG_TIMEOUT:?missing --timeout}"
    # The engine validates type and range, but a recipe is also runnable
    # directly from a shell, so it validates its own input too.
    [[ "$timeout" =~ ^[0-9]+$ ]] || recipe_die "timeout must be a positive integer"
    ((timeout >= 60 && timeout <= 7200)) || recipe_die "timeout must be between 60 and 7200"

    previous="$(current_value || true)"
    if [[ "$previous" == "$timeout" ]]; then
      recipe_summary "Already configured: ${timeout} seconds"
      recipe_note "Already configured: timeout=$timeout"
      exit 0
    fi

    if [[ -e "$target" || -L "$target" ]]; then
      recipe_backup_file "$target"
    else
      recipe_mark_absent "$target"
    fi
    printf 'timeout=%s\n' "$timeout" | recipe_atomic_write "$target"
    [[ "$(current_value)" == "$timeout" ]] || recipe_die "verification failed"
    recipe_summary "${previous:-unset} → ${timeout} seconds"
    recipe_note "Configured $target: timeout=$timeout"
    ;;

  undo)
    recipe_restore_file "$target"
    recipe_summary "Restored previous demo timeout"
    recipe_note "Restored prior state for $target"
    ;;

  *) recipe_die "expected action check|apply|undo" ;;
esac
