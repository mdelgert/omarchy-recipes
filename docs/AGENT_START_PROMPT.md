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

Core product idea: omarchy-recipes is a self-describing, reversible workstation automation system. It is not merely a shell-script launcher. Recipe Bash files are the source of truth for metadata and behavior. CLI/TUI/GUI frontends must dynamically discover recipes and generate controls from normalized metadata. Backup, exact restoration, idempotence, history, validation, least privilege, and human auditability are first-class concepts.

Preserve the boundary between the distro-independent recipe engine and the Omarchy frontend. Do not parse recipe metadata separately in QML. Do not concatenate untrusted parameter values into shell commands or use eval. Modifying recipes must inspect and backup existing state before mutation and implement honest undo behavior.

Before coding, run the existing tests and validate the recipes. Keep the starter small; do not turn it into Ansible, a scheduler, remote orchestration, dependency solver, or marketplace.

When you finish a change, run:
  make test
  make validate
and update docs/spec when changing the contract.
```

## Suggested first agent tasks

1. Implement a proper `tui` command using Gum when available, with a dependency-free fallback.
2. Implement the native Omarchy menu against the current built-in Quattro menu APIs.
3. Add `preview`/`diff` protocol support for file-based recipes.
4. Add a real low-risk Omarchy recipe (for example a user-level hotkey or idle setting) with exact backup/restore and tests.
5. Add a user recipe search path such as `~/.config/omarchy-recipes/recipes/` without breaking repository recipes.
6. Harden secret parameter handling before encouraging recipes that require secrets.
