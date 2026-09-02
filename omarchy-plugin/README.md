# Omarchy Recipes — native plugin

The Omarchy `menu` frontend for `omarchy-recipes`. It discovers recipes through
the engine's JSON interface and renders them; it contains no knowledge of any
individual recipe.

```bash
./install.sh                                           # or: make plugin
omarchy plugin enable io.github.mdelgert.omarchy-recipes right
```

Opens from the bar icon, from `omarchy-shell shell toggle
io.github.mdelgert.omarchy-recipes '{}'`, or from a keybinding you add.

## Layering

```text
BarWidget.qml       bar icon; opens the menu, holds no state
Menu.qml            surface, navigation, keys, confirmation
  RecipeDetail.qml  generated form, status, actions, output, history
  ParameterControl.qml   one control per declared parameter type
RecipeEngine.qml    every engine call; the only file that talks to the runner
RecipeModel.js      pure presentation helpers (unit tested by `make test-qml`)
```

## Rules this frontend keeps

- The engine is the authoritative boundary. No recipe parsing, parameter
  validation, backup logic, state management, or execution logic lives here.
- Parameter values reach the runner as argv entries. No command string is built
  from metadata or user input, and there is no `eval`.
- Recipe metadata and recipe output are untrusted: they render as
  `Text.PlainText` and are never turned into QML or JavaScript.
- Selecting a recipe runs only the non-mutating `check`. Apply and Undo require
  an explicit, confirmed action.
- Adding a recipe never requires a change in this directory.

See [`../docs/OMARCHY_PLUGIN.md`](../docs/OMARCHY_PLUGIN.md) for the runner
resolution order, the development loop, and manual testing steps.
