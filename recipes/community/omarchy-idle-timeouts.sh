#!/usr/bin/env bash
set -Eeuo pipefail

# @recipe.id omarchy-idle-timeouts
# @recipe.title Screensaver and lock timeouts
# @recipe.description Turn the idle screensaver and the idle screen lock on or off, and set how many idle seconds each waits, by editing the idle block of ~/.config/omarchy/shell.json.
# @recipe.category Desktop
# @recipe.platform linux,omarchy
# @recipe.distro arch
# @recipe.privilege user
# @recipe.undo restore
# @recipe.risk low
# @recipe.tags idle,screensaver,lock,timeout,shell
# @recipe.generated-with-ai true
# @recipe.reviewed false
# @param screensaver boolean default=true label="Screensaver on idle" description="Show the screensaver after the session has been idle. Off writes a timeout of 0, which the Omarchy shell treats as disabled."
# @param screensaver-timeout integer required=true default=150 min=10 max=86400 label="Screensaver timeout (seconds)" description="Idle seconds before the screensaver starts. Ignored when the screensaver is off."
# @param lock boolean default=true label="Lock on idle" description="Lock the screen after the session has been idle. Off writes a timeout of 0, which the Omarchy shell treats as disabled."
# @param lock-timeout integer required=true default=300 min=10 max=86400 label="Lock timeout (seconds)" description="Idle seconds before the screen locks. Ignored when idle locking is off."

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

# Idle behaviour on Omarchy is configured in shell.json, not hypridle.conf. The
# shell hot-reloads shell.json on save, so nothing needs restarting. Only the
# idle block is rewritten; bar layout, plugins and every other key are carried
# through unchanged, and the SUPER + CTRL + I "toggle locking on idle" binding
# is left alone.
target="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/shell.json"

action="${1:-}"
shift || true
recipe_parse_args "$@"

require_python() {
  command -v python3 >/dev/null 2>&1 || recipe_die "python3 is required to read and edit $target safely"
}

# Prints "<screensaver> <lock>" as integers, using "-" for a key that is absent
# or not a number. A real JSON parser is used so a hand-formatted file is read
# correctly instead of guessed at with a regex.
read_idle() {
  python3 - "$target" <<'PY'
import json, sys

with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)

idle = data.get("idle") if isinstance(data, dict) else None
if not isinstance(idle, dict):
    idle = {}


def fmt(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "-"
    return str(int(value))


print(fmt(idle.get("screensaver")), fmt(idle.get("lock")))
PY
}

describe_stage() {
  local label="$1" value="$2"
  case "$value" in
    -) printf '%s unset' "$label" ;;
    0) printf '%s off' "$label" ;;
    *) printf '%s %ss' "$label" "$value" ;;
  esac
}

describe() {
  printf '%s, %s' "$(describe_stage screensaver "$1")" "$(describe_stage lock "$2")"
}

case "$action" in
  check)
    # Read-only: parses the file and reports what is currently set.
    if [[ ! -f "$target" ]]; then
      recipe_state not-configured "No $target"
      exit 0
    fi
    require_python
    if ! values="$(read_idle)"; then
      recipe_die "$target is not valid JSON; fix it before running this recipe"
    fi
    read -r current_screensaver current_lock <<<"$values"
    if [[ "$current_screensaver" == "-" && "$current_lock" == "-" ]]; then
      recipe_state not-configured "No idle screensaver or lock timeout in $target"
    else
      recipe_state configured "$(describe "$current_screensaver" "$current_lock")"
    fi
    ;;

  apply)
    require_python

    # The engine validates types and ranges, but this recipe is also runnable
    # straight from a shell, so it validates its own input before any value
    # reaches an arithmetic context or the file.
    screensaver_enabled="${RECIPE_ARG_SCREENSAVER:-true}"
    lock_enabled="${RECIPE_ARG_LOCK:-true}"
    case "$screensaver_enabled" in true|false) ;; *) recipe_die "screensaver must be true or false" ;; esac
    case "$lock_enabled" in true|false) ;; *) recipe_die "lock must be true or false" ;; esac

    screensaver_timeout="${RECIPE_ARG_SCREENSAVER_TIMEOUT:-150}"
    lock_timeout="${RECIPE_ARG_LOCK_TIMEOUT:-300}"
    [[ "$screensaver_timeout" =~ ^[0-9]+$ ]] || recipe_die "screensaver-timeout must be a positive integer"
    [[ "$lock_timeout" =~ ^[0-9]+$ ]] || recipe_die "lock-timeout must be a positive integer"
    ((screensaver_timeout >= 10 && screensaver_timeout <= 86400)) || recipe_die "screensaver-timeout must be between 10 and 86400 seconds"
    ((lock_timeout >= 10 && lock_timeout <= 86400)) || recipe_die "lock-timeout must be between 10 and 86400 seconds"

    desired_screensaver=0
    desired_lock=0
    if [[ "$screensaver_enabled" == "true" ]]; then
      desired_screensaver="$screensaver_timeout"
    fi
    if [[ "$lock_enabled" == "true" ]]; then
      desired_lock="$lock_timeout"
    fi

    if [[ "$screensaver_enabled" == "true" && "$lock_enabled" == "true" ]] && ((desired_lock < desired_screensaver)); then
      recipe_warn "lock fires at ${desired_lock}s, before the screensaver at ${desired_screensaver}s; the screensaver will never be seen"
    fi

    if [[ -f "$target" ]]; then
      if ! current="$(read_idle)"; then
        recipe_die "$target is not valid JSON; fix it before running this recipe"
      fi
      read -r current_screensaver current_lock <<<"$current"
      if [[ "$current_screensaver" == "$desired_screensaver" && "$current_lock" == "$desired_lock" ]]; then
        recipe_summary "Already configured: $(describe "$desired_screensaver" "$desired_lock")"
        recipe_note "Already configured: $target"
        exit 0
      fi
      recipe_backup_file "$target"
    elif [[ -e "$target" || -L "$target" ]]; then
      recipe_die "$target exists but is not a regular file"
    else
      current_screensaver="-"
      current_lock="-"
      recipe_mark_absent "$target"
    fi

    new_json="$(python3 - "$target" "$desired_screensaver" "$desired_lock" <<'PY'
import json, os, sys

path = sys.argv[1]
screensaver = int(sys.argv[2])
lock = int(sys.argv[3])

existed = os.path.exists(path)
data = {}
if existed:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
if not isinstance(data, dict):
    raise SystemExit("shell.json must contain a JSON object")

idle = data.get("idle")
if not isinstance(idle, dict):
    idle = {}
idle["screensaver"] = screensaver
idle["lock"] = lock
data["idle"] = idle
if not existed:
    # A file written from scratch still needs the schema version the shell reads.
    data["version"] = 1

print(json.dumps(data, indent=2, sort_keys=True))
PY
)"
    printf '%s\n' "$new_json" | recipe_atomic_write "$target"

    verify="$(read_idle)"
    read -r new_screensaver new_lock <<<"$verify"
    if [[ "$new_screensaver" != "$desired_screensaver" || "$new_lock" != "$desired_lock" ]]; then
      recipe_die "verification failed: $target now reports $(describe "$new_screensaver" "$new_lock")"
    fi

    recipe_summary "$(describe "$current_screensaver" "$current_lock") → $(describe "$desired_screensaver" "$desired_lock")"
    recipe_note "Updated the idle block in $target (other keys untouched; JSON reformatted to 2-space indent)."
    recipe_note "The Omarchy shell reloads shell.json on save, so no restart is needed."
    ;;

  undo)
    recipe_restore_file "$target"
    if [[ ! -e "$target" ]]; then
      recipe_summary "Removed $target; it did not exist before"
    elif command -v python3 >/dev/null 2>&1 && restored="$(read_idle)"; then
      read -r restored_screensaver restored_lock <<<"$restored"
      recipe_summary "Restored: $(describe "$restored_screensaver" "$restored_lock")"
    else
      recipe_summary "Restored previous $target"
    fi
    recipe_note "Restored prior state for $target"
    ;;

  *) recipe_die "expected action check|apply|undo" ;;
esac
