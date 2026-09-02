# Recipe Authoring Skill

Use this skill whenever creating or modifying an `omarchy-recipes` recipe,
whether a human is typing it or an agent is generating it from a request.

This file is the authoritative ruleset. An agent must read it before generating
a recipe, and the engine enforces the parts it can check
(`omarchy-recipes lint`).

## Goal

Produce Bash recipes that are predictable, inspectable, idempotent where practical, reversible by default, and safe for another person to run after reviewing the file.

## Generating a recipe from a natural-language request

Never go straight from a request to a running command. The recipe is the
durable artifact; the conversation is not. Work in this order:

1. **Understand the request.** Restate what will change, in one sentence, and
   what it will not touch.
2. **Inspect before deciding.** `omarchy-recipes inspect --json [domain ...]`
   reads keybindings, packages, services, ports, mounts, containers, and the
   environment. Use it instead of running your own shell commands: the engine
   is the only thing allowed to touch the system, and inspection is read-only
   by construction.
3. **Declare what you intend to touch and check for conflicts** before writing
   any Bash:

   ```bash
   echo '{"resources":[{"type":"keybinding","value":"SUPER + RETURN"}]}' \
     | omarchy-recipes conflicts --json
   ```

   Supported claims: `keybinding`, `file`, `package`, `service`, `port`,
   `mount`, `container`, `environment`, `config`, `recipe`.
4. **Stop when `requires_user_decision` is true.** Present the conflict and the
   offered `resolutions` and let the user choose. Never silently replace an
   existing binding, port, container, or file. A `status` of `unknown` means the
   check could not run — treat it as a conflict, not as permission.
5. **Check for an existing recipe** with a `{"type": "recipe", "keywords": [...]}`
   claim. Prefer running or improving what exists over adding a near-duplicate.
6. **Write the recipe** following the rules below.
7. **Lint it before it touches disk:** `omarchy-recipes lint --json < draft.sh`.
   Fix every error. Explain every remaining warning to the user.
8. **Show the generated Bash.** It is never hidden. The project's principle is
   AI-authorable, human-auditable.
9. **Save it** with `omarchy-recipes create <id> --json < draft.sh`. It lands in
   the user's local collection, marked as agent-generated. It does not become a
   bundled recipe, and it cannot take the id of one.
10. **Test it** with the normal runner: `check`, then `run`, then `undo`.

## Mandatory structure

1. Start with `#!/usr/bin/env bash`.
2. Use `set -Eeuo pipefail`.
3. Include required `@recipe.*` metadata.
4. Declare every UI/user input with `@param`.
5. Source `${OMARCHY_RECIPES_LIB:?}/recipe.sh` when helper functions are needed.
6. Implement the `check`, `apply`, and `undo` action protocol. If undo is declared `none`, implement `undo` by clearly reporting it is unsupported and returning non-zero.

## Safety rules

1. **Inspect before modification.** Determine current state before deciding what to change.
2. **Backup before modification.** If an existing user/system file will change, call `recipe_backup_file` before the first write.
3. **Track absence.** If a target file does not exist and the recipe will create it, call `recipe_mark_absent` first so undo can remove it.
4. **Restore exact prior state.** Do not undo by writing a guessed default when an exact backup can be restored.
5. **Preserve metadata.** Backup/restore should preserve permissions/ownership/timestamps where practical; use the provided helpers.
6. **Be idempotent.** Applying the same desired configuration twice should normally produce the same state without duplicate lines, duplicate services, duplicate keybindings, etc.
7. **Validate inputs.** Reject invalid choices, ranges, paths, hostnames, ports, etc. before making changes.
8. **Never eval user input.** Do not construct a shell command string from parameter values.
9. **Quote expansions.** Quote variable expansions unless word splitting is explicitly required and safe.
10. **Use least privilege.** Do not run the whole script under sudo merely because one command needs elevation. Elevate the smallest possible command.
11. **Do not silently destroy user customization.** Prefer targeted edits. Explain when replacing an entire managed file is intentional.
12. **Make `check` read-only.** `check` must not install packages, create directories, touch files, restart services, or otherwise mutate the machine. Frontends run it every time a recipe is selected.
13. **Report state from `check`.** End `check` with `recipe_state configured "<detail>"` or `recipe_state not-configured "<detail>"` so a UI shows a state instead of guessing from prose. Use `recipe_summary` from `apply` and `undo` to say what changed (`"300 → 600 seconds"`).
14. **Verify after change.** After `apply` and `undo`, verify the expected condition when practical.
15. **Fail clearly.** Use meaningful error messages and non-zero exit status.
16. **Avoid curl-pipe-shell.** Download artifacts explicitly, verify source/signature/checksum when available, then execute/install.
17. **Package installs are stateful.** Check whether the package was already present. Future undo must not uninstall something the recipe did not install.
18. **Services are stateful.** Preserve whether a service was enabled/running before the recipe changed it.
19. **Sensitive values.** Do not print secrets. Mark secret inputs as `type=secret`; the engine's complete secret-redaction support is future work, so avoid recipes requiring secrets until that work is complete.

## Provenance

Do not write `@recipe.generated-with-ai` or `@recipe.reviewed` into a draft. The
engine stamps both when the recipe is saved and ignores whatever the file
claims, because a recipe must not be able to assert that a human reviewed it.

Do not put any part of the conversation into the recipe. Metadata is a
description of the change, not a transcript.

## Metadata guidance

Prefer concise categories that remain useful as the collection grows: `System`, `Power`, `Applications`, `Development`, `Networking`, `Storage`, `Security`, `Omarchy`, `Desktop`.

Set risk honestly:

- `low`: local user config, easy exact restore
- `medium`: package/service/network changes, or privileged but bounded configuration
- `high`: boot/security/storage/destructive changes or changes with significant lockout potential

Set undo honestly:

- `restore`: exact state can be restored from captured backup/state
- `command`: inverse operation is explicit and safe
- `none`: automatic reversal is not reliable

## Preferred flow

```bash
apply() {
  validate_inputs
  inspect_current_state
  if already_desired; then
    recipe_summary "Already configured"
    recipe_note "Already configured"
    return 0
  fi
  recipe_backup_file "$target"
  make_atomic_change
  verify_desired_state
}
```

For a newly created file:

```bash
if [[ -e "$target" || -L "$target" ]]; then
  recipe_backup_file "$target"
else
  recipe_mark_absent "$target"
fi
```

Undo:

```bash
undo() {
  recipe_restore_file "$target"
  verify_prior_or_valid_state
}
```

## AI review checklist

Before finishing a generated recipe, answer internally:

- What exact resources does this modify?
- What happens if it runs twice?
- What happens if it fails halfway?
- Is every existing file backed up before mutation?
- If a resource was absent beforehand, is that captured?
- Does undo restore what was there, not what I assume was there?
- Can any parameter become shell syntax?
- Is sudo scope minimal?
- Is `check` truly read-only, and does it report a state?
- Will stdout/stderr help a human debug failure?
