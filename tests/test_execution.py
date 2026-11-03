"""Synthetic software checks only; no scientific hypothesis is being tested."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from research_harness.core import Workspace
from research_harness.execution import file_hash, run

ROOT = Path(__file__).resolve().parents[1]
WORKER = '''import json, sys
from pathlib import Path
seed, output = int(sys.argv[1]), Path(sys.argv[2])
print("synthetic software fixture", seed)
output.write_text(json.dumps({
    "seed": seed, "baseline_score": 10, "candidate_score": 9,
    "validity": {"No test leakage": True, "Evaluation implementation unchanged": True},
    "measurements": {"storage_byte_hours": 10, "latency_ms": 2}
}))
'''


class ExecutionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.worker = self.root / 'worker.py'
        self.worker.write_text(WORKER)
        self.ws = Workspace(self.root / 'runs')
        self.p = json.loads((ROOT / 'examples/protocol.json').read_text())
        self.p['execution'] = {
            'cwd': str(self.root.resolve()),
            'command': ['{python}', 'worker.py', '{seed}', '{output}'],
            'timeout_seconds': 2,
            'compute_usd_per_hour': 1,
            'fixed_costs': {'data_usd': 0.1, 'storage_usd': 0, 'tuning_usd': 0},
            'inputs': {'worker.py': file_hash(self.worker)},
        }

    def register(self):
        self.p['execution']['inputs']['worker.py'] = file_hash(self.worker)
        self.ws.register(self.p)

    def events(self):
        return self.ws.load(self.p['id'])[2]

    def test_end_to_end_and_idempotent_closed_run(self):
        self.register()
        report = run(self.ws, self.p['id'])
        self.assertEqual(report['status'], 'CONTINUE')
        self.assertEqual(report['n'], 3)
        self.assertEqual(report['cost_totals']['data_usd'], 0.1 * 3)
        self.assertEqual(report['cost_totals']['storage_byte_hours'], 30)
        self.assertEqual(len([e for e in self.events() if e['event'] == 'ATTEMPT_STARTED']), 3)
        self.assertEqual(run(self.ws, self.p['id']), report)
        self.assertIn('synthetic', (self.ws.folder(self.p['id']) / 'attempts/seed-11/stdout.log').read_text())

    def test_failed_attempt_charged_and_never_retried(self):
        self.worker.write_text('raise SystemExit(7)\n')
        self.register()
        report = run(self.ws, self.p['id'])
        self.assertEqual(report['status'], 'STOP')
        self.assertEqual(report['n'], 0)
        self.assertGreater(report['total_usd'], 0.1)
        self.assertEqual(len([e for e in self.events() if e['event'] == 'ATTEMPT_STARTED']), 1)
        self.assertEqual(run(self.ws, self.p['id']), report)

    def test_timeout_stops(self):
        self.worker.write_text('import time\ntime.sleep(30)\n')
        self.p['execution']['timeout_seconds'] = 0.05
        self.register()
        report = run(self.ws, self.p['id'])
        self.assertEqual(report['status'], 'STOP')
        self.assertIn('timed out', report['reason'])

    def test_budget_prevents_process_start(self):
        self.p['budget_usd'] = 0.05
        self.register()
        report = run(self.ws, self.p['id'])
        self.assertEqual(report['status'], 'STOP')
        self.assertEqual(report['total_usd'], 0)
        self.assertFalse(any(e['event'] == 'ATTEMPT_STARTED' for e in self.events()))

    def test_source_change_rejected_before_launch(self):
        self.register()
        self.worker.write_text('print("changed")\n')
        with self.assertRaisesRegex(ValueError, 'Input changed'):
            run(self.ws, self.p['id'])
        self.assertFalse(any(e['event'] == 'ATTEMPT_STARTED' for e in self.events()))

    def test_missing_invalid_and_wrong_seed_outputs_stop(self):
        for index, script in enumerate(('print("no output")', 'import sys; open(sys.argv[2], "w").write("not JSON")', WORKER.replace('"seed": seed', '"seed": 999'))):
            self.p['id'] = f'malformed-{index}'
            self.worker.write_text(script)
            self.register()
            report = run(self.ws, self.p['id'])
            self.assertEqual(report['status'], 'STOP')
            self.assertGreater(report['total_usd'], 0)

    def test_interrupted_attempt_does_not_retry(self):
        self.register()
        self.ws.append(self.ws.folder(self.p['id']), {'event': 'ATTEMPT_STARTED', 'attempt': 'seed-11'})
        with self.assertRaisesRegex(ValueError, 'reconciliation'):
            run(self.ws, self.p['id'])

    def test_argv_has_no_shell_expansion(self):
        self.worker.write_text(WORKER + '\nassert sys.argv[3] == "$(touch SHOULD_NOT_EXIST)"\n')
        self.p['execution']['command'].append('$(touch SHOULD_NOT_EXIST)')
        self.register()
        self.assertEqual(run(self.ws, self.p['id'])['status'], 'CONTINUE')
        self.assertFalse((self.root / 'SHOULD_NOT_EXIST').exists())

    def test_managed_results_cannot_bypass_runner(self):
        self.register()
        result = json.loads((ROOT / 'examples/result.json').read_text())
        with self.assertRaisesRegex(ValueError, 'completed execution'):
            self.ws.record(self.p['id'], result)


if __name__ == '__main__':
    unittest.main()
