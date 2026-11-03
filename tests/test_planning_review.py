"""Offline model-boundary and workflow regression tests, not research experiments."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_harness.core import Workspace, digest
from research_harness.execution import file_hash, run
from research_harness.planning import make_plan, validate_plan
from research_harness.review import approve, build_review, register_review, report

ROOT = Path(__file__).resolve().parents[1]


class PlanningReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ws = Workspace(self.root / 'runs')
        self.response = json.loads((ROOT / 'examples/local_demo/plan-response.json').read_text())
        self.response_path = self.root / 'response.json'
        self.response_path.write_text(json.dumps(self.response))
        self.brief = ROOT / 'examples/local_demo/brief.md'
        self.execution = {
            'cwd': str(ROOT / 'examples/local_demo'),
            'command': ['{python}', 'worker.py', '--seed', '{seed}', '--output', '{output}'],
            'timeout_seconds': 5, 'compute_usd_per_hour': 0,
            'fixed_costs': {'data_usd': 0, 'storage_usd': 0, 'tuning_usd': 0},
            'inputs': {'worker.py': file_hash(ROOT / 'examples/local_demo/worker.py')},
        }
        self.execution_path = self.root / 'execution.json'
        self.execution_path.write_text(json.dumps(self.execution))

    def draft(self):
        return make_plan(self.brief, self.root / 'proposal', response_path=self.response_path)

    def bundle(self):
        draft = self.draft()
        return build_review(draft['proposal'], self.execution_path, self.root / 'review')

    def test_full_reviewed_workflow(self):
        review = self.bundle()
        bundle = review['bundle']
        self.assertFalse(self.ws.root.exists())
        with self.assertRaises(FileNotFoundError):
            register_review(self.ws, bundle)
        approve(bundle, review['sha256'], 'Synthetic test reviewer (not actual user approval)')
        register_review(self.ws, bundle)
        decision = run(self.ws, self.response['protocol']['id'])
        self.assertEqual(decision['status'], 'CONTINUE')
        target = self.root / 'REPORT.md'
        report(self.ws, self.response['protocol']['id'], target)
        text = target.read_text()
        self.assertIn('CONTINUE', text)
        self.assertIn('11', text)
        self.assertIn('22', text)
        self.assertIn('33', text)
        with self.assertRaises(FileExistsError):
            report(self.ws, self.response['protocol']['id'], target)

    def test_no_approval_without_exact_hash(self):
        review = self.bundle()
        with self.assertRaisesRegex(ValueError, 'exact reviewed'):
            approve(review['bundle'], 'wrong', 'Reviewer')
        self.assertFalse((self.root / 'review/approval.json').exists())

    def test_approval_does_not_survive_bundle_mutation(self):
        review = self.bundle()
        approve(review['bundle'], review['sha256'], 'Fixture reviewer')
        path = Path(review['bundle'])
        bundle = json.loads(path.read_text())
        bundle['content']['protocol']['minimum_effect'] = 0.01
        bundle['sha256'] = digest(bundle['content'])
        path.write_text(json.dumps(bundle))
        with self.assertRaisesRegex(ValueError, 'stale'):
            register_review(self.ws, path)

    def test_planner_cannot_supply_execution(self):
        bad = copy.deepcopy(self.response)
        bad['protocol']['execution'] = self.execution
        with self.assertRaisesRegex(ValueError, 'never execution'):
            validate_plan(bad)

    def test_missing_context_blocks_review(self):
        self.response.update(status='needs_context', protocol=None, questions=['Which dataset and budget?'])
        self.response_path.write_text(json.dumps(self.response))
        draft = self.draft()
        self.assertEqual(draft['status'], 'needs_context')
        with self.assertRaisesRegex(ValueError, 'Missing context'):
            build_review(draft['proposal'], self.execution_path, self.root / 'review')
        self.assertFalse((self.root / 'review').exists())

    def test_plan_rejects_unknowns_hidden_in_ready_response(self):
        self.response['questions'] = ['What budget?']
        with self.assertRaises(ValueError):
            validate_plan(self.response)

    def test_fixture_never_calls_external_provider(self):
        with patch('research_harness.planning.subprocess.Popen') as popen:
            self.assertTrue(self.draft()['replay_only'])
            popen.assert_not_called()

    def test_invalid_output_not_retried_and_preserved(self):
        self.response_path.write_text('not JSON')
        with self.assertRaises(ValueError):
            self.draft()
        self.assertEqual((self.root / 'proposal/response.json').read_text(), 'not JSON')
        self.assertFalse((self.root / 'proposal/proposal.json').exists())

    def test_codex_uses_readonly_structured_request(self):
        # Mock transport, never consume model usage in a unit test.
        from unittest.mock import MagicMock
        process = MagicMock()
        process.returncode = 0
        process.pid = 12345
        def transport(*args, **kwargs):
            command = args[0]
            self.assertIn('read-only', command)
            self.assertIn('--ignore-user-config', command)
            self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', command)
            self.assertIn('--output-schema', command)
            self.assertNotIn('--model', command)
            Path(command[command.index('--output-last-message') + 1]).write_text(json.dumps(self.response))
            return process
        with patch('research_harness.planning.subprocess.Popen', side_effect=transport), patch('research_harness.planning.os.killpg'):
            result = make_plan(self.brief, self.root / 'proposal', provider='codex')
        self.assertEqual(result['status'], 'ready_for_review')
        self.assertIsNone(json.loads((self.root / 'proposal/provider.json').read_text())['billing_usd'])

    def test_codex_timeout_keeps_failure_record(self):
        from unittest.mock import MagicMock
        process = MagicMock(pid=12345)
        process.communicate.side_effect = subprocess.TimeoutExpired('codex', 1)
        with patch('research_harness.planning.subprocess.Popen', return_value=process), patch('research_harness.planning.os.killpg'):
            with self.assertRaisesRegex(ValueError, 'timed out'):
                make_plan(self.brief, self.root / 'proposal', provider='codex')
        self.assertEqual(json.loads((self.root / 'proposal/provider.json').read_text())['status'], 'FAILED')
        self.assertFalse((self.root / 'proposal/proposal.json').exists())


if __name__ == '__main__':
    unittest.main()
