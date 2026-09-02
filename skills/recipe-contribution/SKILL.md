# Recipe Contribution Skill

Use this skill when offering a locally authored recipe to the canonical
collection at `mdelgert/omarchy-recipes`.

A contribution is a pull request a human will read. It is never a direct write
to the maintainer's `main` branch, and it is never something to complete on the
user's behalf without showing them what will be sent.

## Before proposing a contribution

Work through these in order and stop at the first one that fails.

1. **Validate.** `omarchy-recipes lint --json <path>` must report `ok: true`.
   Lint errors are not negotiable; they are the reason the recipe would be
   rejected anyway.
2. **Verify the metadata.** Id, title, description, and category must be
   present and accurate. The description should say what the recipe changes,
   not what it is called.
3. **Verify backup and undo.** A recipe that writes files must call
   `recipe_backup_file` or `recipe_mark_absent` first, and its `@recipe.undo`
   declaration must match what `undo)` actually does. `undo: none` on a recipe
   that could restore state is a bug, not a shortcut.
4. **Check naming.** The id is lowercase, hyphenated, and describes the change
   (`configure-screen-timeout`, not `my-recipe-2`). Ids are stable once
   published; picking a vague one now costs someone else later.
5. **Look for an existing equivalent.**
   `omarchy-recipes conflicts` with a `{"type": "recipe", "keywords": [...]}`
   claim, or read `omarchy-recipes list --json`. If something close exists,
   prefer improving it or adding a parameter to it over adding a second recipe
   that does the same job. Ask the user which they want.
6. **Test it.** Apply and undo the recipe on the machine, and record what you
   did — it goes in the pull request body. `make test` must still pass.
7. **Add tests when the recipe changes engine behavior.** A recipe on its own
   usually needs none; a new parameter type or protocol change does.
8. **Update documentation** if the contribution changes a documented contract.

## Preparing the pull request

```bash
omarchy-recipes contribute <recipe-id> --testing "what you did" --json
```

This is a dry run by default. It reports the branch it would create, the files
it would add, any duplicates it found, and the full pull request body. Show that
to the user before going further.

Then, only with the user's agreement:

```bash
omarchy-recipes contribute <recipe-id> --testing "..." --commit   # branch + commit
omarchy-recipes contribute <recipe-id> --testing "..." --push     # and open the PR
```

## Rules

- **Never push to `main` or `master`.** The engine refuses, and so should you.
- **One recipe per pull request.** A reviewer should be able to accept or reject
  a single, complete change.
- **Never include the conversation.** The recipe and its metadata are the
  artifact. Chat transcripts, prompts, and reasoning do not belong in the
  repository.
- **Never include secrets.** Not in the recipe, not in the PR body, not in the
  test notes.
- **Say plainly that AI was involved.** The pull request template has a field
  for it. A reviewer weighing an AI-authored recipe deserves to know which parts
  a human actually ran.
- **A fork is required when the contributor lacks write access.** Use
  `gh repo fork --remote` and push the branch there; the pull request still
  targets the canonical repository.

## Pull request body

`omarchy-recipes contribute` generates the body from the recipe's own metadata,
following the template in `docs/milestones/MILESTONE-2-SPEC.md`: recipe,
purpose, changes, backup, undo, compatibility, testing, conflicts, and whether
AI generated it. Fill in the testing section with what was actually run — an
empty or invented testing section is worse than none.
