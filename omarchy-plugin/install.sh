#!/usr/bin/env bash
# Install this working tree as an Omarchy plugin and reload the shell.
#
# For a normal install, prefer:
#
#   omarchy plugin add https://github.com/mdelgert/omarchy-recipes.git --enable
#
# which clones the repository straight into the plugins directory. This script
# is the development equivalent: it copies the working tree, uncommitted changes
# and all, so you can iterate without pushing.
#
# The copy mirrors the repository exactly rather than rearranging it, so a
# plugin installed from git and one installed from here are the same layout and
# share the one `manifest.json` at the repository root. `.git` is excluded
# because the shell never loads it and it is large.
#
# Re-run after editing. Set OMARCHY_RECIPES_BIN to point the plugin at a
# different runner instead, when iterating on the engine alone.
set -Eeuo pipefail

PLUGIN_ID=io.github.mdelgert.omarchy-recipes
SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/$PLUGIN_ID"

mkdir -p "$DEST"

rsync -a --delete \
  --exclude '.git/' \
  --exclude '.github/' \
  --exclude '.qml-imports/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "$SRC/" "$DEST/"

printf 'installed %s -> %s\n' "$PLUGIN_ID" "$DEST"

if command -v omarchy-plugin-validate >/dev/null 2>&1; then
  omarchy-plugin-validate "$DEST" || { printf 'manifest validation failed\n' >&2; exit 1; }
  printf 'manifest validated\n'
fi

"$DEST/bin/omarchy-recipes" validate >/dev/null || {
  printf 'installed recipes failed validation\n' >&2
  exit 1
}
printf 'recipes validated\n'

# rescanPlugins re-walks the plugin directories and hot-reloads plugin code. It
# needs a running shell; outside a session this is expected to fail.
if command -v omarchy-shell >/dev/null 2>&1; then
  omarchy-shell shell rescanPlugins >/dev/null 2>&1 \
    && printf 'shell reloaded\n' \
    || printf 'could not reach omarchy-shell (is the shell running?)\n' >&2
fi

cat <<EOF

Enable and open it with:
  omarchy plugin enable $PLUGIN_ID right
  omarchy-shell shell toggle $PLUGIN_ID '{}'

Note: a menu plugin's QML is cached by the shell. After changing QML, run
  omarchy-restart-shell
EOF
