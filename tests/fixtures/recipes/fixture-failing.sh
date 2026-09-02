#!/usr/bin/env bash
set -Eeuo pipefail

# Test fixture: both check and apply fail, so the engine's failure reporting
# can be exercised without a real broken system.

# @recipe.id fixture-failing
# @recipe.title Always fails
# @recipe.description Fixture whose check and apply both exit non-zero.
# @recipe.category Failures
# @recipe.privilege user
# @recipe.undo restore
# @recipe.risk medium

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

case "${1:-}" in
  check) recipe_die "cannot determine state: dependency missing" ;;
  apply) recipe_die "refusing to apply: dependency missing" ;;
  undo)  recipe_die "nothing to undo" ;;
  *)     recipe_die "expected action check|apply|undo" ;;
esac
