#!/usr/bin/env bash
set -Eeuo pipefail

# @recipe.id error-log-report
# @recipe.title Error Log Report
# @recipe.description Installs a read-only error log report (recent journal errors, failed systemd units, recent coredumps) and adds a row for it to the Omarchy menu extension file.
# @recipe.category System
# @recipe.platform linux,omarchy
# @recipe.privilege user
# @recipe.undo restore
# @recipe.risk low
# @recipe.tags report,logs,journalctl,diagnostics,systemd
# @recipe.generated-with-ai true
# @recipe.reviewed false

source "${OMARCHY_RECIPES_LIB:?}/recipe.sh"

report_bin="$HOME/.local/bin/omarchy-error-log-report"
menu_file="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/extensions/omarchy-menu.jsonc"
menu_key='"error-log-report"'

menu_entry="$(cat <<'ENTRY'
  "error-log-report": {"icon":"","label":"Error Log Report","description":"Recent journal errors, failed units, and coredumps","action":"omarchy-launch-or-focus-tui \"bash -c '~/.local/bin/omarchy-error-log-report; read -n 1'\""},
ENTRY
)"

menu_has_entry() {
  [[ -f "$menu_file" ]] && grep -Fq "$menu_key" "$menu_file"
}

# Print the menu file with the entry inserted before its final closing brace.
# Exits 3 when no top-level closing brace can be located, so the caller can
# fail loudly instead of rewriting a file it did not understand.
insert_entry() {
  awk -v entry="$menu_entry" '
    { line[NR] = $0 }
    /^[[:space:]]*\}[[:space:]]*$/ { last = NR }
    END {
      if (!last) exit 3
      for (i = 1; i <= NR; i++) {
        if (i == last) print entry
        print line[i]
      }
    }
  ' "$1"
}

write_report_bin() {
  cat <<'REPORT' | recipe_atomic_write "$report_bin"
#!/usr/bin/env bash
# Read-only report of current error logs.
# Installed by the omarchy-recipes recipe "error-log-report".
# Usage: omarchy-error-log-report [line-count]   (default 50)
#
# This script only reads logs. It never clears, rotates, or writes to them.
set -uo pipefail

lines="${1:-50}"
case "$lines" in
  '' | *[!0-9]*)
    printf 'usage: %s [line-count]\n' "${0##*/}" >&2
    exit 2
    ;;
esac

section() { printf '\n== %s ==\n\n' "$1"; }

printf 'Error log report for %s at %s\n' "$(hostname 2>/dev/null || printf 'this machine')" "$(date '+%Y-%m-%d %H:%M:%S')"

section "Failed system units"
systemctl --failed --no-pager --no-legend || printf 'Unable to query system units.\n'

section "Failed user units"
systemctl --user --failed --no-pager --no-legend || printf 'Unable to query user units.\n'

section "System journal errors this boot (last $lines)"
if ! journalctl --boot --priority=err --no-pager --lines="$lines" 2>/dev/null; then
  printf 'Unable to read the system journal. Membership in the systemd-journal or wheel group is required.\n'
fi

section "User journal errors this boot (last $lines)"
if ! journalctl --user --boot --priority=err --no-pager --lines="$lines" 2>/dev/null; then
  printf 'No readable user journal.\n'
fi

section "Coredumps in the last 7 days"
if command -v coredumpctl >/dev/null 2>&1; then
  coredumpctl list --since=-7d --no-pager 2>/dev/null || printf 'No coredumps recorded in the last 7 days.\n'
else
  printf 'coredumpctl is not installed.\n'
fi

printf '\nThis report only read logs. Nothing was changed.\n'
REPORT
}

restore_if_recorded() {
  local target="$1" index
  index="${OMARCHY_RECIPES_SOURCE_RUN_DIR:-}/backup-index.tsv"
  [[ -n "${OMARCHY_RECIPES_SOURCE_RUN_DIR:-}" && -f "$index" ]] || return 1
  awk -F '\t' -v p="$target" '$3 == p { found = 1 } END { exit found ? 0 : 1 }' "$index" || return 1
  recipe_restore_file "$target"
}

case "${1:-}" in
  check)
    if command -v journalctl >/dev/null 2>&1; then
      recipe_note "journalctl is available"
    else
      recipe_note "journalctl was not found; the report would have nothing to read"
    fi

    if [[ -x "$report_bin" ]]; then
      recipe_note "Report script installed: $report_bin"
    else
      recipe_note "Report script not installed: $report_bin"
    fi

    if menu_has_entry; then
      recipe_note "Menu entry present in $menu_file"
    else
      recipe_note "Menu entry absent from $menu_file"
    fi

    if [[ -x "$report_bin" ]] && menu_has_entry; then
      recipe_state configured "Report installed and listed in the Omarchy menu"
    else
      recipe_state not-configured "Report script or menu entry missing"
    fi
    ;;

  apply)
    if [[ -x "$report_bin" ]] && menu_has_entry; then
      recipe_note "Already configured: $report_bin and the menu entry are both present"
      recipe_summary "Already configured"
      exit 0
    fi

    if [[ -e "$report_bin" || -L "$report_bin" ]]; then
      recipe_backup_file "$report_bin"
    else
      recipe_mark_absent "$report_bin"
    fi
    write_report_bin
    chmod 755 "$report_bin"
    bash -n "$report_bin" || recipe_die "generated report script is not valid bash: $report_bin"

    if [[ -e "$menu_file" || -L "$menu_file" ]]; then
      recipe_backup_file "$menu_file"
    else
      recipe_mark_absent "$menu_file"
      printf '{\n}\n' | recipe_atomic_write "$menu_file"
    fi

    if menu_has_entry; then
      recipe_note "Menu entry already present in $menu_file"
    else
      updated="$(insert_entry "$menu_file")" ||
        recipe_die "could not find the top-level closing brace of $menu_file; add the menu entry by hand"
      printf '%s\n' "$updated" | recipe_atomic_write "$menu_file"
    fi

    [[ -x "$report_bin" ]] || recipe_die "verification failed: $report_bin is not executable"
    menu_has_entry || recipe_die "verification failed: menu entry missing from $menu_file"

    if ! command -v omarchy-launch-or-focus-tui >/dev/null 2>&1; then
      recipe_warn "omarchy-launch-or-focus-tui was not found on PATH; the menu row cannot open a terminal until it is. The report still runs directly: $report_bin"
    fi

    recipe_note "Installed $report_bin"
    recipe_note "Added the \"Error Log Report\" row to $menu_file"
    recipe_note "Run it from a terminal with: $report_bin"
    recipe_summary "Error log report installed and added to the Omarchy menu"
    ;;

  undo)
    restored=0
    if restore_if_recorded "$menu_file"; then
      recipe_note "Restored prior state for $menu_file"
      restored=1
    fi
    if restore_if_recorded "$report_bin"; then
      recipe_note "Restored prior state for $report_bin"
      restored=1
    fi
    ((restored)) || recipe_die "no backup state was recorded for this recipe; nothing to restore"

    if menu_has_entry; then
      recipe_note "Menu entry still present; it existed before this recipe ran"
    fi
    recipe_summary "Reverted the error log report installation"
    ;;

  *) recipe_die "expected action check|apply|undo" ;;
esac
