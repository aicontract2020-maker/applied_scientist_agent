import copy
import json
import tempfile
import unittest
from pathlib import Path
from research_harness.core import Workspace, validate_protocol

ROOT = Path(__file__).resolve().parents[1]


class ReproductionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ws = Workspace(self.temp.name)
        self.p = json.loads((ROOT / 'examples/protocol.json').read_text())
        self.p.update(design='deterministic_reproduction', replicates=1, seeds=[0], minimum_effect=0,
                      reference_score=38.14, reproduction_tolerance=0.02,
                      reference_source='Synthetic fixture reference, not real measurement')
        self.r = json.loads((ROOT / 'examples/result.json').read_text())
        self.r.update(seed=0, baseline_score=38.14)

    def test_tolerance_is_two_sided(self):
        for i, value in enumerate((38.12, 38.14, 38.16)):
            p = copy.deepcopy(self.p)
            p['id'] = f'inside-{i}'
            self.ws.register(p)
            self.r['candidate_score'] = value
            self.assertEqual(self.ws.record(p['id'], self.r)['status'], 'CONTINUE')

    def test_improvement_far_above_reference_still_fails_reproduction(self):
        self.ws.register(self.p)
        self.r['candidate_score'] = 39
        report = self.ws.record(self.p['id'], self.r)
        self.assertEqual(report['status'], 'STOP')
        self.assertIsNone(report['effect_std'])

    def test_cannot_change_reference_in_result(self):
        self.ws.register(self.p)
        self.r.update(candidate_score=38.14, baseline_score=39)
        with self.assertRaisesRegex(ValueError, 'frozen reference'):
            self.ws.record(self.p['id'], self.r)

    def test_reproduction_needs_reference_and_single_execution(self):
        self.p.pop('reference_source')
        with self.assertRaises(ValueError):
            validate_protocol(self.p)

    def test_improvement_design_still_requires_three_replicates(self):
        self.p['design'] = 'paired_improvement'
        self.p['minimum_effect'] = 0.1
        with self.assertRaisesRegex(ValueError, '3 paired'):
            validate_protocol(self.p)
