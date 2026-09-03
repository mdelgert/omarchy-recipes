#!/usr/bin/env bash
# Shared helper functions for omarchy-recipes Bash recipes.

recipe_note() { printf '%s\n' "$*"; }
recipe_warn() { printf 'warning: %s\n' "$*" >&2; }
recipe_die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# Report the state `check` found, so frontends read a value instead of
# guessing from prose. The engine strips these marker lines out of the text it
# hands a UI for display; the raw stream still lands in the run log.
#
#   recipe_state configured "mode=balanced"
#
# States: configured | not-configured | partial | unsupported | unknown
recipe_state() {
  printf '@recipe.state %s\n' "$1"
  if (($# > 1)); then
    shift
    recipe_summary "$@"
  fi
}

# One-line human summary of the current or resulting state. Safe to call from
# check, apply, and undo.
recipe_summary() { printf '@recipe.summary %s\n' "$*"; }

recipe_require_runtime() {
  : "${OMARCHY_RECIPES_RUN_DIR:?recipe must be executed by omarchy-recipes}"
  : "${OMARCHY_RECIPES_BACKUP_DIR:?missing backup directory}"
}

# Run one command with root privileges, asking wherever the user can actually
# answer.
#
#   recipe_sudo pacman -S --needed --noconfirm nano
#
# Use this instead of bare `sudo`. A recipe is run by the engine as a
# subprocess with its output captured, so when it is launched from the menu
# there is no terminal attached and plain `sudo` cannot prompt — it fails with
# "sudo: a terminal is required to read the password", which reads to the user
# as a broken recipe rather than a missing password.
#
# The rules below are ordered cheapest-first, so a recipe behaves correctly in
# all three contexts without knowing which one it is in:
#
#   already root      nothing to elevate
#   passwordless      no prompt at all (NOPASSWD rules, CI, containers)
#   a terminal        sudo asks there, as it would for any CLI tool
#   no terminal       pkexec asks through the desktop's polkit agent
#
# Only the single command passed here is elevated. Do not wrap the whole
# recipe.
recipe_sudo() {
  (($#)) || recipe_die "recipe_sudo needs a command to run"

  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
    return
  fi

  if sudo -n true 2>/dev/null; then
    sudo -n "$@"
    return
  fi

  # `-t 0` alone is not enough: the engine gives a recipe an empty stdin, so a
  # run from the menu can still look readable. Requiring stderr too matches
  # where sudo actually writes its prompt.
  if [[ -t 0 && -t 2 ]]; then
    sudo "$@"
    return
  fi

  if command -v pkexec >/dev/null 2>&1; then
    pkexec "$@"
    return
  fi

  recipe_die "this step needs root, but there is no terminal to ask in and pkexec is not installed"
}

recipe_path_key() {
  # Hex encoding avoids collisions involving slash/underscore substitutions.
  printf '%s' "$1" | od -An -tx1 | tr -d ' \n'
}

recipe_index_file() {
  printf '%s/backup-index.tsv' "${OMARCHY_RECIPES_RUN_DIR:?}"
}

recipe_backup_file() {
  recipe_require_runtime
  local target="$1" key dest index
  [[ -e "$target" || -L "$target" ]] || recipe_die "cannot backup absent path: $target (use recipe_mark_absent)"
  key="$(recipe_path_key "$target")"
  dest="$OMARCHY_RECIPES_BACKUP_DIR/$key"
  index="$(recipe_index_file)"
  if grep -Fq $'\tpresent\t'"$target"$'\t' "$index" 2>/dev/null; then
    return 0
  fi
  cp -a -- "$target" "$dest"
  printf '%s\tpresent\t%s\t%s\n' "$key" "$target" "$dest" >> "$index"
}

recipe_mark_absent() {
  recipe_require_runtime
  local target="$1" key index
  [[ ! -e "$target" && ! -L "$target" ]] || recipe_die "path exists; use recipe_backup_file: $target"
  key="$(recipe_path_key "$target")"
  index="$(recipe_index_file)"
  grep -Fq $'\tabsent\t'"$target"$'\t' "$index" 2>/dev/null || printf '%s\tabsent\t%s\t-\n' "$key" "$target" >> "$index"
}

recipe_restore_file() {
  local target="$1" source index line state backup
  source="${OMARCHY_RECIPES_SOURCE_RUN_DIR:?undo requires OMARCHY_RECIPES_SOURCE_RUN_DIR}"
  index="$source/backup-index.tsv"
  [[ -f "$index" ]] || recipe_die "source run has no backup index"
  line="$(awk -F '\t' -v p="$target" '$3 == p {print; exit}' "$index")"
  [[ -n "$line" ]] || recipe_die "no backup state recorded for $target"
  IFS=$'\t' read -r _key state _path backup <<< "$line"
  case "$state" in
    present)
      [[ -e "$backup" || -L "$backup" ]] || recipe_die "backup payload missing: $backup"
      rm -rf -- "$target"
      mkdir -p -- "$(dirname -- "$target")"
      cp -a -- "$backup" "$target"
      ;;
    absent)
      rm -rf -- "$target"
      ;;
    *) recipe_die "invalid backup state for $target: $state" ;;
  esac
}

recipe_atomic_write() {
  # Usage: printf ... | recipe_atomic_write /path/to/file
  local target="$1" dir tmp
  dir="$(dirname -- "$target")"
  mkdir -p -- "$dir"
  tmp="$(mktemp --tmpdir="$dir" ".$(basename -- "$target").XXXXXX")"
  cat > "$tmp"
  if [[ -e "$target" ]]; then
    chmod --reference="$target" "$tmp" 2>/dev/null || true
  fi
  mv -f -- "$tmp" "$target"
}

recipe_parse_args() {
  while (($#)); do
    [[ "$1" == --* ]] || recipe_die "expected --parameter, got: $1"
    local name="${1#--}"
    shift
    (($#)) || recipe_die "missing value for --$name"
    local value="$1"
    shift
    local var="RECIPE_ARG_${name^^}"
    var="${var//-/_}"
    printf -v "$var" '%s' "$value"
    export "$var"
  done
}
