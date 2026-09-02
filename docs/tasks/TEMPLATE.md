# Task: <short title>

Status: Draft | Ready | In progress | Done
Type: feature | bug | chore
Roadmap link: <v0.1/v0.2/v0.3/Later item this maps to, if any>

## Goal

One or two sentences: what should be true when this is done, from the user's
point of view.

## Context / current behavior

What exists today, and why this task is needed. Link to the relevant code,
recipe, or doc. For a bug: exact repro steps and observed vs. expected
behavior.

## Scope

Bullet list of what must be implemented. Be concrete enough that an agent
does not have to guess (e.g. "add `preview` action to `check`", not "improve
previews").

## Out of scope

What NOT to do here, even if related. Keeps the agent from wandering into
adjacent roadmap items.

## Acceptance criteria

- [ ] ...
- [ ] tests added/updated for the new behavior
- [ ] `make test validate` (or `make check`) passes
- [ ] docs/spec updated if the contract changed
- [ ] undo declared and documented, if this adds a modifying recipe or engine mutation

## Testing notes

Anything specific to exercise manually (Omarchy plugin testing steps, edge
cases, fixtures to use).

## Report

Filled in by the agent when done: what was implemented, decisions made, known
limitations, follow-up ideas. Move this file to `docs/tasks/done/` and set
Status to Done when finished.
