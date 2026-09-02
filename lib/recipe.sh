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
