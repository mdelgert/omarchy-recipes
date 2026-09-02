import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui
import "RecipeModel.js" as Model

// Describe a change; get back a recipe you can read before anything runs.
//
// The flow is fixed and the user is never skipped over:
//
//   describe → plan + conflicts → resolve → draft → review the Bash → save
//
// The conflict step is not advisory. When the engine reports a blocking
// conflict the Generate button stays disabled until a resolution is chosen,
// and the engine refuses to draft anyway — this view cannot route around it.
//
// The generated Bash is always shown in full. That is the project's principle:
// AI-authorable, human-auditable.
FocusScope {
  id: root

  required property var engine
  property color foreground: Color.menu.text
  property color accent: Color.accent
  property string fontFamily: Style.font.menuFamily

  signal openRecipeRequested(string recipeId)

  readonly property alias contentHeight: column.implicitHeight

  // What the user picked for each blocking conflict, keyed by resource type.
  property var decisions: ({})

  readonly property var findings: engine.planConflicts && engine.planConflicts.findings
    ? engine.planConflicts.findings : []
  readonly property var blocking: {
    var out = []
    for (var i = 0; i < findings.length; i++) {
      if (findings[i].severity === "block" && findings[i].status === "conflict") out.push(findings[i])
    }
    return out
  }
  readonly property bool allResolved: {
    for (var i = 0; i < blocking.length; i++) {
      if (!decisions[String(blocking[i].resource.type || "")]) return false
    }
    return true
  }
  readonly property string draftId: engine.plan && engine.plan.recipe_id ? String(engine.plan.recipe_id) : ""

  function reset() {
    decisions = ({})
    engine.resetAuthoring()
    requestField.text = ""
  }

  function decide(resourceType, resolution) {
    var next = ({})
    for (var key in decisions) next[key] = decisions[key]
    next[String(resourceType)] = String(resolution)
    decisions = next
  }

  Connections {
    target: root.engine
    function onRecipeSaved(recipeId) { root.openRecipeRequested(recipeId) }
  }

  ScrollView {
    id: scrollArea
    anchors.fill: parent
    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

    Column {
      id: column
      width: scrollArea.width - Style.space(12)
      spacing: Style.spacing.panelGap

      Text {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.WordWrap
        text: "Describe what you want your system to do. The agent inspects this machine, "
            + "checks for conflicts, and proposes a reversible recipe. Nothing runs until you say so."
        color: Qt.darker(root.foreground, 1.3)
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
      }

      // ---- the request ----------------------------------------------------

      TextField {
        id: requestField
        width: parent.width
        enabled: !root.engine.authoringBusy
        placeholderText: "Add a hotkey Super+Alt+Y that launches Firefox"
        foreground: root.foreground
        accent: root.accent
        onAccepted: if (!root.engine.authoringBusy) root.engine.requestPlan(text)
      }

      Row {
        spacing: Style.spacing.controlGap

        Button {
          text: root.engine.planning ? "Thinking…" : "Ask agent"
          bordered: true
          focusable: true
          enabled: !root.engine.authoringBusy && requestField.text.trim() !== ""
          opacity: enabled ? 1 : 0.5
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: root.engine.requestPlan(requestField.text)
        }

        Button {
          text: "Start over"
          bordered: true
          focusable: true
          visible: !!root.engine.plan || root.engine.authoringError !== ""
          enabled: !root.engine.authoringBusy
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: root.reset()
        }
      }

      Text {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.WordWrap
        visible: root.engine.authoringError !== ""
        text: root.engine.authoringError
        color: Color.urgent
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      // ---- what the agent proposes ----------------------------------------

      PanelSeparator { foreground: root.foreground; visible: !!root.engine.plan }

      PanelSectionHeader {
        visible: !!root.engine.plan
        text: "Proposed change"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      Column {
        width: parent.width
        spacing: Style.spacing.xs
        visible: !!root.engine.plan

        Text {
          textFormat: Text.PlainText
          width: parent.width
          wrapMode: Text.WordWrap
          text: root.engine.plan ? String(root.engine.plan.summary || "") : ""
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
        }

        Text {
          textFormat: Text.PlainText
          width: parent.width
          wrapMode: Text.WordWrap
          visible: text !== ""
          text: root.engine.plan
            ? [String(root.engine.plan.title || ""), String(root.engine.plan.category || ""),
               Model.riskLabel(root.engine.plan.risk)].filter(function(x) { return x }).join("  ·  ")
            : ""
          color: Qt.darker(root.foreground, 1.5)
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }

        Repeater {
          model: root.engine.plan && root.engine.plan.questions ? root.engine.plan.questions : []
          delegate: Text {
            required property var modelData
            textFormat: Text.PlainText
            width: column.width
            wrapMode: Text.WordWrap
            text: "?  " + String(modelData)
            color: Qt.darker(root.foreground, 1.2)
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }

      // ---- conflicts ------------------------------------------------------

      PanelSeparator { foreground: root.foreground; visible: root.findings.length > 0 }

      PanelSectionHeader {
        visible: root.findings.length > 0
        text: "Conflicts"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      Column {
        width: parent.width
        spacing: Style.spacing.md
        visible: root.findings.length > 0

        Repeater {
          model: root.findings

          delegate: Column {
            required property var modelData
            width: column.width
            spacing: Style.spacing.xs

            readonly property string resourceType: String(modelData.resource && modelData.resource.type || "")
            readonly property bool isBlocking: modelData.severity === "block" && modelData.status === "conflict"
            readonly property string chosen: root.decisions[resourceType] || ""

            Text {
              textFormat: Text.PlainText
              width: parent.width
              wrapMode: Text.WordWrap
              text: (modelData.status === "conflict" ? "✗  " : modelData.status === "unknown" ? "?  " : "✓  ")
                    + String(modelData.detail || "")
              color: modelData.status === "conflict"
                ? (parent.isBlocking ? Color.urgent : Qt.darker(root.foreground, 1.2))
                : Qt.darker(root.foreground, 1.3)
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }

            // One button per resolution the engine offered. The UI never
            // invents an option, and never picks one on the user's behalf.
            Row {
              spacing: Style.spacing.xs
              visible: parent.isBlocking

              Repeater {
                model: modelData.resolutions || []

                delegate: Button {
                  required property var modelData
                  text: String(modelData).replace(/-/g, " ")
                  bordered: true
                  focusable: true
                  selected: parent.parent.chosen === String(modelData)
                  foreground: root.foreground
                  accent: root.accent
                  fontFamily: root.fontFamily
                  fontSize: Style.font.caption
                  enabled: !root.engine.authoringBusy
                  onClicked: root.decide(parent.parent.resourceType, String(modelData))
                }
              }
            }
          }
        }

        Text {
          textFormat: Text.PlainText
          width: parent.width
          wrapMode: Text.WordWrap
          visible: root.blocking.length > 0 && !root.allResolved
          text: "Choose how to handle each blocking conflict before generating the recipe."
          color: Color.urgent
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }
      }

      // ---- generate -------------------------------------------------------

      Button {
        visible: !!root.engine.plan && root.engine.draftText === ""
        text: root.engine.drafting ? "Writing the recipe…" : "Generate recipe"
        bordered: true
        focusable: true
        enabled: !root.engine.authoringBusy && root.allResolved
        opacity: enabled ? 1 : 0.5
        foreground: root.foreground
        accent: root.accent
        fontFamily: root.fontFamily
        onClicked: root.engine.requestDraft(requestField.text, root.decisions)
      }

      // ---- the generated recipe -------------------------------------------

      PanelSeparator { foreground: root.foreground; visible: root.engine.draftText !== "" }

      PanelSectionHeader {
        visible: root.engine.draftText !== ""
        text: "Generated recipe — read it before you save it"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      Column {
        width: parent.width
        spacing: Style.spacing.xs
        visible: root.engine.draftLint !== null

        Text {
          textFormat: Text.PlainText
          width: parent.width
          text: {
            if (!root.engine.draftLint) return ""
            var l = root.engine.draftLint
            return (l.ok ? "✓  passes validation" : "✗  refused: " + l.errors + " error(s)")
                 + (l.warnings > 0 ? "  ·  " + l.warnings + " warning(s)" : "")
          }
          color: root.engine.draftLint && root.engine.draftLint.ok ? root.accent : Color.urgent
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
        }

        Repeater {
          model: root.engine.draftLint ? root.engine.draftLint.findings : []
          delegate: Text {
            required property var modelData
            textFormat: Text.PlainText
            width: column.width
            wrapMode: Text.WordWrap
            text: String(modelData.severity) + "  " + String(modelData.rule) + " — " + String(modelData.message)
            color: modelData.severity === "error" ? Color.urgent : Qt.darker(root.foreground, 1.5)
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }

      Row {
        spacing: Style.spacing.controlGap
        visible: root.engine.draftText !== ""

        Button {
          text: root.engine.saving ? "Saving…" : "Save to my recipes"
          bordered: true
          focusable: true
          enabled: !root.engine.authoringBusy
            && !!root.draftId
            && !!root.engine.draftLint && root.engine.draftLint.ok
          opacity: enabled ? 1 : 0.5
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: root.engine.saveDraft(root.draftId, root.engine.draftText)
        }

        Button {
          text: "Discard"
          bordered: true
          focusable: true
          enabled: !root.engine.authoringBusy
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: root.reset()
        }
      }

      // Generated Bash is untrusted text: plain, verbatim, never interpreted.
      BorderSurface {
        width: parent.width
        visible: root.engine.draftText !== ""
        implicitHeight: Math.min(draftText.implicitHeight + Style.spacing.rowPaddingX * 2, Style.space(300))
        color: Util.alpha(root.foreground, 0.04)
        radius: Style.cornerRadius
        borderSpec: Border.flat(Util.alpha(root.foreground, 0.10), 1)
        clip: true

        Flickable {
          anchors.fill: parent
          anchors.margins: Style.spacing.rowPaddingX
          contentHeight: draftText.implicitHeight
          clip: true
          boundsBehavior: Flickable.StopAtBounds

          Text {
            id: draftText
            textFormat: Text.PlainText
            width: parent.width
            wrapMode: Text.Wrap
            text: root.engine.draftText
            color: Qt.darker(root.foreground, 1.15)
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }

      Text {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.WordWrap
        visible: root.engine.draftText !== ""
        text: "Saving stores this in your own collection, marked as agent-generated. "
            + "It is not applied — open it and press Apply when you have read it."
        color: Qt.darker(root.foreground, 1.6)
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      Item { width: 1; height: Style.spacing.md }
    }
  }
}
