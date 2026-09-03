# Task: Fix Esc key trapped in Create Recipe until Apply

Status: Done
Type: bug
Roadmap link: none (UX bug in Milestone 2 authoring UI)

## Goal

A user in the "Create a recipe" chat/authoring view can press `Esc` to close
the dialog and keep (or discard) a generated-but-not-yet-applied recipe,
instead of `Esc` only working after Apply.

## Context / current behavior

Reported in `docs/dev/KNOWN_BUGS.md`:

> After create a script does not allow esc key only allows esc key if apply
> the script, I should be able to create and save recipe without applying it.

Currently the authoring UI (`CreateRecipe.qml` / whatever controls its modal
state) appears to only accept `Esc` once the drafted recipe has been applied.
The user should be able to generate a recipe, save it locally via `create`
(see `docs/milestones/MILESTONE-2-REPORT.md` — `create` already supports
saving without running), and close the dialog at any point without being
forced to Apply first.

## Scope

- Reproduce the issue: open Create Recipe, generate a draft, do not apply it,
  press `Esc`.
- Fix the QML key handling so `Esc` always closes/cancels the authoring flow,
  regardless of draft state.
- If a draft exists and hasn't been saved, decide (and document) whether
  `Esc` discards it silently or prompts — prefer silent discard with an
  explicit "Save" step already available, to match the existing save-without-
  apply flow.

## Out of scope

- Changing the save/apply/undo protocol itself.
- Adding a confirmation dialog framework if one doesn't already exist for
  other flows — reuse whatever pattern `ConfirmDialog` already provides only
  if it fits; otherwise keep this minimal.

## Acceptance criteria

- [x] `Esc` closes the Create Recipe view at every stage: empty prompt,
      after plan, after draft (pre-save), and after save.
- [x] Existing keybindings (`Ctrl+N` to open, etc.) still work.
- [x] QML logic test covering the key-handling state if `RecipeModel.js` or
      an equivalent testable module owns this logic.
- [x] `make check` passes.

## Testing notes

Manual, per `docs/OMARCHY_PLUGIN.md` conventions: open the menu, `Ctrl+N`,
type a request, wait for the draft, press `Esc` without clicking Apply —
the card should close.

## Report

Fixed, plus a second defect found while reproducing it.

### Escape was not the thing that was broken

Escape is handled in `Menu.qml`'s card key handler and has never had a
draft-state condition, so the reported "only works after apply" was not a
missing branch. Two suspects were ruled out by testing rather than reading:

1. **The draft `TextEdit` swallowing the key.** It has `selectByKeyboard`, so
   it takes focus, and looked like the obvious culprit. `tests/qml/tst_esckey.qml`
   drives real key events at that arrangement and shows Escape reaches the outer
   handler. The test is kept: nothing else pins that invariant down.
2. **State after a draft.** Escape from the after-plan stage returns to the
   browse list, verified in the running plugin.

The actual defect is keyboard focus. The menu takes `OnDemand` keyboard focus
120 ms after opening, so clicking away to another window drops the keyboard —
and an agent call runs for minutes, which makes that the normal case, not an
edge one. Clicking the card is how the user gets it back, but that reclaim read:

```qml
onClicked: if (root.view === "browse") keyCatcher.forceActiveFocus()
```

Only the browse view. Create Recipe and the detail view were therefore
keyboard-dead once focus had been lost, with no way to recover: no handler ran,
Escape silently did nothing, and finishing the flow was the only way out. That
matches the report exactly. The reclaim now runs in every view, routed through
`Model.focusTargetForView()` so the choice is unit-testable without a compositor.

### The second defect: the view could not be typed into

While reproducing, typed text never reached the request field. That was not the
harness: `CreateRecipe.qml` is a `FocusScope` and `openCreate()` focused the
scope, but the field sits inside a `ScrollView`, which takes the scope's focus
for itself. Nothing forwarded it on, so `Ctrl+N` opened a view you could not
type into until you clicked the field.

`focus: true` on the field was not enough — confirmed by measuring the field's
focus ring in a screenshot, which did not change. Naming the field directly
(`create.focusRequest()`) does work: the ring changes, and typing then lands.
This is why the flow above could be driven at all.

### Draft retention on Escape

Escape keeps the draft; "Start over" discards it. The scope asked for a decision
between silent discard and a prompt, preferring "silent discard with an explicit
Save already available" — read as *do not put a confirmation in the way of
Escape*, which is honoured: nothing blocks it. Retaining the draft goes slightly
further than the letter of that preference, deliberately: Escape is easy to hit
by accident and a generation costs minutes, so destroying it silently is the
worse failure. Discarding stays available and explicit.

### Verified

- Escape returns to the browse list from: create (empty prompt), create
  (after plan), and settings — all in the running plugin.
- Typing works immediately on `Ctrl+N`, measured by the field's focus state and
  then by driving a real request end to end through plan and conflict checking.
- 134 engine tests + 40 QML tests (up from 33), no new kinds of qmllint warning.

### Not verified

Escape after a *draft* and after a *save* were not exercised live. Reaching
those needs a click on "Generate recipe" and this session has no pointer
injection. They are covered by reasoning rather than observation: the Escape
handler has no draft-state condition, and the draft widget is shown not to
consume the key. Worth a manual pass.
