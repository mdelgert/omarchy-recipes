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
    answerField.text = ""
  }

  // Put the caret in the request box. Called instead of focusing this scope:
  // the field sits inside a ScrollView, which takes the scope's focus for
  // itself, so focusing the scope left the view unable to accept typing until
  // the user clicked the field. Naming the field directly skips that.
  function focusRequest() {
    requestField.forceActiveFocus()
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
        // Named rather than inlined so the sentence stays readable, and so the
        // engine's resolved provider/model is formatted in exactly one place.
        readonly property string agent: Model.agentSummary(root.engine.agentProvider,
                                                           root.engine.agentModel)
        text: "Describe what you want your system to do. The agent inspects this machine, "
            + "checks for conflicts, and proposes a reversible recipe. Nothing runs until you say so."
            + (agent
               ? "\n\nUses " + agent + ", already installed on this machine, with its file and "
                 + "shell tools switched off — it is given facts and returns text.\n"
                 + "Change it with:  omarchy-recipes config set agent.provider <name>"
               : "")
        color: Qt.darker(root.foreground, 1.3)
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
      }

      // ---- the request ----------------------------------------------------

      TextField {
        id: requestField
        width: parent.width
        // This view is a FocusScope, and Menu.qml focuses the scope when it
        // opens. Without a child claiming focus the scope has nothing to hand
        // the keyboard to, so Ctrl+N landed on a view you could not type into
        // until you clicked the field.
        focus: true
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

      // ---- progress --------------------------------------------------------
      //
      // A model call takes minutes. Without an elapsed count and something
      // moving, a disabled button is indistinguishable from a freeze — which
      // is exactly how it read the first time.
      Column {
        width: parent.width
        spacing: Style.spacing.xs
        visible: root.engine.authoringBusy

        Row {
          spacing: Style.spacing.controlGap

          Text {
            id: spinner
            textFormat: Text.PlainText
            property int frame: 0
            readonly property string frames: "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            text: frames.charAt(frame)
            color: root.accent
            font.family: root.fontFamily
            font.pixelSize: Style.font.body

            Timer {
              interval: 90
              repeat: true
              running: root.engine.authoringBusy
              onTriggered: spinner.frame = (spinner.frame + 1) % spinner.frames.length
            }
          }

          Text {
            textFormat: Text.PlainText
            text: (root.engine.planning ? "Asking the agent"
                  : root.engine.drafting ? "Writing the recipe"
                  : "Saving")
                  + " — " + root.engine.elapsedSeconds + "s"
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
          }
        }

        Text {
          textFormat: Text.PlainText
          width: parent.width
          wrapMode: Text.WordWrap
          text: root.engine.drafting
            ? "Writing a recipe usually takes one to three minutes. Nothing is being "
              + "changed on your system — the agent is only being asked for text."
            : "Usually under a minute."
          color: Qt.darker(root.foreground, 1.5)
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }

        Button {
          text: "Cancel"
          bordered: true
          focusable: true
          visible: root.engine.planning || root.engine.drafting
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: root.engine.cancelAuthoring()
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

        // What the user has already told the agent. Shown rather than hidden,
        // because a correction that silently vanishes is one the user cannot
        // tell was applied.
        Repeater {
          model: root.engine.answers
          delegate: Text {
            required property var modelData
            textFormat: Text.PlainText
            width: column.width
            wrapMode: Text.WordWrap
            text: "→  " + String(modelData)
            color: root.accent
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }

      // ---- answering back --------------------------------------------------

      Column {
        width: parent.width
        spacing: Style.spacing.controlGap
        visible: !!root.engine.plan && root.engine.draftText === ""

        TextField {
          id: answerField
          width: parent.width
          enabled: !root.engine.authoringBusy
          placeholderText: "Answer a question, or correct the plan — then ask again"
          foreground: root.foreground
          accent: root.accent
          onAccepted: if (!root.engine.authoringBusy) {
            root.engine.answerAndReplan(requestField.text, text)
            text = ""
          }
        }

        Button {
          text: root.engine.planning ? "Thinking…" : "Send answer"
          bordered: true
          focusable: true
          enabled: !root.engine.authoringBusy && answerField.text.trim() !== ""
          opacity: enabled ? 1 : 0.5
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: {
            root.engine.answerAndReplan(requestField.text, answerField.text)
            answerField.text = ""
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

        // Said plainly when the engine corrected the draft before showing it.
        // Auto-repair that the user cannot see would undercut the one promise
        // this view makes: that what is on screen is what will be saved, and
        // that they know where it came from.
        Text {
          textFormat: Text.PlainText
          width: parent.width
          wrapMode: Text.WordWrap
          visible: text !== ""
          text: Model.repairSummary(root.engine.draftRepairs)
          color: Qt.darker(root.foreground, 1.3)
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
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
          text: "Copy"
          bordered: true
          focusable: true
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: {
            draftText.selectAll()
            draftText.copy()
            draftText.deselect()
          }
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

          // TextEdit rather than Text: the whole point of showing the script
          // is that the user can audit it, and auditing often means copying it
          // somewhere else. readOnly keeps it display-only; the engine still
          // re-lints whatever is saved regardless of what happens here.
          TextEdit {
            id: draftText
            readOnly: true
            selectByMouse: true
            selectByKeyboard: true
            textFormat: TextEdit.PlainText
            width: parent.width
            wrapMode: TextEdit.Wrap
            text: root.engine.draftText
            color: Qt.darker(root.foreground, 1.15)
            selectionColor: Style.selectionFillFor(root.foreground, root.accent)
            selectedTextColor: root.foreground
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
