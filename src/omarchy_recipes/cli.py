from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import RecipeError, discover, execute, get_recipe, history, parse_recipe


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_param_argv(items: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    i = 0
    while i < len(items):
        token = items[i]
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

    cp = sub.add_parser("check", help="run a recipe's read-only check")
    cp.add_argument("recipe_id")
    cp.add_argument("args", nargs=argparse.REMAINDER)

    rp = sub.add_parser("run", help="apply a recipe")
    rp.add_argument("recipe_id")
    rp.add_argument("args", nargs=argparse.REMAINDER)

    up = sub.add_parser("undo", help="undo the latest eligible successful run")
    up.add_argument("recipe_id")

    hp = sub.add_parser("history", help="show run history")
    hp.add_argument("recipe_id", nargs="?")
    hp.add_argument("--json", action="store_true")

    vp = sub.add_parser("validate", help="parse and validate all recipe metadata")
    vp.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            recipes = discover(root)
            if args.json:
                print(json.dumps([r.to_dict() for r in recipes], indent=2))
            else:
                if not recipes:
                    print("No recipes found")
                for r in recipes:
                    print(f"{r.id:28}  {r.category:14}  {r.title}")
            return 0

        if args.command == "info":
            r = get_recipe(root, args.recipe_id)
            if args.json:
                print(json.dumps(r.to_dict(), indent=2))
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

        if args.command in {"check", "run"}:
            r = get_recipe(root, args.recipe_id)
            raw = parse_param_argv(args.args)
            return execute(root, r, "check" if args.command == "check" else "apply", raw)

        if args.command == "undo":
            return execute(root, get_recipe(root, args.recipe_id), "undo")

        if args.command == "history":
            rows = history(args.recipe_id)
            if args.json:
                print(json.dumps(rows, indent=2))
            else:
                if not rows:
                    print("No history")
                for row in rows:
                    print(f"{row.get('started_at','?')}  {row.get('recipe_id','?'):24}  {row.get('action','?'):5}  {row.get('status','?')}")
            return 0

        if args.command == "validate":
            rows = []
            for path in sorted((root / "recipes").rglob("*.sh")):
                r = parse_recipe(path)
                rows.append({"path": str(path.relative_to(root)), "id": r.id, "status": "ok"})
            # discover also checks duplicate IDs
            discover(root)
            if args.json:
                print(json.dumps(rows, indent=2))
            else:
                for row in rows:
                    print(f"ok  {row['id']:28} {row['path']}")
                print(f"Validated {len(rows)} recipe(s)")
            return 0

    except RecipeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
