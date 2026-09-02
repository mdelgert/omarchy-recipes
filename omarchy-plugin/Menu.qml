import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.Commons
import qs.Ui
import "RecipeModel.js" as Model

// Native Omarchy menu for omarchy-recipes.
//
// This file is a view. It draws the surface, routes keys, and asks
// RecipeEngine for things; it does not know what a recipe is made of. Recipe
// discovery, metadata, parameter validation, backup, execution, history, and
// undo eligibility all come from the `omarchy-recipes` engine over its JSON
// interface — adding a recipe never means touching QML.
//
// Safety rules this file keeps:
//   * every string that came from a recipe renders as Text.PlainText
//   * no command string is built from metadata or user input
//   * no recipe content is evaluated as QML or JavaScript
//   * selecting a recipe runs only the non-mutating `check`; a modifying
//     action always requires an explicit, confirmed Apply
Item {
  id: root

  // ---- host injections (set by the shell's plugin Loader) -----------------
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var shell: null
  property var manifest: null

  // ---- plugin lifecycle ---------------------------------------------------

  property bool opened: false

  function open(payloadJson) {
    var payload = ({})
    try { payload = JSON.parse(payloadJson || "{}") } catch (e) { payload = ({}) }

    root.filterText = ""
    root.goBrowse()
    root.opened = true
    recipeEngine.reload()

    // `{"recipe": "<id>"}` opens straight into one recipe's detail view, so a
    // keybind can point at a specific recipe. It still only runs `check`.
    if (payload.recipe) Qt.callLater(function() { root.openRecipe(String(payload.recipe)) })
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  function close() {
    root.opened = false
    confirmDialog.opened = false
    root.pendingAction = ""
  }

  function refresh() {
    recipeEngine.reload()
    return "ok"
  }

  function ping() { return "ok" }

  // User-initiated close. Tell the host so its open-plugin bookkeeping stays
  // in step and the next toggle opens rather than closes.
  function requestClose() {
    if (shell && typeof shell.hide === "function") shell.hide(root.pluginId)
    else root.close()
  }

  readonly property string pluginId: manifest && manifest.id
    ? String(manifest.id)
    : "io.github.mdelgert.omarchy-recipes"

  // ---- navigation ---------------------------------------------------------

  property string view: "browse"          // "browse" | "detail" | "create"
  property string filterText: ""
  property int selectedIndex: 0
  property bool cursorActive: false

  readonly property var rows: Model.rowsFor(recipeEngine.recipes, filterText)

  function goBrowse() {
    view = "browse"
    recipeEngine.select("")
    panel.holdFocus()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  function openRecipe(recipeId) {
    if (!recipeId) return
    view = "detail"
    recipeEngine.select(recipeId)
  }

  function openCreate() {
    view = "create"
    recipeEngine.select("")
    // Take the keyboard first, then hand the rest of the desktop back.
    panel.releaseFocusAfterPrime()
    Qt.callLater(function() { create.forceActiveFocus() })
  }

  function setFilter(text) {
    filterText = text
    selectedIndex = Math.max(0, Model.firstSelectableRow(rows))
    cursorActive = false
  }

  function moveCursor(step) {
    if (rows.length === 0) return
    if (!cursorActive) {
      cursorActive = true
      selectedIndex = Math.max(0, Model.firstSelectableRow(rows))
      return
    }
    selectedIndex = Model.nextSelectableRow(rows, selectedIndex, step)
    resultList.positionViewAtIndex(selectedIndex, ListView.Contain)
  }

  function activateCursor() {
    if (rows.length === 0) return
    var index = cursorActive ? selectedIndex : Model.firstSelectableRow(rows)
    if (index < 0 || index >= rows.length) return
    var row = rows[index]
    if (row.kind === "recipe") openRecipe(row.recipeId)
  }

  onRowsChanged: {
    if (selectedIndex >= rows.length || (rows[selectedIndex] && rows[selectedIndex].kind !== "recipe"))
      selectedIndex = Math.max(0, Model.firstSelectableRow(rows))
  }

  // ---- confirmation -------------------------------------------------------
  //
  // A modifying action is never a side effect of navigation. Apply and Undo
  // both route through here, and the pending action is remembered as an action
  // name plus form values — never as a command to execute.

  property string pendingAction: ""
  property var pendingValues: ({})

  function requestApply(values) {
    pendingAction = "apply"
    pendingValues = values || ({})
    confirmDialog.opened = true
  }

  function requestUndo() {
    pendingAction = "undo"
    pendingValues = ({})
    confirmDialog.opened = true
  }

  function runPendingAction() {
    var action = pendingAction
    pendingAction = ""
    confirmDialog.opened = false
    if (action === "apply") recipeEngine.apply(pendingValues)
    else if (action === "undo") recipeEngine.undo()
  }

  readonly property string confirmMessage: {
    if (!recipeEngine.recipe) return ""
    var title = String(recipeEngine.recipe.title || recipeEngine.recipe.id)
    if (pendingAction === "undo") return "Undo the last change made by \"" + title + "\"?"
    var text = "Apply \"" + title + "\" now?"
    if (String(recipeEngine.recipe.undo) === "none") text += "  This recipe declares no automatic undo."
    if (String(recipeEngine.recipe.risk) === "high") text += "  The author marked this recipe high risk."
    return text
  }

  // ---- theme (menu surface roles, same as the built-in Omarchy menu) ------

  property string fontFamily: Style.font.menuFamily
  readonly property color background: Color.menu.background
  readonly property color foreground: Color.menu.text
  readonly property color borderColor: Color.menu.border
  readonly property color scrim: Color.menu.scrim
  readonly property color selectedBackground: Color.menu.selectedBackground
  readonly property color selectedText: Color.menu.selectedText
  readonly property var borderSpec: Border.surfaceSpec("menu", "border", borderColor, Math.max(1, Style.space(2)))

  readonly property int headerHeight: Math.max(Style.space(34), Style.font.heading + Style.spacing.controlPaddingY * 2)
  readonly property int rowHeight: Math.max(Style.space(46), Style.font.body + Style.spacing.rowPaddingX * 2)
  readonly property int detailRowHeight: Math.max(Style.space(56), Style.font.body + Style.font.caption + Style.spacing.rowPaddingX * 2)
  readonly property int headerRowHeight: Math.max(Style.space(26), Style.font.caption * 2)

  // Height the browse list wants, measured from the row model rather than read
  // back off the ListView: the list is sized by the card, so asking the list
  // how tall it is in order to size the card would be a binding loop.
  // The create row sits above the list, so the card has to account for it or
  // the last recipe is clipped.
  readonly property bool createRowVisible: view === "browse" && filterText === ""
  readonly property int browseContentHeight: {
    var total = createRowVisible ? rowHeight + Style.spacing.xs : 0
    for (var i = 0; i < rows.length; i++) {
      if (i > 0) total += Style.spacing.xs
      total += rows[i].kind === "header"
        ? headerRowHeight
        : (filterText && rows[i].detail ? detailRowHeight : rowHeight)
    }
    return Math.max(rowHeight, total)
  }

  // ---- engine -------------------------------------------------------------

  RecipeEngine {
    id: recipeEngine
    onActionCompleted: function(action, run) {
      // Whatever the run reports, current state is re-read from the recipe's
      // own non-mutating check rather than inferred from an exit code.
      detail.refreshState()
    }
  }

  // ---- surface ------------------------------------------------------------

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore

    WlrLayershell.namespace: "omarchy-recipes-menu"
    WlrLayershell.layer: WlrLayer.Overlay

    // Keyboard focus differs by view, because the two views want opposite
    // things from the compositor.
    //
    // Browsing is a pick-a-row launcher: it must own the keyboard the instant
    // it appears, so it takes Exclusive like the built-in Omarchy menu.
    //
    // Create Recipe is a form. You may well want to copy a prompt out of an
    // editor on another monitor while it is open, and Exclusive makes Hyprland
    // route every pointer event to this surface no matter which output the
    // cursor is over — which locks the rest of the desktop. So the authoring
    // view primes with Exclusive to take the keyboard, then drops to OnDemand
    // and lets you click away. Clicking the card takes the keyboard back.
    property bool focusPrimed: false

    function releaseFocusAfterPrime() {
      panel.focusPrimed = false
      focusPrimeTimer.restart()
    }

    function holdFocus() {
      focusPrimeTimer.stop()
      panel.focusPrimed = false
    }

    WlrLayershell.keyboardFocus: !root.opened
      ? WlrKeyboardFocus.None
      : (panel.focusPrimed ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.Exclusive)

    onVisibleChanged: if (!visible) panel.holdFocus()

    Timer {
      id: focusPrimeTimer
      // Long enough for a few Wayland commit cycles, short enough that the
      // grab is never noticeable.
      interval: 120
      onTriggered: if (root.opened && root.view === "create") panel.focusPrimed = true
    }

    // The detail view carries a generated form, run output, and history, so it
    // is given a wider card than the browse list.
    readonly property int cardWidth: Math.min(
      root.view === "browse" ? Style.space(420) : Style.space(620),
      panel.width - Style.gapsOut * 2)

    // The card is as tall as its content and no taller, the way the built-in
    // menu behaves — a four-recipe list should not open a full-height panel.
    // Past the ceiling the body scrolls instead of the card growing.
    readonly property int maxCardHeight: Math.min(
      Math.round(panel.height * 0.78),
      panel.height - Style.gapsOut * 2)
    readonly property int bodyContentHeight: root.view === "detail"
      ? detail.contentHeight
      : (root.view === "create" ? create.contentHeight : root.browseContentHeight)
    readonly property int cardChromeHeight: Style.spacing.panelPadding * 2
      + Border.top(root.borderSpec) + Border.bottom(root.borderSpec)
      + root.headerHeight + Style.spacing.md
      + (problems.visible ? problems.height + Style.spacing.md : 0)
    readonly property int cardHeight: Math.min(
      cardChromeHeight + bodyContentHeight, maxCardHeight)

    Rectangle {
      anchors.fill: parent
      color: root.scrim
    }

    MouseArea {
      anchors.fill: parent
      onClicked: root.requestClose()
    }

    BorderSurface {
      id: card
      width: panel.cardWidth
      height: panel.cardHeight
      anchors.centerIn: parent
      radius: Style.cornerRadius
      color: root.background
      borderSpec: root.borderSpec
      padding: Style.spacing.panelPadding

      // Clicks on the card must not reach the dismissal area behind it. They
      // also take the keyboard back: with OnDemand focus the user can click
      // away to another window, and clicking the card is how they return.
      MouseArea {
        anchors.fill: parent
        onClicked: if (root.view !== "create") keyCatcher.forceActiveFocus()
      }

      // One key handler for the whole card. Content lives inside it, and
      // `Keys.AfterItem` lets a focused text field, spin box, or dropdown
      // consume its own keys first; whatever they ignore (Escape, and the
      // browse list's navigation) bubbles up here.
      Item {
        id: keyCatcher
        anchors.fill: parent
        anchors.topMargin: card.contentTopInset
        anchors.rightMargin: card.contentRightInset
        anchors.bottomMargin: card.contentBottomInset
        anchors.leftMargin: card.contentLeftInset
        focus: true

        Keys.priority: Keys.AfterItem
        Keys.onPressed: function(event) {
          if (confirmDialog.opened) {
            if (confirmDialog.handleKey(event)) event.accepted = true
            return
          }
          if (event.key === Qt.Key_Escape) {
            if (root.view !== "browse") root.goBrowse()
            else if (root.filterText) root.setFilter("")
            else root.requestClose()
            event.accepted = true
            return
          }
          if (event.key === Qt.Key_N && (event.modifiers & Qt.ControlModifier)) {
            root.openCreate()
            event.accepted = true
            return
          }
          if (event.key === Qt.Key_F5) {
            recipeEngine.reload()
            if (root.view === "detail") detail.refreshState()
            event.accepted = true
            return
          }
          // Below here is browse-list navigation and type-to-filter. In the
          // detail view those keys belong to the generated controls.
          if (root.view !== "browse") return

          if (Util.editsFilter(event, root.filterText)) {
            root.setFilter(Util.editedFilter(event, root.filterText))
            event.accepted = true
          } else if (event.key === Qt.Key_Up) {
            root.moveCursor(-1)
            event.accepted = true
          } else if (event.key === Qt.Key_Down) {
            root.moveCursor(1)
            event.accepted = true
          } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Right) {
            root.activateCursor()
            event.accepted = true
          } else if (event.text && event.text.length === 1
                     && event.text.charCodeAt(0) >= 32 && event.text.charCodeAt(0) !== 127
                     && (event.modifiers === Qt.NoModifier || event.modifiers === Qt.ShiftModifier)) {
            root.setFilter(root.filterText + event.text)
            event.accepted = true
          }
        }

        Column {
          id: content
          anchors.fill: parent
          spacing: Style.spacing.md

          // ---- header ---------------------------------------------------
          Item {
            id: headerItem
            width: parent.width
            height: root.headerHeight

            Text {
              textFormat: Text.PlainText
              anchors.left: parent.left
              anchors.right: hint.left
              anchors.rightMargin: Style.spacing.md
              anchors.verticalCenter: parent.verticalCenter
              text: root.view === "create"
                ? "Create a recipe"
                : root.view === "detail"
                  ? (recipeEngine.recipe ? String(recipeEngine.recipe.title || recipeEngine.recipe.id) : "Recipe")
                  : (root.filterText || "Search recipes…")
              color: root.foreground
              opacity: root.view !== "browse" || root.filterText ? 1 : 0.58
              font.family: root.fontFamily
              font.pixelSize: Style.font.heading
              elide: Text.ElideRight
            }

            Text {
              id: hint
              textFormat: Text.PlainText
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              text: root.view !== "browse"
                ? "Esc  back"
                : (recipeEngine.loadingList ? "loading…" : String(recipeEngine.recipes.length) + " recipes")
              color: Qt.darker(root.foreground, 1.5)
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }
          }

          // ---- engine problems -------------------------------------------
          //
          // A runner that cannot be reached, or a recipe that failed to parse,
          // is reported rather than silently leaving the menu short a few
          // entries.
          Column {
            id: problems
            width: parent.width
            spacing: Style.spacing.xs
            visible: recipeEngine.engineError !== "" || recipeEngine.problems.length > 0

            Text {
              textFormat: Text.PlainText
              visible: recipeEngine.engineError !== ""
              width: parent.width
              wrapMode: Text.WordWrap
              text: "Recipe engine unavailable: " + recipeEngine.engineError
              color: Color.urgent
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }

            Text {
              textFormat: Text.PlainText
              visible: recipeEngine.problems.length > 0
              width: parent.width
              wrapMode: Text.WordWrap
              text: recipeEngine.problems.length
                + (recipeEngine.problems.length === 1 ? " recipe was skipped: " : " recipes were skipped: ")
                + Model.firstLine(recipeEngine.problems.length ? recipeEngine.problems[0].error : "", 200)
              color: Color.urgent
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }
          }

          // ---- body -------------------------------------------------------
          Item {
            width: parent.width
            height: content.height - headerItem.height - content.spacing
              - (problems.visible ? problems.height + content.spacing : 0)

            Item {
              id: createRow
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.top: parent.top
              height: root.rowHeight
              visible: root.createRowVisible

              Rectangle {
                anchors.fill: parent
                radius: Style.cornerRadius
                color: createMouse.containsMouse ? root.selectedBackground : "transparent"

                Text {
                  textFormat: Text.PlainText
                  anchors.left: parent.left
                  anchors.leftMargin: Style.spacing.rowPaddingX
                  anchors.verticalCenter: parent.verticalCenter
                  text: "＋  Create recipe…            Ctrl+N"
                  color: createMouse.containsMouse ? root.selectedText : root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                }

                MouseArea {
                  id: createMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  onClicked: root.openCreate()
                }
              }
            }

            ListView {
              id: resultList
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.bottom: parent.bottom
              anchors.top: createRow.visible ? createRow.bottom : parent.top
              visible: root.view === "browse"
              model: root.rows
              clip: true
              spacing: Style.spacing.xs
              boundsBehavior: Flickable.StopAtBounds

              delegate: Item {
                id: row
                required property var modelData
                required property int index

                width: resultList.width
                height: (row.modelData ? row.modelData.kind : "") === "header"
                  ? root.headerRowHeight
                  : (root.filterText && (row.modelData ? row.modelData.detail : "") ? root.detailRowHeight : root.rowHeight)

                PanelSectionHeader {
                  visible: (row.modelData ? row.modelData.kind : "") === "header"
                  anchors.left: parent.left
                  anchors.bottom: parent.bottom
                  anchors.bottomMargin: Style.spacing.xxs
                  text: row.modelData ? row.modelData.label : ""
                  foreground: root.foreground
                  fontFamily: root.fontFamily
                }

                Rectangle {
                  visible: (row.modelData ? row.modelData.kind : "") === "recipe"
                  anchors.fill: parent
                  radius: Style.cornerRadius
                  color: root.cursorActive && root.selectedIndex === row.index
                    ? root.selectedBackground : "transparent"

                  Column {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Style.spacing.rowPaddingX
                    anchors.rightMargin: Style.spacing.rowPaddingX
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Style.spacing.xxs

                    Row {
                      width: parent.width
                      spacing: Style.spacing.controlGap

                      Text {
                        textFormat: Text.PlainText
                        width: Math.min(implicitWidth, parent.width - badge.width - Style.spacing.controlGap)
                        text: row.modelData ? row.modelData.label : ""
                        color: root.cursorActive && root.selectedIndex === row.index
                          ? root.selectedText : root.foreground
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.body
                        elide: Text.ElideRight
                      }

                      // Origin, shown on anything that did not ship with the
                      // project. An agent-generated recipe must never be
                      // mistaken for a reviewed one.
                      Text {
                        id: badge
                        textFormat: Text.PlainText
                        anchors.verticalCenter: parent.verticalCenter
                        visible: text !== ""
                        text: row.modelData && row.modelData.badge ? row.modelData.badge : ""
                        color: Qt.darker(root.foreground, 1.6)
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.caption
                      }
                    }

                    Text {
                      textFormat: Text.PlainText
                      visible: root.filterText !== "" && (row.modelData ? row.modelData.detail : "") !== ""
                      width: parent.width
                      text: (row.modelData ? row.modelData.detail : "")
                      color: Qt.darker(root.foreground, 1.5)
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      elide: Text.ElideRight
                    }
                  }

                  MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    onEntered: { root.cursorActive = true; root.selectedIndex = row.index }
                    onClicked: root.openRecipe(row.modelData ? row.modelData.recipeId : "")
                  }
                }
              }
            }

            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              width: parent.width
              horizontalAlignment: Text.AlignHCenter
              wrapMode: Text.WordWrap
              visible: root.view === "browse" && root.rows.length === 0
              text: recipeEngine.engineError !== ""
                ? "No recipes could be loaded."
                : (recipeEngine.loadingList ? "Loading recipes…"
                                      : (root.filterText ? "No matching recipes" : "No recipes found"))
              color: Qt.darker(root.foreground, 1.4)
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }

            CreateRecipe {
              id: create
              anchors.fill: parent
              visible: root.view === "create"
              enabled: visible
              engine: recipeEngine
              foreground: root.foreground
              accent: root.selectedText
              fontFamily: root.fontFamily
              onOpenRecipeRequested: function(recipeId) { root.openRecipe(recipeId) }
            }

            RecipeDetail {
              id: detail
              anchors.fill: parent
              visible: root.view === "detail"
              enabled: visible
              engine: recipeEngine
              foreground: root.foreground
              accent: root.selectedText
              selectedBackground: root.selectedBackground
              fontFamily: root.fontFamily
              onApplyRequested: function(values) { root.requestApply(values) }
              onUndoRequested: root.requestUndo()
            }
          }
        }

        ConfirmDialog {
          id: confirmDialog
          anchors.fill: parent
          z: 10
          opened: false
          message: root.confirmMessage
          confirmText: root.pendingAction === "undo" ? "Undo" : "Apply"
          background: root.background
          foreground: root.foreground
          scrim: root.scrim
          selectedBackground: root.selectedBackground
          selectedText: root.selectedText
          fontFamily: root.fontFamily
          cornerRadius: Style.cornerRadius
          // The dialog owns the keyboard while it is up, so a field that had
          // focus cannot swallow the Enter that confirms or the Esc that cancels.
          onOpenedChanged: if (opened) keyCatcher.forceActiveFocus()
          onCanceled: { root.pendingAction = ""; opened = false }
          onConfirmed: root.runPendingAction()
        }
      }
    }
  }
}
