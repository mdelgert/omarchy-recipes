import QtQuick
import Quickshell
import Quickshell.Io
import "RecipeModel.js" as Model

// Controller between the QML menu and the `omarchy-recipes` engine.
//
// Every piece of knowledge about recipes enters the plugin through this file,
// and it enters as parsed JSON from the runner. Nothing here reads a recipe
// file, decides what is reversible, validates a parameter value, or touches
// the state directory: the engine is the authoritative boundary and the UI is
// a view over what it reports.
//
// Processes are argv arrays. No command string is ever assembled from recipe
// metadata or user input, and nothing from a recipe is evaluated as code.
Item {
  id: engine

  // ---- engine contract ----------------------------------------------------

  // Bumped by the engine when the JSON shape changes incompatibly. A response
  // stamped with anything else is refused rather than half-understood.
  readonly property int schemaVersion: 1

  // ---- runner resolution --------------------------------------------------
  //
  // OMARCHY_RECIPES_BIN, when set, is the whole list: an explicit override that
  // does not exist is a configuration mistake worth reporting, not something to
  // quietly paper over with a different runner. Otherwise, in priority order:
  //   1. <plugin>/bin/omarchy-recipes     installed plugin ships the engine
  //   2. <plugin>/../bin/omarchy-recipes  running straight from a checkout
  //   3. ~/.local/bin/omarchy-recipes     user install
  //   4. omarchy-recipes                  whatever is on PATH
  readonly property string pluginDir: Model.pathFromUrl(Qt.resolvedUrl("."))
  readonly property string runnerOverride: String(Quickshell.env("OMARCHY_RECIPES_BIN") || "")
  readonly property var runnerCandidates: {
    if (runnerOverride) return [runnerOverride]
    var out = []
    if (pluginDir) {
      out.push(pluginDir + "/bin/omarchy-recipes")
      out.push(Model.parentDir(pluginDir) + "/bin/omarchy-recipes")
    }
    var home = Quickshell.env("HOME")
    if (home) out.push(home + "/.local/bin/omarchy-recipes")
    return out
  }

  property int candidateIndex: -1
  property string runnerPath: ""
  property bool runnerResolved: false

  // ---- observable state ---------------------------------------------------

  property bool loadingList: false
  property var recipes: []
  // Recipes the engine could not parse. Surfaced rather than hidden: a
  // malformed recipe is the author's bug, and silently dropping it is how it
  // stays unnoticed.
  property var problems: []

  property string selectedId: ""
  property var recipe: null
  property var status: null
  property var checkResult: null
  property var history: []
  property var lastAction: null
  property string logText: ""

  property bool loadingDetail: false
  property bool checking: false
  property bool busy: false          // an apply or undo is in flight
  property string engineError: ""    // failure to reach or understand the engine

  readonly property bool available: runnerResolved && runnerPath !== ""
  readonly property bool undoAvailable: !!(status && status.undo_available)

  // ---- authoring (Milestone 2) --------------------------------------------
  //
  // The agent proposes, the engine checks, the user decides. These properties
  // mirror that: a plan and its conflicts arrive first, a draft only after the
  // user has resolved anything blocking.
  property bool planning: false
  property bool drafting: false
  property bool saving: false
  property var plan: null            // agent's intent + claimed resources
  property var planConflicts: null   // engine's verdict on those claims
  property string draftText: ""      // the generated recipe, shown in full
  property var draftLint: null
  property string authoringError: ""
  property string savedRecipeId: ""

  readonly property bool authoringBusy: planning || drafting || saving

  signal detailLoaded(string recipeId)
  signal actionCompleted(string action, var run)
  signal planReady()
  signal draftReady()
  signal recipeSaved(string recipeId)

  // ---- lifecycle ----------------------------------------------------------

  Component.onCompleted: resolveRunner()

  function resolveRunner() {
    candidateIndex = -1
    runnerResolved = false
    runnerPath = ""
    tryNextCandidate()
  }

  function tryNextCandidate() {
    candidateIndex += 1
    if (candidateIndex < runnerCandidates.length) {
      runnerProbe.path = runnerCandidates[candidateIndex]
      return
    }
    if (runnerOverride) {
      runnerPath = runnerOverride
      runnerResolved = true
      engineError = "OMARCHY_RECIPES_BIN points at a runner that does not exist\nRunner: " + runnerOverride
      return
    }
    // Nothing on disk matched. Fall back to PATH and let the first real call
    // report the failure, so the message names a command the user can run.
    runnerPath = "omarchy-recipes"
    runnerResolved = true
    reload()
  }

  // Existence probe rather than a trial execution: resolving which runner to
  // use must not run anything.
  //
  // The next candidate is scheduled rather than assigned directly: reassigning
  // `path` from inside this FileView's own failure handler does not start a new
  // load, which silently stops the walk at the second candidate.
  FileView {
    id: runnerProbe
    printErrors: false
    onLoaded: {
      engine.runnerPath = path
      engine.runnerResolved = true
      engine.reload()
    }
    onLoadFailed: Qt.callLater(engine.tryNextCandidate)
  }

  function argv(args) {
    return [runnerPath].concat(args)
  }

  // ---- list ---------------------------------------------------------------

  function reload() {
    if (!runnerResolved || listProc.running) return
    loadingList = true
    listProc.command = argv(["list", "--json"])
    listProc.running = true
    listWatchdog.restart()
  }

  // A command that cannot start never reports an exit, which would otherwise
  // leave the menu saying "Loading recipes…" forever. Only discovery is
  // guarded: every other call happens after a successful list, which is proof
  // the runner works, and an apply that takes minutes is legitimate.
  Timer {
    id: listWatchdog
    interval: 10000
    onTriggered: {
      listProc.running = false
      engine.loadingList = false
      engine.recipes = []
      engine.problems = []
      engine.engineError = "the recipe engine could not be started or did not respond"
        + "\nRunner: " + engine.runnerPath
    }
  }

  Process {
    id: listProc
    stdout: StdioCollector { id: listOut; waitForEnd: true }
    stderr: StdioCollector { id: listErr; waitForEnd: true }
    onExited: function(exitCode) {
      listWatchdog.stop()
      engine.loadingList = false
      var parsed = Model.parseResponse(listOut.text, engine.schemaVersion)
      if (!parsed.ok) {
        engine.recipes = []
        engine.problems = []
        engine.engineError = engine.describeFailure(parsed.error, exitCode, listErr.text)
        return
      }
      engine.engineError = ""
      engine.recipes = parsed.data.recipes || []
      engine.problems = parsed.data.problems || []
    }
  }

  function describeFailure(reason, exitCode, stderrText) {
    var detail = Model.firstLine(stderrText, 200)
    var message = reason
    if (detail) message += " — " + detail
    if (!detail && exitCode !== 0) message += " (exit " + exitCode + ")"
    return message + "\nRunner: " + runnerPath
  }

  // ---- detail -------------------------------------------------------------

  // Selecting a recipe loads its metadata, its engine-side status, and runs
  // `check`. `check` is the only action taken on selection, and the recipe
  // protocol requires it to be non-mutating; nothing that modifies the system
  // ever runs without an explicit Apply.
  function select(recipeId) {
    selectedId = String(recipeId || "")
    recipe = null
    status = null
    checkResult = null
    history = []
    lastAction = null
    logText = ""
    if (!selectedId) return
    loadingDetail = true
    infoProc.command = argv(["info", "--json", selectedId])
    infoProc.running = true
  }

  Process {
    id: infoProc
    stdout: StdioCollector { id: infoOut; waitForEnd: true }
    stderr: StdioCollector { id: infoErr; waitForEnd: true }
    onExited: function(exitCode) {
      engine.loadingDetail = false
      var parsed = Model.parseResponse(infoOut.text, engine.schemaVersion)
      if (!parsed.ok) {
        engine.engineError = engine.describeFailure(parsed.error, exitCode, infoErr.text)
        return
      }
      engine.engineError = ""
      engine.recipe = parsed.data.recipe
      engine.refreshStatus()
      engine.detailLoaded(engine.selectedId)
    }
  }

  // ---- status + history ---------------------------------------------------

  function refreshStatus() {
    if (!selectedId || statusProc.running) return
    statusProc.command = argv(["status", "--json", selectedId])
    statusProc.running = true
  }

  Process {
    id: statusProc
    stdout: StdioCollector { id: statusOut; waitForEnd: true }
    onExited: function() {
      var parsed = Model.parseResponse(statusOut.text, engine.schemaVersion)
      engine.status = parsed.ok ? parsed.data.status : null
      engine.refreshHistory()
    }
  }

  function refreshHistory() {
    if (!selectedId || historyProc.running) return
    historyProc.command = argv(["history", "--json", selectedId, "--limit", "20"])
    historyProc.running = true
  }

  Process {
    id: historyProc
    stdout: StdioCollector { id: historyOut; waitForEnd: true }
    onExited: function() {
      var parsed = Model.parseResponse(historyOut.text, engine.schemaVersion)
      engine.history = parsed.ok ? (parsed.data.runs || []) : []
    }
  }

  // ---- check --------------------------------------------------------------

  function runCheck(values) {
    if (!selectedId || checkProc.running) return
    checking = true
    checkProc.command = argv(["check", "--json", selectedId]
      .concat(Model.argvFor(engine.recipe ? engine.recipe.parameters : [], values)))
    checkProc.running = true
  }

  Process {
    id: checkProc
    stdout: StdioCollector { id: checkOut; waitForEnd: true }
    stderr: StdioCollector { id: checkErr; waitForEnd: true }
    onExited: function(exitCode) {
      engine.checking = false
      var parsed = Model.parseResponse(checkOut.text, engine.schemaVersion)
      if (parsed.ok) {
        engine.checkResult = parsed.data.run
        return
      }
      // A check that could not run at all (e.g. a required parameter has no
      // value yet) is a status the user should see, not a silent blank.
      engine.checkResult = {
        state: "error",
        summary: parsed.error || Model.firstLine(checkErr.text, 160),
        stdout: "",
        stderr: checkErr.text,
        exit_code: exitCode
      }
    }
  }

  // ---- apply / undo -------------------------------------------------------

  // Called only from an explicit, confirmed user action in the UI.
  function apply(values) {
    if (!selectedId || busy) return
    busy = true
    lastAction = null
    actionProc.action = "apply"
    actionProc.command = argv(["run", "--json", selectedId]
      .concat(Model.argvFor(engine.recipe ? engine.recipe.parameters : [], values)))
    actionProc.running = true
  }

  function undo() {
    if (!selectedId || busy) return
    busy = true
    lastAction = null
    actionProc.action = "undo"
    actionProc.command = argv(["undo", "--json", selectedId])
    actionProc.running = true
  }

  Process {
    id: actionProc
    property string action: ""
    stdout: StdioCollector { id: actionOut; waitForEnd: true }
    stderr: StdioCollector { id: actionErr; waitForEnd: true }
    onExited: function(exitCode) {
      engine.busy = false
      var parsed = Model.parseResponse(actionOut.text, engine.schemaVersion)
      if (parsed.ok) {
        engine.lastAction = parsed.data.run
      } else {
        engine.lastAction = {
          action: actionProc.action,
          status: "failed",
          exit_code: exitCode,
          summary: parsed.error,
          stdout: "",
          stderr: actionErr.text
        }
      }
      // State on disk has changed: re-read status, history, and the recipe's
      // own view of the world rather than assuming what the run did.
      engine.refreshStatus()
      engine.actionCompleted(actionProc.action, engine.lastAction)
    }
  }

  // ---- authoring calls ----------------------------------------------------

  function resetAuthoring() {
    plan = null
    planConflicts = null
    draftText = ""
    draftLint = null
    authoringError = ""
    savedRecipeId = ""
  }

  // Ask what the request would touch. The engine checks the claims itself, so
  // the conflicts attached to the reply are not the agent's opinion.
  function requestPlan(request) {
    if (planning || !String(request || "").trim()) return
    resetAuthoring()
    planning = true
    planProc.command = argv(["agent", "plan", "--json", String(request)])
    planProc.running = true
  }

  Process {
    id: planProc
    stdout: StdioCollector { id: planOut; waitForEnd: true }
    stderr: StdioCollector { id: planErr; waitForEnd: true }
    onExited: function(exitCode) {
      engine.planning = false
      var parsed = Model.parseResponse(planOut.text, engine.schemaVersion)
      if (!parsed.ok) {
        engine.authoringError = engine.describeFailure(parsed.error, exitCode, planErr.text)
        return
      }
      engine.plan = parsed.data.plan || null
      engine.planConflicts = parsed.data.conflicts || null
      engine.planReady()
    }
  }

  // `decisions` maps a resource type to the resolution the user picked. The
  // engine refuses to draft while a blocking conflict has no decision, so this
  // cannot skip the user.
  function requestDraft(request, decisions) {
    if (drafting || !engine.plan) return
    drafting = true
    authoringError = ""
    var payload = JSON.stringify({
      plan: engine.plan,
      conflicts: engine.planConflicts,
      decisions: decisions || ({})
    })
    draftProc.command = argv(["agent", "draft", "--json", String(request), "--plan", payload])
    draftProc.running = true
  }

  Process {
    id: draftProc
    stdout: StdioCollector { id: draftOut; waitForEnd: true }
    stderr: StdioCollector { id: draftErr; waitForEnd: true }
    onExited: function(exitCode) {
      engine.drafting = false
      var parsed = Model.parseResponse(draftOut.text, engine.schemaVersion)
      if (!parsed.ok) {
        engine.authoringError = engine.describeFailure(parsed.error, exitCode, draftErr.text)
        return
      }
      engine.draftText = String(parsed.data.recipe || "")
      engine.draftLint = parsed.data.lint || null
      engine.draftReady()
    }
  }

  // Saving is a separate, explicit step. The engine lints again and refuses
  // anything with errors, so this button cannot write a bad recipe.
  function saveDraft(recipeId, text) {
    if (saving || !String(recipeId || "").trim()) return
    saving = true
    authoringError = ""
    saveProc.recipeId = String(recipeId)
    saveProc.command = argv(["create", "--json", String(recipeId), "--body", String(text)])
    saveProc.running = true
  }

  Process {
    id: saveProc
    property string recipeId: ""
    stdout: StdioCollector { id: saveOut; waitForEnd: true }
    stderr: StdioCollector { id: saveErr; waitForEnd: true }
    onExited: function(exitCode) {
      engine.saving = false
      var parsed = Model.parseResponse(saveOut.text, engine.schemaVersion)
      if (!parsed.ok || !parsed.data.saved) {
        engine.authoringError = parsed.ok
          ? String(parsed.data.reason || "the engine refused to save the recipe")
          : engine.describeFailure(parsed.error, exitCode, saveErr.text)
        return
      }
      engine.savedRecipeId = saveProc.recipeId
      engine.reload()
      engine.recipeSaved(saveProc.recipeId)
    }
  }

  // ---- contribution -------------------------------------------------------

  property bool contributing: false
  property var contributePlan: null

  // Always a dry run from the UI. Offering a recipe upstream is a pull request
  // someone will read; the plugin shows what would be sent and stops there.
  function planContribution(recipeId) {
    if (contributing || !recipeId) return
    contributing = true
    contributePlan = null
    authoringError = ""
    contributeProc.command = argv(["contribute", "--json", String(recipeId)])
    contributeProc.running = true
  }

  Process {
    id: contributeProc
    stdout: StdioCollector { id: contributeOut; waitForEnd: true }
    stderr: StdioCollector { id: contributeErr; waitForEnd: true }
    onExited: function(exitCode) {
      engine.contributing = false
      var parsed = Model.parseResponse(contributeOut.text, engine.schemaVersion)
      if (!parsed.ok) {
        engine.authoringError = engine.describeFailure(parsed.error, exitCode, contributeErr.text)
        return
      }
      engine.contributePlan = parsed.data
    }
  }

  // ---- run log ------------------------------------------------------------

  function loadLog(runId) {
    if (!selectedId || logProc.running) return
    logText = ""
    var args = ["log", "--json", selectedId]
    if (runId) args = args.concat(["--run", String(runId)])
    logProc.command = argv(args)
    logProc.running = true
  }

  Process {
    id: logProc
    stdout: StdioCollector { id: logOut; waitForEnd: true }
    stderr: StdioCollector { id: logErr; waitForEnd: true }
    onExited: function() {
      var parsed = Model.parseResponse(logOut.text, engine.schemaVersion)
      if (!parsed.ok) {
        engine.logText = parsed.error
        return
      }
      var text = String(parsed.data.stdout || "")
      var errText = String(parsed.data.stderr || "")
      if (errText) text += (text ? "\n" : "") + errText
      engine.logText = text || "(no output recorded)"
    }
  }
}
