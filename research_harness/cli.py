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
    research = sub.add_parser("research", help="Run an SR cycle or an explicit human-reviewed tabular stage")
    research.add_argument("--id", required=True, help="New unique study name; cannot overwrite/retry")
    research.add_argument("--task", default="swinir-s-x2", help="Built-in task; tabular workflow requires an explicit stage")
    research.add_argument("--stage",choices=("propose","execute"),help="Explicit tabular workflow stage; proposal stops for human review")
    research.add_argument("--baseline",help="Qualified baseline for tabular proposal stage")
    research.add_argument("--review",help="Exact approved trial for tabular execution stage")
    research.add_argument("--data-review",help="Candidate-scoped qualification for tabular proposal stage only")
    research.add_argument("--intended-use",help="Exact candidate intended use; forbidden as an execution override")
    task = sub.add_parser("task", help="Inspect built-in task contracts and supported capabilities (no execution)")
    task_commands = task.add_subparsers(dest="task_command", required=True)
    task_commands.add_parser("list")
    task_show = task_commands.add_parser("show")
    task_show.add_argument("id")
    task_caps=task_commands.add_parser("capabilities",help="Workflow capabilities separate from immutable evaluation bindings")
    task_caps.add_argument("id")
    data_review = sub.add_parser("data-review", help="Offline metadata qualification; never authorizes experiments")
    dc = data_review.add_subparsers(dest="data_review_command", required=True)
    dc.add_parser("template", help="Write an unfilled metadata template").add_argument("--out", required=True)
    dp = dc.add_parser("prepare", help="Freeze explicitly selected metadata evidence; no data scoring")
    dp.add_argument("draft"); dp.add_argument("--out", required=True)
    dp = dc.add_parser("inspect", help="Read-only integrity and qualification status")
    dp.add_argument("packet")
    dp = dc.add_parser("decide", help="Record exact-hash human review for protocol design only")
    dp.add_argument("packet"); dp.add_argument("--sha256", required=True)
    dp.add_argument("--reviewer", required=True); dp.add_argument("--decision", choices=("accept", "reject"), required=True)
    dp.add_argument("--reason", required=True)
    tabular = sub.add_parser("tabular", help="Reviewed baseline/feature trials, exclusion memory and private evidence")
    tabular_commands = tabular.add_subparsers(dest="tabular_command", required=True)
    tabular_fetch = tabular_commands.add_parser("fetch", help="Download pinned public UCI data only; no scoring")
    tabular_fetch.add_argument("--out", required=True)
    tabular_prepare = tabular_commands.add_parser("prepare", help="Prepare pinned UCI data and a review packet; no training")
    tabular_prepare.add_argument("--data", required=True)
    tabular_prepare.add_argument("--out", required=True)
    tabular_prepare.add_argument("--data-review", required=True, help="Accepted C4 metadata packet; not execution approval")
    tabular_prepare.add_argument("--intended-use", required=True, help="Exact use stated in accepted metadata")
    for name in ("verify", "approve", "baseline", "preflight"):
        command = tabular_commands.add_parser(name)
        command.add_argument("--review", required=True)
        if name == "approve":
            command.add_argument("--sha256", required=True)
            command.add_argument("--reviewer", required=True)
    tabular_commands.add_parser("probe", help="Test actual task isolation using synthetic secrets only")
    tabular_commands.add_parser("screen-history", help="Read published/local task-scoped proposal closures")
    audit_baseline = tabular_commands.add_parser("audit-baseline", help="Read-only completed baseline audit; never execute historical sources")
    audit_baseline.add_argument("--review", required=True)
    screen = tabular_commands.add_parser("screen", help="Screen one fixed calibration proposal using existing validation records only")
    screen.add_argument("--baseline", required=True)
    screen.add_argument("--protocol", required=True)
    screen.add_argument("--out", required=True)
    for name in ("verify-screen", "retain-screen"):
        command = tabular_commands.add_parser(name)
        command.add_argument("--baseline", required=True)
        command.add_argument("--proposal", required=True)
    proposer=tabular_commands.add_parser("propose", help="One isolated literature/feature proposal; no data rows, training or scoring")
    proposer.add_argument("--baseline",required=True); proposer.add_argument("--out",required=True)
    proposer.add_argument("--recover-launch",help="Explicit one-time recovery of a retained pre-agent Node initialization abort only")
    proposer.add_argument("--data-review",required=True); proposer.add_argument("--intended-use",required=True)
    trial=tabular_commands.add_parser("prepare-trial", help="Freeze one concrete feature study for human review; no real experiment")
    trial.add_argument("--baseline",required=True); trial.add_argument("--proposal",required=True)
    trial.add_argument("--literature",required=True); trial.add_argument("--out",required=True)
    trial.add_argument("--data-review",required=True); trial.add_argument("--intended-use",required=True)
    for name in ("verify-trial","approve-trial","run-trial","audit-trial","preflight-trial"):
        command=tabular_commands.add_parser(name)
        command.add_argument("--review",required=True)
        if name=="approve-trial":
            command.add_argument("--sha256",required=True); command.add_argument("--reviewer",required=True)
    tab_memory=tabular_commands.add_parser("memory",help="Conservative tabular exclusion handoff; no data reclamation")
    tab_memory.add_argument("--root",help="Checkout to inspect/import/export (default: current checkout)")
    tm=tab_memory.add_subparsers(dest="tabular_memory_command",required=True)
    tm.add_parser("status")
    tm.add_parser("export").add_argument("--out",required=True)
    tm.add_parser("import").add_argument("packet")
    tm.add_parser("retain").add_argument("--review",required=True)
    tab_evidence=tabular_commands.add_parser("evidence",help="PRIVATE full evidence, including labels and paper text; no publishing")
    te=tab_evidence.add_subparsers(dest="tabular_evidence_command",required=True)
    command=te.add_parser("export"); command.add_argument("--review",required=True); command.add_argument("--out",required=True)
    te.add_parser("verify").add_argument("packet")
    command=te.add_parser("unpack"); command.add_argument("packet"); command.add_argument("--out",required=True)
    airfoil = sub.add_parser("airfoil", help="Pinned condition-grouped public task; baseline qualification requires review")
    ac = airfoil.add_subparsers(dest="airfoil_command", required=True)
    ac.add_parser("fetch").add_argument("--out", required=True)
    ap = ac.add_parser("prepare"); ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--data-review", required=True, help="Accepted C4 metadata packet; not execution approval")
    ap.add_argument("--intended-use", required=True, help="Exact use stated in accepted metadata")
    for name in ("review", "approve", "baseline", "audit", "preflight"):
        ap = ac.add_parser(name); ap.add_argument("--review", required=True)
        if name == "approve":
            ap.add_argument("--sha256", required=True); ap.add_argument("--reviewer", required=True)
    ap=ac.add_parser("prepare-trial"); ap.add_argument("--baseline",required=True); ap.add_argument("--proposal",required=True); ap.add_argument("--out",required=True)
    ap.add_argument("--data-review",required=True); ap.add_argument("--intended-use",required=True)
    for name in ("approve-trial","execute-trial","audit-trial","preflight-trial"):
        ap=ac.add_parser(name); ap.add_argument("--review",required=True)
        if name=="approve-trial": ap.add_argument("--sha256",required=True); ap.add_argument("--reviewer",required=True)
    memory = sub.add_parser("memory", help="Exchange conservative research history without models or images")
    memory.add_argument("--root", help="Source checkout whose history to manage (default: this checkout)")
    memory_commands = memory.add_subparsers(dest="memory_command", required=True)
    memory_commands.add_parser("status", help="Show scored/reserved holdout availability and retained decisions")
    memory_export = memory_commands.add_parser("export", help="Export shareable STOP/proposal text, source and exclusions")
    memory_export.add_argument("--out", required=True)
    memory_import = memory_commands.add_parser("import", help="Trust and merge a colleague's checked snapshot; never reclaim data")
    memory_import.add_argument("packet")
    study = sub.add_parser("study", help="Inspect and exchange autonomous research evidence")
    study_commands = study.add_subparsers(dest="study_command", required=True)
    study_list = study_commands.add_parser("list", help="List local autonomous runs and reservations")
    study_list.add_argument("--root", help="Source checkout (default: this checkout)")
    for name in ("status", "audit"):
        command = study_commands.add_parser(name, help="Inspect an existing run directory without modifying it")
        command.add_argument("--run", required=True)
    study_export = study_commands.add_parser("export", help="Export audited allowlisted run evidence; review text before sharing")
    study_export.add_argument("--run", required=True)
    study_export.add_argument("--out", required=True)
    study_verify = study_commands.add_parser("verify", help="Verify and independently audit an evidence packet offline")
    study_verify.add_argument("packet")
    study_unpack = study_commands.add_parser("unpack", help="Create a new review-only container from verified evidence")
    study_unpack.add_argument("packet")
    study_unpack.add_argument("--out", required=True)
    args = parser.parse_args()
    workspace = Workspace(args.workspace)
    try:
        if args.command == "data-review":
            from . import data_qualification as dq
            if args.data_review_command == "template": output = dq.template(args.out)
            elif args.data_review_command == "prepare": output = dq.prepare(args.draft, args.out)
            elif args.data_review_command == "inspect": output = dq.inspect(args.packet)
            else: output = dq.decide(args.packet, args.sha256, args.reviewer, args.decision, args.reason)
        elif args.command == "airfoil":
            from . import airfoil_baseline as ab
            if args.airfoil_command.endswith("-trial"):
                from . import airfoil_trial as at
                if args.airfoil_command=="prepare-trial": output=at.prepare(args.baseline,args.proposal,args.out,data_review=args.data_review,intended_use=args.intended_use)
                elif args.airfoil_command=="preflight-trial": output=at.preflight(args.review)
                elif args.airfoil_command=="approve-trial": output=at.approve(args.review,args.sha256,args.reviewer)
                elif args.airfoil_command=="audit-trial": output=at.audit(args.review)
                else:
                    output=at.execute(args.review)
                    print(json.dumps(output,indent=2,ensure_ascii=False))
                    return 0 if output['measurement_valid'] else 1
            elif args.airfoil_command == "fetch":
                from .airfoil_data import fetch
                output = fetch(args.out)
            elif args.airfoil_command == "prepare": output = ab.prepare(args.data, args.out, args.data_review, args.intended_use)
            elif args.airfoil_command == "preflight": output = ab.preflight(args.review)
            elif args.airfoil_command == "review":
                packet, _ = ab.load_review(args.review)
                output = {"sha256": packet["sha256"], "content": packet["content"]}
            elif args.airfoil_command == "approve": output = ab.approve(args.review, args.sha256, args.reviewer)
            elif args.airfoil_command == "audit": output = ab.audit(args.review)
            else:
                output = ab.execute(args.review)
                print(json.dumps(output, indent=2, ensure_ascii=False))
                return 0 if output["measurement_valid"] else 1
        elif args.command == "tabular":
            from .tabular_baseline import prepare, load_review, approve as approve_baseline, execute as execute_baseline
            if args.tabular_command == "memory":
                from .portable import ROOT
                from .tabular_memory import snapshot,export_memory,import_memory,retain_trial
                root=Path(args.root).resolve() if args.root else ROOT
                if args.tabular_memory_command=='status':
                    records=snapshot(root)
                    output={'records':records,'reserved_or_consumed_scopes':len(records),
                            'known_excluded_feature_groups':len({k for r in records for k in r['data_keys'] or []}),
                            'note':'Offline exclusions, not a global lock or authenticated execution evidence'}
                elif args.tabular_memory_command=='export': output=export_memory(args.out,root)
                elif args.tabular_memory_command=='import': output=import_memory(args.packet,root)
                else: output=retain_trial(args.review,root)
            elif args.tabular_command == "evidence":
                from .tabular_evidence import export as export_evidence,verify as verify_evidence,unpack as unpack_evidence
                if args.tabular_evidence_command=='export': output=export_evidence(args.review,args.out)
                elif args.tabular_evidence_command=='unpack': output=unpack_evidence(args.packet,args.out)
                else:
                    output=verify_evidence(args.packet)
                    print(json.dumps(output,indent=2,ensure_ascii=False))
                    return 0 if output['audit_ok'] else 1
            elif args.tabular_command == "propose":
                from .tabular_proposer import propose
                output=propose(args.baseline,args.out,recover_launch=args.recover_launch,data_review=args.data_review,intended_use=args.intended_use)
            elif args.tabular_command == "prepare-trial":
                from .tabular_trial import prepare as prepare_trial
                output=prepare_trial(args.baseline,args.proposal,args.out,args.literature,data_review=args.data_review,intended_use=args.intended_use)
            elif args.tabular_command in ("verify-trial","approve-trial","run-trial","audit-trial","preflight-trial"):
                from .tabular_trial import load_trial,approve_trial,execute_trial,audit_trial,preflight_trial
                if args.tabular_command=="approve-trial": output=approve_trial(args.review,args.sha256,args.reviewer)
                elif args.tabular_command=="preflight-trial": output=preflight_trial(args.review)
                elif args.tabular_command in ("run-trial","audit-trial"):
                    output=(execute_trial if args.tabular_command=="run-trial" else audit_trial)(args.review)
                    print(json.dumps(output,indent=2,ensure_ascii=False))
                    return 0 if output.get('audit_ok',output.get('measurement_valid',False)) else 1
                else:
                    envelope,_,_=load_trial(args.review)
                    output={'integrity_ok':True,'sha256':envelope['sha256'],'status':'AWAITING_RESEARCH_REVIEW'}
            elif args.tabular_command == "screen-history":
                from .tabular_screen import history_records
                output = history_records()
            elif args.tabular_command == "audit-baseline":
                from .tabular_audit import audit_baseline
                output = audit_baseline(args.review)
                print(json.dumps(output, indent=2, ensure_ascii=False))
                return 0 if output['audit_ok'] else 1
            elif args.tabular_command in ("screen", "verify-screen", "retain-screen"):
                from .tabular_screen import screen, verify_screen, retain_screen
                if args.tabular_command == "screen":
                    output = screen(args.baseline, args.protocol, args.out)
                elif args.tabular_command == "retain-screen":
                    output = retain_screen(args.baseline, args.proposal)
                else:
                    _, result, scope = verify_screen(args.baseline, args.proposal)
                    output = {'screen_integrity_ok': True, 'read_only': True, 'scope': scope, 'result': result}
            elif args.tabular_command == "fetch":
                from .tabular_data import fetch_abalone
                output = fetch_abalone(args.out)
            elif args.tabular_command == "prepare":
                output = prepare(args.data, args.out, args.data_review, args.intended_use)
            elif args.tabular_command == "preflight":
                from .tabular_baseline import preflight
                output = preflight(args.review)
            elif args.tabular_command == "verify":
                packet, _ = load_review(args.review)
                output = {'review_integrity_ok': True, 'sha256': packet['sha256'], 'counts': packet['content']['counts'],
                          'note': 'Content integrity only; not approval, execution success or scientific validity'}
            elif args.tabular_command == "approve":
                output = approve_baseline(args.review, args.sha256, args.reviewer)
            elif args.tabular_command == "probe":
                from .tabular_sandbox import isolation_probe
                from .portable import ROOT
                output = isolation_probe(ROOT, ROOT/'.venv-tabular/bin/python')
            else:
                output = execute_baseline(args.review)
                print(json.dumps(output, indent=2, ensure_ascii=False))
                return 0 if output['measurement_valid'] else 1
        elif args.command == "task":
            from .task_contracts import list_tasks, contract, binding, capabilities
            output = capabilities(args.id) if args.task_command=='capabilities' else (list_tasks() if args.task_command == "list" else dict(contract(args.id), binding=binding(args.id)))
        elif args.command == "study":
            from .study_inspection import list_studies, run_status, audit_run
            from .portable import ROOT
            if args.study_command in ("export", "verify", "unpack"):
                from .evidence_bundle import export_bundle, verify_bundle, unpack_bundle
                if args.study_command == "export":
                    output = export_bundle(args.run, args.out)
                elif args.study_command == "unpack":
                    output = unpack_bundle(args.packet, args.out)
                else:
                    output = verify_bundle(args.packet)
                    print(json.dumps(output, indent=2, ensure_ascii=False))
                    return 0 if output['audit_ok'] else 1
            elif args.study_command == "list":
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
            output = research(args.id, task=args.task,stage=args.stage,baseline=args.baseline,review=args.review,
                              data_review=args.data_review,intended_use=args.intended_use)
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
