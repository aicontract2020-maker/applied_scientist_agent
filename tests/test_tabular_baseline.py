"""Software-only protocol/label/approval/stopping boundaries."""
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_harness.core import digest
from research_harness.tabular_data import split_rows, parse_abalone, fetch_abalone, FILES
from research_harness.tabular_baseline import (prepare_rows, load_review, approve, execute, qualify, RECIPE)


class TabularBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = [{'id': f'fixture-{i}', 'features': [float(i+j) for j in range(10)], 'target': float(2*i)} for i in range(150)]
        self.folder = self.root/'review'
        self.review = prepare_rows(self.rows, self.folder, {'id': 'synthetic-software-fixture'})

    def output(self, learned_error=1):
        _, parts = load_review(self.folder)
        targets = parts['validation-targets.json']
        results = []
        for seed in RECIPE['seeds']:
            for model in RECIPE['models']:
                results.append({'model': model, 'seed': seed, 'fit_seconds': .1, 'predict_seconds': .01,
                                'predictions': [{'id': r['id'], 'prediction': r['target']+(2 if model == 'median' else learned_error)} for r in targets]})
        return {'results': results, 'peak_rss_native': 1}, targets

    def test_feature_only_split_and_identical_features_stay_together(self):
        parts = split_rows(self.rows)
        changed = copy.deepcopy(self.rows)
        for row in changed: row['target'] += 10000
        alternate = split_rows(changed)
        for name in ('train.json', 'validation.json', 'holdout.json'):
            self.assertEqual([r['id'] for r in parts[name]], [r['id'] for r in alternate[name]])
        duplicate = dict(self.rows[0], id='another-same-feature')
        grouped = split_rows([*self.rows, duplicate])
        for name in ('train.json', 'validation.json', 'holdout.json'):
            ids = {r['id'] for r in grouped[name]}
            self.assertEqual('fixture-0' in ids, 'another-same-feature' in ids)
        self.assertTrue(all(set(row) == {'id','features'} for row in parts['validation.json'] + parts['holdout.json']))

    def test_prepare_is_nonexecuting_exclusive_and_pins_all_sources(self):
        self.assertFalse((self.folder/'run').exists()); self.assertFalse((self.folder/'approval.json').exists())
        packet, parts = load_review(self.folder)
        self.assertEqual(set(parts), set(FILES))
        self.assertIn('research_harness/tabular_worker.py', packet['content']['sources'])
        with self.assertRaises(FileExistsError): prepare_rows(self.rows, self.folder, {'id': 'synthetic-software-fixture'})
        raw = self.root/'fake.data'; raw.write_text('not pinned UCI')
        with self.assertRaisesRegex(ValueError, 'SHA-256'): parse_abalone(raw)

    def test_changed_bundle_data_or_source_rejected(self):
        packet_path = self.folder/'bundle.json'; original = packet_path.read_text()
        packet = json.loads(original); packet['content']['recipe']['minimum_validation_gain'] = 0
        packet['sha256'] = digest(packet['content']); packet_path.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, 'unsupported'): load_review(self.folder)
        packet_path.write_text(original)
        with patch('research_harness.tabular_baseline.source_hashes', return_value={}):
            with self.assertRaisesRegex(ValueError, 'source changed'): load_review(self.folder)
        (self.folder/'validation-targets.json').write_text('[]')
        with self.assertRaisesRegex(ValueError, 'data changed'): load_review(self.folder)

    def test_symlink_unknown_fields_and_stale_approval_rejected(self):
        packet_path = self.folder/'bundle.json'
        original = packet_path.read_text(); packet = json.loads(original)
        packet['content']['command'] = 'never execute'; packet['sha256'] = digest(packet['content'])
        packet_path.write_text(json.dumps(packet))
        with self.assertRaises(ValueError): load_review(self.folder)
        packet_path.write_text(original)
        approve(self.folder, self.review['sha256'], 'fixture')
        approval = json.loads((self.folder/'approval.json').read_text()); approval['sha256'] = '0'*64
        (self.folder/'approval.json').write_text(json.dumps(approval))
        with patch('research_harness.tabular_baseline.environment') as env:
            with self.assertRaisesRegex(ValueError, 'stale'): execute(self.folder)
            env.assert_not_called()
        file = self.folder/'holdout.json'; file.unlink(); file.symlink_to(self.folder/'validation.json')
        with self.assertRaises(ValueError): load_review(self.folder)

    def test_download_refuses_unknown_bytes_and_existing_output(self):
        with patch('research_harness.tabular_data.urllib.request.urlopen', return_value=io.BytesIO(b'not pinned')):
            with self.assertRaisesRegex(ValueError, 'archive'): fetch_abalone(self.root/'download')
        self.assertFalse((self.root/'download').exists())
        with patch('research_harness.tabular_data.urllib.request.urlopen') as network:
            with self.assertRaisesRegex(ValueError, 'exists'): fetch_abalone(self.folder)
            network.assert_not_called()

    def test_approval_absence_wrong_hash_and_existing_attempt_block(self):
        with patch('research_harness.tabular_baseline.environment') as env:
            with self.assertRaises(ValueError): execute(self.folder)
            env.assert_not_called()
        with self.assertRaises(ValueError): approve(self.folder, '0'*64, 'fixture')
        approve(self.folder, self.review['sha256'], 'fixture')
        with self.assertRaises(FileExistsError): approve(self.folder, self.review['sha256'], 'fixture')
        (self.folder/'run').mkdir()
        with patch('research_harness.tabular_baseline.environment') as env:
            with self.assertRaisesRegex(ValueError, 'consumed'): execute(self.folder)
            env.assert_not_called()

    def test_qualification_positive_negative_and_repeatability_rules(self):
        output, targets = self.output()
        result = qualify(output, targets)
        self.assertEqual(result['status'], 'CONTINUE'); self.assertEqual(result['selected_baseline'], 'ridge')
        output, targets = self.output(learned_error=1.99)
        self.assertEqual(qualify(output, targets)['status'], 'STOP')
        output['results'][1]['predictions'][0]['prediction'] += .01
        with self.assertRaisesRegex(ValueError, 'repeatability'): qualify(output, targets)

    def test_missing_duplicate_extra_and_nonfinite_predictions_rejected(self):
        output, targets = self.output()
        for change in (lambda x: x['results'].pop(), lambda x: x['results'].append(x['results'][0]),
                       lambda x: x['results'][0]['predictions'].pop(),
                       lambda x: x['results'][0]['predictions'][0].update(prediction=float('nan')),
                       lambda x: x['results'][0]['predictions'][0].update(id='foreign'),
                       lambda x: x['results'][0].update(seed=True),
                       lambda x: x['results'][0].update(command='no execution')):
            bad = copy.deepcopy(output); change(bad)
            with self.assertRaises(ValueError): qualify(bad, targets)

    def test_execution_stages_no_labels_and_failure_consumes_attempt(self):
        approve(self.folder, self.review['sha256'], 'fixture')
        def failed(*args, **kwargs):
            inputs, output = args[4], args[5]
            value = json.loads((inputs/'request.json').read_text())
            self.assertEqual(set(value), {'recipe','train','validation'})
            self.assertTrue(all(set(row) == {'id','features'} for row in value['validation']))
            output.mkdir(); (output/'stderr.log').write_text('fixture failure')
            return {'error':'fixture failure','wall_seconds':.1}
        with patch('research_harness.tabular_baseline.environment', return_value={}), \
             patch('research_harness.tabular_sandbox.isolation_probe', return_value={}), \
             patch('research_harness.tabular_sandbox.isolated_worker', side_effect=failed):
            result = execute(self.folder)
            self.assertEqual(result['status'], 'STOP'); self.assertFalse(result['measurement_valid'])
            self.assertIsNone(result['actual_local_cost_usd'])
            with self.assertRaisesRegex(ValueError, 'consumed'): execute(self.folder)
        events = [json.loads(line)['event'] for line in (self.folder/'run/ledger.jsonl').read_text().splitlines()]
        self.assertEqual(events, ['REGISTER','BASELINE_STARTED','DECISION'])

    def test_isolation_failure_prevents_real_attempt(self):
        approve(self.folder, self.review['sha256'], 'fixture')
        with patch('research_harness.tabular_baseline.environment', return_value={}), \
             patch('research_harness.tabular_sandbox.isolation_probe', side_effect=ValueError('blocked')):
            with self.assertRaisesRegex(ValueError, 'blocked'): execute(self.folder)
        self.assertFalse((self.folder/'run').exists())

    def test_successful_fixture_records_cost_limits_and_no_holdout_score(self):
        approve(self.folder, self.review['sha256'], 'fixture')
        raw, _ = self.output()
        def success(*args, **kwargs):
            output = args[5]; output.mkdir()
            (output/'predictions.json').write_text(json.dumps(raw))
            return {'error': None, 'wall_seconds': .1}
        with patch('research_harness.tabular_baseline.environment', return_value={}), \
             patch('research_harness.tabular_sandbox.isolation_probe', return_value={}), \
             patch('research_harness.tabular_sandbox.isolated_worker', side_effect=success):
            result = execute(self.folder)
        self.assertEqual(result['status'], 'CONTINUE'); self.assertTrue(result['measurement_valid'])
        self.assertFalse(result['final_holdout_scored']); self.assertIsNone(result['actual_local_cost_usd'])
        self.assertGreater(result['retained_bytes_before_report'], 0)
        self.assertFalse((self.folder/'run/inputs/holdout.json').exists())
