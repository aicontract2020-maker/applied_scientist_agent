"""Offline end-to-end software demo with explicitly synthetic review records.

This script NEVER calls a model or approves a real research proposal. It must not
be adapted into automatic approval of model plans. Artifacts live in runs/.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--out', default='runs/reviewed-software-demo')
args = parser.parse_args()
root = Path(args.out).resolve()
root.mkdir(parents=True, exist_ok=False)


def command(*argv):
    return json.loads(subprocess.check_output([sys.executable, '-m', 'research_harness', '--workspace', str(root / 'experiments'), *map(str, argv)], text=True))


here = Path(__file__).resolve().parent
protocol = json.loads(subprocess.check_output([sys.executable, str(here / 'prepare.py')], text=True))
execution = root / 'execution.json'
execution.write_text(json.dumps(protocol['execution'], indent=2))
proposal = command('plan', here / 'brief.md', '--response', here / 'plan-response.json', '--out', root / 'proposal')
review = command('review', proposal['proposal'], '--execution', execution, '--out', root / 'review')
command('approve', review['bundle'], '--sha256', review['sha256'], '--reviewer', 'SOFTWARE FIXTURE ONLY - not user approval')
command('register-review', review['bundle'])
decision = command('run', 'synthetic-reviewed-demo')
export = command('report', 'synthetic-reviewed-demo', '--out', root / 'REPORT.md')
print(json.dumps({'synthetic_only': True, 'status': decision['status'], 'report': export['report']}, indent=2))
