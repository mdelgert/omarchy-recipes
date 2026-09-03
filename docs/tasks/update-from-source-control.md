# Task: Update from source control and reload, from inside omarchy-recipes

Status: Ready
Type: feature
Roadmap link: v0.2 — usable interaction (settings/config area)

## Goal

From the Settings view (or the CLI), a user can check whether a newer version
of omarchy-recipes is available from its source (git) and update to it, with
the running engine/plugin picking up the change without a manual
`git pull && make plugin` + shell restart dance.

## Context / current behavior

Today, picking up an update is entirely manual and documented only in
`README.md` (~lines 260-300):

- A plain checkout run as a CLI (`git clone` + run from the checkout, README
  ~line 262-267): updating means the user runs `git pull` themselves.
- A working-tree plugin install (`omarchy-plugin/install.sh`, i.e. `make
  plugin`): the script rsyncs the repo into
  `${XDG_CONFIG_HOME:-~/.config}/omarchy/plugins/io.github.mdelgert.omarchy-recipes`,
  validates the manifest and recipes, and — if a shell is running — calls
  `omarchy-shell shell rescanPlugins` to hot-reload it. README explicitly says
  "After a `git pull`, re-run `make plugin`" (~line 294) — i.e. today's reload
  path already exists, it's just two manual steps with no discoverability
  from inside the app.
- A plugin installed the normal way (`omarchy plugin add <git-url>`) is
  updated by Omarchy's own `omarchy plugin update <id>` (mentioned in
  `README.md` ~line 107) — that path is owned by Omarchy, not this project.
- `omarchy-plugin/SettingsView.qml` already has a `reload()` function (~line
  41) used after config changes; `RecipeEngine.qml`'s `reload()` (~line 223)
  is what re-lists recipes after a change. Neither currently triggers a
  source update — they only re-read what's already on disk.
- There is no version/commit-awareness anywhere in the engine today:
  `src/omarchy_recipes/__init__.py` has a static `__version__ = "0.1.0"`
  that nothing currently compares against a remote.

## Scope

1. Add a way for the engine to report what it's currently running from:
   detect whether the installed tree (or the CLI's own checkout) is a git
   working directory, and if so, its current commit/branch and whether the
   configured remote has newer commits (`git fetch` + compare, not a network
   call made implicitly on every command — only when the user asks).
2. Add an `omarchy-recipes update` CLI action (or extend an existing
   subcommand — `sources` and `config` both already exist as precedent for
   where engine-level, non-recipe operations live) that:
   - Reports "up to date" / "N commits behind" / "not a git checkout" without
     mutating anything (a `check`-style, read-only step).
   - On confirmation, runs `git pull` (argv, no `shell=True`) in the detected
     checkout.
   - If the current install is the working-tree plugin mirror
     (`omarchy-plugin/install.sh`'s destination), re-run the equivalent
     mirroring step and the existing `omarchy-shell shell rescanPlugins`
     reload call this script already makes, rather than duplicating that
     logic — call `install.sh` or refactor its reload step into something
     both can call.
3. Surface an "Update" action and current version/status in
   `omarchy-plugin/SettingsView.qml`, using the existing `reload()` pattern
   to refresh the recipe list afterward.
4. Handle the "not a git checkout" and "no remote reachable" cases with a
   clear message — this is not always available (e.g. a tarball install or a
   plugin installed via Omarchy's own `omarchy plugin add`, which is not this
   project's mirror path) and must fail clearly rather than silently no-op.

## Out of scope

- Anything for a plugin installed via `omarchy plugin add`/`omarchy plugin
  update` — that path is owned by Omarchy itself; don't duplicate or
  shadow it. This task only covers the working-tree/manual-checkout path
  this project's own `install.sh`/README already describe.
- Automatic/background update checking or a scheduler — user-initiated only,
  matching the project's non-goals in `docs/VISION.md` ("not a scheduler").
- Signing/verification of pulled commits — out of scope until the
  collections/trust work in `docs/VISION.md`'s "Later" section.
- Rewriting `install.sh`'s mirroring or reload logic beyond what's needed to
  share it with the new update path.

## Acceptance criteria

- [ ] engine can report git status (checkout detected, current ref, ahead/
      behind a remote) without mutating anything
- [ ] `omarchy-recipes update` (or equivalent) pulls and, for a working-tree
      plugin install, re-mirrors and triggers the existing shell reload
- [ ] `SettingsView.qml` surfaces version/update status and an update action,
      reusing the existing `reload()` pattern
- [ ] clear, non-crashing behavior when there's no git checkout or no
      reachable remote
- [ ] tests added for the git-status detection logic (mockable/fake git
      checkout, no real network access required in tests)
- [ ] `make test validate` (or `make check`) passes
- [ ] `./bin/omarchy-recipes validate` passes

## Testing notes

- Test against a throwaway local git checkout (with a local second clone as
  its "remote") rather than reaching the real GitHub repo, so tests stay
  offline and deterministic.
- Manually verify the full loop once: edit `omarchy-plugin/install.sh`'s
  destination tree via a local commit, run the new update path, confirm the
  shell picks up the change without a manual `omarchy-restart-shell`.

## Report

<!-- Filled in by the agent when done. Move this file to docs/tasks/done/ and
set Status to Done when finished. -->
