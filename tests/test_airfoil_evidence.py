"""Synthetic records only: no worker, model, real data or research experiment."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_harness import airfoil_baseline as ab, airfoil_trial as at, airfoil_evidence as ae
from research_harness.core import digest, Workspace
from research_harness.tabular_data import write_json


def envelope(files):
    payload = {'kind': ae.KIND, 'version': 1, 'files': {
        name: {'content': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
        for name, text in files.items()}}
    return {'payload': payload, 'sha256': digest(payload)}


class EvidenceFormatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.files = {name: '{}' if name.endswith('.json') else '' for name in ae.FILES - {ae.RAW}}
        self.files['baseline/bundle.json'] = json.dumps({'content': {'source': ab.FIXTURE}})

    def test_closed_task_version_paths_and_source_specific_inventory(self):
        value = envelope(self.files); ae._validate(value)
        for key, new in [('kind', 'research-harness-tabular-evidence'), ('version', True)]:
            bad = copy.deepcopy(value); bad['payload'][key] = new; bad['sha256'] = digest(bad['payload'])
            with self.assertRaises(ValueError): ae._validate(bad)
        for name in ('../escape', '/tmp/escape', ae.RAW):
            with self.assertRaises(ValueError): ae._validate(envelope({**self.files, name: ''}))
        real = {**self.files, 'baseline/bundle.json': json.dumps({'content': {'source': ab.SOURCE}})}
        with self.assertRaises(ValueError): ae._validate(envelope(real))
        ae._validate(envelope({**real, ae.RAW: ''}))  # Structure only; actual audit still requires pinned bytes.

    def test_hashes_missing_files_and_bounded_sizes(self):
        value = envelope(self.files); value['payload']['files']['candidate.py']['content'] = 'tampered'
        with self.assertRaises(ValueError): ae._validate(value)
        value = envelope(self.files); value['sha256'] = '0' * 64
        with self.assertRaises(ValueError): ae._validate(value)
        files = dict(self.files); files.pop('candidate.py')
        with self.assertRaises(ValueError): ae._validate(envelope(files))
        with patch.object(ae, 'FILE_LIMIT', 1), self.assertRaises(ValueError): ae._validate(envelope(self.files))
        with patch.object(ae, 'TOTAL_LIMIT', 1), self.assertRaises(ValueError): ae._validate(envelope(self.files))
        path = self.root / 'packet'; write_json(path, envelope(self.files))
        with patch.object(ae, 'PACKET_LIMIT', 1), self.assertRaises(ValueError): ae.load_packet(path)

    def test_duplicate_nonfinite_and_nested_json_are_rejected(self):
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', '[' * 2000 + '0' + ']' * 2000):
            with self.assertRaises(ValueError): ae._decode(text)
            for name in ('trial.json', 'trial-run/ledger.jsonl'):
                with self.assertRaises(ValueError): ae._validate(envelope({**self.files, name: text}))

    def test_links_fifo_and_existing_outputs_are_rejected(self):
        path = self.root / 'packet'; write_json(path, envelope(self.files))
        link = self.root / 'link'; link.symlink_to(path)
        with self.assertRaises(ValueError): ae.load_packet(link)
        linked = self.root / 'parent'; linked.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): ae.load_packet(linked / 'packet')
        fifo = self.root / 'fifo'; os.mkfifo(fifo)
        with self.assertRaises(ValueError): ae.load_packet(fifo)
        with self.assertRaises(FileExistsError): ae._write(path, b'replace')
        self.assertEqual(ae.load_packet(path), envelope(self.files))

    def test_review_only_marker_blocks_all_live_paths_even_if_dangling(self):
        folder = self.root / 'review'; folder.mkdir()
        (folder / 'EVIDENCE_ONLY.json').symlink_to(self.root / 'missing')
        with patch.object(ab, 'environment') as environment, patch.object(at, 'qualified') as qualified:
            for action in (lambda: ab.load_review(folder), lambda: ab.preflight(folder, root=self.root),
                           lambda: ab.approve(folder, 'a' * 64, 'fixture', root=self.root),
                           lambda: ab.execute(folder, root=self.root), lambda: at.load_trial(folder),
                           lambda: at.preflight(folder, root=self.root),
                           lambda: at.approve(folder, 'a' * 64, 'fixture', root=self.root),
                           lambda: at.execute(folder, root=self.root),
                           lambda: at.prepare(folder, 'unused', self.root / 'new', root=self.root)):
                with self.assertRaisesRegex(ValueError, 'read-only'): action()
            environment.assert_not_called(); qualified.assert_not_called()
        self.assertFalse((self.root / 'new').exists())

    def test_wrong_runtime_refuses_exact_audit(self):
        with patch.object(ae.sys, 'version_info', (3, 10)), self.assertRaisesRegex(ValueError, '3.12'):
            ae._audit(envelope(self.files))


@unittest.skipUnless(sys.version_info[:2] == (3, 12), 'Exact Airfoil audit requires Python 3.12')
class EvidenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name).resolve(); base = cls.root / 'base'; cls.trial = cls.root / 'trial'
        rows = [{'id': f'fixture-{i:03}-{j}', 'features': [500. + j * 500., float(i), .1 + i * .001, 30. + i, .003],
                 'target': 100. + i * .2 + j} for i in range(150) for j in range(3)]
        bp = ab.prepare_rows(rows, base, root=cls.root); _, parts = ab.load_review(base)
        ab.approve(base, bp['sha256'], 'SYNTHETIC SOFTWARE FIXTURE', root=cls.root)
        raw = {'peak_rss_native': 100, 'results': []}
        for model in ab.RECIPE['models']:
            for seed in ab.RECIPE['seeds']:
                error = 5. if model == 'median' else (1. if model == 'extra_trees' else 2.)
                raw['results'].append({'model': model, 'seed': seed, 'fit_seconds': .1, 'predict_seconds': .01,
                    'predictions': [{'id': r['id'], 'prediction': r['target'] + error} for r in parts['validation-targets.json']]})
        run = base / 'run'
        for name in ('trusted', 'inputs', 'output'): (run / name).mkdir(parents=True)
        shutil.copyfile(ab.ROOT / 'research_harness/airfoil_worker.py', run / 'trusted/worker.py')
        write_json(run / 'inputs/request.json', ab.worker_request(parts)); write_json(run / 'output/predictions.json', raw)
        cls.pre = {'environment': {'python': [3, 12], 'packages': ab.PACKAGES}, 'platform': 'darwin',
            'isolation': {k: True for k in ('private_labels_denied', 'repo_denied', 'input_readonly', 'network_denied', 'output_writable')}}
        write_json(run / 'preflight.json', cls.pre); write_json(run / 'process.json', {'error': None, 'returncode': 0})
        result = ab.qualify(raw, parts['validation-targets.json'])
        result.update(peak_rss_bytes=100, wall_seconds=1., model_calls=0, actual_local_cost_usd=None,
                      retained_bytes_before_report=1, scope=ab.SCOPE)
        write_json(run / 'result.json', result)
        for event in ('REGISTER', 'BASELINE_STARTED'): Workspace.append(run, {'event': event, 'review_sha256': bp['sha256']})
        Workspace.append(run, {'event': 'DECISION', 'result': result})
        tp = at.prepare(base, ab.ROOT / 'tasks/airfoil_noise/a2/proposal.json', cls.trial, root=cls.root)
        at.approve(cls.trial, tp['sha256'], 'SYNTHETIC SOFTWARE FIXTURE', root=cls.root)
        candidate = {'results': [], 'transform_train_seconds': .01, 'peak_rss_native': 100}
        reference = {r['seed']: [p['prediction'] for p in r['predictions']] for r in raw['results'] if r['model'] == 'extra_trees'}
        for seed in at.RECIPE['seeds']:
            for kind in ('baseline', 'candidate'):
                candidate['results'].append({'kind': kind, 'seed': seed, 'fit_seconds': .1, 'timing_seconds': [1.] * 5,
                    'batch_seconds': 1., 'validation_predictions': reference[seed] if kind == 'baseline' else None,
                    'predictions': [{'id': r['id'], 'prediction': r['target'] + (1. if kind == 'baseline' else .5)} for r in parts['holdout-targets.json']]})
        run = cls.trial / 'trial-run'
        for name in ('trusted', 'inputs', 'output'): (run / name).mkdir(parents=True)
        for name in ('airfoil_candidate.py', 'airfoil_trial_worker.py'):
            shutil.copyfile(ab.ROOT / 'research_harness' / name, run / 'trusted' / name)
        write_json(run / 'inputs/request.json', at.request(parts)); write_json(run / 'output/predictions.json', candidate)
        write_json(run / 'preflight.json', cls.pre); write_json(run / 'process.json', {'error': None, 'returncode': 0})
        result = at.evaluate(candidate, parts, raw)
        result.update(peak_rss_bytes=100, wall_seconds=1., model_calls=0, actual_local_cost_usd=None,
                      retained_bytes_before_report=1, holdout_exposed=True)
        write_json(run / 'result.json', result)
        for event in ('REGISTER', 'HOLDOUT_EXPOSED'): Workspace.append(run, {'event': event, 'review_sha256': tp['sha256']})
        Workspace.append(run, {'event': 'DECISION', 'result': result})
        cls.packet = cls.root / 'packet.json'; ae.export(cls.trial, cls.packet)

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(); self.addCleanup(self.work.cleanup)
        self.out = Path(self.work.name).resolve()

    def test_roundtrip_audits_without_execution_or_memory_import_and_is_private(self):
        with patch('subprocess.Popen', side_effect=AssertionError('No execution')):
            self.assertTrue(ae.verify(self.packet)['audit_ok'])
            result = ae.unpack(self.packet, self.out / 'received')
            review = Path(result['review']); self.assertTrue(at.audit(review)['audit_ok'])
            self.assertTrue(ab.audit(review / 'baseline')['audit_ok'])
        self.assertFalse(result['execution_permitted'])
        self.assertEqual(self.packet.stat().st_mode & 0o777, 0o600)
        for path in (self.out / 'received').rglob('*'):
            self.assertEqual(path.stat().st_mode & 0o777, 0o700 if path.is_dir() else 0o600)
        self.assertFalse((self.out / 'received/.research-memory').exists())
        for folder in (review, review / 'baseline'):
            self.assertTrue((folder / 'EVIDENCE_ONLY.json').exists())
        with self.assertRaisesRegex(ValueError, 'read-only'):
            at.prepare(review / 'baseline', 'unused', self.out / 'new', root=self.out)
        # The nested marker independently blocks active candidate loading.
        (review / 'EVIDENCE_ONLY.json').unlink()
        with self.assertRaisesRegex(ValueError, 'read-only'): at.load_trial(review)

    def test_rehashed_predictions_and_process_tampering_fail_before_unpack(self):
        original = ae.load_packet(self.packet)
        for name in ('trial-run/result.json', 'trial-run/process.json', 'baseline/run/output/predictions.json'):
            files = {k: v['content'] for k, v in original['payload']['files'].items()}
            value = json.loads(files[name])
            if name.endswith('result.json'): value['mean_gain_db'] += 1
            elif name.endswith('process.json'): value['returncode'] = 1
            else: value['results'][0]['predictions'][0]['prediction'] += 1
            files[name] = json.dumps(value); path = self.out / 'bad.json'; path.write_text(json.dumps(envelope(files)))
            with self.assertRaises(ValueError): ae.unpack(path, self.out / 'received')
            self.assertFalse((self.out / 'received').exists())

    def test_invalid_measurement_and_incomplete_evidence_cannot_export(self):
        trial = self.out / 'trial'; shutil.copytree(self.trial, trial)
        path = trial / 'trial-run/result.json'; result = json.loads(path.read_text()); result['measurement_valid'] = False
        path.write_text(json.dumps(result))
        with self.assertRaises(ValueError): ae.export(trial, self.out / 'packet')
        self.assertFalse((self.out / 'packet').exists())
        path.unlink()
        with self.assertRaises(OSError): ae.export(trial, self.out / 'packet')

    def test_valid_stop_is_preserved_as_a_final_auditable_output(self):
        trial = self.out / 'trial'; shutil.copytree(self.trial, trial)
        _, _, parts, reference = at.load_trial(trial, current=False)
        path = trial / 'trial-run/output/predictions.json'; raw = json.loads(path.read_text())
        for entry in raw['results']:
            if entry['kind'] == 'candidate':
                entry['predictions'] = [{'id': r['id'], 'prediction': r['target'] + .9} for r in parts['holdout-targets.json']]
        path.write_text(json.dumps(raw))
        path = trial / 'trial-run/result.json'; result = json.loads(path.read_text())
        result.update(at.evaluate(raw, parts, reference)); self.assertEqual(result['status'], 'STOP')
        path.write_text(json.dumps(result))
        path = trial / 'trial-run/ledger.jsonl'; ledger = [json.loads(line) for line in path.read_text().splitlines()]
        ledger[-1]['result'] = result; path.write_text(''.join(json.dumps(row) + '\n' for row in ledger))
        packet = self.out / 'stopped.json'; ae.export(trial, packet)
        self.assertEqual(ae.verify(packet)['audit']['status'], 'STOP')

    def test_changed_source_and_links_during_export_leave_no_packet(self):
        trial = self.out / 'trial'; shutil.copytree(self.trial, trial)
        original = ae._audit
        def change(packet):
            result = original(packet); (trial / 'candidate.py').write_text('changed'); return result
        with patch.object(ae, '_audit', side_effect=change), self.assertRaisesRegex(ValueError, 'changed during'):
            ae.export(trial, self.out / 'packet')
        self.assertFalse((self.out / 'packet').exists())
        path = trial / 'candidate.py'; path.unlink(); path.symlink_to(self.trial / 'candidate.py')
        with self.assertRaises(ValueError): ae.export(trial, self.out / 'packet')

    def test_unpack_failure_cleanup_and_no_overwrite(self):
        output = self.out / 'received'; output.mkdir(); (output / 'keep').write_text('keep')
        with self.assertRaises(FileExistsError): ae.unpack(self.packet, output)
        self.assertEqual((output / 'keep').read_text(), 'keep')
        original = ae._materialize
        def fail(packet, folder):
            original(packet, folder)
            if Path(folder).name == '.pending': raise OSError('injected write failure')
        with patch.object(ae, '_materialize', side_effect=fail), self.assertRaises(OSError):
            ae.unpack(self.packet, self.out / 'failed')
        self.assertFalse((self.out / 'failed').exists())

    def test_cli_export_verify_unpack(self):
        from research_harness.cli import main
        packet = self.out / 'cli.json'
        for args in (['export', '--review', str(self.trial), '--out', str(packet)], ['verify', str(packet)],
                     ['unpack', str(packet), '--out', str(self.out / 'cli')]):
            stream = io.StringIO()
            with patch('sys.stdout', stream), patch('sys.argv', ['research-harness', 'airfoil', 'evidence', *args]): main()
            self.assertTrue(json.loads(stream.getvalue())['audit_ok'])
