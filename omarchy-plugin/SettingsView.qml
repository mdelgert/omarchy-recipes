import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui
import "RecipeModel.js" as Model

// Choose which AI provider answers an authoring request, and which model it
// uses. This is the only screen that writes the engine's config file.
//
// It writes through `omarchy-recipes config set`, never by editing JSON here.
// The engine validates every write and refuses an unknown provider, so this
// view cannot store a setting the engine would then fail to read back — and
// the value shown after a save is what the engine reports, not what was typed.
//
// No credential is collected here and none belongs here. Each provider CLI
// (`claude`, `copilot`, `codex`) owns its own login; the config holds a
// provider name and a model name and nothing else.
FocusScope {
  id: root

  required property var engine
  property color foreground: Color.menu.text
  property color accent: Color.accent
  property color selectedBackground: Color.menu.selectedBackground
  property string fontFamily: Style.font.menuFamily

  readonly property alias contentHeight: column.implicitHeight

  // Edit state is local until Save. Clicking through the providers to see what
  // is installed must not change what the agent actually uses.
  property string chosenProvider: ""
  property string modelText: ""

  readonly property var options: Model.providerOptions(engine.agentProviders, root.chosenProvider)
  readonly property string savedModel: String((engine.agentModels || ({}))[root.chosenProvider] || "")
  readonly property bool dirty: root.chosenProvider !== String(engine.agentProvider || "")
    || root.modelText !== root.savedModel

  // Seed from the engine whenever the screen is shown, so it always opens on
  // the current truth rather than whatever was left from a previous visit.
  function reload() {
    root.chosenProvider = String(engine.agentProvider || "")
    root.modelText = root.savedModel
  }

  function selectProvider(name) {
    root.chosenProvider = String(name)
    // A model belongs to one provider, so switching shows that provider's own
    // setting instead of leaving the previous provider's text behind.
    root.modelText = root.savedModel
  }

  function save() {
    if (!root.chosenProvider || engine.savingConfig) return
    engine.saveAgentConfig(root.chosenProvider, root.modelText)
  }

  Connections {
    target: root.engine
    function onConfigSaved() { root.reload() }
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
        text: "Which AI writes your recipes. Applies to authoring only — it has no "
            + "bearing on what a recipe does when it runs."
        color: Qt.darker(root.foreground, 1.3)
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
      }

      // ---- provider ---------------------------------------------------------

      Text {
        textFormat: Text.PlainText
        text: "Provider"
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
      }

      Column {
        width: parent.width
        spacing: Style.spacing.xs

        Repeater {
          model: root.options

          delegate: Rectangle {
            id: option
            required property var modelData

            width: parent.width
            height: Style.space(34)
            radius: Style.cornerRadius
            color: optionMouse.containsMouse ? root.selectedBackground : "transparent"

            Row {
              anchors.left: parent.left
              anchors.leftMargin: Style.spacing.rowPaddingX
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.spacing.controlGap

              Text {
                textFormat: Text.PlainText
                text: option.modelData.selected ? "(•)" : "( )"
                color: option.modelData.selected ? root.accent : root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
              }

              Text {
                textFormat: Text.PlainText
                width: Style.space(90)
                text: option.modelData.name
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
              }

              // Availability is reported, not enforced: an uninstalled provider
              // can still be chosen, and the engine names the missing CLI when
              // it is actually used.
              Text {
                textFormat: Text.PlainText
                anchors.verticalCenter: parent.verticalCenter
                text: option.modelData.status
                color: option.modelData.available
                  ? Qt.darker(root.foreground, 1.5)
                  : Color.urgent
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }
            }

            MouseArea {
              id: optionMouse
              anchors.fill: parent
              hoverEnabled: true
              onClicked: root.selectProvider(option.modelData.name)
            }
          }
        }
      }

      // ---- model ------------------------------------------------------------

      Text {
        textFormat: Text.PlainText
        visible: root.chosenProvider !== ""
        text: "Model for " + root.chosenProvider
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
      }

      // A picker for the common case, and a free-text field beside it because
      // the list cannot be complete: no provider CLI can enumerate its models,
      // so the engine's list is written down and will go stale. Locking the
      // field to it would block a model released tomorrow.
      Dropdown {
        id: modelPicker
        visible: root.chosenProvider !== ""
        width: Math.min(parent.width, Style.spacing.dropdownWidth)
        showLabel: false
        enabled: !root.engine.savingConfig
        options: Model.modelOptions(root.engine.agentModelOptions,
                                    root.chosenProvider, root.modelText)
        value: Model.modelToOption(root.modelText)
        foreground: root.foreground
        accent: root.accent
        fontFamily: root.fontFamily
        onChanged: function(picked) { root.modelText = Model.modelFromOption(picked) }
      }

      TextField {
        id: modelField
        width: parent.width
        visible: root.chosenProvider !== ""
        enabled: !root.engine.savingConfig
        placeholderText: "or type a model the list does not have"
        foreground: root.foreground
        accent: root.accent
        text: root.modelText
        onTextChanged: root.modelText = text
        onAccepted: root.save()
      }

      Text {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.WordWrap
        visible: root.chosenProvider !== ""
        text: "The list is a shortlist, not everything the provider accepts — no CLI can "
            + "report its own models, so anything you type is allowed. "
            + Model.modelDefaultLabel() + " lets the provider choose. A --model flag, or "
            + "OMARCHY_RECIPES_MODEL, still wins for a single call."
        color: Qt.darker(root.foreground, 1.5)
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      // ---- save -------------------------------------------------------------

      Row {
        spacing: Style.spacing.controlGap

        Button {
          text: root.engine.savingConfig ? "Saving…" : "Save"
          bordered: true
          focusable: true
          enabled: root.dirty && !root.engine.savingConfig && root.chosenProvider !== ""
          opacity: enabled ? 1 : 0.5
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: root.save()
        }

        Button {
          text: "Revert"
          bordered: true
          focusable: true
          visible: root.dirty
          enabled: !root.engine.savingConfig
          foreground: root.foreground
          accent: root.accent
          fontFamily: root.fontFamily
          onClicked: root.reload()
        }
      }

      Text {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.WordWrap
        visible: root.engine.configError !== ""
        text: "Could not save: " + root.engine.configError
        color: Color.urgent
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      Text {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.WordWrap
        text: "Saved in ~/.config/omarchy-recipes/config.json — a provider name and a "
            + "model name, never a credential. Each CLI owns its own login."
        color: Qt.darker(root.foreground, 1.6)
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
    }
  }
}
