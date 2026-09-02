import QtQuick
import qs.Commons
import qs.Ui
import "RecipeModel.js" as Model

// One generated control for one declared recipe parameter.
//
// The control is picked from `parameter.type` alone — no recipe is ever named
// here, and adding a parameter type means adding a case to RecipeModel.js and
// a Loader branch below, not restructuring the form. Values leave through
// `changed(name, value)` and reach the runner as argv; nothing is interpolated
// into a command string, and nothing from the metadata is evaluated as code.
Column {
  id: root

  required property var parameter
  property var value: undefined
  property color foreground: Color.menu.text
  property color accent: Color.accent
  property string fontFamily: Style.font.menuFamily

  // True while an embedded editor owns the keyboard, so the hosting view can
  // stop treating keystrokes as navigation.
  readonly property bool editing: loader.item
    ? (loader.item.editing === undefined ? false : loader.item.editing)
    : false

  signal changed(string name, var newValue)

  readonly property string controlKind: Model.controlFor(parameter)
  readonly property string paramName: String(parameter && parameter.name || "")

  spacing: Style.spacing.labelGap
  width: parent ? parent.width : implicitWidth

  Text {
    // PlainText everywhere recipe-authored strings are shown: metadata is
    // untrusted input and must never be promoted to rich text.
    textFormat: Text.PlainText
    text: Model.parameterLabel(root.parameter) + (root.parameter && root.parameter.required ? " *" : "")
    color: Qt.darker(root.foreground, 1.3)
    font.family: root.fontFamily
    font.pixelSize: Style.font.bodySmall
    font.bold: true
  }

  Loader {
    id: loader
    width: parent.width
    sourceComponent: {
      switch (root.controlKind) {
        case "number": return numberControl
        case "toggle": return toggleControl
        case "choice": return choiceControl
        case "secret": return secretControl
        case "path":   return pathControl
        default:       return textControl
      }
    }
  }

  Text {
    textFormat: Text.PlainText
    visible: text !== ""
    width: parent.width
    wrapMode: Text.WordWrap
    text: String(root.parameter && root.parameter.description || "")
    color: Qt.darker(root.foreground, 1.6)
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
  }

  // ---- controls -----------------------------------------------------------

  Component {
    id: textControl
    TextField {
      property bool editing: activeFocus
      width: Math.min(parent.width, Style.space(320))
      text: Model.valueAsText(root.value)
      foreground: root.foreground
      accent: root.accent
      placeholderText: Model.valueAsText(root.parameter ? root.parameter.default : "")
      onTextChanged: root.changed(root.paramName, text)
    }
  }

  Component {
    id: pathControl
    TextField {
      property bool editing: activeFocus
      width: parent.width
      text: Model.valueAsText(root.value)
      foreground: root.foreground
      accent: root.accent
      placeholderText: Model.valueAsText(root.parameter ? root.parameter.default : "") || "/path/to/target"
      onTextChanged: root.changed(root.paramName, text)
    }
  }

  Component {
    id: secretControl
    TextField {
      property bool editing: activeFocus
      width: Math.min(parent.width, Style.space(320))
      password: true
      text: Model.valueAsText(root.value)
      foreground: root.foreground
      accent: root.accent
      onTextChanged: root.changed(root.paramName, text)
    }
  }

  Component {
    id: numberControl
    Row {
      property bool editing: field.field.activeFocus
      spacing: Style.spacing.controlGap

      NumberField {
        id: field
        // The engine re-validates the range; these bounds only stop the
        // spinner from offering a value the recipe already rejected.
        from: root.parameter && root.parameter.min !== null && root.parameter.min !== undefined
          ? root.parameter.min : -2147483647
        to: root.parameter && root.parameter.max !== null && root.parameter.max !== undefined
          ? root.parameter.max : 2147483647
        value: {
          var n = parseInt(Model.valueAsText(root.value), 10)
          return isNaN(n) ? from : n
        }
        foreground: root.foreground
        accent: root.accent
        fontFamily: root.fontFamily
        onModified: function(v) { root.changed(root.paramName, v) }
      }

      Text {
        textFormat: Text.PlainText
        anchors.verticalCenter: field.verticalCenter
        visible: text !== ""
        text: {
          var p = root.parameter
          if (!p) return ""
          var hasMin = p.min !== null && p.min !== undefined
          var hasMax = p.max !== null && p.max !== undefined
          if (hasMin && hasMax) return p.min + "–" + p.max
          if (hasMin) return "min " + p.min
          if (hasMax) return "max " + p.max
          return ""
        }
        color: Qt.darker(root.foreground, 1.6)
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
    }
  }

  Component {
    id: toggleControl
    // A Row rather than a bare switch: the Loader stretches its item to the
    // form width, which would centre the switch away from its own label.
    Row {
      property bool editing: false

      ToggleSwitch {
        id: toggleSwitch
        checked: root.value === true || Model.valueAsText(root.value) === "true"
        foreground: root.foreground
        accent: root.accent
        onToggled: root.changed(root.paramName, !checked)
      }
    }
  }

  Component {
    id: choiceControl
    Dropdown {
      property bool editing: popupOpen
      width: Math.min(parent.width, Style.spacing.dropdownWidth)
      showLabel: false
      options: (root.parameter && root.parameter.choices) || []
      value: Model.valueAsText(root.value)
      foreground: root.foreground
      accent: root.accent
      fontFamily: root.fontFamily
      onChanged: function(v) { root.changed(root.paramName, v) }
    }
  }
}
