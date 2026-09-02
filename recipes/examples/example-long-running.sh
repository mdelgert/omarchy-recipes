#!/usr/bin/env bash
set -Eeuo pipefail

# @recipe.id example-long-running
# @recipe.title Example long-running task
# @recipe.description Prints a progress message every few seconds so you can see how the UI behaves during a slow recipe. Writes only a small log in the demo directory.
# @recipe.category Examples
# @recipe.platform linux,omarchy
# @recipe.privilege user
# @recipe.undo restore
# @recipe.risk low
# @recipe.tags example,progress,slow
# @param steps integer required=true default=10 min=1 max=120 label="Steps" description="How many messages to print"
# @param delay integer required=true default=1 min=1 max=10 label="Seconds per step" description="Pause between messages"

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

target="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-recipes-demo/long-running.log"

action="${1:-}"
shift || true
recipe_parse_args "$@"

case "$action" in
  check)
    if [[ -f "$target" ]]; then
      recipe_state configured "$(wc -l < "$target" | tr -d ' ') message(s) from the last run"
    else
      recipe_state not-configured "Has not been run yet"
    fi
    ;;

  apply)
    steps="${RECIPE_ARG_STEPS:?missing --steps}"
    delay="${RECIPE_ARG_DELAY:?missing --delay}"
    # The engine validates type and range, but a recipe is runnable straight
    # from a shell too, so it checks its own input.
    [[ "$steps" =~ ^[0-9]+$ ]] || recipe_die "steps must be a positive integer"
    [[ "$delay" =~ ^[0-9]+$ ]] || recipe_die "delay must be a positive integer"
    ((steps >= 1 && steps <= 120)) || recipe_die "steps must be between 1 and 120"
    ((delay >= 1 && delay <= 10)) || recipe_die "delay must be between 1 and 10"

    if [[ -e "$target" || -L "$target" ]]; then
      recipe_backup_file "$target"
    else
      recipe_mark_absent "$target"
    fi

    # Built up in memory and written once at the end, so an interrupted run
    # leaves the previous log intact rather than a half-written one.
    output=""
    started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    for ((i = 1; i <= steps; i++)); do
      line="step $i of $steps — $(date -u +%H:%M:%S)"
      recipe_note "$line"
      output+="$line"$'\n'
      # No sleep after the last step: nothing is waiting on it.
      ((i < steps)) && sleep "$delay"
    done

    printf 'started %s\n%s' "$started" "$output" | recipe_atomic_write "$target"
    [[ -f "$target" ]] || recipe_die "verification failed: $target was not written"
    recipe_summary "Printed $steps message(s) over about $((steps * delay - delay))s"
    recipe_note "Wrote $target"
    ;;

  undo)
    recipe_restore_file "$target"
    recipe_summary "Restored the previous log"
    recipe_note "Restored prior state for $target"
    ;;

  *) recipe_die "expected action check|apply|undo" ;;
esac
