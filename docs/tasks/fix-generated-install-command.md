# Task: Fix generated install command bug (e.g. `sudo pacman -S remmina`)

Status: Ready
Type: bug
Roadmap link: none (agent-authoring / recipe generation correctness)

## Goal

The AI recipe-authoring agent (or the package-install recipe pattern it
generates from) produces a working install command instead of a broken one.

## Context / current behavior

Reported in `docs/dev/KNOWN_BUGS.md`:

> Generated a bug on install script like `sudo pacman -S remmina`

Exact failure mode is not yet captured (wrong flag, missing `--noconfirm`,
wrong package name resolution, quoting issue, etc.) — reproduce first and
record what actually goes wrong before fixing.

## Scope

- Reproduce: ask the authoring agent for a recipe that installs a package via
  pacman (e.g. "install remmina") and capture the generated Bash and its
  actual failure output.
- Root-cause whether the bug is in the agent's generated Bash, in `lint`
  passing something it shouldn't, or in how the recipe protocol expects
  package-install recipes to be structured.
- Fix the generation prompt/skill (`skills/recipe-authoring/SKILL.md`) and/or
  the lint rule so this class of recipe is generated correctly and reliably.
- Add or update an example recipe / fixture covering package install if one
  doesn't already exist, so regressions are caught by `make test`.

## Out of scope

- Building a general distro/package-manager abstraction layer (that's the
  v0.3 "distro/package-manager capability helpers" roadmap item, not this
  bug fix).

## Acceptance criteria

- [ ] Root cause documented in the Report section below.
- [ ] Fix applied (skill guidance, lint rule, or example recipe correction).
- [ ] Regression test added under `tests/` reproducing the original failure.
- [ ] `make check` / `make validate` passes.

## Testing notes

Re-run the exact request that produced the bug through the authoring flow
and confirm the resulting recipe installs/uninstalls cleanly on a real
Omarchy session.

## Report

(fill in when done)
