# Tasks

This directory is the single place to describe a unit of work small enough to
hand to a coding agent in one sitting ("implement this feature from this
markdown file").

## Files

- `TEMPLATE.md` — copy this to start a new task.
- `<slug>.md` — one task, one feature or one bug, ready to assign.
- `done/` — finished tasks, moved here once merged, for history/reference.

## Where a task idea comes from

- `ROADMAP.md` tracks the high-level phase checklist. When you're ready to
  work an unchecked roadmap item, write a task file for it here first — the
  roadmap line stays a one-line pointer, the task file has the real detail.
- `docs/dev/` is a scratch inbox for half-formed bug reports and feature
  ideas. It is not agent-ready. Promote an idea into a task file (using
  `TEMPLATE.md`) before assigning it, then delete the note from the inbox.

## Naming

`kebab-case-slug.md`, e.g. `screensaver-locktime-recipe.md`,
`fix-create-recipe-esc-key.md`. Prefix bugs with `fix-` so `ls` sorts them
apart from feature work.

## Workflow

See `docs/AGENT_WORKFLOW.md` for the full process. Short version: pick one
`pending`-equivalent task file here, hand it to the agent alongside
`AGENTS.md`, review the diff yourself, run `make check`/`make validate`, then
move the file to `done/` with its report filled in.
