from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import sources as sources_mod

RECIPE_KEY_RE = re.compile(r"^\s*#\s*@recipe\.([A-Za-z0-9_-]+)\s+(.+?)\s*$")
PARAM_RE = re.compile(r"^\s*#\s*@param\s+(.+?)\s*$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PARAM_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
VALID_TYPES = {"string", "integer", "boolean", "choice", "path", "secret"}
VALID_PRIVILEGE = {"user", "mixed", "root"}
VALID_UNDO = {"restore", "command", "none"}
VALID_RISK = {"low", "medium", "high"}

# Machine-readable output contract version. Frontends should refuse output they
# do not understand rather than guessing at a newer shape.
SCHEMA_VERSION = 1

# Reported state of a recipe on this machine, as answered by `check`.
VALID_STATES = {"configured", "not-configured", "partial", "unsupported", "unknown", "error"}

# `check` reports state by emitting these markers on stdout. They are stripped
# from the text the engine hands a frontend for display, and the raw stream is
# still what lands in the run log.
STATE_MARKER_RE = re.compile(r"^@recipe\.state\s+(\S+)\s*$")
SUMMARY_MARKER_RE = re.compile(r"^@recipe\.summary\s+(.*?)\s*$")


def _split_csv(value: str) -> list[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def _bool(value: str) -> bool:
    v = value.strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean: {value}")


def _coerce_default(param_type: str, value: str) -> Any:
    if param_type == "integer":
        return int(value)
    if param_type == "boolean":
        return _bool(value)
    return value


@dataclass
class Parameter:
    name: str
    type: str
    required: bool = False
    default: Any = None
    label: str | None = None
    description: str | None = None
    choices: list[str] | None = None
    min: int | None = None
    max: int | None = None
    extra: dict[str, Any] | None = None


@dataclass
class Recipe:
    id: str
    title: str
    description: str
    category: str
    path: str
    platform: list[str]
    distro: list[str]
    privilege: str
    undo: str
    risk: str
    tags: list[str]
    parameters: list[Parameter]
    extra: dict[str, str]
    # Where the recipe came from, decided by which directory it was found in
    # rather than by anything the file claims about itself.
    source: str = sources_mod.BUNDLED
    # Provenance the file may declare: whether an agent wrote it and whether a
    # human has since reviewed it. Never used to raise trust on its own.
    authoring: dict[str, Any] = field(default_factory=lambda: {"generated_with_ai": False, "reviewed": False})

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_label"] = sources_mod.SOURCE_LABELS.get(self.source, self.source)
        data["reviewed_upstream"] = sources_mod.SOURCE_REVIEWED_UPSTREAM.get(self.source, False)
        return data


@dataclass
class RunResult:
    """Normalized outcome of one recipe action.

    This is the single shape every frontend consumes for check/apply/undo, so
    no client has to interpret exit codes or scrape human text itself.
    """

    recipe_id: str
    action: str
    status: str
    exit_code: int
    started_at: str
    finished_at: str
    duration_seconds: float
    parameters: dict[str, Any] = field(default_factory=dict)
    state: str = "unknown"
    summary: str = ""
    stdout: str = ""
    stderr: str = ""
    run_dir: str | None = None
    run_id: str | None = None
    source_run: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RecipeError(RuntimeError):
    pass


def parse_recipe(path: Path) -> Recipe:
    meta: dict[str, str] = {}
    params: list[Parameter] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i > 200:
                break
            m = RECIPE_KEY_RE.match(line)
            if m:
                meta[m.group(1)] = m.group(2).strip()
                continue
            p = PARAM_RE.match(line)
            if p:
                try:
                    tokens = shlex.split(p.group(1))
                except ValueError as e:
                    raise RecipeError(f"{path}: unparsable @param line: {e}") from e
                if len(tokens) < 2:
                    raise RecipeError(f"{path}: invalid @param line")
                name, ptype, *attrs = tokens
                if not PARAM_NAME_RE.match(name):
                    raise RecipeError(f"{path}: invalid parameter name {name!r}")
                if ptype not in VALID_TYPES:
                    raise RecipeError(f"{path}: unsupported parameter type {ptype!r}")
                raw: dict[str, str] = {}
                for token in attrs:
                    if "=" not in token:
                        raise RecipeError(f"{path}: invalid parameter attribute {token!r}; expected key=value")
                    k, v = token.split("=", 1)
                    raw[k] = v
                known = {"required", "default", "label", "description", "choices", "min", "max"}
                extra = {k: v for k, v in raw.items() if k not in known}
                try:
                    default = _coerce_default(ptype, raw["default"]) if "default" in raw else None
                    required = _bool(raw.get("required", "false"))
                    minimum = int(raw["min"]) if "min" in raw else None
                    maximum = int(raw["max"]) if "max" in raw else None
                except ValueError as e:
                    raise RecipeError(f"{path}: invalid attribute for --{name}: {e}") from e
                param = Parameter(
                    name=name,
                    type=ptype,
                    required=required,
                    default=default,
                    label=raw.get("label") or name.replace("-", " ").replace("_", " ").title(),
                    description=raw.get("description"),
                    choices=_split_csv(raw["choices"]) if "choices" in raw else None,
                    min=minimum,
                    max=maximum,
                    extra=extra or None,
                )
                if param.type == "choice" and not param.choices:
                    raise RecipeError(f"{path}: choice parameter --{name} declares no choices=")
                params.append(param)

    required_keys = ["id", "title", "description", "category"]
    missing = [k for k in required_keys if not meta.get(k)]
    if missing:
        raise RecipeError(f"{path}: missing metadata: {', '.join('@recipe.' + x for x in missing)}")
    rid = meta["id"]
    if not ID_RE.match(rid):
        raise RecipeError(f"{path}: invalid recipe id {rid!r}")
    privilege = meta.get("privilege", "user")
    undo = meta.get("undo", "none")
    risk = meta.get("risk", "medium")
    # Name the accepted values. A bare "invalid privilege 'sudo'" says only that
    # the guess was wrong, which leaves a human guessing again and gives an
    # authoring agent nothing to correct itself with.
    if privilege not in VALID_PRIVILEGE:
        raise RecipeError(f"{path}: invalid privilege {privilege!r}; "
                          f"expected one of: {', '.join(sorted(VALID_PRIVILEGE))}")
    if undo not in VALID_UNDO:
        raise RecipeError(f"{path}: invalid undo {undo!r}; "
                          f"expected one of: {', '.join(sorted(VALID_UNDO))}")
    if risk not in VALID_RISK:
        raise RecipeError(f"{path}: invalid risk {risk!r}; "
                          f"expected one of: {', '.join(sorted(VALID_RISK))}")
    known = {
        "id", "title", "description", "category", "platform", "distro", "privilege",
        "undo", "risk", "tags", "generated-with-ai", "reviewed",
    }

    def flag(key: str) -> bool:
        raw = meta.get(key)
        if raw is None:
            return False
        try:
            return _bool(raw)
        except ValueError as e:
            raise RecipeError(f"{path}: @recipe.{key} must be true or false") from e

    return Recipe(
        id=rid,
        title=meta["title"],
        description=meta["description"],
        category=meta["category"],
        path=str(path.resolve()),
        platform=_split_csv(meta.get("platform", "linux")),
        distro=_split_csv(meta.get("distro", "")),
        privilege=privilege,
        undo=undo,
        risk=risk,
        tags=_split_csv(meta.get("tags", "")),
        parameters=params,
        extra={k: v for k, v in meta.items() if k not in known},
        authoring={"generated_with_ai": flag("generated-with-ai"), "reviewed": flag("reviewed")},
    )


def recipe_root(explicit: Path | None = None) -> Path:
    """Directory holding the `recipes/` tree.

    `OMARCHY_RECIPES_ROOT` lets a caller (notably the tests) point the engine at
    an alternate checkout without inventing a recipe-source feature.
    """
    if explicit is not None:
        return explicit
    env = os.environ.get("OMARCHY_RECIPES_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def _sort_key(recipe: Recipe) -> tuple[str, str]:
    return (recipe.category.lower(), recipe.title.lower())


def scan(root: Path) -> tuple[list[Recipe], list[dict[str, str]]]:
    """Discover recipes without letting one bad file hide the good ones.

    Walks every source in trust order, so a local or community recipe can never
    take an id a bundled one already claimed. That matters now that an agent can
    write recipes here: shadowing `install-docker` with a generated file would
    let untrusted code run under a name the user believes is reviewed.

    Returns the recipes that parsed plus a problem report. A frontend shows the
    working recipes and surfaces the problems; `validate` turns them into an
    error.
    """
    recipes: list[Recipe] = []
    problems: list[dict[str, str]] = []
    seen: dict[str, Recipe] = {}

    for source in sources_mod.sources(root):
        if not source.path.exists():
            continue
        for path in sorted(source.path.rglob("*.sh")):
            try:
                recipe = parse_recipe(path)
            except RecipeError as e:
                problems.append({"path": str(path), "source": source.name, "error": str(e)})
                continue
            except OSError as e:
                problems.append({"path": str(path), "source": source.name, "error": f"unreadable: {e}"})
                continue
            recipe.source = source.name
            previous = seen.get(recipe.id)
            if previous is not None:
                if previous.source == sources_mod.BUNDLED and source.name == sources_mod.LOCAL:
                    # The ordinary end state of contributing a recipe: it now
                    # ships in the collection, so the local copy is redundant
                    # rather than broken.
                    detail = (f"{recipe.id!r} now ships with omarchy-recipes; your local copy at "
                              f"{path} is unused and can be deleted")
                else:
                    detail = (f"duplicate recipe id {recipe.id!r}; the {previous.source} recipe at "
                              f"{previous.path} is used instead")
                problems.append({"path": str(path), "source": source.name, "error": detail,
                                 "superseded": previous.source == sources_mod.BUNDLED
                                               and source.name == sources_mod.LOCAL})
                continue
            seen[recipe.id] = recipe
            recipes.append(recipe)

    recipes.sort(key=_sort_key)
    return recipes, problems


def faults(problems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Problems that mean something is wrong.

    A local copy of a recipe that now ships with the project is reported so the
    user knows which file is being ignored, but it is not a fault: the recipe
    works, and failing validation over it would block installs for a tidy-up
    task nobody has to do.
    """
    return [p for p in problems if not p.get("superseded")]


def discover(root: Path) -> list[Recipe]:
    """Strict discovery: any malformed or genuinely duplicated recipe is an error."""
    recipes, problems = scan(root)
    blocking = faults(problems)
    if blocking:
        raise RecipeError(blocking[0]["error"])
    return recipes


def get_recipe(root: Path, recipe_id: str) -> Recipe:
    recipes, problems = scan(root)
    for recipe in recipes:
        if recipe.id == recipe_id:
            return recipe
    for problem in problems:
        if recipe_id in problem["error"]:
            raise RecipeError(f"recipe {recipe_id!r} is not usable: {problem['error']}")
    raise RecipeError(f"recipe not found: {recipe_id}")


def validate_values(recipe: Recipe, raw_values: dict[str, str]) -> dict[str, Any]:
    declared = {p.name: p for p in recipe.parameters}
    unknown = sorted(set(raw_values) - set(declared))
    if unknown:
        raise RecipeError(f"unknown parameter(s): {', '.join(unknown)}")
    values: dict[str, Any] = {}
    for p in recipe.parameters:
        supplied = p.name in raw_values
        if supplied:
            raw = raw_values[p.name]
            if p.type == "integer":
                try:
                    value: Any = int(raw)
                except ValueError as e:
                    raise RecipeError(f"--{p.name} must be an integer") from e
            elif p.type == "boolean":
                try:
                    value = _bool(raw)
                except ValueError as e:
                    raise RecipeError(f"--{p.name} must be true or false") from e
            else:
                value = raw
        elif p.default is not None:
            value = p.default
        elif p.required:
            raise RecipeError(f"missing required parameter --{p.name}")
        else:
            continue
        if p.type == "choice" and p.choices and str(value) not in p.choices:
            raise RecipeError(f"--{p.name} must be one of: {', '.join(p.choices)}")
        if p.type == "integer":
            if p.min is not None and value < p.min:
                raise RecipeError(f"--{p.name} must be >= {p.min}")
            if p.max is not None and value > p.max:
                raise RecipeError(f"--{p.name} must be <= {p.max}")
        values[p.name] = value
    return values


def values_to_argv(recipe: Recipe, values: dict[str, Any]) -> list[str]:
    argv: list[str] = []
    by_name = {p.name: p for p in recipe.parameters}
    for name, value in values.items():
        p = by_name[name]
        argv.append(f"--{name}")
        if p.type == "boolean":
            argv.append("true" if value else "false")
        else:
            argv.append(str(value))
    return argv


def state_root() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "omarchy-recipes"


def new_run_dir(recipe_id: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = state_root() / "runs" / recipe_id / f"{stamp}-{uuid.uuid4().hex[:8]}"
    (path / "backup").mkdir(parents=True, exist_ok=False)
    return path


def successful_apply_runs(recipe_id: str) -> list[Path]:
    base = state_root() / "runs" / recipe_id
    if not base.exists():
        return []
    matches: list[Path] = []
    for d in sorted(base.iterdir(), reverse=True):
        meta = d / "run.json"
        if not meta.exists():
            continue
        try:
            data = json.loads(meta.read_text())
        except Exception:
            continue
        if data.get("action") == "apply" and data.get("status") == "success" and not data.get("undone_by"):
            matches.append(d)
    return matches


def mark_source_undone(source: Path, undo_run: Path) -> None:
    meta = source / "run.json"
    data = json.loads(meta.read_text())
    data["undone_by"] = str(undo_run)
    meta.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def replayable_values(recipe: Recipe, source_run: Path) -> dict[str, Any]:
    """Parameter values recorded by a previous apply, re-validated for undo.

    Secret values are never recorded, so they cannot be replayed; a recipe that
    needs one for undo must recover it itself. Values that no longer validate
    (the recipe's parameters changed since the run) are dropped rather than
    passed on, so undo falls back to the recipe's own defaults instead of
    failing on a stale argument.
    """
    meta = source_run / "run.json"
    if not meta.exists():
        return {}
    try:
        recorded = json.loads(meta.read_text()).get("parameters") or {}
    except (OSError, ValueError):
        return {}
    by_name = {p.name: p for p in recipe.parameters}
    raw = {
        name: str(value)
        for name, value in recorded.items()
        if name in by_name and by_name[name].type != "secret" and value is not None
    }
    try:
        return validate_values(recipe, raw)
    except RecipeError:
        return {}


def parse_check_output(stdout: str, exit_code: int, stderr: str) -> tuple[str, str, str]:
    """Split `@recipe.state`/`@recipe.summary` markers out of check output.

    Returns (state, summary, display_stdout). Recipes that predate the marker
    protocol still work: their state is reported as `unknown` and their first
    line of output becomes the summary.
    """
    state = ""
    summary = ""
    kept: list[str] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        m = STATE_MARKER_RE.match(stripped)
        if m:
            state = m.group(1).lower()
            continue
        s = SUMMARY_MARKER_RE.match(stripped)
        if s:
            summary = s.group(1)
            continue
        kept.append(line)

    display = "\n".join(kept).strip("\n")
    if state not in VALID_STATES:
        state = "unknown"
    if exit_code != 0:
        state = "error"
    if not summary:
        source = display if exit_code == 0 else (stderr.strip() or display)
        for line in source.splitlines():
            if line.strip():
                summary = line.strip()
                break
    return state, summary, display


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def execute(
    root: Path,
    recipe: Recipe,
    action: str,
    raw_values: dict[str, str] | None = None,
) -> RunResult:
    """Run one recipe action and return its normalized result.

    Parameters always travel as argv. Nothing here builds a shell command
    string, so a parameter value can never become shell syntax.
    """
    raw_values = raw_values or {}
    if action not in {"check", "apply", "undo"}:
        raise RecipeError(f"unsupported action: {action}")
    if action == "undo" and recipe.undo == "none":
        raise RecipeError(f"{recipe.id} declares undo=none")

    source_run: Path | None = None
    if action == "undo":
        runs = successful_apply_runs(recipe.id)
        if not runs:
            raise RecipeError(f"no successful, not-yet-undone apply run found for {recipe.id}")
        source_run = runs[0]
        # Replay the source run's parameters. A recipe whose target path or
        # resource depends on a parameter can only reverse the right thing if
        # undo sees the values the apply actually used.
        values = replayable_values(recipe, source_run)
    else:
        values = validate_values(recipe, raw_values)

    # `check` is declared non-mutating, so it gets a throwaway working
    # directory: a frontend that checks state every time a recipe is selected
    # must not accumulate run directories or pollute the history a user reads.
    ephemeral = tempfile.mkdtemp(prefix="omarchy-recipes-check-") if action == "check" else None
    run_dir = Path(ephemeral) if ephemeral else new_run_dir(recipe.id)
    if ephemeral:
        (run_dir / "backup").mkdir(parents=True, exist_ok=True)

    try:
        env = os.environ.copy()
        env.update(
            {
                "OMARCHY_RECIPES_ROOT": str(root),
                "OMARCHY_RECIPES_LIB": str(root / "lib"),
                "OMARCHY_RECIPES_RUN_DIR": str(run_dir),
                "OMARCHY_RECIPES_BACKUP_DIR": str(run_dir / "backup"),
                "OMARCHY_RECIPES_RECIPE_ID": recipe.id,
                "OMARCHY_RECIPES_ACTION": action,
            }
        )
        if source_run:
            env["OMARCHY_RECIPES_SOURCE_RUN_DIR"] = str(source_run)

        by_name = {p.name: p for p in recipe.parameters}
        recorded_params = {
            k: ("<redacted>" if by_name[k].type == "secret" else v) for k, v in values.items()
        }

        argv = [recipe.path, action] + values_to_argv(recipe, values)
        start = datetime.now(timezone.utc)
        run_meta: dict[str, Any] = {
            "recipe_id": recipe.id,
            "recipe_path": recipe.path,
            "action": action,
            "status": "running",
            "started_at": _iso(start),
            "parameters": recorded_params,
            "source_run": str(source_run) if source_run else None,
        }
        if not ephemeral:
            (run_dir / "run.json").write_text(json.dumps(run_meta, indent=2, sort_keys=True) + "\n")

        try:
            proc = subprocess.run(
                argv, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
            )
            exit_code = proc.returncode
            stdout, stderr = proc.stdout, proc.stderr
        except OSError as e:
            # Missing interpreter, lost exec bit, deleted file: report it the
            # same way a failing recipe is reported instead of crashing.
            exit_code, stdout, stderr = 127, "", f"cannot execute {recipe.path}: {e}\n"

        end = datetime.now(timezone.utc)
        state, summary, display_stdout = parse_check_output(stdout, exit_code, stderr)
        if action != "check":
            # apply/undo report success or failure; current state comes from a
            # follow-up `check`, which is the only non-mutating source of truth.
            state = "unknown"

        result = RunResult(
            recipe_id=recipe.id,
            action=action,
            status="success" if exit_code == 0 else "failed",
            exit_code=exit_code,
            started_at=_iso(start),
            finished_at=_iso(end),
            duration_seconds=round((end - start).total_seconds(), 3),
            parameters=recorded_params,
            state=state,
            summary=summary,
            stdout=display_stdout,
            stderr=stderr,
            run_dir=None if ephemeral else str(run_dir),
            run_id=None if ephemeral else run_dir.name,
            source_run=str(source_run) if source_run else None,
        )

        if not ephemeral:
            (run_dir / "stdout.log").write_text(stdout)
            (run_dir / "stderr.log").write_text(stderr)
            run_meta.update(
                {
                    "status": result.status,
                    "exit_code": exit_code,
                    "finished_at": result.finished_at,
                    "duration_seconds": result.duration_seconds,
                    "summary": summary,
                }
            )
            (run_dir / "run.json").write_text(json.dumps(run_meta, indent=2, sort_keys=True) + "\n")
            if action == "undo" and exit_code == 0 and source_run:
                mark_source_undone(source_run, run_dir)
        return result
    finally:
        if ephemeral:
            shutil.rmtree(ephemeral, ignore_errors=True)


def history(recipe_id: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    base = state_root() / "runs"
    if not base.exists():
        return []
    recipe_dirs = [base / recipe_id] if recipe_id else [p for p in base.iterdir() if p.is_dir()]
    rows: list[dict[str, Any]] = []
    for rdir in recipe_dirs:
        if not rdir.exists():
            continue
        for d in rdir.iterdir():
            meta = d / "run.json"
            if meta.exists():
                try:
                    row = json.loads(meta.read_text())
                    row["run_dir"] = str(d)
                    row["run_id"] = d.name
                    row["undone"] = bool(row.get("undone_by"))
                    rows.append(row)
                except Exception:
                    pass
    rows.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    return rows[:limit] if limit else rows


def status(recipe: Recipe) -> dict[str, Any]:
    """Everything a frontend needs to decide what actions to offer.

    Deliberately does not execute the recipe: opening a browser must never run
    anything, and undo eligibility is engine state, not a UI guess.
    """
    rows = history(recipe.id)
    applies = successful_apply_runs(recipe.id)
    last_apply = None
    for row in rows:
        if row.get("action") == "apply" and row.get("status") == "success" and not row.get("undone_by"):
            last_apply = row
            break
    return {
        "recipe_id": recipe.id,
        "undo": recipe.undo,
        "undo_supported": recipe.undo != "none",
        "undo_available": recipe.undo != "none" and bool(applies),
        "runs": len(rows),
        "last_run": rows[0] if rows else None,
        "last_apply": last_apply,
    }


def run_output(recipe_id: str, run_id: str | None = None) -> dict[str, Any]:
    """Read back a recorded run's captured output.

    Frontends ask the engine for logs rather than reaching into the state
    directory themselves, which keeps the layout an engine detail.
    """
    base = state_root() / "runs" / recipe_id
    if run_id is not None:
        if not RUN_ID_RE.match(run_id):
            raise RecipeError(f"invalid run id: {run_id!r}")
        run_dir = base / run_id
    else:
        rows = history(recipe_id, limit=1)
        if not rows:
            raise RecipeError(f"no recorded runs for {recipe_id}")
        run_dir = Path(rows[0]["run_dir"])
    if not (run_dir / "run.json").exists():
        raise RecipeError(f"run not found: {recipe_id}/{run_id or '<latest>'}")

    def read(name: str) -> str:
        path = run_dir / name
        return path.read_text(errors="replace") if path.exists() else ""

    row = json.loads((run_dir / "run.json").read_text())
    row["run_dir"] = str(run_dir)
    row["run_id"] = run_dir.name
    return {"run": row, "stdout": read("stdout.log"), "stderr": read("stderr.log")}
