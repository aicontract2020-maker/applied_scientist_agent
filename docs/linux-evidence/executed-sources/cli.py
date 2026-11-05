import argparse
import json
import subprocess
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
    autonomous = sub.add_parser("autonomous", help="Run one externally isolated agent-authored SR research cycle (macOS/Linux)")
    autonomous.add_argument("--out", required=True)
    autonomous.add_argument("--study", help="A separately frozen task directory")
    autonomous.add_argument("--literature", action="store_true", help="Require agent live search and independently fetched primary papers")
    sub.add_parser("setup-assets", help="Download and verify pinned SR repositories, weights and data")
    health = sub.add_parser("doctor", help="Check dependencies, login, assets and actual OS isolation; no model call")
    health.add_argument("--network", action="store_true")
    research = sub.add_parser("research", help="Prepare fresh SR holdout, run one autonomous cycle, preserve all evidence")
    research.add_argument("--id", required=True, help="New unique study name; cannot overwrite/retry")
    args = parser.parse_args()
    workspace = Workspace(args.workspace)
    try:
        if args.command == "setup-assets":
            from .portable import setup_assets
            output = setup_assets()
        elif args.command == "doctor":
            from .doctor import doctor
            output = doctor(args.network)
            print(json.dumps(output, indent=2, ensure_ascii=False))
            return 0 if output['ok'] else 1
        elif args.command == "research":
            from .onboarding import research
            output = research(args.id)
        elif args.command == "autonomous":
            from .autonomy import AutonomousStudy
            if args.literature:
                if not args.study: raise ValueError("--literature requires --study")
                from .literature_study import LiteratureStudy
                output = LiteratureStudy(args.out, args.study).launch()
            else:
                output = AutonomousStudy(args.out, args.study).launch()
        elif args.command == "register":
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
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
