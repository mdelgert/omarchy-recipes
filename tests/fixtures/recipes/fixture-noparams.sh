#!/usr/bin/env bash
set -Eeuo pipefail

# Test fixture: a recipe with no parameters and no automatic undo.

# @recipe.id fixture-noparams
# @recipe.title No parameters
# @recipe.description Fixture with no declared parameters and undo=none.
# @recipe.category Diagnostics
# @recipe.privilege user
# @recipe.undo none
# @recipe.risk low

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

case "${1:-}" in
  check) recipe_state configured "always ready" ;;
  apply) recipe_note "nothing to do" ;;
  undo)  recipe_die "no undo for this recipe" ;;
  *)     recipe_die "expected action check|apply|undo" ;;
esac
