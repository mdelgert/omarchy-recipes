# AGENTS.md

## Mission

Build `omarchy-recipes` as a self-describing, reversible workstation recipe system. Do not reduce it to a generic shell-script launcher. Read `docs/VISION.md` before making architectural changes.

## Architectural constraints

- Recipe format/engine must remain frontend-neutral.
- Omarchy QML is a frontend, not the source of truth.
- Frontends consume normalized engine output; they do not independently parse recipe comments.
- Adding a normal recipe must not require UI code changes.
- Backup/undo/history are core product concepts, not optional polish.
- Avoid dependencies unless they create clear value.

## Before changing code

Read:

1. `docs/VISION.md`
2. `docs/ARCHITECTURE.md`
3. `docs/RECIPE_SPEC.md`
4. `skills/recipe-authoring/SKILL.md` when editing or adding recipes
5. `docs/tasks/<slug>.md` for the specific assignment, if one was given — see
   `docs/AGENT_WORKFLOW.md` for how tasks are scoped and reviewed

## Coding expectations

- Keep the Python engine compatible with the Python available on a normal current Arch/Omarchy install.
- Prefer standard library for the starter.
- Do not invoke shell commands with `shell=True` when argv can be used.
- Do not use `eval` for user-provided values.
- Preserve stable JSON output because GUI/TUI clients consume it.
- Add tests for parser/protocol changes.
- Keep recipe IDs stable once published.

## Omarchy integration

Current Omarchy plugins run unsandboxed in the long-running shell. Keep execution in the external runner process. Use current official Omarchy plugin docs and built-in examples before changing QML; APIs can evolve.

## Definition of done

A change is not complete until:

- tests pass
- `./bin/omarchy-recipes validate` passes
- docs/spec are updated if the contract changed
- new modifying recipes have an undo declaration and documented reversal behavior
- if you were given a `docs/tasks/<slug>.md` file, its Report section is
  filled in and its Acceptance criteria are checked off
