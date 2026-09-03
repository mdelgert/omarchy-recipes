#!/usr/bin/env bash
set -Eeuo pipefail

# @recipe.id jsonplaceholder-rest-example
# @recipe.title JSONPlaceholder REST response example
# @recipe.description Fetches a live JSONPlaceholder REST payload and prints the response body.
# @recipe.category Development
# @recipe.platform linux,omarchy
# @recipe.privilege user
# @recipe.undo none
# @recipe.risk low

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

action="${1:-}"
shift || true

if (($#)); then
  recipe_die "unexpected parameters"
fi

case "$action" in
  check)
    recipe_state not-configured "No local state; apply fetches and prints a live REST response"
    ;;

  apply)
    response="$(curl -fsS -- "https://jsonplaceholder.typicode.com/posts/1")"
    [[ -n "$response" ]] || recipe_die "empty response from JSONPlaceholder"
    case "$response" in
      \{*\}) ;;
      *) recipe_die "unexpected response format from JSONPlaceholder" ;;
    esac
    recipe_note "GET https://jsonplaceholder.typicode.com/posts/1"
    printf '%s\n' "$response"
    recipe_summary "Printed the JSONPlaceholder REST response"
    ;;

  undo)
    recipe_die "undo is unsupported: this recipe only fetches and prints a live REST response"
    ;;

  *)
    recipe_die "expected action check|apply|undo"
    ;;
esac
