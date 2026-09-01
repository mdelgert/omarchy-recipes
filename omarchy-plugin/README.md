# Omarchy native plugin scaffold

This folder is the starting point for the native Quattro frontend.

Before use:

1. Replace `REPLACE_ME` in `manifest.json` with the GitHub namespace/author.
2. Implement `Menu.qml` against the current Omarchy built-in menu examples.
3. Ensure the `omarchy-recipes` runner is installed or addressable by an absolute/configured path.
4. Validate with `omarchy plugin validate` and `qmllint` as documented in `docs/OMARCHY_PLUGIN.md`.

The empty QML entry point is intentional: the core engine is runnable and tested now; the native UI should be authored/tested on the actual current Omarchy shell rather than guessed from stale Quickshell conventions.
