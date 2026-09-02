# Starter prompt for coding agents

Use this when handing the repository to Claude Code, Codex, Copilot CLI, or another coding agent:

```text
You are working on the omarchy-recipes project.

First read, in order:
1. AGENTS.md
2. docs/VISION.md
3. docs/ARCHITECTURE.md
4. docs/RECIPE_SPEC.md
5. skills/recipe-authoring/SKILL.md
6. docs/OMARCHY_PLUGIN.md if touching the Omarchy GUI
7. docs/tasks/<slug>.md — the specific task you are assigned below

Core product idea: omarchy-recipes is a self-describing, reversible workstation automation system. It is not merely a shell-script launcher. Recipe Bash files are the source of truth for metadata and behavior. CLI/TUI/GUI frontends must dynamically discover recipes and generate controls from normalized metadata. Backup, exact restoration, idempotence, history, validation, least privilege, and human auditability are first-class concepts.

Preserve the boundary between the distro-independent recipe engine and the Omarchy frontend. Do not parse recipe metadata separately in QML. Do not concatenate untrusted parameter values into shell commands or use eval. Modifying recipes must inspect and backup existing state before mutation and implement honest undo behavior.

Before coding, run the existing tests and validate the recipes. Keep the starter small; do not turn it into Ansible, a scheduler, remote orchestration, dependency solver, or marketplace.

When you finish a change, run:
  make test
  make validate
and update docs/spec when changing the contract.
```

## What to hand the agent next

Don't improvise a task list here — it goes stale and duplicates the roadmap.
Pick (or write) one file under `docs/tasks/` (see `docs/tasks/README.md` for
the convention and `docs/AGENT_WORKFLOW.md` for the full process), and add to
the prompt above:

```text
Also read docs/tasks/<slug>.md and implement exactly that task.
```

`ROADMAP.md` tracks which phase-level items are still open if you need to
choose what to turn into a task next.
