# Task: Recipe icons (Nerd Font glyphs) shown in the UI

Status: Ready
Type: feature
Roadmap link: v0.2 — usable interaction

## Goal

A recipe can declare an icon (a Nerd Font glyph, matching the convention
already used for the plugin's own bar icon) that both the QML frontend and
any other frontend can show next to its title in a list or detail view —
without any per-recipe UI code. Recipes that don't declare one still render
sensibly with a category-based fallback glyph.

## Context / current behavior

- `docs/dev/NEW_FEATURES.md` has an unscoped note: "Add icons to recipes."
- `docs/OMARCHY_PLUGIN.md` (the bar icon section, ~line 169) already
  documents drawing a Nerd Font glyph via a `Text`-style element in QML and
  warns that "several plausible-looking codepoints in JetBrainsMono Nerd Font
  render as blank" — whatever this task picks must be verified the same way.
- `recipes/community/error-log-report.sh` already writes an `"icon":""`
  key into Omarchy's own menu JSON when it installs a menu entry — i.e. the
  *host* Omarchy menu already has an icon concept; recipes themselves don't
  yet have one that the recipe engine understands.
- Recipe metadata parsing lives in `src/omarchy_recipes/core.py`: the
  `Recipe` dataclass (~line 78) and the known-metadata-key list plus the
  required-keys check (~lines 193, 216-217, 233-243). There is no `icon`
  field today.
- `docs/RECIPE_SPEC.md` lists required and recommended metadata; there is no
  icon entry.
- QML rendering of recipe lists/details lives in `omarchy-plugin/Menu.qml`
  and `omarchy-plugin/RecipeDetail.qml`; neither reads an icon field today
  because the engine doesn't emit one.

## Scope

1. Add `@recipe.icon` as a **recommended** (not required) metadata key:
   - A single Nerd Font glyph character (or its codepoint, author's choice —
     pick one convention and document it, matching how `BarWidget.qml`
     specifies its glyph).
   - Parse it in `src/omarchy_recipes/core.py`: add to the known-keys list,
     add a field on `Recipe`, include it in normalized JSON output.
   - When absent, the engine supplies (or the frontend falls back to) a
     sensible default glyph keyed by `category` (reuse the existing category
     list: `System`, `Power`, `Applications`, `Development`, `Networking`,
     `Storage`, `Security`, `Omarchy`, `Desktop`, `Diagnostics`) rather than
     leaving every un-iconed recipe blank. Decide and document whether this
     default lookup lives in the engine (so all frontends get it for free) or
     the frontend — prefer the engine, per the project's "frontends consume
     normalized output" constraint.
2. Document the new field in `docs/RECIPE_SPEC.md`'s metadata section, with
   the glyph-vs-codepoint convention and a short list of category defaults.
3. Add lint guidance (`omarchy-recipes lint`) that **warns** (does not error)
   when `@recipe.icon` is missing, and errors if present but empty/not a
   single glyph, so existing recipes aren't broken by this addition.
4. Update `skills/recipe-authoring/SKILL.md` metadata guidance to mention
   choosing an icon and to reuse the same "verify it actually renders, don't
   guess a codepoint" caution already written for the bar icon in
   `docs/OMARCHY_PLUGIN.md`.
5. Update `omarchy-plugin/Menu.qml` and `omarchy-plugin/RecipeDetail.qml` to
   render the recipe's icon (falling back to the category default) next to
   its title, following the existing `BarWidget.qml` approach for drawing a
   glyph. This must be additive to existing layout, not a redesign.
6. Add/adjust parser tests (`tests/test_core.py` or
   `tests/test_engine_api.py`, whichever already covers metadata parsing) for:
   the new field parsing correctly, the missing-icon fallback default, and
   the lint warning/error behavior.

## Out of scope

- Retrofitting every existing recipe in `recipes/examples/` and
  `recipes/community/` with a hand-picked icon — a follow-up task can do a
  pass once this lands. (It's fine to add one to a recipe or two as a smoke
  test if convenient, but it's not required here.)
- Non-Nerd-Font icon formats (SVG/PNG assets, icon packs, emoji-only mode) —
  out of scope for v1; the Vision doc's generated-controls model stays
  text/glyph based for now.
- Any change to the bar icon itself (`BarWidget.qml` stays as-is).
- New `@param` types or engine action verbs — this is metadata + rendering
  only.

## Acceptance criteria

- [ ] `@recipe.icon` parses in `src/omarchy_recipes/core.py` and appears in
      normalized JSON output
- [ ] category-based fallback glyph applied when `@recipe.icon` is absent
- [ ] `docs/RECIPE_SPEC.md` documents the field, its convention, and the
      category defaults
- [ ] `omarchy-recipes lint` warns on missing icon, errors on a malformed one
- [ ] `skills/recipe-authoring/SKILL.md` updated
- [ ] `omarchy-plugin/Menu.qml` and `omarchy-plugin/RecipeDetail.qml` render
      the icon/fallback next to the recipe title
- [ ] tests added/updated for parsing, fallback, and lint behavior
- [ ] `make test validate` (or `make check`) passes
- [ ] `./bin/omarchy-recipes validate` passes on the existing recipe library
      (i.e. adding this field doesn't break recipes that predate it)

## Testing notes

- Verify chosen glyphs actually render in JetBrainsMono Nerd Font before
  picking category defaults — `docs/OMARCHY_PLUGIN.md` already flags that
  some plausible codepoints render blank; reuse whatever verification method
  it describes (e.g. rendering to an image with `magick`/`convert` as noted
  there) rather than trusting a codepoint by inspection.
- Confirm an existing recipe with no `@recipe.icon` still lints/validates
  (warning only, not a failure) and still renders (fallback glyph, not blank).

## Report

<!-- Filled in by the agent when done. Move this file to docs/tasks/done/ and
set Status to Done when finished. -->
