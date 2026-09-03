import QtQuick
import QtTest

// Escape must reach the card's key handler from inside the draft view.
//
// Written while chasing "Escape does nothing after a draft is generated". The
// first suspect was this arrangement — the draft is a TextEdit with
// selectByKeyboard, which takes focus, so it looked like it might swallow the
// key before the card saw it. It does not: these pass against the unmodified
// code, which is what ruled the widget out and pointed at keyboard focus being
// lost at the surface instead.
//
// Kept as a regression test rather than deleted. Nothing else asserts that a
// focusable, key-handling widget in the draft area leaves Escape alone, and
// giving the draft its own key handling later would break the way out.
TestCase {
  id: testCase
  name: "EscapeKey"
  when: windowShown
  width: 200
  height: 200

  property int escapesSeen: 0

  Item {
    id: keyCatcher
    anchors.fill: parent
    focus: true

    // Same priority Menu.qml uses: a focused field gets its own keys first,
    // and whatever it ignores bubbles up here.
    Keys.priority: Keys.AfterItem
    Keys.onPressed: function(event) {
      if (event.key === Qt.Key_Escape) {
        testCase.escapesSeen += 1
        event.accepted = true
      }
    }

    TextEdit {
      id: draft
      anchors.fill: parent
      readOnly: true
      selectByKeyboard: true
      text: "#!/usr/bin/env bash\nset -Eeuo pipefail\n"
    }
  }

  function init() {
    testCase.escapesSeen = 0
    keyCatcher.forceActiveFocus()
  }

  function test_escape_reaches_the_card_when_nothing_is_focused() {
    keyCatcher.forceActiveFocus()
    keyClick(Qt.Key_Escape)
    compare(testCase.escapesSeen, 1)
  }

  function test_escape_reaches_the_card_from_the_draft_view() {
    // The regression: with the draft focused, Escape has to escape.
    draft.forceActiveFocus()
    verify(draft.activeFocus)
    keyClick(Qt.Key_Escape)
    compare(testCase.escapesSeen, 1, "Escape was swallowed by the draft TextEdit")
  }

  function test_draft_still_handles_its_own_keys() {
    // The fix must not cost the user text selection inside the draft.
    draft.forceActiveFocus()
    draft.select(0, 5)
    verify(draft.selectedText.length > 0)
  }
}
