# Task: Ansible as an optional adapter for routine, idempotent-change recipes

Status: Draft
Type: feature
Roadmap link: none yet — read "Conflict to resolve before assigning" below
before promoting this out of Draft

## Conflict to resolve before assigning

`docs/VISION.md`'s non-goals list (~line 195) explicitly says: "Do not turn
v1 into: ... Ansible." `docs/dev/NEW_FEATURES.md` already carried an
unscoped note about this with the same caveat. This task is written as the
narrower version — **an optional adapter for recipes whose routine change is
naturally idempotent-module-shaped (package/service/file/template changes)**,
not a replacement for the bash recipe format and not a "preferred" default.
Do not start this task until a human has decided it doesn't violate the
non-goal as scoped below. If the answer is "it still does," delete this file
instead of implementing it.

## Goal

For a recipe whose change is well-served by an existing, battle-tested
Ansible module (package install, service enable/disable, file templating,
line-in-file edits), an author can express the `apply` step as a small,
declarative Ansible task list instead of hand-rolled bash — while the recipe
still honestly reports state, gets backed up, and can be undone through the
same mechanism every other recipe uses. Nothing about a normal bash recipe
changes; this is strictly additive.

## Context / current behavior

- `docs/RECIPE_SPEC.md`'s execution protocol is bash-specific: argv[1] is the
  action, parameters arrive as long options, `lib/recipe.sh` provides
  `recipe_parse_args`, `recipe_state`, `recipe_backup_file`, etc. There is no
  concept today of a recipe whose body isn't a bash script the engine
  executes directly.
- `skills/recipe-authoring/SKILL.md`'s safety rules (backup before
  modification, idempotent, verify after apply, honest `undo`) are all
  implemented by hand in every existing recipe (`recipes/examples/`,
  `recipes/community/`). Ansible's built-in modules already guarantee several
  of these (idempotency, check-mode/dry-run) for the specific operations they
  cover — but Ansible has **no built-in undo**; the backup/restore-before-
  modify discipline this project already built in `lib/recipe.sh` would still
  be required around it, not replaced by it.
- Ansible playbooks are YAML, which supports `#` comments, so the existing
  `@recipe.*` metadata comment grammar (`docs/RECIPE_SPEC.md`) could sit
  unchanged at the top of a playbook file — metadata parsing does not
  inherently require the body to be bash.
- `ansible-core` is not part of a stock Arch/Omarchy install and would be a
  new runtime dependency; `AGENTS.md` says to avoid dependencies unless they
  create clear value.

## Scope

1. Get explicit sign-off that this doesn't contradict `docs/VISION.md`'s
   non-goal before writing any code (see "Conflict to resolve" above) —
   likely as an amendment to `docs/VISION.md` narrowing the non-goal to
   "Ansible as the primary format" rather than "Ansible at all."
2. Design a recipe "kind" or file convention that marks a recipe as
   Ansible-backed (e.g. a `.yml` recipe file alongside `.sh` ones, or a
   `@recipe.engine ansible` metadata key) so discovery in
   `src/omarchy_recipes/core.py` can tell the two apart without guessing from
   file contents.
3. Define how `check` / `apply` / `undo` map onto Ansible for this kind:
   - `check`: Ansible's `--check` (dry-run) mode reporting whether anything
     would change, translated into the existing `recipe_state
     configured|not-configured|...` marker contract so frontends don't need
     to know an Ansible recipe exists.
   - `apply`: runs the playbook for real; still calls the same backup
     discipline (`recipe_backup_file`/`recipe_mark_absent` equivalents) for
     any file Ansible is about to touch, since Ansible modules don't record
     the kind of restorable snapshot this project's undo model needs.
   - `undo`: same `restore`/`command`/`none` vocabulary as bash recipes —
     Ansible gives no undo for free, so this is still hand-authored per
     recipe, same as today.
4. Require the same declared-resource conflict-checking flow
   (`omarchy-recipes conflicts`) before an Ansible-backed recipe is authored,
   same as bash recipes today.
5. Add exactly one real example recipe using this adapter (something
   genuinely idempotent-module-shaped, e.g. ensuring a package is installed)
   to prove the round trip end-to-end, not a library of them.
6. Update `docs/RECIPE_SPEC.md` and `skills/recipe-authoring/SKILL.md` to
   document this as one additional, optional recipe kind — explicitly not a
   replacement for or the preferred way to write bash recipes.

## Out of scope

- Making Ansible the default, recommended, or preferred way to write any
  recipe. Plain bash recipes remain the primary format.
- Retrofitting any existing bash recipe to Ansible.
- Remote/multi-host orchestration, inventories, or dynamic inventory —
  `docs/VISION.md` excludes remote orchestration from v1 regardless of this
  task's outcome; this is single-machine, local-connection use only
  (`ansible-playbook` against `localhost`/`connection: local`).
- Any change to the JSON contract's `schemaVersion` or existing fields —
  additive only.
- A general plugin system for "arbitrary alternative recipe engines" — scope
  this narrowly to Ansible, don't build an abstraction for hypothetical
  future engines that don't exist yet.

## Acceptance criteria

- [ ] `docs/VISION.md` conflict explicitly resolved (amended non-goal, or
      this task is closed instead of implemented)
- [ ] Ansible-backed recipes are discoverable and distinguishable from bash
      recipes in `core.py` without breaking existing bash-recipe discovery
- [ ] `check`/`apply`/`undo` for an Ansible-backed recipe produce the same
      normalized JSON shape as a bash recipe (frontend-neutral: no QML/CLI
      code needs to know which kind it's looking at)
- [ ] backup-before-modify and honest `undo` declarations still hold for the
      one example recipe
- [ ] one working example recipe added and passing `omarchy-recipes lint`/
      `validate`
- [ ] `docs/RECIPE_SPEC.md` and `skills/recipe-authoring/SKILL.md` document
      this as optional, not preferred
- [ ] `make test validate` (or `make check`) passes
- [ ] `./bin/omarchy-recipes validate` passes

## Testing notes

- Test `ansible-core` absent as well as present — the engine must fail
  clearly for an Ansible-backed recipe on a machine without it installed,
  not crash the whole recipe list.
- Confirm a bash-only machine (no Ansible recipes authored) sees zero
  behavior change.

## Report

<!-- Filled in by the agent when done. Move this file to docs/tasks/done/ and
set Status to Done when finished. -->
