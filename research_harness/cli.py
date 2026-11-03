import argparse
import json
import sys
from pathlib import Path
from .core import Workspace
from .execution import run


def main():
    parser = argparse.ArgumentParser(description="Preregister, record, and decide research experiments")
    parser.add_argument("--workspace", default="runs", help="Local experiment store (default: runs)")
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register", help="Freeze a protocol before any experiment")
    register.add_argument("protocol")
    record = sub.add_parser("record", help="Record one paired replication, including all costs")
    record.add_argument("id")
    record.add_argument("result")
    evaluate = sub.add_parser("evaluate", help="Show progress or a final decision")
    evaluate.add_argument("id")
    execute = sub.add_parser("run", help="Run preregistered trusted local commands (not a sandbox)")
    execute.add_argument("id")
    args = parser.parse_args()
    workspace = Workspace(args.workspace)
    try:
        if args.command == "register":
            output = {"registered": str(workspace.register(json.loads(Path(args.protocol).read_text())))}
        elif args.command == "record":
            output = workspace.record(args.id, json.loads(Path(args.result).read_text()))
        elif args.command == "run":
            output = run(workspace, args.id)
        else:
            output = workspace.evaluate(args.id)
        print(json.dumps(output, indent=2, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
