# Task: Recipe icons (Nerd Font glyphs) shown in the UI

Status: Done
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

- [x] `@recipe.icon` parses in `src/omarchy_recipes/core.py` and appears in
      normalized JSON output
- [x] category-based fallback glyph applied when `@recipe.icon` is absent
- [x] `docs/RECIPE_SPEC.md` documents the field, its convention, and the
      category defaults
- [x] `omarchy-recipes lint` warns on missing icon, errors on a malformed one
- [x] `skills/recipe-authoring/SKILL.md` updated
- [x] `omarchy-plugin/Menu.qml` and `omarchy-plugin/RecipeDetail.qml` render
      the icon/fallback next to the recipe title
- [x] tests added/updated for parsing, fallback, and lint behavior
- [x] `make test validate` (or `make check`) passes
- [x] `./bin/omarchy-recipes validate` passes on the existing recipe library
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

Implemented. `@recipe.icon` parses, the engine resolves a category fallback so
nothing renders blank, lint warns on absence and errors on a malformed value,
and both the browse list and the detail header draw the glyph.

### The verification step was the whole job

`docs/OMARCHY_PLUGIN.md` warns that plausible codepoints render blank, and it is
right: of the candidates picked by icon name, **`f5fc` ("apps") and `f6ff`
("network-wired") draw nothing**. Both were in the first draft of the category
table. They were replaced with `f009` and `f0e8`, confirmed by rendering.

Verifying it was itself error-prone, in a way worth recording. Two intermediate
render passes reported *every* glyph blank, including ones already known good —
false negatives caused by literal private-use-area characters being stripped on
their way into the command, not by the codepoints. The reliable method generates
the label file from codepoints and checks the bytes landed:

```bash
python3 -c 'print(f"{0xf085:04x} {chr(0xf085)}")' > labels.txt
od -c labels.txt | head -2          # confirm 357 202 205 is present
magick -font .../JetBrainsMonoNerdFont-Regular.ttf -pointsize 40 label:@labels.txt out.png
```

That is the same fragility the field convention exists for, met three times
while building it: literal glyphs pasted into the code, the tests, and the docs
all failed to survive a round-trip — once landing as a NUL byte that made the
test file unparsable. Everything therefore stores `\uXXXX` escapes, including
the engine's own table and the docs' copyable examples. Only the rendered
reference table in `RECIPE_SPEC.md` holds literal glyphs, because there the
point is to show them.

### Decisions

- **Escape, not literal.** `@recipe.icon \uf085`. A pasted single character is
  accepted, but the escape is documented, for the reason above.
- **Fallback in the engine, not the frontend.** `icon` in `--json` is always a
  single character, so no client carries its own table or decides what a missing
  icon looks like. `RecipeModel.js` only forwards it.
- **Malformed is a parse error, not a lint-only warning.** It is refused the same
  way an invalid `privilege` is; an icon that silently renders as a blank gap is
  worse than a refusal, because the recipe looks broken and nothing says why.
- **A valueless `# @recipe.icon` line is its own error.** The metadata regex
  requires a value, so such a line is invisible to the parser; reporting it as
  merely "absent" would leave the author staring at a line that is right there.

### Verified

- 134 engine tests + 33 QML tests; `validate` passes on all 9 recipes, none of
  which declared an icon before this change.
- Rendered in the running plugin: category fallbacks (grid, monitor, bug,
  lightbulb) and a declared glyph (`\uf186`, moon) on `omarchy-idle-timeouts`,
  which is the smoke test the scope allowed for.
- No new kinds of qmllint warning.

### Unrelated finding

The shell crashed (SIGSEGV) during a restart while this was being verified. It
is not from this work: the crashing frame is `QQmlComponent::createObject()`
reached from `/usr/share/omarchy/shell/shell.qml:300`, the shell's own *service*
plugin loader; this plugin is `menu`-kind and contains no `createObject` call at
all. `coredumpctl` shows the same crash at 14:23, when this plugin was not
installed on the machine (first install 17:50). Pre-existing and upstream, not
reported anywhere yet.
