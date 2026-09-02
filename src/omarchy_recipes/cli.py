from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import agent as agent_mod, authoring, conflicts as conflicts_mod, contribution, inspection, lint as lint_mod, sources as sources_mod
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

    # ---- authoring support (Milestone 2) --------------------------------
    #
    # These exist so an authoring agent never has to run its own shell: it
    # reads facts, asks about conflicts, and submits a draft for validation.

    sp2 = sub.add_parser("sources", help="list recipe sources and their trust level")
    sp2.add_argument("--json", action="store_true")

    ip2 = sub.add_parser("inspect", help="read-only snapshot of the machine, for conflict detection")
    ip2.add_argument("domains", nargs="*", help=f"default: all ({', '.join(sorted(inspection.INSPECTORS))})")
    ip2.add_argument("--json", action="store_true")

    cp2 = sub.add_parser("conflicts", help="check claimed resources against the machine; reads JSON on stdin")
    cp2.add_argument("--json", action="store_true")

    lp2 = sub.add_parser("lint", help="static and safety checks for a recipe file, or a draft on stdin")
    lp2.add_argument("path", nargs="?", help="recipe file; omit to read a draft from stdin")
    lp2.add_argument("--json", action="store_true")

    np2 = sub.add_parser("create", help="save a drafted recipe to the local collection; reads the script on stdin")
    np2.add_argument("recipe_id")
    np2.add_argument("--json", action="store_true")
    np2.add_argument("--overwrite", action="store_true")
    np2.add_argument("--reviewed", action="store_true", help="record that a human has reviewed this draft")
    np2.add_argument("--not-ai", dest="not_ai", action="store_true", help="record that no agent authored this draft")
    np2.add_argument("--strict", action="store_true", help="refuse to save on warnings, not just errors")
    np2.add_argument("--body", default=None, help="recipe text as an argument, instead of on stdin")

    ap2 = sub.add_parser("agent", help="AI-assisted authoring: plan a change, then draft a recipe")
    asub = ap2.add_subparsers(dest="agent_command", required=True)

    agp = asub.add_parser("providers", help="list AI providers and whether they are installed")
    agp.add_argument("--json", action="store_true")

    agl = asub.add_parser("plan", help="ask what a request would touch, and check for conflicts")
    agl.add_argument("request")
    agl.add_argument("--json", action="store_true")
    agl.add_argument("--provider", default=None)
    agl.add_argument("--model", default=None)
    agl.add_argument("--answer", action="append", dest="answers", default=None,
                     help="an answer to one of the agent's questions, or a correction; repeatable")
    agl.add_argument("--domain", action="append", dest="domains", default=None,
                     help="inspection domain to gather; repeatable (default: config-files, keybindings, packages, services)")

    agd = asub.add_parser("draft", help="generate the recipe text; reads the plan JSON on stdin")
    agd.add_argument("request")
    agd.add_argument("--json", action="store_true")
    agd.add_argument("--provider", default=None)
    agd.add_argument("--model", default=None)
    agd.add_argument("--plan", default=None, help="plan JSON as an argument, instead of on stdin")

    bp2 = sub.add_parser("contribute", help="prepare a pull request offering a local recipe upstream")
    bp2.add_argument("recipe_id")
    bp2.add_argument("--json", action="store_true")
    bp2.add_argument("--testing", default="", help="how the recipe was tested; goes in the pull request body")
    bp2.add_argument("--commit", action="store_true", help="actually branch and commit (default is a dry run)")
    bp2.add_argument("--push", action="store_true", help="push the branch and open a pull request")
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

        if args.command == "sources":
            rows = [s.to_dict() for s in sources_mod.sources(root)]
            if args.json:
                emit({"sources": rows, "workspace": str(sources_mod.workspace_root())})
            else:
                for row in rows:
                    mark = "present" if row["exists"] else "absent"
                    print(f"{row['name']:10} {mark:8} {row['path']}")
            return 0

        if args.command == "inspect":
            try:
                result = inspection.inspect(args.domains or None)
            except ValueError as e:
                raise RecipeError(str(e)) from e
            if args.json:
                emit({"inspection": {name: d.to_dict() for name, d in result.items()}})
            else:
                for name, d in result.items():
                    state = f"{len(d.items)} item(s)" if d.available else f"unavailable: {d.error}"
                    print(f"{name:14} {state}")
            return 0

        if args.command == "conflicts":
            raw = sys.stdin.read()
            try:
                payload = json.loads(raw) if raw.strip() else {}
            except ValueError as e:
                raise RecipeError(f"expected JSON on stdin: {e}") from e
            resources = payload.get("resources") if isinstance(payload, dict) else payload
            if not isinstance(resources, list):
                raise RecipeError('expected {"resources": [...]} on stdin')
            report = conflicts_mod.check(resources, root)
            if args.json:
                emit(report)
            else:
                for finding in report["findings"]:
                    print(f"{finding['status']:8} {finding['severity']:5} {finding['detail']}")
                print(f"{report['conflicts']} conflict(s), {report['blocking']} blocking")
            # Non-zero when the user must decide something, so a caller that
            # ignores the report still cannot barrel past a blocking conflict.
            return 3 if report["requires_user_decision"] else 0

        if args.command == "lint":
            if args.path:
                report = lint_mod.lint(Path(args.path))
            else:
                report = authoring.draft_report(sys.stdin.read())
            if args.json:
                emit({"lint": report})
            else:
                for finding in report["findings"]:
                    where = f"line {finding['line']}" if finding["line"] else "recipe"
                    print(f"{finding['severity']:7} {finding['rule']:22} {where:10} {finding['message']}")
                print(f"{report['errors']} error(s), {report['warnings']} warning(s)")
            return 0 if report["ok"] else 2

        if args.command == "agent":
            if args.agent_command == "providers":
                rows = [p.to_dict() for p in agent_mod.providers()]
                if args.json:
                    emit({"providers": rows, "default": agent_mod.default_provider()})
                else:
                    for row in rows:
                        state = "available" if row["available"] else row["reason"]
                        print(f"{row['name']:10} {state}")
                return 0

            if args.agent_command == "plan":
                # Only the domains the request plausibly needs: a plan should
                # not ship the machine's entire package list to a model.
                domains = args.domains or ["config-files", "keybindings", "packages", "services"]
                facts = {name: d.to_dict() for name, d in inspection.inspect(domains).items()}
                plan = agent_mod.plan(args.request, root, inspection_data=facts,
                                      notes=args.answers or None,
                                      provider=args.provider, model=args.model)
                report = conflicts_mod.check(plan.get("resources") or [], root)
                payload = {"plan": plan, "conflicts": report}
                if args.json:
                    emit(payload)
                else:
                    print(plan.get("summary") or "(no summary)")
                    for question in plan.get("questions") or []:
                        print(f"question: {question}")
                    for finding in report["findings"]:
                        print(f"{finding['status']:8} {finding['severity']:5} {finding['detail']}")
                return 3 if report["requires_user_decision"] else 0

            if args.agent_command == "draft":
                raw = args.plan if args.plan is not None else sys.stdin.read()
                try:
                    payload = json.loads(raw) if raw.strip() else {}
                except ValueError as e:
                    raise RecipeError(f"expected the plan JSON on stdin: {e}") from e
                plan = payload.get("plan") or payload
                findings = (payload.get("conflicts") or {}).get("findings") or []
                decisions = payload.get("decisions") or {}

                # Refuse to draft while a blocking conflict is unresolved. The
                # spec requires the user to decide, not the agent.
                unresolved = [
                    f for f in findings
                    if f.get("severity") == conflicts_mod.BLOCK
                    and f.get("status") == conflicts_mod.CONFLICT
                    and not decisions.get(str((f.get("resource") or {}).get("type", "")))
                ]
                if unresolved:
                    raise RecipeError(
                        f"{len(unresolved)} blocking conflict(s) not resolved; "
                        "supply a `decisions` object naming the chosen resolution")

                text = agent_mod.draft(args.request, root, plan, findings=findings,
                                       decisions=decisions, provider=args.provider, model=args.model)
                report = authoring.draft_report(text)
                if args.json:
                    emit({"recipe_id": plan.get("recipe_id") or "", "recipe": text, "lint": report})
                else:
                    sys.stdout.write(text if text.endswith("\n") else text + "\n")
                    for finding in report["findings"]:
                        print(f"{finding['severity']:7} {finding['rule']:22} {finding['message']}", file=sys.stderr)
                return 0 if report["ok"] else 2

        if args.command == "contribute":
            result = contribution.submit(
                root, args.recipe_id, testing=args.testing,
                dry_run=not (args.commit or args.push), push=args.push,
            )
            if args.json:
                emit(result)
            else:
                if result.get("blockers"):
                    for blocker in result["blockers"]:
                        print(f"blocked: {blocker}", file=sys.stderr)
                for duplicate in result.get("duplicates", []):
                    print(f"possible duplicate: {duplicate['id']} ({duplicate['title']})", file=sys.stderr)
                for step in result.get("steps", []):
                    print(f"{'would run' if result.get('dry_run') else 'ran'}: {step}")
                if result.get("submitted"):
                    print(f"committed on {result['branch']}")
            return 0 if (result.get("submitted") or result.get("dry_run")) else 2

        if args.command == "create":
            result = authoring.save(
                root,
                args.recipe_id,
                args.body if args.body is not None else sys.stdin.read(),
                generated_with_ai=not args.not_ai,
                reviewed=args.reviewed,
                overwrite=args.overwrite,
                allow_warnings=not args.strict,
            )
            if args.json:
                emit(result)
            else:
                if result["saved"]:
                    print(f"saved {result['path']}")
                else:
                    print(f"not saved: {result['reason']}", file=sys.stderr)
                for finding in result["lint"]["findings"]:
                    print(f"{finding['severity']:7} {finding['rule']:22} {finding['message']}", file=sys.stderr)
            return 0 if result["saved"] else 2

    except RecipeError as e:
        if getattr(args, "json", False):
            emit({"error": str(e)})
        else:
            print(f"error: {e}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
