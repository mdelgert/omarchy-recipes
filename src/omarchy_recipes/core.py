from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RECIPE_KEY_RE = re.compile(r"^\s*#\s*@recipe\.([A-Za-z0-9_-]+)\s+(.+?)\s*$")
PARAM_RE = re.compile(r"^\s*#\s*@param\s+(.+?)\s*$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PARAM_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
VALID_TYPES = {"string", "integer", "boolean", "choice", "path", "secret"}
VALID_PRIVILEGE = {"user", "mixed", "root"}
VALID_UNDO = {"restore", "command", "none"}
VALID_RISK = {"low", "medium", "high"}


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

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


class RecipeError(RuntimeError):
    pass


def parse_recipe(path: Path) -> Recipe:
    meta: dict[str, str] = {}
    params: list[Parameter] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i > 200:
                break
            m = RECIPE_KEY_RE.match(line)
            if m:
                meta[m.group(1)] = m.group(2).strip()
                continue
            p = PARAM_RE.match(line)
            if p:
                tokens = shlex.split(p.group(1))
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
                default = _coerce_default(ptype, raw["default"]) if "default" in raw else None
                param = Parameter(
                    name=name,
                    type=ptype,
                    required=_bool(raw.get("required", "false")),
                    default=default,
                    label=raw.get("label") or name.replace("-", " ").replace("_", " ").title(),
                    description=raw.get("description"),
                    choices=_split_csv(raw["choices"]) if "choices" in raw else None,
                    min=int(raw["min"]) if "min" in raw else None,
                    max=int(raw["max"]) if "max" in raw else None,
                    extra=extra or None,
                )
                params.append(param)

    required = ["id", "title", "description", "category"]
    missing = [k for k in required if not meta.get(k)]
    if missing:
        raise RecipeError(f"{path}: missing metadata: {', '.join('@recipe.' + x for x in missing)}")
    rid = meta["id"]
    if not ID_RE.match(rid):
        raise RecipeError(f"{path}: invalid recipe id {rid!r}")
    privilege = meta.get("privilege", "user")
    undo = meta.get("undo", "none")
    risk = meta.get("risk", "medium")
    if privilege not in VALID_PRIVILEGE:
        raise RecipeError(f"{path}: invalid privilege {privilege!r}")
    if undo not in VALID_UNDO:
        raise RecipeError(f"{path}: invalid undo {undo!r}")
    if risk not in VALID_RISK:
        raise RecipeError(f"{path}: invalid risk {risk!r}")
    known = {"id", "title", "description", "category", "platform", "distro", "privilege", "undo", "risk", "tags"}
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
    )


def discover(root: Path) -> list[Recipe]:
    recipe_dir = root / "recipes"
    recipes: list[Recipe] = []
    if not recipe_dir.exists():
        return recipes
    for path in sorted(recipe_dir.rglob("*.sh")):
        recipes.append(parse_recipe(path))
    seen: dict[str, str] = {}
    for r in recipes:
        if r.id in seen:
            raise RecipeError(f"duplicate recipe id {r.id!r}: {seen[r.id]} and {r.path}")
        seen[r.id] = r.path
    return recipes


def get_recipe(root: Path, recipe_id: str) -> Recipe:
    for recipe in discover(root):
        if recipe.id == recipe_id:
            return recipe
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


def execute(root: Path, recipe: Recipe, action: str, raw_values: dict[str, str] | None = None) -> int:
    raw_values = raw_values or {}
    if action not in {"check", "apply", "undo"}:
        raise RecipeError(f"unsupported action: {action}")
    if action == "undo" and recipe.undo == "none":
        raise RecipeError(f"{recipe.id} declares undo=none")

    values = {} if action == "undo" else validate_values(recipe, raw_values)
    source_run: Path | None = None
    if action == "undo":
        runs = successful_apply_runs(recipe.id)
        if not runs:
            raise RecipeError(f"no successful, not-yet-undone apply run found for {recipe.id}")
        source_run = runs[0]

    run_dir = new_run_dir(recipe.id)
    env = os.environ.copy()
    env.update(
        {
            "OMARCHY_RECIPES_ROOT": str(root),
            "OMARCHY_RECIPES_LIB": str(root / "lib"),
            "OMARCHY_RECIPES_RUN_DIR": str(run_dir),
            "OMARCHY_RECIPES_BACKUP_DIR": str(run_dir / "backup"),
            "OMARCHY_RECIPES_RECIPE_ID": recipe.id,
        }
    )
    if source_run:
        env["OMARCHY_RECIPES_SOURCE_RUN_DIR"] = str(source_run)

    argv = [recipe.path, action] + values_to_argv(recipe, values)
    start = datetime.now(timezone.utc)
    run_meta: dict[str, Any] = {
        "recipe_id": recipe.id,
        "recipe_path": recipe.path,
        "action": action,
        "status": "running",
        "started_at": start.isoformat(),
        "parameters": {k: ("<redacted>" if next(p for p in recipe.parameters if p.name == k).type == "secret" else v) for k, v in values.items()},
        "source_run": str(source_run) if source_run else None,
    }
    (run_dir / "run.json").write_text(json.dumps(run_meta, indent=2, sort_keys=True) + "\n")

    proc = subprocess.run(argv, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    (run_dir / "stdout.log").write_text(proc.stdout)
    (run_dir / "stderr.log").write_text(proc.stderr)
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)

    end = datetime.now(timezone.utc)
    run_meta.update(
        {
            "status": "success" if proc.returncode == 0 else "failed",
            "exit_code": proc.returncode,
            "finished_at": end.isoformat(),
            "duration_seconds": round((end - start).total_seconds(), 3),
        }
    )
    (run_dir / "run.json").write_text(json.dumps(run_meta, indent=2, sort_keys=True) + "\n")
    if action == "undo" and proc.returncode == 0 and source_run:
        mark_source_undone(source_run, run_dir)
    return proc.returncode


def history(recipe_id: str | None = None) -> list[dict[str, Any]]:
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
                    rows.append(row)
                except Exception:
                    pass
    return sorted(rows, key=lambda x: x.get("started_at", ""), reverse=True)
