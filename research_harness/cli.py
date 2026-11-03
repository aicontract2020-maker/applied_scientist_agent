import argparse
import json
import sys
from pathlib import Path

from .core import Workspace
from .execution import run
from .planning import make_plan
from .review import approve, build_review, register_review, report


def main():
    parser = argparse.ArgumentParser(description="ResearchHarness: plan, review, execute, decide")
    parser.add_argument("--workspace", default="runs", help="Local experiment store (default: runs)")
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register", help="Manually register a trusted protocol; no review provenance")
    register.add_argument("protocol")
    record = sub.add_parser("record", help="Record one paired replication, including all costs")
    record.add_argument("id")
    record.add_argument("result")
    evaluate = sub.add_parser("evaluate", help="Show progress or a final decision")
    evaluate.add_argument("id")
    execute = sub.add_parser("run", help="Run preregistered trusted local commands (not a sandbox)")
    execute.add_argument("id")
    plan = sub.add_parser("plan", help="Draft a plan only; never register or execute it")
    plan.add_argument("brief")
    plan.add_argument("--provider", choices=("fixture", "codex"), default="fixture")
    plan.add_argument("--response", help="Saved response JSON for offline fixture replay")
    plan.add_argument("--model", help="Optional explicit Codex model; otherwise keep CLI default")
    plan.add_argument("--timeout", type=float, default=120)
    plan.add_argument("--out", required=True)
    review = sub.add_parser("review", help="Bind a draft to a separately reviewed execution config")
    review.add_argument("proposal")
    review.add_argument("--execution", required=True)
    review.add_argument("--out", required=True)
    approval = sub.add_parser("approve", help="Record human review of an exact bundle hash")
    approval.add_argument("bundle")
    approval.add_argument("--sha256", required=True)
    approval.add_argument("--reviewer", required=True)
    reviewed = sub.add_parser("register-review", help="Register a content-bound approved bundle")
    reviewed.add_argument("bundle")
    export = sub.add_parser("report", help="Export a decision report without overwriting files")
    export.add_argument("id")
    export.add_argument("--out", required=True)
    args = parser.parse_args()
    workspace = Workspace(args.workspace)
    try:
        if args.command == "register":
            output = {"registered": str(workspace.register(json.loads(Path(args.protocol).read_text())))}
        elif args.command == "record":
            output = workspace.record(args.id, json.loads(Path(args.result).read_text()))
        elif args.command == "run":
            output = run(workspace, args.id)
        elif args.command == "plan":
            output = make_plan(args.brief, args.out, args.provider, args.response, args.model, args.timeout)
        elif args.command == "review":
            output = build_review(args.proposal, args.execution, args.out)
        elif args.command == "approve":
            output = approve(args.bundle, args.sha256, args.reviewer)
        elif args.command == "register-review":
            output = register_review(workspace, args.bundle)
        elif args.command == "report":
            output = report(workspace, args.id, args.out)
        else:
            output = workspace.evaluate(args.id)
        print(json.dumps(output, indent=2, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
