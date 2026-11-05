"""Task portability checks use synthetic numeric records only."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from examples.tabular_demo.workflow import fixture, demonstrate
from research_harness.core import Workspace, COST_FIELDS, digest, validate_protocol
from research_harness.regression_evaluation import evaluate_predictions
from research_harness.task_contracts import (binding, contract, validate_binding, validate_sr_policy,
                                            SR_TASK, REGRESSION_TASK)


class TaskContractsTest(unittest.TestCase):
    def setUp(self):
        self.protocol, self.targets, self.baseline, self.candidate = fixture()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def scores(self):
        return evaluate_predictions(self.protocol, self.targets, self.baseline, self.candidate)

    def rebind(self):
        self.protocol['dataset']['sha256'] = digest(self.targets)
        self.protocol['intervention']['baseline_sha256'] = digest(self.baseline)
        self.protocol['intervention']['candidate_sha256'] = digest(self.candidate)

    def decision(self, name):
        workspace = Workspace(self.root/name)
        workspace.register(self.protocol)
        result = dict(self.scores(), seed=0, artifact='SYNTHETIC',
                      validity={key: True for key in self.protocol['validity_checks']},
                      costs={key: 0 for key in COST_FIELDS})
        return workspace, result, workspace.record(self.protocol['id'], result)

    def test_closed_registry_and_immutable_bindings(self):
        for value in ({'id': REGRESSION_TASK}, {**binding(REGRESSION_TASK), 'version': True},
                      {**binding(REGRESSION_TASK), 'sha256': '0'*64},
                      {**binding(REGRESSION_TASK), 'module': 'os'}, binding(SR_TASK) | {'version': 99}):
            with self.assertRaises(ValueError): validate_binding(value)
        with self.assertRaises(ValueError): contract('os.system')
        changed = contract(REGRESSION_TASK); changed['autonomous_research'] = True
        self.assertFalse(contract(REGRESSION_TASK)['autonomous_research'])

    def test_research_capability_fails_before_any_side_effect(self):
        from research_harness.onboarding import research
        with patch('research_harness.state_lock.research_lock') as lock, patch('research_harness.doctor.doctor') as doctor:
            for key in (REGRESSION_TASK, 'unknown'):
                with self.assertRaises(ValueError): research('must-not-reserve', task=key)
            lock.assert_not_called(); doctor.assert_not_called()

    def test_sr_runner_rejects_foreign_task_before_creating_output(self):
        from research_harness.autonomy import AutonomousStudy
        study = self.root/'study'; study.mkdir()
        (study/'policy.json').write_text(json.dumps({'task': binding(REGRESSION_TASK)}))
        with self.assertRaisesRegex(ValueError, 'another task'): AutonomousStudy(self.root/'run', study)
        self.assertFalse((self.root/'run').exists())
        validate_sr_policy({'historical': True})
        validate_sr_policy({'task': binding(SR_TASK), 'primary_metric': {'direction': 'higher', 'unit': 'dB'}})
        with self.assertRaisesRegex(ValueError, 'metric'):
            validate_sr_policy({'task': binding(SR_TASK), 'primary_metric': {'direction': 'lower', 'unit': 'dB'}})

    def test_protocol_cannot_change_design_metric_or_execution_scope(self):
        for change in ({'design': 'paired_improvement'}, {'execution': {}}, {'task': binding(SR_TASK)},
                       {'primary_metric': {'name': 'MAE', 'direction': 'higher', 'unit': 'units'}},
                       {'dataset': {**self.protocol['dataset'], 'observation_unit': 'time_step'}},
                       {'intervention': {'kind': 'train'}}):
            with self.assertRaises(ValueError): validate_protocol({**self.protocol, **change})

    def test_mae_lower_direction_and_stop_is_terminal(self):
        scores = self.scores()
        self.assertEqual(scores['baseline_score'], 2)
        self.assertEqual(scores['candidate_score'], 2.25)
        workspace, result, decision = self.decision('negative')
        self.assertEqual(decision['status'], 'STOP')
        self.assertEqual(decision['mean_effect'], -.25)
        self.assertIn('Independent-row', decision['bootstrap_scope'])
        with self.assertRaisesRegex(ValueError, 'closed'): workspace.record(self.protocol['id'], result)

    def test_all_three_gates_are_required_for_second_task(self):
        # Each scenario is a separate software fixture, not a rescued experiment.
        for row, target in zip(self.candidate, self.targets): row['prediction'] = target['target'] + 1
        self.rebind()
        self.assertEqual(self.decision('positive')[2]['status'], 'CONTINUE')
        for row in self.candidate: row['latency_ms'] = 3
        self.rebind()
        self.assertEqual(self.decision('slow')[2]['status'], 'STOP')
        for row, target in zip(self.candidate, self.targets):
            row.update(prediction=target['target'] + 1.75, latency_ms=1)
        self.rebind()
        self.assertEqual(self.decision('small')[2]['status'], 'STOP')
        for i, (row, target) in enumerate(zip(self.candidate, self.targets)):
            row['prediction'] = target['target'] + (0 if i < 6 else 3)
        self.rebind()
        uncertain = self.decision('uncertain')[2]
        self.assertGreaterEqual(uncertain['mean_effect'], self.protocol['minimum_effect'])
        self.assertLessEqual(uncertain['bootstrap_interval'][0], 0)
        self.assertEqual(uncertain['status'], 'STOP')

    def test_changed_inputs_and_bad_rows_rejected(self):
        for group in ('targets', 'baseline', 'candidate'):
            original = copy.deepcopy(getattr(self, group))
            table = getattr(self, group)
            field = 'target' if group == 'targets' else 'prediction'
            table[0][field] += .1
            with self.assertRaisesRegex(ValueError, 'content differs'): self.scores()
            setattr(self, group, original)
        original = copy.deepcopy(self.candidate)
        for change in (lambda x: x.pop(), lambda x: x[-1].update(id=x[0]['id']),
                       lambda x: x[0].update(id='unplanned'), lambda x: x[0].update(prediction=float('nan')),
                       lambda x: x[0].update(latency_ms=0), lambda x: x[0].update(prediction=True),
                       lambda x: x[0].update(command='do not execute')):
            self.candidate = copy.deepcopy(original); change(self.candidate)
            with self.assertRaises(ValueError): self.scores()

    def test_demo_registers_before_result_and_preserves_closed_report(self):
        output = self.root/'demo'
        result = demonstrate(output)
        self.assertTrue(result['synthetic_only']); self.assertEqual(result['status'], 'STOP')
        events = [json.loads(line)['event'] for line in (output/'experiments/synthetic-tabular/ledger.jsonl').read_text().splitlines()]
        self.assertEqual(events, ['REGISTER', 'RESULT', 'DECISION'])
        text = (output/'REPORT.md').read_text()
        self.assertIn('观测行', text); self.assertNotIn('图像', text)
        with self.assertRaises(FileExistsError): demonstrate(output)

    def test_cli_discovery_and_evaluation_only_rejection(self):
        result = subprocess.run([sys.executable, '-m', 'research_harness', 'task', 'list'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({x['id'] for x in json.loads(result.stdout)}, {SR_TASK, REGRESSION_TASK})
        blocked = subprocess.run([sys.executable, '-m', 'research_harness', 'research', '--id', 'no-run', '--task', REGRESSION_TASK], capture_output=True, text=True)
        self.assertEqual(blocked.returncode, 1); self.assertIn('evaluation-only', blocked.stderr)

