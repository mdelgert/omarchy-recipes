# Agent Workflow

How to run this project solo with one coding agent at a time (Claude Code,
Copilot CLI, Codex, etc.) and no separate reviewer agent.

## Document roles (read this if you're ever unsure where something belongs)

| Doc | Purpose | Changes how often |
| --- | --- | --- |
| `docs/VISION.md` | Why this project exists, what it must never become | rarely |
| `docs/ARCHITECTURE.md` | Component boundaries, JSON contract, lifecycle | when the contract changes |
| `docs/RECIPE_SPEC.md` | Recipe metadata + execution protocol | when the protocol changes |
| `AGENTS.md` | Standing rules every agent must follow, every task | rarely |
| `docs/AGENT_START_PROMPT.md` | The prompt template you paste to kick off an agent | rarely |
| `ROADMAP.md` | Phase-level checklist (v0.1/v0.2/v0.3/Later) | when a phase item starts/finishes |
| `docs/tasks/*.md` | One concrete, assignable unit of work | created/closed per task — **this is where you write what to build next** |
| `docs/dev/*.md` | Scratch inbox: raw bug reports and feature ideas, not yet ready to assign | continuously, low friction |
| `docs/milestones/MILESTONE-N-SPEC.md` | The original brief given to the agent for a past milestone | frozen once written |
| `docs/milestones/MILESTONE-N-REPORT.md` | What the agent actually delivered for that milestone | written once, at milestone close |

Milestones are large (multi-week) bodies of work with their own spec/report
pair. Tasks in `docs/tasks/` are the smaller day-to-day unit — a milestone is
usually built from several tasks.

## Branching

- **`main`** — stable, protected. Only receives merges via PR from `dev` (or
  a milestone/recipe branch), never direct commits.
- **`dev`** — rolling integration branch. This is where you add/edit
  `docs/tasks/*.md`, `ROADMAP.md`, and other low-risk backlog/docs changes
  directly — no branch needed for planning.
- **`task/<slug>`** (or `recipe/<slug>` for a single recipe, matching the
  existing `contribute` command convention) — create this off an up-to-date
  `dev` *before* handing a task to an agent:

  ```bash
  git checkout dev && git pull
  git checkout -b task/<slug>          # matches docs/tasks/<slug>.md
  ```

  The agent works and commits here, never on `dev` or `main` directly. You
  review the diff on this branch, run `make check`/`make validate`, then PR
  it into `dev`. Delete the branch after merge.
- Periodically, once `dev` accumulates a coherent batch of merged tasks, open
  a PR from `dev` into `main` (this replaces the old milestone-branch-to-main
  pattern for the smaller task-sized work).

So: **plan on `dev`, implement on `task/<slug>`.**

## The loop

1. **Capture the idea.** Jot bugs/ideas into `docs/dev/KNOWN_BUGS.md` or
   `docs/dev/NEW_FEATURES.md` the moment you think of them. No formatting
   rules — this is a scratchpad, not a spec.
2. **Promote it to a task.** When you're ready to work on something, copy
   `docs/tasks/TEMPLATE.md` to `docs/tasks/<slug>.md`, fill in Goal / Scope /
   Out of scope / Acceptance criteria, and delete the raw note from the inbox
   it came from. This is the step that turns a vague idea into something an
   agent can execute without guessing scope.
3. **Assign it.** Give the agent the prompt from `docs/AGENT_START_PROMPT.md`
   plus: *"Read `docs/tasks/<slug>.md` and implement it."* The agent already
   reads `AGENTS.md`, `docs/VISION.md`, `docs/ARCHITECTURE.md`,
   `docs/RECIPE_SPEC.md`, and the relevant skill file per the start prompt.
4. **Let it work end to end.** The agent implements, adds/updates tests, runs
   `make test validate` (or `make check`), and fills in the **Report** section
   of the task file (what it did, decisions, limitations, follow-ups) — this
   replaces a separate reviewer agent's write-up.
5. **You are the reviewer.** Since there's no second agent doing code review:
   - Read the diff yourself (`git diff`), focusing on: does it touch `eval`
     or `shell=True`? Does a modifying recipe back up state and declare undo?
     Did it avoid parsing recipe metadata a second time in QML?
   - Re-run `make check` / `make validate` yourself rather than trusting the
     agent's report of green tests.
   - For anything privileged or destructive, do the manual test steps the
     task file's Testing notes describe, on a real Omarchy session, before
     merging.
   - If you want a second opinion without a second live agent, ask the same
     agent (or a different model) to review its own diff *in a fresh
     session/turn* against `AGENTS.md` and the task's acceptance criteria —
     this is a cheap substitute for a dedicated review agent and costs
     nothing to add later if you start running one.
6. **Close it out.** Once merged: check the box in `ROADMAP.md` if this task
   completed a roadmap item, move `docs/tasks/<slug>.md` to
   `docs/tasks/done/`, and commit.
7. **Milestones are just a checkpoint.** When a cluster of tasks adds up to
   a named milestone (a whole UI, a whole subsystem), write the
   `MILESTONE-N-SPEC.md`/`MILESTONE-N-REPORT.md` pair as before — that
   process doesn't change, it just now sits one level above individual task
   files instead of being the only unit of work.

## Why this shape

- **One canonical backlog location** (`docs/tasks/`) instead of task ideas
  being scattered across `ROADMAP.md`, `docs/dev/*.md`, and a prompt file's
  own "suggested first tasks" list — you previously had four places an agent
  could plausibly look for "what's next."
- **Low-friction capture stays separate from execution-ready specs.**
  `docs/dev/` remains the place to dump a one-line bug note without ceremony;
  nothing is lost by not writing a full task file for every idea immediately.
- **No reviewer agent needed for the loop to work.** The task file's
  Acceptance Criteria section is what the agent is held to, and you (the
  human) are the reviewer using it as a checklist — this is what a reviewer
  agent would otherwise check against.
