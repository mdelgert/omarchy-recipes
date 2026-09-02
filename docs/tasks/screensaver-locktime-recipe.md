# Task: Screensaver / lock-timeout recipe

Status: Ready
Type: feature
Roadmap link: v0.3 — power/idle recipe

## Goal

A recipe that lets a user enable/disable the screensaver and lock, and adjust
the screensaver and lock timeout, through the normal recipe protocol
(check/apply/undo).

## Context / current behavior

Idea captured in `docs/dev/TEST_RECIPE.md`:

> Add recipe to enable disable screensaver and locktime, also ability to
> adjust the screensaver and locktime timeout.

No recipe currently controls idle/screensaver/lock behavior. This is the
"power/idle recipe" line item in `ROADMAP.md` v0.3.

## Scope

- Follow `skills/recipe-authoring/SKILL.md` for structure and metadata.
- Parameters: an `enabled` boolean (screensaver/lock on or off) and a
  `timeout` integer (seconds, with sane min/max, mirroring the pattern in the
  existing `example-numeric-setting` recipe).
- `check` reports current enabled/disabled state and current timeout via the
  `@recipe.state` / `@recipe.summary` protocol.
- `apply` backs up the prior config before writing (`recipe_backup_file` or
  equivalent), and is idempotent.
- `undo` restores the exact prior state (enabled/disabled + timeout), not
  just a hardcoded default.
- Identify the actual Omarchy/Hyprland mechanism this should target (e.g.
  `hypridle` config) — use `omarchy-recipes inspect` during authoring rather
  than assuming a file path.

## Out of scope

- Power plan switching (separate roadmap idea, see
  `docs/dev/NEW_FEATURES.md` / a future task for "omarchy power plans").
- VNC/RDP passthrough keybinding (separate task).

## Acceptance criteria

- [ ] Recipe added under an appropriate `recipes/` subdirectory with a stable
      kebab-case id.
- [ ] `check`/`apply`/`undo` all implemented and tested.
- [ ] Declares risk/privilege/undo metadata per `docs/RECIPE_SPEC.md`.
- [ ] `omarchy-recipes lint` passes clean.
- [ ] Engine test covering enable/disable + timeout change + undo restoring
      exact prior values.
- [ ] `make check` / `make validate` passes.

## Testing notes

Manual: apply with a short timeout, verify the system actually idles/locks
at that interval or that the config file reflects it; undo and verify the
prior value is restored exactly, including if the prior state was
"disabled."

## Report

(fill in when done)
