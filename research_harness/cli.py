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
    memory = sub.add_parser("memory", help="Exchange conservative research history without models or images")
    memory.add_argument("--root", help="Source checkout whose history to manage (default: this checkout)")
    memory_commands = memory.add_subparsers(dest="memory_command", required=True)
    memory_commands.add_parser("status", help="Show scored/reserved holdout availability and retained decisions")
    memory_export = memory_commands.add_parser("export", help="Export shareable STOP/proposal text, source and exclusions")
    memory_export.add_argument("--out", required=True)
    memory_import = memory_commands.add_parser("import", help="Trust and merge a colleague's checked snapshot; never reclaim data")
    memory_import.add_argument("packet")
    study = sub.add_parser("study", help="Read-only autonomous run status and artifact audit")
    study_commands = study.add_subparsers(dest="study_command", required=True)
    study_list = study_commands.add_parser("list", help="List local autonomous runs and reservations")
    study_list.add_argument("--root", help="Source checkout (default: this checkout)")
    for name in ("status", "audit"):
        command = study_commands.add_parser(name, help="Inspect an existing run directory without modifying it")
        command.add_argument("--run", required=True)
    args = parser.parse_args()
    workspace = Workspace(args.workspace)
    try:
        if args.command == "study":
            from .study_inspection import list_studies, run_status, audit_run
            from .portable import ROOT
            if args.study_command == "list":
                output = list_studies(Path(args.root).resolve() if args.root else ROOT)
            elif args.study_command == "status":
                output = run_status(args.run)
            else:
                output = audit_run(args.run)
                print(json.dumps(output, indent=2, ensure_ascii=False))
                return 0 if output['audit_ok'] else 1
        elif args.command == "memory":
            from .portable import ROOT
            from .memory import status, export_memory, import_memory
            root = Path(args.root).resolve() if args.root else ROOT
            if args.memory_command == "status":
                output = status(root)
            elif args.memory_command == "export":
                output = export_memory(root, args.out)
            else:
                output = import_memory(root, args.packet)
        elif args.command == "setup-assets":
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
