"""Synthetic pre-execution checks; no public data or real research experiment."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from examples.data_qualification.baseline import qualification, USE
from research_harness import airfoil_baseline as ab, tabular_baseline as tb
from research_harness import data_admission as admission
from research_harness.core import digest


class DataAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.rows = [{'id': f'synthetic-{i}', 'features': [float(i+j) for j in range(10)],
                      'target': float(i)} for i in range(150)]
        self.airfoil_rows = [{'id': f'synthetic-{i}-{j}',
                             'features': [float(500*(j+1)), float(i), .1+.001*i, 30.+i, .003],
                             'target': 100.+i*.2+j} for i in range(150) for j in range(3)]

    def build(self, module):
        parent = self.root/module.ADAPTER; parent.mkdir()
        snapshot = qualification(parent/'qualification', module.ADAPTER, module.FIXTURE)
        folder = parent/'review'
        rows = self.airfoil_rows if module is ab else self.rows
        prepared = module.prepare_rows(rows, folder, module.FIXTURE, qualification=snapshot, intended_use=USE)
        return folder, prepared, snapshot

    def approve(self, module, folder, sha):
        if module is ab: return ab.approve(folder, sha, 'SYNTHETIC', root=self.root)
        return tb.approve(folder, sha, 'SYNTHETIC')

    def invoke(self, module, name, folder):
        return getattr(module, name)(folder, **({'root': self.root} if module is ab else {}))

    def rewrite(self, folder, change):
        path = folder/'bundle.json'; packet = json.loads(path.read_text())
        change(packet['content'])
        packet['sha256'] = digest(packet['content']); path.write_text(json.dumps(packet))
        return packet

    def test_public_prepare_rejects_before_parsing_any_data(self):
        for module, parser in ((ab, 'parse'), (tb, 'parse_abalone')):
            with patch.object(module, parser) as read:
                with self.assertRaisesRegex(ValueError, 'qualification'):
                    module.prepare(self.root/'not-real-data', self.root/'output')
                read.assert_not_called()
            self.assertFalse((self.root/'output').exists())

    def test_accepted_qualification_does_not_replace_execution_approval(self):
        for module in (ab, tb):
            folder, prepared, _ = self.build(module)
            with patch.object(module, 'environment') as env:
                with self.assertRaises((ValueError, OSError)): self.invoke(module, 'execute', folder)
                env.assert_not_called()
            self.approve(module, folder, prepared['sha256'])
            before = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
            with patch.object(module, 'environment') as env, patch('research_harness.tabular_sandbox.isolation_probe') as probe:
                result = self.invoke(module, 'preflight', folder)
                self.assertEqual(result['status'], 'PRECHECK_PASSED')
                self.assertFalse(result['execution_authorized']); self.assertFalse(result['isolation_checked'])
                env.assert_not_called(); probe.assert_not_called()
            self.assertEqual(before, {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*') if p.is_file()})
            self.assertFalse((folder/'run').exists())

    def test_wrong_scope_and_unaccepted_snapshot_cannot_be_bound(self):
        snapshot = qualification(self.root/'qualification', tb.ADAPTER, tb.FIXTURE)
        for adapter, source, use in ((ab.ADAPTER, tb.FIXTURE, USE), (tb.ADAPTER, ab.FIXTURE, USE),
                                     (tb.ADAPTER, tb.FIXTURE, 'different use')):
            with self.assertRaisesRegex(ValueError, 'differs'):
                admission.bind(snapshot, adapter, source, use, {}, {})
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            admission.context('arbitrary-training', tb.FIXTURE, USE)
        for state in ('unresolved', 'incompatible'):
            altered = copy.deepcopy(snapshot)
            p, d = altered['packet'], altered['decision']
            p['content']['criteria']['permission']['state'] = state
            p['sha256'] = digest(p['content']); d['content']['packet_sha256'] = p['sha256']
            d['sha256'] = digest(d['content'])
            with self.assertRaisesRegex(ValueError, 'Cannot accept'):
                admission.bind(altered, tb.ADAPTER, tb.FIXTURE, USE, {}, {})
        rejected = copy.deepcopy(snapshot)
        rejected['decision']['content']['decision'] = 'reject'
        rejected['decision']['sha256'] = digest(rejected['decision']['content'])
        with self.assertRaisesRegex(ValueError, 'not been accepted'):
            admission.bind(rejected, tb.ADAPTER, tb.FIXTURE, USE, {}, {})

    def test_embedded_evidence_decision_scope_and_partition_tampering_block_worker(self):
        for module in (ab, tb):
            folder, prepared, _ = self.build(module)
            self.approve(module, folder, prepared['sha256'])
            original = (folder/'bundle.json').read_bytes()
            mutations = [lambda c: c['data_admission']['qualification']['packet']['content']['evidence']['note'].update(content='changed'),
                         lambda c: c['data_admission']['qualification']['decision']['content'].update(reviewer='changed'),
                         lambda c: c['data_admission']['context'].update(intended_use='different'),
                         lambda c: c['data_admission']['context']['dataset'].update(version='2'),
                         lambda c: c['data_admission']['data_files'].update(**{'train.json': '0'*64}),
                         lambda c: c['data_admission'].update(recipe_sha256='0'*64),
                         lambda c: c['data_admission'].update(version=True)]
            for mutation in mutations:
                self.rewrite(folder, mutation)
                with patch.object(module, 'environment') as env, patch('research_harness.tabular_sandbox.isolated_worker') as worker:
                    with self.assertRaises(ValueError): self.invoke(module, 'execute', folder)
                    env.assert_not_called(); worker.assert_not_called()
                self.assertFalse((folder/'run').exists())
                (folder/'bundle.json').write_bytes(original)

    def test_removing_admission_cannot_downgrade_real_data_to_legacy_execution(self):
        for module in (ab, tb):
            folder, _, _ = self.build(module)
            packet = self.rewrite(folder, lambda c: (c.pop('data_admission'), c.update(source=module.SOURCE)))
            with patch.object(module, 'environment') as env:
                with self.assertRaisesRegex(ValueError, 'audit-only'):
                    self.invoke(module, 'execute', folder)
                env.assert_not_called()
            # Historical metadata inspection alone can still interpret the old format.
            self.assertIsNone(admission.verify(packet['content'], module.ADAPTER, required=False))

    def test_data_file_changes_block_before_environment(self):
        for module in (ab, tb):
            folder, prepared, _ = self.build(module)
            self.approve(module, folder, prepared['sha256'])
            path = folder/'train.json'; rows = json.loads(path.read_text()); rows[0]['target'] += 1
            path.write_text(json.dumps(rows))
            with patch.object(module, 'environment') as env:
                with self.assertRaisesRegex(ValueError, 'data changed'): self.invoke(module, 'execute', folder)
                env.assert_not_called()

    def test_qualification_update_requires_fresh_execution_approval(self):
        for module in (ab, tb):
            folder, prepared, _ = self.build(module)
            self.approve(module, folder, prepared['sha256'])
            def change(c):
                entry = c['data_admission']; entry['context']['intended_use'] += ' revision'
                p = entry['qualification']['packet']; d = entry['qualification']['decision']
                p['content']['intended_use'] = entry['context']['intended_use']; p['sha256'] = digest(p['content'])
                d['content']['packet_sha256'] = p['sha256']; d['sha256'] = digest(d['content'])
            self.rewrite(folder, change)
            with patch.object(module, 'environment') as env:
                with self.assertRaisesRegex(ValueError, 'stale'): self.invoke(module, 'execute', folder)
                env.assert_not_called()

    def test_recheck_after_probe_prevents_changed_approval_before_reservation(self):
        for module in (ab, tb):
            folder, prepared, _ = self.build(module)
            self.approve(module, folder, prepared['sha256'])
            def probe(*args):
                path = folder/'approval.json'; value = json.loads(path.read_text())
                value['reviewer'] = 'CHANGED_DURING_PROBE'; path.write_text(json.dumps(value))
                return {}
            with patch.object(module, 'environment', return_value={}), \
                 patch('research_harness.tabular_sandbox.isolation_probe', side_effect=probe), \
                 patch('research_harness.tabular_sandbox.isolated_worker') as worker:
                with self.assertRaisesRegex(ValueError, 'changed during preflight'):
                    self.invoke(module, 'execute', folder)
                worker.assert_not_called()
            self.assertFalse((folder/'run').exists())
            self.assertFalse((self.root/'.research-memory/airfoil-baseline').exists())

    def test_private_evidence_is_not_staged_to_worker(self):
        for module in (ab, tb):
            folder, prepared, _ = self.build(module)
            self.approve(module, folder, prepared['sha256'])
            def worker(*args, **kwargs):
                request = json.loads((args[4]/'request.json').read_text())
                self.assertNotIn('SYNTHETIC METADATA', json.dumps(request))
                self.assertNotIn('qualification', request)
                self.assertEqual(set(request), {'train','validation'} | ({'recipe'} if module is tb else set()))
                args[5].mkdir()
                return {'error': 'synthetic stop before fitting'}
            with patch.object(module, 'environment', return_value={}), \
                 patch('research_harness.tabular_sandbox.isolation_probe', return_value={}), \
                 patch('research_harness.tabular_sandbox.isolated_worker', side_effect=worker) as run:
                result = self.invoke(module, 'execute', folder)
                self.assertFalse(result['measurement_valid']); self.assertEqual(run.call_count, 1)
                with self.assertRaises(ValueError): self.invoke(module, 'execute', folder)
                self.assertEqual(run.call_count, 1)

    def test_cli_requires_qualification_and_preflight_is_read_only(self):
        folder, prepared, _ = self.build(tb)
        self.approve(tb, folder, prepared['sha256'])
        repo = str(Path(__file__).resolve().parents[1])
        def cli(*args):
            return subprocess.run([sys.executable, '-m', 'research_harness', *args], cwd=self.root,
                                  env={**os.environ, 'PYTHONPATH': repo}, capture_output=True, text=True, timeout=15)
        for name in ('airfoil','tabular'):
            result = cli(name, 'prepare', '--data', 'nonexistent', '--out', 'unused')
            self.assertEqual(result.returncode, 2)
            self.assertIn('--data-review', result.stderr)
        result = cli('tabular','preflight','--review',str(folder))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['read_only'])
        self.assertFalse((folder/'run').exists()); self.assertFalse((self.root/'runs').exists())

    def test_combined_packet_limit_is_checked_before_creating_review(self):
        with self.assertRaisesRegex(ValueError, '4 MiB'):
            admission.check_packet_size({'metadata': '\u0100' * (1024 * 1024)})
