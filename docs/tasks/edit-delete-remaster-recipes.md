# Task: Edit, delete, and remaster (fork) recipes

Status: Ready
Type: feature
Roadmap link: v0.2 → local recipe workspace; "remix of recipes" idea in
`docs/dev/NEW_FEATURES.md`

## Goal

A user (or the authoring agent, through the plugin) can:

1. **Edit** a recipe they own (a `local` recipe) and re-save it through the
   same validation path as authoring a new one.
2. **Delete** a `local` recipe, reversibly — deleting a recipe file is itself
   a mutation this project's own principles apply to, not a special case
   exempt from backup/undo.
3. **Remaster** (fork) any recipe — bundled, community, or local — into an
   editable copy in the `local` tier under a new id, so the user can
   customize a recipe they didn't author without touching the original.

Today `create --overwrite` (`authoring.save()`, `src/omarchy_recipes/
authoring.py:78`) can already blindly overwrite a `local` recipe body, but
there is no way to *read back* a recipe's current source to edit it, no
delete, and no fork/copy path. `docs/RECIPE_SPEC.md`'s trust model
(`src/omarchy_recipes/sources.py`) says only the `local` tier is writable —
this task must not weaken that: bundled and community recipes stay read-only
originals; "editing" one always means forking it into `local` first.

## Scope

### Edit

- `omarchy-recipes edit <recipe-id> --json` — refuse unless the recipe's
  `source == "local"` (per `sources.py`); print a clear error pointing at
  `remaster` for anything else.
- Add a way to read a local recipe's current body (e.g.
  `omarchy-recipes show <recipe-id> --raw` or extend `info`) so the plugin's
  Create/edit UI can pre-populate the editor instead of starting blank.
- Re-saving goes through the existing `authoring.save(..., overwrite=True)`
  path — same lint gate, same provenance stamping rules. Do not add a second
  way to write a recipe file to disk.

### Delete

- `omarchy-recipes delete <recipe-id> --json`, restricted to `source ==
  "local"` — bundled recipes cannot be deleted this way (they aren't files
  the user owns), and community recipes are out of scope for this task (see
  Out of scope).
- Reversible: move the file into a dated archive directory under the
  workspace (e.g. `~/.config/omarchy-recipes/trash/<id>-<timestamp>.sh`)
  rather than unlinking it, and record the operation so `undo` (or a new
  `restore-recipe` command — pick one and document why) can bring it back.
  Follow the existing `recipe_backup_file` pattern's spirit even though this
  isn't a recipe execution.
- A recipe with run history should still delete cleanly; deleting the recipe
  file must not corrupt `history`/`log` for past runs of that id.

### Remaster (fork)

- `omarchy-recipes remaster <source-id> <new-id> --json` — reads the source
  recipe's body from whichever tier it's actually in (bundled, community, or
  local), strips provenance the same way `authoring._strip_provenance` does
  for agent drafts, and saves it to `local` under `<new-id>` via
  `authoring.save()`. Refuse if `<new-id>` collides with a `bundled` id (same
  rule `sources.py` already documents for shadowing).
- The forked copy is clearly marked as derived: e.g. a `@recipe.forked-from
  <source-id>` marker (new metadata field — add it to `docs/RECIPE_SPEC.md`
  and strip/re-stamp it the same way `generated-with-ai`/`reviewed` are
  handled, so a fork can't fake a different lineage).
- Forking does not require the agent — a person should be able to fork a
  recipe to hand-edit it without going through `agent plan`/`agent draft`.

### Plugin (minimal)

- `RecipeDetail.qml` gains "Edit" (only for `local` recipes) and "Remaster"
  actions; "Edit" opens the existing Create/authoring view pre-populated with
  the current body instead of a blank prompt. A dedicated delete
  confirmation dialog, reusing `ConfirmDialog`, warns that this removes the
  recipe (mention it's recoverable if you kept the archive-not-unlink
  behavior above).

## Out of scope

- Deleting or editing `community` recipes in place (only remastering them
  into `local` is in scope; managing the community collection itself is a
  separate, later feature — see the "Git-backed recipe collections/sources"
  roadmap item).
- Any diffing/merge UI between the original and a remastered fork.
- Automatic permanent purge of the trash/archive directory (a manual `omarchy-
  recipes trash empty` command is fine to add later, not required here).
- Changing `check`/`apply`/`undo` semantics for the recipe's own execution
  protocol — this task is entirely about managing recipe *files*, not what
  they do when run.

## Acceptance criteria

- [ ] `edit`, `delete`, and `remaster` CLI subcommands implemented, each
      restricted to the correct source tier as described above.
- [ ] Delete is reversible (archived, not unlinked) and documented as such.
- [ ] Remaster strips and re-stamps provenance; a new `@recipe.forked-from`
      marker is added to `docs/RECIPE_SPEC.md` and handled the same way as
      the existing provenance markers (never trusted from the file itself).
- [ ] Attempting to edit/delete a non-local recipe fails with a clear error,
      not a silent no-op or a write to the wrong tier.
- [ ] Attempting to remaster into an id a bundled recipe already owns is
      refused.
- [ ] Engine tests cover: edit round-trip, delete-then-list (recipe gone),
      delete-then-restore (recipe back), remaster from each of the three
      tiers, and the two collision/permission refusals above.
- [ ] `make check` / `make validate` passes.
- [ ] `docs/RECIPE_SPEC.md` and `docs/ARCHITECTURE.md` updated for the new
      metadata marker and CLI surface.

## Testing notes

```bash
omarchy-recipes remaster example-numeric-setting my-numeric-setting --json
omarchy-recipes edit my-numeric-setting --json   # should succeed
omarchy-recipes edit example-numeric-setting     # should refuse (bundled)
omarchy-recipes delete my-numeric-setting --json
omarchy-recipes list --json                      # confirm it's gone
# confirm the archived file exists and can be restored, per whatever
# restore command this task settles on
```

## Report

(fill in when done)
