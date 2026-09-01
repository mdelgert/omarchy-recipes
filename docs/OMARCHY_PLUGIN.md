# Omarchy plugin integration

Omarchy's current plugin development guide (updated August 13, 2026) defines `menu` as a summoned menu entry point (`Menu.qml`) and `service` as a headless singleton (`Service.qml`). Third-party plugins live under `~/.config/omarchy/plugins/<plugin-id>/`, and Omarchy validates the manifest with `omarchy plugin validate`.

The documentation also warns that plugins share the long-running Omarchy shell process and run unsandboxed with the user's permissions. Keep recipe execution behind the runner boundary rather than embedding arbitrary shell code into QML.

Reference: https://plugins.omarchy.org/develop.html

## Proposed plugin contract

The starter manifest uses a `menu` entry point only. A later version may add a `service` if persistent indexing/state observation is justified.

```json
{
  "schemaVersion": 1,
  "id": "io.github.REPLACE_ME.omarchy-recipes",
  "name": "Omarchy Recipes",
  "version": "0.1.0",
  "author": "REPLACE_ME",
  "license": "MIT",
  "description": "Browse and run self-describing, reversible workstation recipes.",
  "kinds": ["menu"],
  "entryPoints": { "menu": "Menu.qml" }
}
```

## Why the QML starter is intentionally thin

The native menu should be implemented against the current built-in `omarchy.menu` patterns and current Quickshell APIs on an actual Omarchy installation. The project should not duplicate parsing or lifecycle rules in JavaScript/QML.

Native UI implementation sequence:

1. Run `bin/omarchy-recipes list --json` and populate model.
2. Search/filter by title, category, tags.
3. On selection, run `info <id> --json`.
4. Generate controls from `parameters[]`.
5. Run `check <id>` to display current state.
6. Confirm risk/reversibility.
7. Execute `run <id> --<param> <value> ...` in a controlled child process.
8. Stream/display output without interpreting it as commands.
9. Refresh status/history.
10. Expose `undo <id>` only when an eligible successful apply exists.

## Local installation during development

Use a namespaced ID you control. Then place or clone the plugin under:

```text
~/.config/omarchy/plugins/<plugin-id>/
```

Validate:

```bash
omarchy plugin validate ~/.config/omarchy/plugins/<plugin-id>
```

Force discovery if needed:

```bash
omarchy-shell shell rescanPlugins
```

Summon a menu plugin through the shell using its plugin ID; follow the current Omarchy docs/built-in examples for the payload expected by the chosen Menu base component.

## Agent task for the first native GUI PR

Use the current Omarchy built-in `shell/plugins/menu/Menu.qml` as a runtime reference, but create a much smaller recipe-focused menu. Do not copy the huge built-in menu wholesale. Prefer existing `qs.Ui`/`qs.Commons` components, match current panel/menu lifecycle conventions, and validate with `qmllint -I "$OMARCHY_PATH/shell"`.
