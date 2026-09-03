.pragma library

// Presentation helpers for the Omarchy Recipes menu.
//
// Everything here is a pure function over data the engine already normalized.
// This file must never parse a recipe file, decide whether a change is
// reversible, validate a parameter, or build a command line for a shell: the
// `omarchy-recipes` engine owns all of that and stays the source of truth.
// What lives here is only the question "how should this be shown".

// ---- plugin directory resolution (same contract other Omarchy plugins use:
//      the entry point resolves siblings relative to its own URL).

function pathFromUrl(url) {
  var text = String(url || "")
  if (text.indexOf("file://") !== 0) return ""
  text = text.slice("file://".length)
  try {
    text = decodeURIComponent(text)
  } catch (e) {
    return ""
  }
  while (text.length > 1 && text.charAt(text.length - 1) === "/") {
    text = text.slice(0, -1)
  }
  return text
}

function parentDir(path) {
  var text = String(path || "")
  var cut = text.lastIndexOf("/")
  if (cut <= 0) return text
  return text.slice(0, cut)
}

// ---- engine responses

// Decode one `--json` response. The engine stamps every payload with
// schemaVersion; anything else is treated as unusable rather than guessed at.
function parseResponse(text, expectedVersion) {
  var raw = String(text || "").trim()
  if (!raw) return { ok: false, error: "the recipe engine returned no output", data: null }
  var data
  try {
    data = JSON.parse(raw)
  } catch (e) {
    return { ok: false, error: "the recipe engine returned output that is not JSON", data: null }
  }
  if (!data || typeof data !== "object") {
    return { ok: false, error: "unexpected engine response", data: null }
  }
  if (data.schemaVersion !== expectedVersion) {
    return {
      ok: false,
      data: null,
      error: "engine speaks schema version " + String(data.schemaVersion)
        + ", this plugin understands " + String(expectedVersion) + " — update the plugin"
    }
  }
  if (typeof data.error === "string" && data.error) {
    return { ok: false, error: data.error, data: data }
  }
  return { ok: true, error: "", data: data }
}

// stderr is untrusted text from a recipe. Keep it short and single-line when
// it is being used as an inline error label rather than log output.
function firstLine(text, limit) {
  var lines = String(text || "").split("\n")
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].replace(/^\s+|\s+$/g, "")
    if (line) return truncate(line, limit || 160)
  }
  return ""
}

function truncate(text, limit) {
  var s = String(text || "")
  return s.length > limit ? s.slice(0, limit - 1) + "…" : s
}

// ---- browsing

function matchesQuery(recipe, query) {
  var q = String(query || "").toLowerCase().replace(/^\s+|\s+$/g, "")
  if (!q) return true
  var terms = q.split(/\s+/)
  var haystack = [
    recipe.id, recipe.title, recipe.description, recipe.category,
    (recipe.tags || []).join(" ")
  ].join(" ").toLowerCase()
  for (var i = 0; i < terms.length; i++) {
    if (haystack.indexOf(terms[i]) === -1) return false
  }
  return true
}

function filterRecipes(recipes, query) {
  var out = []
  var list = recipes || []
  for (var i = 0; i < list.length; i++) {
    if (matchesQuery(list[i], query)) out.push(list[i])
  }
  return out
}

// Flatten to the row list the menu renders: a category header followed by its
// recipes. The engine already sorts by category then title, so grouping here
// is a single pass and the on-screen order matches `omarchy-recipes list`.
function rowsFor(recipes, query) {
  var filtered = filterRecipes(recipes, query)
  var rows = []
  var currentCategory = null
  for (var i = 0; i < filtered.length; i++) {
    var recipe = filtered[i]
    var category = String(recipe.category || "Uncategorized")
    if (category !== currentCategory) {
      currentCategory = category
      // Every row carries the same keys so the delegate never binds undefined.
      rows.push({ kind: "header", label: category, detail: "", recipeId: "" })
    }
    rows.push({
      kind: "recipe",
      label: String(recipe.title || recipe.id),
      detail: String(recipe.description || ""),
      recipeId: String(recipe.id),
      badge: sourceBadge(recipe)
    })
  }
  return rows
}

// Names what will actually answer an authoring request: the provider the engine
// resolved, plus the model when one is pinned. The engine has already applied
// the flag/env/config precedence, so this only formats what it reported.
//
// Returns "" when no provider is known yet, so the caller can drop the sentence
// entirely rather than render a half-empty one while the engine is still
// starting up.
function agentSummary(provider, model) {
  var name = String(provider || "").trim()
  if (!name) return ""
  var pinned = String(model || "").trim()
  return pinned ? name + " (" + pinned + ")" : name
}

// What an unset model is called in the picker. Empty is the shipped state and
// needs a name a user can actually read.
function modelDefaultLabel() { return "(provider default)" }

// Options for the settings model picker: the provider's known models, with the
// "unset" row first.
//
// The engine's list is a convenience shortlist, not a validated set — no
// provider CLI can enumerate its own models, so the list is written down and
// will go stale. A configured value the shortlist has never heard of is
// therefore kept and offered rather than dropped, and the field stays free
// text, so a model released after that list was written still works.
function modelOptions(byProvider, provider, current) {
  var out = [modelDefaultLabel()]
  var known = (byProvider || ({}))[String(provider || "")] || []
  for (var i = 0; i < known.length; i++) {
    var name = String(known[i] || "").trim()
    if (name && out.indexOf(name) < 0) out.push(name)
  }
  var value = String(current || "").trim()
  if (value && out.indexOf(value) < 0) out.push(value)
  return out
}

// Picker selection -> what the config stores. The default row means "not
// configured", which the engine records as null.
function modelFromOption(option) {
  var value = String(option || "")
  return value === modelDefaultLabel() ? "" : value
}

// Stored model -> which picker row is selected.
function modelToOption(model) {
  var value = String(model || "").trim()
  return value === "" ? modelDefaultLabel() : value
}

// Rows for the settings provider picker: every provider the engine has an
// adapter for, with whether its CLI is installed and which one is chosen.
//
// An uninstalled provider is listed rather than hidden. Configuring one you
// have not installed yet is legitimate — the engine reports the missing CLI
// plainly when you actually use it — and hiding it would make the list look
// like the project supports fewer providers than it does.
function providerOptions(providers, selected) {
  var out = []
  var list = providers || []
  for (var i = 0; i < list.length; i++) {
    var entry = list[i] || {}
    var name = String(entry.name || "")
    if (!name) continue
    out.push({
      name: name,
      available: !!entry.available,
      status: entry.available ? "available" : (String(entry.reason || "") || "not installed"),
      selected: name === String(selected || "")
    })
  }
  return out
}

// Short origin marker for the browse list. Bundled recipes get nothing: they
// are the baseline, and badging everything would make the marker invisible.
function sourceBadge(recipe) {
  var source = String(recipe && recipe.source || "bundled")
  if (source === "bundled") return ""
  var ai = recipe && recipe.authoring && recipe.authoring.generated_with_ai
  if (source === "local") return ai ? "local · ai" : "local"
  return source
}

function sourceLabel(recipe) {
  var label = String(recipe && recipe.source_label || "")
  if (!label) return ""
  var ai = recipe && recipe.authoring && recipe.authoring.generated_with_ai
  var reviewed = recipe && recipe.authoring && recipe.authoring.reviewed
  if (!ai) return label
  return label + (reviewed ? " · AI-generated, reviewed" : " · AI-generated, not reviewed")
}

// Split discovery problems into "something is broken" and "you have a local
// copy of something that now ships with the project". Only the first is a
// fault; showing both in red taught the user to ignore the colour.
function problemSummary(problems) {
  var faults = []
  var superseded = []
  var list = problems || []
  for (var i = 0; i < list.length; i++) {
    if (list[i].superseded) superseded.push(list[i])
    else faults.push(list[i])
  }
  var faultText = ""
  if (faults.length === 1) faultText = "1 recipe could not be loaded: " + firstLine(faults[0].error, 200)
  else if (faults.length > 1) faultText = faults.length + " recipes could not be loaded: " + firstLine(faults[0].error, 200)

  var supersededText = ""
  if (superseded.length === 1) supersededText = firstLine(superseded[0].error, 200)
  else if (superseded.length > 1)
    supersededText = superseded.length + " of your local recipes now ship with omarchy-recipes and are unused."

  return { faultText: faultText, supersededText: supersededText }
}

function firstSelectableRow(rows) {
  for (var i = 0; i < (rows || []).length; i++) {
    if (rows[i].kind === "recipe") return i
  }
  return -1
}

// Move the cursor to the next selectable row, skipping category headers.
function nextSelectableRow(rows, from, step) {
  var list = rows || []
  if (list.length === 0) return -1
  var i = from
  for (var guard = 0; guard < list.length; guard++) {
    i += step
    if (i < 0 || i >= list.length) return from
    if (list[i].kind === "recipe") return i
  }
  return from
}

// ---- generated controls
//
// The control is chosen from the declared parameter type. An unknown type
// falls back to a plain text field so a recipe written against a newer engine
// still renders and still round-trips its value through the runner's validated
// argument interface — new types can be added by extending this map alone.
function controlFor(parameter) {
  switch (String(parameter && parameter.type)) {
    case "integer": return "number"
    case "boolean": return "toggle"
    case "choice":  return "choice"
    case "path":    return "path"
    case "secret":  return "secret"
    case "string":  return "text"
    default:        return "text"
  }
}

function parameterLabel(parameter) {
  if (!parameter) return ""
  return String(parameter.label || parameter.name || "")
}

function defaultValues(parameters) {
  var values = ({})
  var list = parameters || []
  for (var i = 0; i < list.length; i++) {
    var p = list[i]
    if (p.default !== null && p.default !== undefined) values[p.name] = p.default
    else if (p.type === "boolean") values[p.name] = false
    else values[p.name] = ""
  }
  return values
}

function valueAsText(value) {
  if (value === null || value === undefined) return ""
  if (value === true) return "true"
  if (value === false) return "false"
  return String(value)
}

// Build the runner's `--name value` argument list. Values travel as separate
// argv entries and are never spliced into a command string, so a parameter
// value can never become shell syntax. The engine re-validates every value.
function argvFor(parameters, values) {
  var argv = []
  var list = parameters || []
  for (var i = 0; i < list.length; i++) {
    var p = list[i]
    var raw = values ? values[p.name] : undefined
    if (raw === undefined || raw === null) continue
    var text = valueAsText(raw)
    // An empty field means "leave it to the recipe's declared default". A
    // required parameter that is still empty is caught by missingRequired()
    // before Apply is offered, and by the engine if it ever gets that far.
    if (text === "") continue
    argv.push("--" + p.name)
    argv.push(text)
  }
  return argv
}

// Only the "required but still empty" case is answered here, purely so Apply
// can be disabled before a pointless round trip. Type, range, and choice
// validation stay in the engine; this never decides a value is acceptable.
function missingRequired(parameters, values) {
  var missing = []
  var list = parameters || []
  for (var i = 0; i < list.length; i++) {
    var p = list[i]
    if (!p.required) continue
    if (p.type === "boolean") continue
    var text = valueAsText(values ? values[p.name] : undefined)
    if (text === "") missing.push(parameterLabel(p))
  }
  return missing
}

// ---- status presentation

function stateLabel(state) {
  switch (String(state || "")) {
    case "configured":     return "Configured"
    case "not-configured": return "Not configured"
    case "partial":        return "Partially configured"
    case "unsupported":    return "Not supported here"
    case "error":          return "Check failed"
    default:               return "Unknown"
  }
}

function stateGlyph(state) {
  switch (String(state || "")) {
    case "configured":     return "✓"
    case "not-configured": return "○"
    case "partial":        return "◐"
    case "unsupported":    return "–"
    case "error":          return "!"
    default:               return "?"
  }
}

function riskLabel(risk) {
  switch (String(risk || "")) {
    case "low":    return "Low risk"
    case "medium": return "Medium risk"
    case "high":   return "High risk"
    default:       return "Unknown risk"
  }
}

// What the user is promised about reversal, stated from the recipe's own
// declaration rather than from anything the UI infers.
function reversibilityLines(recipe, status) {
  var lines = []
  var undo = String(recipe && recipe.undo || "none")
  if (undo === "restore") {
    lines.push({ ok: true, text: "Previous state is backed up before the change" })
    lines.push({ ok: true, text: "Automatic undo restores the exact prior state" })
  } else if (undo === "command") {
    lines.push({ ok: true, text: "Automatic undo runs an explicit inverse action" })
  } else {
    lines.push({ ok: false, text: "This recipe declares no automatic undo" })
  }
  if (status && status.undo_supported && !status.undo_available) {
    lines.push({ ok: false, text: "Nothing to undo yet — no recorded apply" })
  }
  return lines
}

function privilegeLabel(privilege) {
  switch (String(privilege || "")) {
    case "root":  return "Requires root"
    case "mixed": return "Elevates some steps"
    default:      return "Runs as you"
  }
}

// ---- history

function formatTimestamp(iso) {
  var text = String(iso || "")
  if (!text) return ""
  var date = new Date(text)
  if (isNaN(date.getTime())) return text
  var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
  function pad(n) { return n < 10 ? "0" + n : String(n) }
  return months[date.getMonth()] + " " + date.getDate() + "  " + pad(date.getHours()) + ":" + pad(date.getMinutes())
}

function historyRows(runs, limit) {
  var out = []
  var list = runs || []
  var max = limit || list.length
  for (var i = 0; i < list.length && out.length < max; i++) {
    var run = list[i]
    out.push({
      when: formatTimestamp(run.started_at),
      action: String(run.action || ""),
      status: String(run.status || ""),
      summary: truncate(String(run.summary || ""), 90),
      undone: run.undone === true,
      runId: String(run.run_id || "")
    })
  }
  return out
}

function describeParameters(parameters) {
  var parts = []
  for (var name in (parameters || {})) {
    parts.push(name + "=" + valueAsText(parameters[name]))
  }
  return parts.join("  ")
}
