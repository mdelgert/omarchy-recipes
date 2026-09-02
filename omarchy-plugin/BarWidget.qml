import QtQuick
import qs.Ui

// Bar icon that opens the recipe menu.
//
// Deliberately stateless. The menu is the plugin; this is a doorway to it, the
// same shape as Omarchy's own menu widget. Showing live recipe status here
// would mean running `check` for every recipe on a timer in the background,
// and the bar is not the place to spend that — a recipe browser is something
// you open, not something you monitor.
//
// The plugin declares both `menu` and `bar-widget`, so the shell's panel loader
// keeps owning the menu surface. This widget only asks the shell to toggle it,
// which means the icon, the keybinding, and `omarchy-shell shell toggle` are
// all the same path.
BarWidget {
  id: root
  moduleName: "io.github.mdelgert.omarchy-recipes"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    // Nerd Font book, U+F02D. Verified by rendering the glyph rather than
    // trusting a name: several plausible-looking Material Design codepoints in
    // this font draw something else entirely.
    text: "\uf02d"
    tooltipText: "Recipes"

    // A fully literal command. `bar.run` hands its argument to `bash -lc`, so
    // nothing dynamic is allowed to reach it — not even this plugin's own id
    // read back from a property.
    onPressed: function(mouseButton) {
      if (!root.bar) return
      if (mouseButton !== Qt.LeftButton) return
      root.bar.run("omarchy-shell shell toggle io.github.mdelgert.omarchy-recipes '{}'")
    }
  }
}
