import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui
import "RecipeModel.js" as Model

// Detail view for one recipe: what it is, what state the machine is in, the
// controls its metadata asks for, what it promises about reversal, the result
// of the last run, and its history.
//
// Every section is generated from what the engine reported. No recipe is named
// here, and no recipe-specific branch exists: a new recipe with new parameters
// renders without a QML change.
FocusScope {
  id: root

  required property var engine
  property color foreground: Color.menu.text
  property color accent: Color.accent
  property color selectedBackground: Util.alpha(Color.menu.text, 0.08)
  property string fontFamily: Style.font.menuFamily

  signal applyRequested(var values)
  signal undoRequested()

  // Natural height of the detail content, so the hosting card can size itself
  // to what it is showing instead of always opening full height.
  readonly property alias contentHeight: detailColumn.implicitHeight

  readonly property var recipe: engine.recipe
  readonly property var parameters: recipe && recipe.parameters ? recipe.parameters : []
  readonly property var checkResult: engine.checkResult
  readonly property var status: engine.status
  readonly property var lastRun: engine.lastAction

  // Current form values, seeded from the parameter defaults the engine
  // normalized. The engine re-validates everything on the way in, so this is
  // only what the user has typed so far.
  property var values: ({})
  property var missing: []

  readonly property bool canApply: !!recipe && !engine.busy && missing.length === 0
  readonly property bool canUndo: engine.undoAvailable && !engine.busy

  function resetForm() {
    values = Model.defaultValues(root.parameters)
    missing = Model.missingRequired(root.parameters, values)
    engine.runCheck(values)
  }

  function setValue(name, value) {
    var next = ({})
    for (var key in values) next[key] = values[key]
    next[name] = value
    values = next
    missing = Model.missingRequired(root.parameters, values)
  }

  // Re-read state from the engine. Called after apply and after undo so the
  // status, history, and undo affordance describe what is true now.
  function refreshState() {
    if (!recipe) return
    engine.runCheck(values)
  }

  Connections {
    target: root.engine
    function onDetailLoaded(recipeId) { root.resetForm() }
  }

  ScrollView {
    id: scrollArea
    anchors.fill: parent
    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

    Column {
      id: detailColumn
      // Derived from the card width only. Reading `availableWidth` would tie
      // the content height to whether a scrollbar is showing, which in turn
      // depends on the content height.
      width: scrollArea.width - Style.space(12)
      spacing: Style.spacing.panelGap

      // ---- description ----------------------------------------------------

      Text {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.WordWrap
        visible: text !== ""
        text: root.recipe ? String(root.recipe.description || "") : ""
        color: Qt.darker(root.foreground, 1.3)
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
      }

      Text {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.WordWrap
        visible: !!root.recipe
        text: root.recipe
          ? [String(root.recipe.category || ""),
             Model.riskLabel(root.recipe.risk),
             Model.privilegeLabel(root.recipe.privilege),
             Model.sourceLabel(root.recipe)].filter(function(x) { return x }).join("  ·  ")
          : ""
        color: Qt.darker(root.foreground, 1.6)
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      // ---- status ---------------------------------------------------------

      PanelSeparator { foreground: root.foreground }

      PanelSectionHeader {
        text: "Status"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      Row {
        width: parent.width
        spacing: Style.spacing.controlGap

        Text {
          textFormat: Text.PlainText
          text: root.engine.checking ? "…" : Model.stateGlyph(root.checkResult ? root.checkResult.state : "")
          color: root.checkResult && root.checkResult.state === "configured" ? root.accent : Qt.darker(root.foreground, 1.3)
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
        }

        Text {
          textFormat: Text.PlainText
          width: parent.width - Style.space(30)
          wrapMode: Text.WordWrap
          text: {
            if (root.engine.checking) return "Checking…"
            if (!root.checkResult) return "Unknown"
            var label = Model.stateLabel(root.checkResult.state)
            var summary = String(root.checkResult.summary || "")
            return summary ? label + " — " + summary : label
          }
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
        }
      }

      // ---- generated parameter controls -----------------------------------

      PanelSeparator {
        foreground: root.foreground
        visible: root.parameters.length > 0
      }

      PanelSectionHeader {
        visible: root.parameters.length > 0
        text: "Parameters"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      Column {
        width: parent.width
        spacing: Style.spacing.panelGap

        Repeater {
          model: root.parameters

          delegate: ParameterControl {
            required property var modelData
            width: parent.width
            parameter: modelData
            value: root.values[modelData.name]
            foreground: root.foreground
            accent: root.accent
            fontFamily: root.fontFamily
            enabled: !root.engine.busy
            onChanged: function(name, newValue) { root.setValue(name, newValue) }
          }
        }
      }

      Text {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.WordWrap
        visible: root.missing.length > 0
        text: "Needs a value: " + root.missing.join(", ")
        color: Color.urgent
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      // ---- reversibility --------------------------------------------------

      PanelSeparator { foreground: root.foreground }

      PanelSectionHeader {
        text: "Reversibility"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      Column {
        width: parent.width
        spacing: Style.spacing.xs

        Repeater {
          model: Model.reversibilityLines(root.recipe, root.status)

          delegate: Text {
            required property var modelData
            textFormat: Text.PlainText
            width: parent.width
            wrapMode: Text.WordWrap
            text: (modelData.ok ? "✓  " : "✗  ") + modelData.text
            color: modelData.ok ? Qt.darker(root.foreground, 1.2) : Color.urgent
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }

      // ---- actions --------------------------------------------------------

      Row {
        width: parent.width
        spacing: Style.spacing.controlGap

        Button {
          text: root.engine.busy ? "Working…" : "Apply"
          bordered: true
          focusable: true
          enabled: root.canApply
          opacity: enabled ? 1 : 0.5
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: if (root.canApply) root.applyRequested(root.values)
        }

        Button {
          text: "Undo last change"
          bordered: true
          focusable: true
          visible: root.status && root.status.undo_supported
          enabled: root.canUndo
          opacity: enabled ? 1 : 0.5
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: if (root.canUndo) root.undoRequested()
        }

        Button {
          // Only a locally authored recipe can be offered upstream; a bundled
          // one is already there.
          text: root.engine.contributing ? "Checking…" : "Contribute…"
          bordered: true
          focusable: true
          visible: !!root.recipe && String(root.recipe.source) === "local"
          enabled: !root.engine.busy && !root.engine.contributing
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: root.engine.planContribution(root.recipe ? root.recipe.id : "")
        }

        Button {
          text: "Re-check"
          bordered: true
          focusable: true
          enabled: !root.engine.busy && !root.engine.checking
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: root.refreshState()
        }
      }

      // ---- contribution preview -------------------------------------------

      PanelSeparator {
        foreground: root.foreground
        visible: !!root.engine.contributePlan
      }

      Column {
        width: parent.width
        spacing: Style.spacing.xs
        visible: !!root.engine.contributePlan

        PanelSectionHeader {
          text: "Contribute upstream"
          foreground: root.foreground
          fontFamily: root.fontFamily
        }

        Text {
          textFormat: Text.PlainText
          width: parent.width
          wrapMode: Text.WordWrap
          text: {
            var p = root.engine.contributePlan
            if (!p) return ""
            if (p.blockers && p.blockers.length > 0) return "✗  " + p.blockers.join("; ")
            return "✓  ready to open a pull request on branch " + String(p.branch || "")
          }
          color: root.engine.contributePlan && root.engine.contributePlan.ready
            ? root.accent : Color.urgent
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
        }

        Repeater {
          model: root.engine.contributePlan && root.engine.contributePlan.duplicates
            ? root.engine.contributePlan.duplicates : []
          delegate: Text {
            required property var modelData
            textFormat: Text.PlainText
            width: parent.width
            wrapMode: Text.WordWrap
            text: "possible duplicate: " + String(modelData.id) + " — " + String(modelData.title)
            color: Color.urgent
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }

        Text {
          textFormat: Text.PlainText
          width: parent.width
          wrapMode: Text.WordWrap
          text: "This is a preview. Run `omarchy-recipes contribute "
              + (root.recipe ? String(root.recipe.id) : "<id>")
              + " --push` in a terminal to branch, commit, and open the pull request."
          color: Qt.darker(root.foreground, 1.6)
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }

        Repeater {
          model: root.engine.contributePlan && root.engine.contributePlan.steps
            ? root.engine.contributePlan.steps : []
          delegate: Text {
            required property var modelData
            textFormat: Text.PlainText
            width: parent.width
            wrapMode: Text.WordWrap
            text: "· " + String(modelData)
            color: Qt.darker(root.foreground, 1.5)
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }

      // ---- last run -------------------------------------------------------

      PanelSeparator {
        foreground: root.foreground
        visible: !!root.lastRun
      }

      Column {
        width: parent.width
        spacing: Style.spacing.xs
        visible: !!root.lastRun

        Text {
          textFormat: Text.PlainText
          width: parent.width
          wrapMode: Text.WordWrap
          text: {
            if (!root.lastRun) return ""
            var ok = String(root.lastRun.status) === "success"
            var verb = String(root.lastRun.action) === "undo" ? "Undo" : "Recipe"
            return (ok ? "✓  " : "✗  ") + verb + (ok ? " completed successfully" : " failed")
          }
          color: root.lastRun && String(root.lastRun.status) === "success" ? root.accent : Color.urgent
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
        }

        Text {
          textFormat: Text.PlainText
          width: parent.width
          wrapMode: Text.WordWrap
          visible: text !== ""
          text: root.lastRun ? String(root.lastRun.summary || "") : ""
          color: Qt.darker(root.foreground, 1.3)
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
        }

        Button {
          text: root.engine.logText ? "Hide log" : "View log"
          bordered: true
          focusable: true
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: {
            if (root.engine.logText) root.engine.logText = ""
            else root.engine.loadLog(root.lastRun ? root.lastRun.run_id : "")
          }
        }
      }

      // Recipe output is untrusted text: it is displayed verbatim as plain
      // text and never interpreted, formatted as markup, or executed.
      BorderSurface {
        width: parent.width
        visible: root.engine.logText !== ""
        implicitHeight: logText.implicitHeight + Style.spacing.rowPaddingX * 2
        color: Util.alpha(root.foreground, 0.04)
        radius: Style.cornerRadius
        borderSpec: Border.flat(Util.alpha(root.foreground, 0.10), 1)

        // Selectable so a failure can be copied into a bug report. Read-only,
        // and still rendered as plain text: recipe output is untrusted.
        TextEdit {
          id: logText
          readOnly: true
          selectByMouse: true
          selectByKeyboard: true
          textFormat: TextEdit.PlainText
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: parent.top
          anchors.margins: Style.spacing.rowPaddingX
          wrapMode: TextEdit.Wrap
          text: root.engine.logText
          color: Qt.darker(root.foreground, 1.2)
          selectionColor: Style.selectionFillFor(root.foreground, root.accent)
          selectedTextColor: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }
      }

      // ---- history --------------------------------------------------------

      PanelSeparator {
        foreground: root.foreground
        visible: root.engine.history.length > 0
      }

      PanelSectionHeader {
        visible: root.engine.history.length > 0
        text: "History"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      Column {
        width: parent.width
        spacing: Style.spacing.xs

        Repeater {
          model: Model.historyRows(root.engine.history, 10)

          delegate: Item {
            required property var modelData
            width: parent.width
            height: historyRow.implicitHeight

            Column {
              id: historyRow
              width: parent.width
              spacing: Style.spacing.xxs

              Row {
                width: parent.width
                spacing: Style.spacing.controlGap

                Text {
                  textFormat: Text.PlainText
                  text: modelData.when
                  color: Qt.darker(root.foreground, 1.5)
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }

                Text {
                  textFormat: Text.PlainText
                  text: modelData.action + "  " + modelData.status + (modelData.undone ? "  (undone)" : "")
                  color: modelData.status === "success" ? Qt.darker(root.foreground, 1.2) : Color.urgent
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }
              }

              Text {
                textFormat: Text.PlainText
                visible: modelData.summary !== ""
                width: parent.width
                elide: Text.ElideRight
                text: modelData.summary
                color: Qt.darker(root.foreground, 1.6)
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }
            }
          }
        }
      }

      Item { width: 1; height: Style.spacing.md }
    }
  }
}
