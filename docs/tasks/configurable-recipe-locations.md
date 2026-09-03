# Task: Configurable recipe locations (current locations stay the default)

Status: Ready
Type: feature
Roadmap link: v0.3 — real recipe library (a step toward "Later: Git-backed
recipe collections/sources", without implementing git fetching)

## Goal

A user can add one or more extra filesystem directories the engine discovers
recipes from — e.g. a synced folder, a mounted drive, a checkout of someone
else's collection — without setting an environment variable every session.
Nobody who does nothing has any change in behavior: discovery still finds
exactly the bundled, local, and community locations it finds today, in the
same order, with the same trust levels.

## Context / current behavior

- `src/omarchy_recipes/sources.py` hardcodes discovery to three fixed
  locations (docstring lines ~9-16, `sources()` ~lines 76-83):
  `<engine root>/recipes` (`bundled`), and under
  `${XDG_CONFIG_HOME:-~/.config}/omarchy-recipes/recipes/`: `local/` and
  `community/`. `workspace_root()` (~line 70) can only be relocated wholesale
  via the `OMARCHY_RECIPES_HOME` environment variable — there is no way to
  add a location, only to move the whole workspace.
- `SOURCE_ORDER`, `SOURCE_LABELS`, and `SOURCE_REVIEWED_UPSTREAM` (top of
  `sources.py`) define trust tiers `bundled` > `local` > `community`;
  discovery in `core.py` walks them in that order so a lower tier can never
  steal an id a higher tier already claimed.
- `src/omarchy_recipes/config.py` already has exactly the right shape for
  this: a JSON file at `workspace_root()/config.json`, a schema of known
  dotted keys, `load`/`save`/`get`/`set_value`, all validating before
  writing. Today it only knows about `agent.provider` and
  `agent.models.<provider>`.
- `omarchy-recipes sources` (`cli.py` ~line 289) already lists configured
  sources and their trust level, read-only. `omarchy-recipes config
  get/set/show` (`cli.py` ~lines 158-168) already exists for the agent
  settings.
- `docs/VISION.md`'s "Later" section anticipates
  `omarchy-recipes source add <git-url>` for git-backed collections — this
  task is deliberately smaller: local filesystem paths only, no fetching, no
  manifests, no signing.

## Scope

1. Extend the config schema (`config.py`) with a new key, e.g.
   `recipes.extra_paths`: a list of absolute directory paths. Default: empty
   list, so a machine with no config file behaves exactly as it does today.
2. Add a lowest-trust tier after `community` (e.g. `external`) to
   `SOURCE_ORDER`/`SOURCE_LABELS`/`SOURCE_REVIEWED_UPSTREAM` in `sources.py`
   for these configured paths, so id-collision rules in `core.py` keep
   working unchanged: bundled and local and community ids always win over
   an externally-configured path.
3. Update `sources(engine_root)` to append one `Source` per configured extra
   path, each with a distinct, stable `name` (paths can collide in basename,
   so don't assume uniqueness) so the JSON discovery output stays consistent
   run to run.
4. Validate each configured path when added: must be an absolute path. Do
   not require it to exist yet (matches the existing "browsing must not
   create directories, `exists` is just a reported field" behavior already
   visible in `Source.to_dict()`), and do not follow the "don't create
   directories during discovery" rule for these either.
5. Add `add` / `remove` subcommands under the existing `omarchy-recipes
   sources` CLI command (`cli.py` ~line 105/289) to manage
   `recipes.extra_paths` (list, add one, remove one), reusing
   `config.py`'s load/save rather than inventing a second config path. Keep
   the existing plain `omarchy-recipes sources` (no subcommand) behavior as
   the "list" case.
6. Update `sources.py`'s module docstring and `docs/ARCHITECTURE.md`'s
   sources/trust description (and `docs/RECIPE_SPEC.md` if it references
   source layout) to describe the new configurable tier.
7. Add tests (likely alongside existing config/sources coverage — check
   `tests/test_authoring.py` and wherever `config.py` is already tested) for:
   default behavior unchanged with no config, an added path appearing in
   `sources()` output at the new trust tier, id collision still resolved in
   favor of higher tiers, and rejection of a non-absolute path.

## Out of scope

- Fetching/cloning git-backed collections (`source add <git-url>`),
  collection manifests, or any signing/trust upgrade — these remain the
  `docs/VISION.md` "Later" ecosystem items, explicitly deferred.
- Changing what `OMARCHY_RECIPES_HOME` does or how the workspace root itself
  is chosen — this task only adds *extra* discovery locations alongside it.
- Any change to recipe execution, undo, or the run/history model.
- QML/GUI changes — this is a CLI + engine feature; a future task can expose
  it in the frontend if wanted.

## Acceptance criteria

- [ ] `recipes.extra_paths` config key added, default empty, documented in
      `config.py`'s `KNOWN_KEYS`/docstring
- [ ] discovery behavior is byte-for-byte unchanged when no extra paths are
      configured
- [ ] a configured extra path is discovered at a new, clearly lower-trust
      tier than `bundled`/`local`/`community`
- [ ] `omarchy-recipes sources add|remove|list` (or equivalent) manages the
      setting; a non-absolute path is rejected before anything is written
- [ ] `docs/ARCHITECTURE.md` (and `sources.py` docstring) updated to describe
      the configurable tier
- [ ] tests added/updated covering default-unchanged, added-path-discovered,
      collision-precedence, and invalid-path-rejected
- [ ] `make test validate` (or `make check`) passes
- [ ] `./bin/omarchy-recipes validate` passes

## Testing notes

- Use `OMARCHY_RECIPES_HOME` (as existing tests already do) to point at a
  throwaway workspace so tests never touch the developer's real config or
  recipes.
- Manually run `omarchy-recipes sources` before and after adding a path and
  confirm the new entry's trust label is honest about being
  externally-configured and unreviewed.

## Report

<!-- Filled in by the agent when done. Move this file to docs/tasks/done/ and
set Status to Done when finished. -->
