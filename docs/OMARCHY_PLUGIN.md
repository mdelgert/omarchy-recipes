# Omarchy plugin integration

The native frontend is an Omarchy `menu` plugin: a summoned layer-shell card
that lists recipes by category, searches them, and drills into one recipe's
generated form, status, output, and history. It also declares `bar-widget`, so
a bar icon opens that same menu — the pattern Omarchy's own menu plugin uses.

Omarchy's plugin guide defines `menu` as a summoned entry point (`Menu.qml`),
validated with `omarchy plugin validate`. Third-party plugins live one level
under `~/.config/omarchy/plugins/<plugin-id>/`. Plugins share the long-running
Omarchy shell process and run unsandboxed with the user's permissions, which is
why recipe execution stays behind the runner boundary instead of being embedded
in QML.

Reference: https://plugins.omarchy.org/develop.html

## Plugin contract

```json
{
  "schemaVersion": 1,
  "id": "io.github.mdelgert.omarchy-recipes",
  "kinds": ["menu", "bar-widget"],
  "entryPoints": {
    "menu": "omarchy-plugin/Menu.qml",
    "barWidget": "omarchy-plugin/BarWidget.qml"
  },
  "barWidget": { "displayName": "Recipes", "defaultSection": "right" }
}
```

`manifest.json` lives at the **repository root**, and its entry points reach
down into `omarchy-plugin/`. That is what makes the repository directly
installable: `omarchy plugin add` clones a repository and validates the clone
root, so a manifest anywhere else means the command fails with
`missing manifest.json`. Entry points may be relative paths as long as they
contain no `..` and the files exist.

A consequence worth keeping: nothing in the repository may be a symlink, since
Omarchy refuses a plugin folder containing one. `make lint-qml` builds its
import directory under `/tmp` for exactly this reason.

Declaring both kinds keeps the menu owned by the shell's panel loader (a plugin
with a `menu`/`panel`/`overlay` kind is excluded from the bar-widget summon
path), so the icon, the keybinding, and `omarchy-shell shell toggle` are all the
same code path.

The shell's plugin Loader injects `omarchyPath`, `shell`, and `manifest` into
the root item, then calls `open(payloadJson)` when the plugin is summoned and
`close()` when it is hidden. `Menu.qml` also answers `ping()` and `refresh()`.

Payload:

| Payload | Effect |
| --- | --- |
| `{}` | opens the browse list |
| `{"recipe": "<recipe-id>"}` | opens straight into that recipe's detail view |

Opening a recipe runs only the non-mutating `check`. Applying or undoing always
requires an explicit, confirmed action.

## File layout

```text
omarchy-plugin/
  manifest.json          menu + bar-widget kinds and their entry points
  Menu.qml               surface, navigation, keys, confirmation
  BarWidget.qml          bar icon; opens the menu, holds no state
  RecipeDetail.qml       generated form, status, actions, output, history
  ParameterControl.qml   one control per declared parameter type
  RecipeEngine.qml       every engine call; the only file that talks to the runner
  RecipeModel.js         pure presentation helpers, unit tested
  install.sh             copy this tree into ~/.config/omarchy/plugins/
```

## Runner resolution

`RecipeEngine.qml` looks for the runner in this order and uses the first that
exists. Resolution is an existence check, not a trial execution: choosing a
runner must not run anything.

1. `$OMARCHY_RECIPES_BIN`
2. `<plugin>/bin/omarchy-recipes` — the installed plugin ships the engine
3. `<plugin>/../bin/omarchy-recipes` — running from a checkout
4. `~/.local/bin/omarchy-recipes`
5. `omarchy-recipes` on `PATH`

If none of them work, the menu says so and names the runner it tried instead of
showing an empty list.

## Installing

Normal install, straight from git:

```bash
omarchy plugin add https://github.com/mdelgert/omarchy-recipes.git --enable
omarchy plugin update io.github.mdelgert.omarchy-recipes     # later
```

Development install, from a working tree including uncommitted changes:

```bash
./omarchy-plugin/install.sh     # or: make plugin
omarchy plugin enable io.github.mdelgert.omarchy-recipes right
```

`install.sh` mirrors the repository rather than rearranging it, so both installs
produce the same layout and share the one manifest. That is deliberate: a plugin
that behaves differently depending on how it was installed is a plugin whose
bugs only reproduce for some people.

The trailing section (`left`, `center`, `right`) places the bar icon. A plugin
already enabled *without* a section stays out of the bar layout — `enable` will
not move it — so disable it first and enable it again with the section.

The installer copies `omarchy-plugin/`, `bin/`, `src/`, `lib/`, and `recipes/`
into the plugin directory so the installed plugin is self-contained. A symlink
is not an option: Omarchy refuses a plugin folder containing one.

Summon it:

```bash
omarchy-shell shell toggle io.github.mdelgert.omarchy-recipes '{}'
omarchy-shell shell toggle io.github.mdelgert.omarchy-recipes '{"recipe":"example-numeric-setting"}'
```

Bind it to a key in `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + SHIFT + R", "Recipes",
  "omarchy-shell shell toggle io.github.mdelgert.omarchy-recipes '{}'")
```

List the bindings already taken with `omarchy menu keybindings --print`.

## Removing

```bash
omarchy plugin disable io.github.mdelgert.omarchy-recipes   # switch it off, keep it installed
omarchy plugin remove io.github.mdelgert.omarchy-recipes --yes
```

`remove` disables the plugin first, then moves the folder to
`~/.config/omarchy/plugins/.io.github.mdelgert.omarchy-recipes.bak.<timestamp>`.
Delete that backup separately if you want the plugin gone entirely. The engine's
state directory is not touched — see the README's uninstall section for the rest.

## Development loop

```bash
make check          # engine tests, QML logic tests, recipe validation
make lint-qml       # qmllint against the live Omarchy shell types
make plugin         # reinstall into ~/.config/omarchy/plugins/
omarchy-restart-shell
```

`omarchy-shell shell rescanPlugins` is enough for bar widgets, but a `menu`-kind
plugin is loaded through the shell's component cache: edited QML keeps running
the previously compiled version until the shell restarts. Run
`omarchy-restart-shell` after `make plugin` when iterating on QML. Engine, recipe,
and `RecipeModel.js` changes to the *installed* copy are picked up on the next
summon.

`qmllint` reports `unqualified` and `missing-property` warnings for the shell's
own singleton pattern (`Style.font.body`, `Color.menu.text`) and for `root.`
access from inside delegates. The built-in Omarchy menu produces the same
classes of warning; compare against it rather than expecting a clean run.

## The bar icon

`BarWidget.qml` is deliberately stateless: it draws a Nerd Font book glyph
(`\uf02d`) and asks the shell to toggle the menu. Showing live recipe status
there would mean running `check` for every recipe on a timer in the background,
and a recipe browser is something you open, not something you monitor.

Two things worth knowing if you change the glyph:

- Pick the codepoint by **rendering** it, not by trusting a Material Design
  icon name. Several plausible-looking codepoints in JetBrainsMono Nerd Font
  draw something entirely different:
  ```bash
  printf '\uf02d \uf0f6 \uf085\n' | magick -font /usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf \
    -pointsize 64 label:@- glyphs.png
  ```
- Write it as a `\uXXXX` escape rather than pasting the literal character.
  A private-use-area character does not survive every editor and shell
  round-trip, and an empty `text` silently collapses the widget to zero width
  instead of erroring.

## Keys

| Key | Browse | Detail |
| --- | --- | --- |
| type | filters recipes | goes to the focused control |
| `↑` `↓` | move the cursor | — |
| `Enter` / `→` | open the recipe | activate the focused button |
| `Tab` | — | move between generated controls and buttons |
| `Esc` | clear the filter, then close | back to the list |
| `F5` | reload recipes | reload and re-check |
