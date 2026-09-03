# Task: Curated candidate recipe list — what Omarchy lacks, what professionals want

Status: Ready
Type: chore
Roadmap link: v0.3 — real recipe library

## Goal

A single document exists listing concrete, categorized recipe ideas —
covering gaps in Omarchy's own defaults and common workstation tasks a
professional (developer, sysadmin, power user) would reach for — so that
picking "what to build next" is a matter of choosing an entry and writing its
`docs/tasks/<slug>.md`, instead of brainstorming from scratch each time. The
list should be broad enough to demonstrate the range of what
`omarchy-recipes` can express (mutating + reversible recipes, and report-only
recipes per `docs/tasks/report-only-diagnostic-recipes.md`).

## Context / current behavior

`docs/dev/NEW_FEATURES.md` already has two related, unscoped notes:

- "Add 'execute bash script and show results' examples: show IP address, open
  ports, logs and other diagnostics, maintenance scripts."
- "Add a curated list of good example recipes for Omarchy."

Neither is concrete enough to hand to an agent yet — that's this task. The
current library (`recipes/examples/`, `recipes/community/`) is small: a
handful of config-value/feature-toggle/report examples plus a few real
community recipes (idle timeouts, error log report, remote desktop
passthrough). There is no single place that surveys what's missing.

## Scope

1. Research current Omarchy defaults (installed packages/services, its
   built-in menu/settings, its documented plugin examples) well enough to
   separate "Omarchy has no built-in way to do this" from "this is just a
   generally useful professional workstation task, Omarchy-agnostic."
2. Produce `docs/RECIPE_IDEAS.md`: a categorized backlog of candidate
   recipes. Reuse the existing category set from
   `skills/recipe-authoring/SKILL.md` (`System`, `Power`, `Applications`,
   `Development`, `Networking`, `Storage`, `Security`, `Omarchy`, `Desktop`,
   plus `Diagnostics` for report-only recipes).
3. For each candidate entry, include:
   - Name / working title
   - One-line description of what it does
   - Category
   - Gap type: `omarchy-gap` (gap in Omarchy itself) vs `professional-utility`
     (generally useful, not Omarchy-specific)
   - Suggested `undo`: `restore` / `command` / `none`
   - Rough risk: `low` / `medium` / `high`
   - One line on why it's worth having (what it demonstrates or who wants it)
4. Cover at minimum: developer tooling (dotfiles sync, SSH key/config
   management, git global config, language version managers), security
   (firewall rule toggling, disk encryption status check, fail2ban), backup
   (rsync/borg-style snapshot job), monitoring/observability, laptop/power
   management beyond what's already covered, and the report-only diagnostics
   already scoped in `docs/tasks/report-only-diagnostic-recipes.md` (cross-
   reference rather than duplicate). Aim for at least 25 entries across at
   least 5 categories.
5. Remove the two superseded bullets from `docs/dev/NEW_FEATURES.md` once
   `docs/RECIPE_IDEAS.md` exists, per the normal inbox-promotion workflow.

## Out of scope

- Implementing any of the listed recipes. Each selected entry gets its own
  `docs/tasks/<slug>.md` later, following the normal one-task-one-recipe
  workflow.
- Any engine, QML, or spec/protocol changes.
- Ansible support (separate, already-flagged inbox item with its own open
  question about contradicting the roadmap's "Later" phase — do not fold it
  into this list).

## Acceptance criteria

- [ ] `docs/RECIPE_IDEAS.md` created with the categorized, tagged entries
      described above (≥25 entries, ≥5 categories)
- [ ] the two superseded notes removed from `docs/dev/NEW_FEATURES.md`
- [ ] cross-references `docs/tasks/report-only-diagnostic-recipes.md` instead
      of duplicating its entries
- [ ] this is a docs-only change: no code, tests, or `validate` impact
      expected; confirm `make check` still passes unchanged

## Testing notes

Docs-only task — no functional testing. Sanity-check the doc renders cleanly
and every entry has all required fields.

## Report

<!-- Filled in by the agent when done. Move this file to docs/tasks/done/ and
set Status to Done when finished. -->
