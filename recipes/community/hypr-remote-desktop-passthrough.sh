#!/usr/bin/env bash
# @recipe.id hypr-remote-desktop-passthrough
# @recipe.title Keybinding passthrough mode for remote desktop sessions
# @recipe.description Adds a Hyprland passthrough submap plus a SUPER + CTRL + ALT + ESCAPE toggle to ~/.config/hypr/bindings.lua. While passthrough is engaged every other Omarchy keybinding is suspended, so keys such as SUPER + RETURN or CTRL + ALT + DELETE reach a VNC, RDP, or Guacamole session instead of the local compositor; pressing the same combination again leaves the mode. The Lua block is appended to the existing file, which is backed up first, and no existing binding is changed or removed.
# @recipe.category Desktop
# @recipe.privilege user
# @recipe.undo restore
# @recipe.risk medium
# @recipe.generated-with-ai true
# @recipe.reviewed false

set -Eeuo pipefail

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

RECIPE_ID="hypr-remote-desktop-passthrough"
TARGET="${HOME}/.config/hypr/bindings.lua"
MARKER_BEGIN="-- >>> omarchy-recipes: ${RECIPE_ID}"
MARKER_END="-- <<< omarchy-recipes: ${RECIPE_ID}"
COMBO="SUPER + CTRL + ALT + ESCAPE"
SUBMAP="passthrough"

# The Lua block appended to bindings.lua. hl.define_submap registers a modal
# keybinding layer; the only binding inside the layer is the one that leaves it,
# so the mode can always be escaped with the same combination that entered it.
managed_block() {
  printf '%s\n' \
    "" \
    "${MARKER_BEGIN}" \
    "-- Passthrough mode for remote desktop sessions (VNC/RDP/Guacamole)." \
    "--" \
    "-- While the submap is active every binding outside it goes dead. That is the" \
    "-- point: SUPER + RETURN, SUPER + 1..4, CTRL + ALT + DELETE and friends stop" \
    "-- being swallowed by Hyprland and reach the remote machine instead. The exit" \
    "-- key below is the only host binding left while the mode is engaged." \
    "hl.define_submap(\"${SUBMAP}\", function()" \
    "  hl.bind(\"${COMBO}\", hl.dsp.submap(\"reset\"), { description = \"Leave passthrough\" })" \
    "end)" \
    "" \
    "o.bind(\"${COMBO}\", \"Passthrough mode (remote desktop)\", hl.dsp.submap(\"${SUBMAP}\"))" \
    "${MARKER_END}"
}

hyprland_running() {
  command -v hyprctl >/dev/null 2>&1 || return 1
  hyprctl version >/dev/null 2>&1
}

block_present() {
  [[ -f "${TARGET}" ]] && grep -qF -- "${MARKER_BEGIN}" "${TARGET}"
}

# The file with this recipe's own block removed, so conflict detection never
# trips over the lines the recipe itself wrote.
without_block() {
  [[ -f "${TARGET}" ]] || return 0
  awk -v begin_marker="${MARKER_BEGIN}" -v end_marker="${MARKER_END}" '
    index($0, begin_marker) { skip = 1 }
    !skip { print }
    index($0, end_marker) { skip = 0 }
  ' "${TARGET}"
}

# True if an active (non-comment) line outside the managed block already binds
# the combo or defines the submap.
foreign_binding_present() {
  [[ -f "${TARGET}" ]] || return 1
  local active
  active="$(without_block | grep -v '^[[:space:]]*--' || true)"
  [[ -n "${active}" ]] || return 1
  grep -qF -e "bind(\"${COMBO}\"" -e "define_submap(\"${SUBMAP}\"" <<<"${active}"
}

# Read-only query of the running compositor: is the submap actually loaded?
live_submap_present() {
  hyprland_running || return 1
  local binds
  binds="$(hyprctl -j binds 2>/dev/null || true)"
  [[ -n "${binds}" ]] || return 1
  grep -qF "\"submap\": \"${SUBMAP}\"" <<<"${binds}"
}

# Read-only query: does Hyprland currently report a clean config?
config_clean() {
  hyprland_running || return 1
  local out
  out="$(hyprctl configerrors 2>/dev/null || true)"
  [[ "${out}" == *"no errors"* ]]
}

reload_hyprland() {
  if ! hyprland_running; then
    recipe_note "Hyprland is not running in this session; the change applies on next login"
    return 0
  fi
  if hyprctl reload >/dev/null 2>&1; then
    recipe_note "Reloaded the running Hyprland configuration"
  else
    recipe_note "Could not reload Hyprland automatically; run 'hyprctl reload' or relog to pick up the change"
  fi
}

do_check() {
  if ! command -v hyprctl >/dev/null 2>&1; then
    recipe_note "hyprctl is not on PATH; this recipe only has an effect on a Hyprland session"
  fi

  if [[ ! -f "${TARGET}" ]]; then
    recipe_state not-configured "${TARGET} does not exist; ${COMBO} does not toggle passthrough"
    return 0
  fi

  if block_present; then
    if hyprland_running && ! live_submap_present; then
      recipe_note "The managed block is in ${TARGET}, but the running compositor does not list a '${SUBMAP}' submap; run 'hyprctl reload' or relog"
    fi
    recipe_state configured "${COMBO} toggles the '${SUBMAP}' submap via the managed block in ${TARGET}"
    return 0
  fi

  if foreign_binding_present; then
    recipe_note "${COMBO} or a '${SUBMAP}' submap is already defined in ${TARGET} by a line this recipe does not manage; applying would duplicate it"
    recipe_state not-configured "passthrough is configured in ${TARGET}, but not by this recipe"
    return 0
  fi

  recipe_state not-configured "${COMBO} is not bound in ${TARGET}"
}

do_apply() {
  if block_present; then
    recipe_summary "Already configured"
    recipe_note "${COMBO} already toggles the '${SUBMAP}' submap; nothing to change"
    return 0
  fi

  if foreign_binding_present; then
    echo "${COMBO} or a '${SUBMAP}' submap is already defined in ${TARGET} by a line this recipe does not manage." >&2
    echo "Remove or rename that definition first so this recipe does not create a duplicate." >&2
    return 1
  fi

  # Was the config already clean before the change? Only then can a new config
  # error be attributed to this recipe.
  local was_clean=0
  if config_clean; then
    was_clean=1
  fi

  local rollback
  rollback="$(mktemp "${TMPDIR:-/tmp}/${RECIPE_ID}.rollback.XXXXXX")"
  trap 'rm -f -- "${rollback}" || true' RETURN

  local had_target=0
  if [[ -e "${TARGET}" || -L "${TARGET}" ]]; then
    had_target=1
    recipe_backup_file "${TARGET}"
    cp -a -- "${TARGET}" "${rollback}"
    { cat -- "${TARGET}"; managed_block; } | recipe_atomic_write "${TARGET}"
  else
    recipe_mark_absent "${TARGET}"
    managed_block | recipe_atomic_write "${TARGET}"
  fi

  if ! block_present; then
    echo "Failed to write the passthrough block into ${TARGET}" >&2
    return 1
  fi

  reload_hyprland

  # If the reload turned a previously clean config into a broken one, put the
  # file back the way it was rather than leaving a half-working config behind.
  if ((was_clean)) && ! config_clean; then
    if ((had_target)); then
      cat -- "${rollback}" | recipe_atomic_write "${TARGET}"
    else
      rm -f -- "${TARGET}"
    fi
    hyprctl reload >/dev/null 2>&1 || true
    echo "Hyprland reported configuration errors after adding the passthrough submap:" >&2
    hyprctl configerrors >&2 || true
    echo "Reverted ${TARGET}. This Omarchy version may not provide hl.define_submap or hl.dsp.submap." >&2
    return 1
  fi

  if hyprland_running && ! live_submap_present; then
    recipe_note "The compositor does not list the '${SUBMAP}' submap yet; it appears once a bound key first enters the mode, or after a relog"
  fi

  recipe_summary "${COMBO} → toggle '${SUBMAP}' submap"
  recipe_note "Added the passthrough submap and its toggle to ${TARGET}"
  recipe_note "Press ${COMBO} to suspend all Omarchy keybindings for a remote session, and the same keys again to restore them"
}

do_undo() {
  # Leave the submap first: after the block is gone there would be no binding
  # left to exit it with.
  if hyprland_running; then
    hyprctl dispatch submap reset >/dev/null 2>&1 || true
  fi

  recipe_restore_file "${TARGET}"

  if block_present; then
    echo "Restore left the managed passthrough block in ${TARGET}" >&2
    return 1
  fi

  reload_hyprland
  recipe_summary "${COMBO} → unbound"
  recipe_note "Restored ${TARGET} to its state before this recipe ran"
}

case "${1:-}" in
  check)
    do_check
    ;;
  apply)
    do_apply
    ;;
  undo)
    do_undo
    ;;
  *)
    echo "usage: $0 {check|apply|undo}" >&2
    exit 2
    ;;
esac
