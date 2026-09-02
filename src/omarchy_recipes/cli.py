from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import (
    SCHEMA_VERSION,
    RecipeError,
    execute,
    get_recipe,
    history,
    recipe_root,
    run_output,
    scan,
    status,
)


def repo_root() -> Path:
    return recipe_root()


def emit(payload: dict[str, Any]) -> None:
    """Every --json response is an object carrying the contract version.

    Frontends check `schemaVersion` before trusting the rest, so the engine can
    grow fields without a client silently misreading a new shape.
    """
    print(json.dumps({"schemaVersion": SCHEMA_VERSION, **payload}, indent=2))


def parse_param_argv(items: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    i = 0
    while i < len(items):
        token = items[i]
        if token == "--json":
            # Ambiguous here: `--json` in this position could equally be a
            # parameter named "json". Say so instead of guessing.
            raise RecipeError("place --json before the recipe id, e.g. `run --json <recipe-id> --value x`")
        if not token.startswith("--") or token == "--":
            raise RecipeError(f"expected --parameter, got {token!r}")
        name = token[2:]
        if not name:
            raise RecipeError("empty parameter name")
        if i + 1 >= len(items):
            raise RecipeError(f"missing value for {token}")
        values[name] = items[i + 1]
        i += 2
    return values


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="omarchy-recipes", description="Self-describing reversible recipe runner")
    sub = p.add_subparsers(dest="command", required=True)

    lp = sub.add_parser("list", help="list discovered recipes")
    lp.add_argument("--json", action="store_true")

    ip = sub.add_parser("info", help="show normalized recipe metadata")
    ip.add_argument("recipe_id")
    ip.add_argument("--json", action="store_true")

    sp = sub.add_parser("status", help="show current engine state for a recipe without executing it")
    sp.add_argument("recipe_id")
    sp.add_argument("--json", action="store_true")

    cp = sub.add_parser("check", help="run a recipe's read-only check")
    cp.add_argument("--json", action="store_true")
    cp.add_argument("recipe_id")
    cp.add_argument("args", nargs=argparse.REMAINDER)

    rp = sub.add_parser("run", help="apply a recipe")
    rp.add_argument("--json", action="store_true")
    rp.add_argument("recipe_id")
    rp.add_argument("args", nargs=argparse.REMAINDER)

    up = sub.add_parser("undo", help="undo the latest eligible successful run")
    up.add_argument("--json", action="store_true")
    up.add_argument("recipe_id")

    hp = sub.add_parser("history", help="show run history")
    hp.add_argument("recipe_id", nargs="?")
    hp.add_argument("--limit", type=int, default=None)
    hp.add_argument("--json", action="store_true")

    gp = sub.add_parser("log", help="show captured output for a recorded run")
    gp.add_argument("recipe_id")
    gp.add_argument("--run", dest="run_id", default=None, help="run id (default: latest run)")
    gp.add_argument("--json", action="store_true")

    vp = sub.add_parser("validate", help="parse and validate all recipe metadata")
    vp.add_argument("--json", action="store_true")
    return p


def print_run_text(result_dict: dict[str, Any]) -> None:
    if result_dict["stdout"]:
        sys.stdout.write(result_dict["stdout"].rstrip("\n") + "\n")
    if result_dict["stderr"]:
        sys.stderr.write(result_dict["stderr"])


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            recipes, problems = scan(root)
            if args.json:
                emit({"recipes": [r.to_dict() for r in recipes], "problems": problems})
            else:
                if not recipes:
                    print("No recipes found")
                for r in recipes:
                    print(f"{r.id:28}  {r.category:14}  {r.title}")
                for problem in problems:
                    print(f"problem: {problem['error']}", file=sys.stderr)
            return 0

        if args.command == "info":
            r = get_recipe(root, args.recipe_id)
            if args.json:
                emit({"recipe": r.to_dict()})
            else:
                print(f"{r.title} ({r.id})")
                print(r.description)
                print(f"Category: {r.category} | Risk: {r.risk} | Undo: {r.undo} | Privilege: {r.privilege}")
                if r.parameters:
                    print("Parameters:")
                    for p in r.parameters:
                        suffix = f" default={p.default}" if p.default is not None else ""
                        print(f"  --{p.name} ({p.type}){suffix}: {p.label or p.name}")
            return 0

        if args.command == "status":
            data = status(get_recipe(root, args.recipe_id))
            if args.json:
                emit({"status": data})
            else:
                print(f"Undo: {data['undo']} | available: {'yes' if data['undo_available'] else 'no'}")
                print(f"Runs recorded: {data['runs']}")
                last = data["last_run"]
                if last:
                    print(f"Last run: {last.get('started_at')} {last.get('action')} {last.get('status')}")
            return 0

        if args.command in {"check", "run"}:
            r = get_recipe(root, args.recipe_id)
            raw = parse_param_argv(args.args)
            result = execute(root, r, "check" if args.command == "check" else "apply", raw).to_dict()
            if args.json:
                emit({"run": result})
            else:
                print_run_text(result)
            return int(result["exit_code"])

        if args.command == "undo":
            result = execute(root, get_recipe(root, args.recipe_id), "undo").to_dict()
            if args.json:
                emit({"run": result})
            else:
                print_run_text(result)
            return int(result["exit_code"])

        if args.command == "history":
            rows = history(args.recipe_id, limit=args.limit)
            if args.json:
                emit({"runs": rows})
            else:
                if not rows:
                    print("No history")
                for row in rows:
                    print(
                        f"{row.get('started_at','?')}  {row.get('recipe_id','?'):24}  "
                        f"{row.get('action','?'):5}  {row.get('status','?')}"
                    )
            return 0

        if args.command == "log":
            data = run_output(args.recipe_id, args.run_id)
            if args.json:
                emit(data)
            else:
                sys.stdout.write(data["stdout"])
                sys.stderr.write(data["stderr"])
            return 0

        if args.command == "validate":
            recipes, problems = scan(root)
            rows = [{"path": r.path, "id": r.id, "status": "ok"} for r in recipes]
            if args.json:
                emit({"recipes": rows, "problems": problems, "ok": not problems})
            else:
                for row in rows:
                    print(f"ok  {row['id']:28} {row['path']}")
                for problem in problems:
                    print(f"error: {problem['error']}", file=sys.stderr)
                print(f"Validated {len(rows)} recipe(s)")
            return 2 if problems else 0

    except RecipeError as e:
        if getattr(args, "json", False):
            emit({"error": str(e)})
        else:
            print(f"error: {e}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
