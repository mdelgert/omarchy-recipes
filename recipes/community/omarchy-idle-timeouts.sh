#!/usr/bin/env bash
set -Eeuo pipefail

# @recipe.id omarchy-idle-timeouts
# @recipe.title Screensaver and lock timeouts
# @recipe.description Set how long the session waits before the screensaver appears and before the screen locks, or keep the session awake so neither ever runs. Writes only the idle block of ~/.config/omarchy/shell.json and uses Omarchy's own stay-awake switch.
# @recipe.category Desktop
# @recipe.platform linux,omarchy
# @recipe.distro arch
# @recipe.privilege user
# @recipe.undo restore
# @recipe.risk low
# @recipe.tags idle,screensaver,lock,timeout,awake,presentation
# @recipe.generated-with-ai true
# @recipe.reviewed false

# @param mode choice choices=timed,stay-awake default=timed label="Idle behaviour" description="timed runs the screensaver and lock after the timeouts below. stay-awake keeps the session awake so neither ever runs, which is the supported way to switch idle off."
# @param screensaver integer default=150 min=10 max=86400 label="Screensaver timeout (seconds)" description="Idle seconds before the screensaver appears. The Omarchy default is 150."
# @param lock integer default=300 min=10 max=86400 label="Lock timeout (seconds)" description="Idle seconds before the screen locks. The Omarchy default is 300."

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

# Idle behaviour on Omarchy lives in two places, and both matter:
#
#   1. The timeouts in the idle block of shell.json. The shell hot-reloads the
#      file on save, so nothing needs restarting.
#
#   2. A stay-awake marker file that the shell's idle service checks. While it
#      exists, neither the screensaver nor the lock runs at all, whatever the
#      timeouts say. `omarchy toggle idle` owns that file.
#
# There is no "0 means never". Reading the shell's own idle service settles it
# (plugins/services/idle/IdleModel.js):
#
#       if (!isFinite(n) || n < 0) return fallback
#       return Math.floor(n)
#
# Only a negative or unparsable value falls back to the default; 0 is kept as a
# literal zero-second timeout, so the action fires the moment the session goes
# idle. Writing 0 to switch idle off does the exact opposite. That is why the
# minimum here is 10 and why switching idle off is a mode rather than a 0 — the
# engine rejects an out-of-range value before this script ever runs.

STATE_FILE="$HOME/.local/state/omarchy/indicators/stay-awake"
SHELL_JSON="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/shell.json"

# `omarchy-toggle-idle` hardcodes $HOME/.local/state rather than honouring
# XDG_STATE_HOME. Match it exactly: a path that disagrees with the command
# would leave this recipe reporting a state the shell does not act on.

want_mode() { printf '%s' "${RECIPE_ARG_MODE:-timed}"; }
want_screensaver() { printf '%s' "${RECIPE_ARG_SCREENSAVER:-150}"; }
want_lock() { printf '%s' "${RECIPE_ARG_LOCK:-300}"; }

require_tools() {
  command -v omarchy-toggle-idle >/dev/null 2>&1 \
    || recipe_die "omarchy-toggle-idle not found; this recipe needs an Omarchy shell"
  command -v python3 >/dev/null 2>&1 \
    || recipe_die "python3 not found; needed to edit shell.json without disturbing other keys"
}

stay_awake_on() { [[ -f "$STATE_FILE" ]]; }

current_mode() { if stay_awake_on; then printf 'stay-awake'; else printf 'timed'; fi; }

# Prints "<screensaver> <lock>", using "-" for a key that is absent or
# unreadable. Read-only: parses the file and prints, and never writes.
read_idle() {
  SHELL_JSON="$SHELL_JSON" python3 - <<'PY'
import json, os
path = os.environ["SHELL_JSON"]
try:
    with open(path) as handle:
        data = json.load(handle)
except (OSError, ValueError):
    print("- -")
    raise SystemExit(0)
idle = data.get("idle") if isinstance(data, dict) else None
if not isinstance(idle, dict):
    idle = {}
def fmt(value):
    return str(int(value)) if isinstance(value, (int, float)) and not isinstance(value, bool) else "-"
print(fmt(idle.get("screensaver")), fmt(idle.get("lock")))
PY
}

# Rewrites only the two idle timeouts. Every other key in shell.json — bar
# layout, plugins, theme — is loaded and written back untouched.
write_idle() {
  SHELL_JSON="$SHELL_JSON" WANT_SCREENSAVER="$1" WANT_LOCK="$2" python3 - <<'PY'
import json, os
path = os.environ["SHELL_JSON"]
with open(path) as handle:
    data = json.load(handle)
if not isinstance(data, dict):
    raise SystemExit("shell.json is not a JSON object")
idle = data.get("idle")
if not isinstance(idle, dict):
    idle = {}
idle["screensaver"] = int(os.environ["WANT_SCREENSAVER"])
idle["lock"] = int(os.environ["WANT_LOCK"])
data["idle"] = idle
with open(path, "w") as handle:
    json.dump(data, handle, indent=2)
    handle.write("\n")
PY
}

describe() {
  local screensaver lock
  read -r screensaver lock <<<"$(read_idle)"
  printf '%s; screensaver=%s lock=%s' "$(current_mode)" "$screensaver" "$lock"
}

at_desired_state() {
  local screensaver lock
  read -r screensaver lock <<<"$(read_idle)"
  [[ "$(current_mode)" == "$(want_mode)" ]] \
    && [[ "$screensaver" == "$(want_screensaver)" ]] \
    && [[ "$lock" == "$(want_lock)" ]]
}

# The screensaver is meant to appear before the lock. A longer screensaver
# timeout is not broken — the shell just locks first and the screensaver never
# meaningfully shows — so this is worth saying, not worth refusing.
warn_if_ordered_oddly() {
  if (( $(want_screensaver) > $(want_lock) )); then
    recipe_warn "screensaver ($(want_screensaver)s) is longer than lock ($(want_lock)s), so the screen will lock before the screensaver appears"
  fi
}

case "${1:-}" in
  check)
    shift || true
    recipe_parse_args "$@"
    require_tools

    detail="$(describe)"
    recipe_note "$detail"
    recipe_note "wanted: $(want_mode); screensaver=$(want_screensaver) lock=$(want_lock)"

    # A 0 already in the file is worth calling out whatever the request was:
    # it means the action fires instantly, which reads as a broken lock screen.
    read -r have_screensaver have_lock <<<"$(read_idle)"
    if [[ "$have_screensaver" == "0" || "$have_lock" == "0" ]]; then
      recipe_note "a timeout of 0 is present; the shell reads that as fire-immediately, not as disabled"
    fi

    if at_desired_state; then
      recipe_state configured "$detail"
    else
      recipe_state not-configured "$detail"
    fi
    ;;

  apply)
    shift || true
    recipe_parse_args "$@"
    require_tools
    warn_if_ordered_oddly

    before="$(describe)"

    if at_desired_state; then
      recipe_summary "Already set"
      recipe_note "$before"
      exit 0
    fi

    [[ -e "$SHELL_JSON" ]] || recipe_die "$SHELL_JSON does not exist"

    # Capture exact prior state before any write, so undo restores what was
    # there rather than a guess. The marker file often does not exist yet.
    recipe_backup_file "$SHELL_JSON"
    if [[ -e "$STATE_FILE" || -L "$STATE_FILE" ]]; then
      recipe_backup_file "$STATE_FILE"
    else
      recipe_mark_absent "$STATE_FILE"
    fi

    write_idle "$(want_screensaver)" "$(want_lock)"

    # Let the command own its own marker file rather than touching it here, so
    # this keeps working if Omarchy changes where the marker lives.
    if [[ "$(want_mode)" == "stay-awake" ]]; then
      omarchy-toggle-idle stay-awake >/dev/null
    else
      omarchy-toggle-idle allow-idle >/dev/null
    fi

    at_desired_state || recipe_die "settings did not take effect: $(describe)"

    if [[ "$(want_mode)" == "stay-awake" ]]; then
      recipe_summary "Staying awake; timeouts $(want_screensaver)s / $(want_lock)s kept for when idle is re-enabled"
    else
      recipe_summary "Screensaver $(want_screensaver)s, lock $(want_lock)s"
    fi
    recipe_note "$before  ->  $(describe)"
    ;;

  undo)
    shift || true
    recipe_parse_args "$@"
    require_tools

    before="$(describe)"

    # Restore both to exactly what was captured. For a marker that was absent
    # beforehand this removes it, which is what re-enables idle.
    recipe_restore_file "$SHELL_JSON"
    recipe_restore_file "$STATE_FILE"

    recipe_summary "Restored the previous idle settings"
    recipe_note "$before  ->  $(describe)"
    ;;

  *)
    recipe_die "usage: $0 {check|apply|undo}"
    ;;
esac
