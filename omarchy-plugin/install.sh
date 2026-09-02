#!/usr/bin/env bash
# Install this working tree as an Omarchy plugin and reload the shell.
#
# The shell only discovers plugins exactly one level under
# ~/.config/omarchy/plugins/, and it refuses a plugin folder containing
# symlinks, so a repository kept elsewhere has to be copied in. The copy is
# self-contained: the QML frontend, the Python engine, the Bash helper library,
# and the recipe tree all land together, so Menu.qml finds the runner at
# <plugin>/bin/omarchy-recipes without anything on $PATH.
#
# Re-run after editing the repository. Set OMARCHY_RECIPES_BIN to point the
# plugin at a different runner instead (useful while iterating on the engine).
set -Eeuo pipefail

PLUGIN_ID=io.github.mdelgert.omarchy-recipes
SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/$PLUGIN_ID"

mkdir -p "$DEST"

# The plugin's own files sit at the plugin root; the engine keeps its
# repository-relative layout underneath so `bin/omarchy-recipes` still finds
# `src/`, `lib/`, `recipes/`, and `skills/` exactly as it does in a checkout.
rsync -a --delete --exclude 'install.sh' "$SRC/omarchy-plugin/" "$DEST/"
rsync -a --delete "$SRC/bin/" "$DEST/bin/"
rsync -a --delete "$SRC/src/" "$DEST/src/"
rsync -a --delete "$SRC/lib/" "$DEST/lib/"
rsync -a --delete "$SRC/recipes/" "$DEST/recipes/"
# The authoring agent reads the skill from the engine root at run time, so the
# rules have to travel with the plugin rather than staying in the checkout.
rsync -a --delete "$SRC/skills/" "$DEST/skills/"

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
  omarchy plugin enable $PLUGIN_ID
  omarchy-shell shell toggle $PLUGIN_ID '{}'
EOF
