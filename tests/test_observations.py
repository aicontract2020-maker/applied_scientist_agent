import copy
import json
import tempfile
import unittest
from pathlib import Path

from research_harness.core import Workspace, validate_protocol
from research_harness.planning import validate_plan

ROOT = Path(__file__).resolve().parents[1]


class PairedImageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ws = Workspace(self.temp.name)
        self.p = json.loads((ROOT / 'examples/protocol.json').read_text())
        self.p.update(design='paired_observations', replicates=1, seeds=[0],
                      observation_ids=[f'image-{i}' for i in range(20)], minimum_effect=0.05,
                      primary_metric={'name': 'PSNR-Y', 'unit': 'dB', 'direction': 'higher'},
                      bootstrap={'resamples': 1000, 'seed': 42, 'confidence': 0.95},
                      max_latency_ratio=2.5, intervention={'kind': 'horizontal_flip_ensemble', 'step_size': 0})
        self.r = json.loads((ROOT / 'examples/result.json').read_text())
        self.r.update(seed=0, baseline_score=30, candidate_score=30.1)
        self.r['observations'] = [{'id': x, 'baseline_score': 30, 'candidate_score': 30.1,
                                  'baseline_latency_ms': 10, 'candidate_latency_ms': 20} for x in self.p['observation_ids']]

    def test_consistent_effect_passes(self):
        self.ws.register(self.p)
        report = self.ws.record(self.p['id'], self.r)
        self.assertEqual(report['status'], 'CONTINUE')
        self.assertEqual(report['n'], 1)
        self.assertEqual(report['observation_count'], 20)
        self.assertGreater(report['bootstrap_interval'][0], 0)
        self.assertEqual(report['latency_ratio'], 2)

    def test_speed_guard_can_reject_good_quality(self):
        self.ws.register(self.p)
        for row in self.r['observations']:
            row['candidate_latency_ms'] = 30
        self.assertEqual(self.ws.record(self.p['id'], self.r)['status'], 'STOP')

    def test_uncertain_mean_is_not_enough(self):
        self.ws.register(self.p)
        for i, row in enumerate(self.r['observations']):
            row['candidate_score'] = 31.2 if i < 10 else 29
        self.assertEqual(self.ws.record(self.p['id'], self.r)['status'], 'STOP')

    def test_subset_and_forged_aggregate_rejected(self):
        self.ws.register(self.p)
        partial = copy.deepcopy(self.r)
        partial['observations'].pop()
        with self.assertRaisesRegex(ValueError, 'every frozen'):
            self.ws.record(self.p['id'], partial)
        partial = copy.deepcopy(self.r)
        partial['candidate_score'] = 31
        with self.assertRaisesRegex(ValueError, 'Aggregate'):
            self.ws.record(self.p['id'], partial)

    def test_duplicate_and_unplanned_ids_rejected(self):
        self.ws.register(self.p)
        for bad_id in ('image-0', 'unplanned'):
            bad = copy.deepcopy(self.r)
            bad['observations'][-1]['id'] = bad_id
            with self.assertRaises(ValueError):
                self.ws.record(self.p['id'], bad)

    def test_invalid_bootstrap_and_pseudoreplication_rejected(self):
        for updates in ({'replicates': 3, 'seeds': [1, 2, 3]}, {'bootstrap': {'resamples': 5, 'seed': 1, 'confidence': 0.95}}):
            with self.assertRaises(ValueError):
                validate_protocol({**self.p, **updates})

    def test_planner_can_propose_image_design_without_execution(self):
        plan = json.loads((ROOT / 'examples/local_demo/plan-response.json').read_text())
        plan['protocol'] = self.p
        validate_plan(plan)
        plan['protocol']['execution'] = {}
        with self.assertRaises(ValueError):
            validate_plan(plan)
