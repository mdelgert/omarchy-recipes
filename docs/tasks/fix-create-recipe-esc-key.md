# Task: Fix Esc key trapped in Create Recipe until Apply

Status: Ready
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

- [ ] `Esc` closes the Create Recipe view at every stage: empty prompt,
      after plan, after draft (pre-save), and after save.
- [ ] Existing keybindings (`Ctrl+N` to open, etc.) still work.
- [ ] QML logic test covering the key-handling state if `RecipeModel.js` or
      an equivalent testable module owns this logic.
- [ ] `make check` passes.

## Testing notes

Manual, per `docs/OMARCHY_PLUGIN.md` conventions: open the menu, `Ctrl+N`,
type a request, wait for the draft, press `Esc` without clicking Apply —
the card should close.

## Report

(fill in when done)
