import QtQuick
import QtTest
import "../../omarchy-plugin/RecipeModel.js" as Model

// Unit tests for the plugin's presentation logic. RecipeModel.js is a pure
// library with no Omarchy or Quickshell dependencies precisely so this can run
// anywhere qmltestrunner does — no shell, and nothing executed.
//
//   make test-qml
TestCase {
  name: "RecipeModel"

  readonly property var recipes: [
    { id: "b-two", title: "Second thing", description: "does two", category: "Alpha", tags: ["net"], undo: "restore" },
    { id: "a-one", title: "First thing", description: "does one", category: "Alpha", tags: [], undo: "none" },
    { id: "c-three", title: "Third thing", description: "does three", category: "Beta", tags: ["disk"], undo: "command" }
  ]

  function test_rows_group_by_category_in_engine_order() {
    var rows = Model.rowsFor(recipes, "")
    compare(rows.length, 5)
    compare(rows[0].kind, "header")
    compare(rows[0].label, "Alpha")
    compare(rows[1].label, "Second thing")
    compare(rows[2].label, "First thing")
    compare(rows[3].kind, "header")
    compare(rows[3].label, "Beta")
    compare(rows[4].recipeId, "c-three")
  }

  function test_every_row_carries_the_same_keys() {
    // The delegate binds `detail` on every row; a header missing it would
    // assign undefined to a typed property.
    var rows = Model.rowsFor(recipes, "")
    for (var i = 0; i < rows.length; i++) {
      verify(rows[i].detail !== undefined, "row " + i + " has no detail")
      verify(rows[i].recipeId !== undefined, "row " + i + " has no recipeId")
    }
  }

  function test_filter_matches_across_fields_and_terms() {
    compare(Model.filterRecipes(recipes, "third").length, 1)
    compare(Model.filterRecipes(recipes, "ALPHA").length, 2)      // category, case-insensitive
    compare(Model.filterRecipes(recipes, "disk").length, 1)       // tag
    compare(Model.filterRecipes(recipes, "does one").length, 1)   // all terms must match
    compare(Model.filterRecipes(recipes, "does zebra").length, 0)
    compare(Model.filterRecipes(recipes, "").length, 3)
  }

  function test_filtered_rows_drop_empty_categories() {
    var rows = Model.rowsFor(recipes, "third")
    compare(rows.length, 2)
    compare(rows[0].label, "Beta")
  }

  function test_cursor_skips_category_headers() {
    var rows = Model.rowsFor(recipes, "")
    compare(Model.firstSelectableRow(rows), 1)
    compare(Model.nextSelectableRow(rows, 1, 1), 2)
    compare(Model.nextSelectableRow(rows, 2, 1), 4)   // jumps the Beta header
    compare(Model.nextSelectableRow(rows, 4, 1), 4)   // clamps at the end
    compare(Model.nextSelectableRow(rows, 1, -1), 1)  // clamps at the start
  }

  function test_control_is_chosen_from_the_declared_type() {
    compare(Model.controlFor({ type: "string" }), "text")
    compare(Model.controlFor({ type: "integer" }), "number")
    compare(Model.controlFor({ type: "boolean" }), "toggle")
    compare(Model.controlFor({ type: "choice" }), "choice")
    compare(Model.controlFor({ type: "path" }), "path")
    compare(Model.controlFor({ type: "secret" }), "secret")
    // A type from a newer engine still renders rather than vanishing.
    compare(Model.controlFor({ type: "multichoice" }), "text")
    compare(Model.controlFor(null), "text")
  }

  readonly property var parameters: [
    { name: "timeout", type: "integer", required: true, default: 600 },
    { name: "mode", type: "choice", required: true, default: "balanced", choices: ["a", "b"] },
    { name: "enabled", type: "boolean", default: true },
    { name: "note", type: "string" },
    { name: "directory", type: "path", required: true, label: "Demo directory" }
  ]

  function test_default_values_come_from_metadata() {
    var values = Model.defaultValues(parameters)
    compare(values.timeout, 600)
    compare(values.mode, "balanced")
    compare(values.enabled, true)
    compare(values.note, "")
    compare(values.directory, "")
  }

  function test_argv_is_a_flat_name_value_list() {
    var argv = Model.argvFor(parameters, {
      timeout: 900, mode: "b", enabled: false, note: "", directory: "/tmp/x"
    })
    compare(argv, ["--timeout", "900", "--mode", "b", "--enabled", "false", "--directory", "/tmp/x"])
  }

  function test_argv_never_splices_a_value_into_one_token() {
    // A value that looks like shell syntax stays exactly one argv entry.
    var argv = Model.argvFor([{ name: "note", type: "string" }], { note: "a; rm -rf ~ && echo $HOME" })
    compare(argv.length, 2)
    compare(argv[0], "--note")
    compare(argv[1], "a; rm -rf ~ && echo $HOME")
  }

  function test_missing_required_lists_only_empty_required_fields() {
    // Reported by the label the engine normalized, falling back to the name.
    compare(Model.missingRequired(parameters, Model.defaultValues(parameters)), ["Demo directory"])
    compare(Model.parameterLabel({ name: "timeout", label: "Screen timeout" }), "Screen timeout")
    compare(Model.parameterLabel({ name: "timeout" }), "timeout")
    var filled = Model.defaultValues(parameters)
    filled.directory = "/tmp/x"
    compare(Model.missingRequired(parameters, filled).length, 0)
  }

  function test_engine_responses_are_version_checked() {
    var ok = Model.parseResponse('{"schemaVersion": 1, "recipes": []}', 1)
    verify(ok.ok)

    var future = Model.parseResponse('{"schemaVersion": 99}', 1)
    verify(!future.ok)
    verify(future.error.indexOf("update the plugin") !== -1)

    verify(!Model.parseResponse("not json at all", 1).ok)
    verify(!Model.parseResponse("", 1).ok)

    var failed = Model.parseResponse('{"schemaVersion": 1, "error": "recipe not found"}', 1)
    verify(!failed.ok)
    compare(failed.error, "recipe not found")
  }

  function test_origin_badges_distinguish_generated_recipes() {
    // A bundled recipe is the baseline and carries no badge; badging
    // everything would make the marker invisible.
    compare(Model.sourceBadge({ source: "bundled" }), "")
    compare(Model.sourceBadge({ source: "local", authoring: { generated_with_ai: true } }), "local · ai")
    compare(Model.sourceBadge({ source: "local", authoring: { generated_with_ai: false } }), "local")
    compare(Model.sourceBadge({ source: "community" }), "community")
  }

  function test_source_label_states_review_status() {
    compare(Model.sourceLabel({ source_label: "Shipped with omarchy-recipes" }),
            "Shipped with omarchy-recipes")
    compare(Model.sourceLabel({ source_label: "Created on this machine",
                                authoring: { generated_with_ai: true, reviewed: false } }),
            "Created on this machine · AI-generated, not reviewed")
    compare(Model.sourceLabel({ source_label: "Created on this machine",
                                authoring: { generated_with_ai: true, reviewed: true } }),
            "Created on this machine · AI-generated, reviewed")
  }

  function test_rows_carry_the_origin_badge() {
    var rows = Model.rowsFor([{ id: "a", title: "A", description: "", category: "X",
                                source: "local", authoring: { generated_with_ai: true } }], "")
    compare(rows[1].badge, "local · ai")
  }

  function test_state_presentation() {
    compare(Model.stateLabel("not-configured"), "Not configured")
    compare(Model.stateLabel("configured"), "Configured")
    compare(Model.stateLabel("anything-else"), "Unknown")
    compare(Model.stateGlyph("configured"), "✓")
  }

  function test_reversibility_is_read_from_the_declaration() {
    var restore = Model.reversibilityLines({ undo: "restore" }, { undo_supported: true, undo_available: true })
    compare(restore.length, 2)
    verify(restore[0].ok)

    var none = Model.reversibilityLines({ undo: "none" }, { undo_supported: false, undo_available: false })
    compare(none.length, 1)
    verify(!none[0].ok)

    var nothingYet = Model.reversibilityLines({ undo: "restore" }, { undo_supported: true, undo_available: false })
    compare(nothingYet.length, 3)
    verify(!nothingYet[2].ok)
  }

  function test_history_rows_are_trimmed_for_display() {
    var runs = [
      { started_at: "2026-09-01T16:05:00+00:00", action: "apply", status: "success", summary: "300 → 600", run_id: "r1", undone: true },
      { started_at: "2026-08-28T19:12:00+00:00", action: "undo", status: "failed", summary: "", run_id: "r2" }
    ]
    var rows = Model.historyRows(runs, 10)
    compare(rows.length, 2)
    compare(rows[0].action, "apply")
    verify(rows[0].undone)
    verify(rows[0].when.length > 0)
    compare(rows[1].undone, false)
    compare(Model.historyRows(runs, 1).length, 1)
  }

  function test_untrusted_output_is_reduced_to_one_short_line() {
    var text = Model.firstLine("\n\n  error: something went wrong  \nmore detail\n", 160)
    compare(text, "error: something went wrong")
    compare(Model.truncate("abcdefghij", 5), "abcd…")
  }

  function test_plugin_directory_resolution() {
    compare(Model.pathFromUrl("file:///home/u/.config/omarchy/plugins/x/"), "/home/u/.config/omarchy/plugins/x")
    compare(Model.pathFromUrl("file:///home/u/a%20b"), "/home/u/a b")
    compare(Model.pathFromUrl("qrc:/nope"), "")
    compare(Model.parentDir("/home/u/plugins/x"), "/home/u/plugins")
  }

  function test_agent_summary_names_the_resolved_provider() {
    compare(Model.agentSummary("copilot", ""), "copilot")
    compare(Model.agentSummary("claude", "claude-sonnet-4.5"), "claude (claude-sonnet-4.5)")
  }

  readonly property var modelsByProvider: ({
    claude: ["opus", "sonnet"],
    copilot: ["auto", "gpt-5.4"]
  })

  function test_model_options_offer_the_providers_shortlist() {
    var opts = Model.modelOptions(modelsByProvider, "claude", "")
    compare(opts[0], Model.modelDefaultLabel())
    compare(opts[1], "opus")
    compare(opts[2], "sonnet")
    compare(opts.length, 3)
  }

  function test_model_options_keep_a_value_the_shortlist_lacks() {
    // The shortlist cannot be complete, so a configured model the engine has
    // never heard of must survive rather than vanish from the picker.
    var opts = Model.modelOptions(modelsByProvider, "claude", "some-future-model")
    compare(opts.indexOf("some-future-model") >= 0, true)
    compare(opts.length, 4)
  }

  function test_model_options_do_not_duplicate_a_known_value() {
    var opts = Model.modelOptions(modelsByProvider, "claude", "opus")
    compare(opts.length, 3)
  }

  function test_model_options_tolerate_an_unknown_provider() {
    compare(Model.modelOptions(modelsByProvider, "nope", ""), [Model.modelDefaultLabel()])
    compare(Model.modelOptions(null, "claude", ""), [Model.modelDefaultLabel()])
  }

  function test_model_option_round_trips_through_the_config_value() {
    compare(Model.modelFromOption(Model.modelDefaultLabel()), "")
    compare(Model.modelToOption(""), Model.modelDefaultLabel())
    compare(Model.modelFromOption("opus"), "opus")
    compare(Model.modelToOption("opus"), "opus")
    // Whitespace-only is still "unset", not a model named " ".
    compare(Model.modelToOption("   "), Model.modelDefaultLabel())
  }

  function test_provider_options_mark_the_chosen_one() {
    var opts = Model.providerOptions([
      { name: "claude", available: true, reason: "" },
      { name: "codex", available: true, reason: "" },
      { name: "copilot", available: true, reason: "" }
    ], "codex")
    compare(opts.length, 3)
    compare(opts[0].selected, false)
    compare(opts[1].name, "codex")
    compare(opts[1].selected, true)
    compare(opts[1].status, "available")
  }

  function test_provider_options_list_uninstalled_providers_too() {
    // Hiding one would make the project look like it supports fewer providers
    // than it does; the engine reports the missing CLI when it is used.
    var opts = Model.providerOptions([
      { name: "claude", available: false, reason: "claude is not installed" }
    ], "claude")
    compare(opts.length, 1)
    compare(opts[0].available, false)
    compare(opts[0].status, "claude is not installed")
    compare(opts[0].selected, true)
  }

  function test_provider_options_tolerate_missing_engine_data() {
    compare(Model.providerOptions(null, "claude").length, 0)
    compare(Model.providerOptions([], "").length, 0)
    // A row with no name is dropped rather than rendered as a blank choice.
    compare(Model.providerOptions([{ available: true }], "").length, 0)
  }

  function test_agent_summary_is_empty_until_the_engine_answers() {
    // The sentence is dropped entirely rather than rendered half-empty while
    // the engine is still starting up.
    compare(Model.agentSummary("", ""), "")
    compare(Model.agentSummary(null, null), "")
    compare(Model.agentSummary(undefined, "some-model"), "")
  }
}
