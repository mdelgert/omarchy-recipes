#!/usr/bin/env bash
set -Eeuo pipefail

# @recipe.id example-demo-report
# @recipe.title Report demo state
# @recipe.description Read-only report of the files the example recipes created. Takes no parameters and changes nothing.
# @recipe.category Diagnostics
# @recipe.platform linux,omarchy
# @recipe.privilege user
# @recipe.undo none
# @recipe.risk low
# @recipe.tags example,report

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

demo_dir="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-recipes-demo"

report() {
  if [[ -d "$demo_dir" ]]; then
    recipe_note "Demo directory: $demo_dir"
    local found=0
    local file
    for file in "$demo_dir"/*; do
      [[ -f "$file" ]] || continue
      found=1
      recipe_note "  $(basename -- "$file"): $(head -n 1 -- "$file")"
    done
    ((found)) || recipe_note "  (no files yet)"
  else
    recipe_note "Demo directory does not exist: $demo_dir"
  fi
}

case "${1:-}" in
  check)
    if [[ -d "$demo_dir" ]]; then
      recipe_state configured "Demo directory present"
    else
      recipe_state not-configured "Demo directory absent"
    fi
    report
    ;;

  apply)
    # This recipe is a report. "Applying" it re-reads and prints state; it
    # never writes, which is why it honestly declares undo=none.
    report
    recipe_summary "Reported demo state"
    ;;

  undo)
    recipe_die "this recipe changes nothing and has no undo"
    ;;

  *) recipe_die "expected action check|apply|undo" ;;
esac
