"""Fixed workflow discovery and native preflight, using synthetic records only."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_harness import workflows as w
from research_harness import airfoil_baseline as ab, tabular_baseline as tb


class WorkflowTests(unittest.TestCase):
    def baseline(self, module, approve=True):
        from test_data_admission import DataAdmissionTests
        f = DataAdmissionTests(); f.setUp(); self.addCleanup(f.doCleanups)
        folder, prepared, _ = f.build(module)
        if approve: f.approve(module, folder, prepared['sha256'])
        return f.root, folder

    def sr(self):
        from test_sr_preflight import SRPreflightTests
        f = SRPreflightTests(); f.setUp(); self.addCleanup(f.doCleanups)
        return f

    def files(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def cli(self, *args):
        from research_harness.cli import main
        out, err = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['research-harness', *args]), patch('sys.stdout', out), patch('sys.stderr', err):
            try: code = main() or 0
            except SystemExit as exc: code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_catalog_is_closed_and_non_authorizing(self):
        result = w.catalog()
        self.assertEqual({x['id'] for x in result['workflows']},
                         {'swinir-s-x2', 'abalone-baseline-v1', 'abalone-candidate-v1',
                          'airfoil-baseline-v1', 'airfoil-candidate-v1'})
        self.assertTrue(result['read_only']); self.assertFalse(result['execution_authorized'])
        for entry in result['workflows']:
            self.assertFalse(entry['execution_authorized']); self.assertEqual(entry['readiness'], 'NOT_CHECKED')

    def test_catalog_distinguishes_fixed_airfoil_from_autonomous_sr(self):
        airfoil = w.workflow('airfoil-candidate-v1'); sr = w.workflow('swinir-s-x2')
        self.assertIn('no autonomous', airfoil['automation'])
        self.assertEqual(airfoil['unit'], 'condition group'); self.assertIn('3.12', airfoil['preflight_python'])
        self.assertIn('autonomous literature', sr['automation'])

    def test_returned_metadata_cannot_mutate_catalog(self):
        first = w.catalog(); first['workflows'][0]['dataset'] = 'any data'
        first['workflows'][0]['execution_platforms'].clear()
        self.assertNotEqual(first, w.catalog())
        self.assertTrue(w.workflow('swinir-s-x2')['execution_platforms'])

    def test_unknown_id_rejected_before_path_access(self):
        with patch.object(w, 'Path') as path:
            for value in ('tabular-regression', '../swinir-s-x2', None, {}, 'external.module:run'):
                with self.assertRaisesRegex(ValueError, 'Unknown workflow'):
                    w.check(value, '/does-not-exist', root='/does-not-exist')
            path.assert_not_called()

    def test_missing_root_never_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'missing'
            with self.assertRaises(OSError): w.check('airfoil-baseline-v1', tmp, root=root)
            self.assertFalse(root.exists())

    def test_file_is_not_a_review_directory(self):
        root, folder = self.baseline(tb)
        with self.assertRaisesRegex(ValueError, 'directories'):
            w.check(tb.ADAPTER, folder/'bundle.json', root=root)

    def test_baseline_checks_preserve_native_result_and_do_not_write(self):
        for module in (tb, ab):
            root, folder = self.baseline(module); before = self.files(root)
            with patch.object(module, 'environment') as env, patch('subprocess.Popen') as process:
                result = w.check(module.ADAPTER, folder, root=root)
                self.assertEqual(result['checks'], module.preflight(folder, root=root))
                env.assert_not_called(); process.assert_not_called()
            self.assertEqual(before, self.files(root))
            self.assertEqual(result['root'], str(root)); self.assertEqual(result['review'], str(folder))
            self.assertFalse(result['execution_authorized']); self.assertFalse(result['isolation_checked'])

    def test_missing_human_approval_still_rejected(self):
        for module in (tb, ab):
            root, folder = self.baseline(module, approve=False); before = self.files(root)
            with self.assertRaises((OSError, ValueError)): w.check(module.ADAPTER, folder, root=root)
            self.assertEqual(before, self.files(root))

    def test_modified_material_still_rejected(self):
        for module in (tb, ab):
            root, folder = self.baseline(module)
            (folder/'train.json').write_text('[]')
            with self.assertRaises(ValueError): w.check(module.ADAPTER, folder, root=root)

    def test_consumed_baseline_still_rejected(self):
        for module in (tb, ab):
            root, folder = self.baseline(module); (folder/'run').mkdir()
            with self.assertRaises(ValueError): w.check(module.ADAPTER, folder, root=root)

    def test_explicit_wrong_workflow_does_not_fall_back(self):
        root, folder = self.baseline(tb)
        with self.assertRaises((ValueError, OSError, KeyError)):
            w.check(ab.ADAPTER, folder, root=root)

    def test_candidate_checks_keep_approval_and_historical_audit(self):
        from test_candidate_admission import CandidateAdmissionTests
        from research_harness import tabular_trial as tt, airfoil_trial as at
        fixture = CandidateAdmissionTests(); self.addCleanup(fixture.doCleanups)
        for module in (tt, at):
            f = fixture.build(module)
            with self.assertRaises((OSError, ValueError)): w.check(module.ADAPTER, f.folder, root=f.root)
            fixture.approve(f); before = self.files(f.root)
            with patch.object(module, 'environment') as env, patch('subprocess.Popen') as process:
                result = w.check(module.ADAPTER, f.folder, root=f.root)
                self.assertEqual(result['checks'], fixture.invoke(f, 'preflight'))
                env.assert_not_called(); process.assert_not_called()
            self.assertTrue(result['checks']['memory_checked']); self.assertEqual(before, self.files(f.root))
        # Airfoil helper substitutes its historical audit here; actual isolated
        # check-airfoil-trial.py exercises that audit without substitution.

    def test_sr_native_check_preserved_without_launch(self):
        f = self.sr(); before = f.files()
        with patch('research_harness.doctor.doctor') as doctor, patch('subprocess.Popen') as process:
            result = w.check('swinir-s-x2', f.study, root=f.root)
            self.assertEqual(result['checks'], f.check())
            self.assertEqual(result['checks']['status'], 'READY_FOR_LAUNCH_CHECKS')
            doctor.assert_not_called(); process.assert_not_called()
        self.assertEqual(before, f.files())

    def test_sr_stale_preparation_still_rejected(self):
        from research_harness.portable import new_study
        f = self.sr(); new_study('later', f.root)
        with self.assertRaisesRegex(ValueError, 'constraints changed'):
            w.check('swinir-s-x2', f.study, root=f.root)

    def test_native_nonpass_cannot_be_reported_as_pass(self):
        root, folder = self.baseline(tb)
        for change in ({'status': 'BLOCKED'}, {'execution_authorized': True}, {'read_only': False}):
            result = dict(tb.preflight(folder, root=root), **change)
            with patch.object(tb, 'preflight', return_value=result), self.assertRaisesRegex(ValueError, 'non-authorizing pass'):
                w.check(tb.ADAPTER, folder, root=root)

    def test_cli_catalog_and_check_are_read_only(self):
        root, folder = self.baseline(ab); before = self.files(root)
        code, out, err = self.cli('task', 'workflows')
        self.assertEqual(code, 0, err); self.assertEqual(json.loads(out), w.catalog())
        code, out, err = self.cli('--workspace', str(root/'unused'), 'task', 'check',
                                  '--workflow', ab.ADAPTER, '--review', str(folder), '--root', str(root))
        self.assertEqual(code, 0, err); self.assertFalse(json.loads(out)['execution_authorized'])
        self.assertEqual(before, self.files(root)); self.assertFalse((root/'unused').exists())

    def test_cli_rejection_is_nonzero_without_success_json(self):
        root, folder = self.baseline(tb, approve=False)
        code, out, err = self.cli('task', 'check', '--workflow', tb.ADAPTER,
                                  '--review', str(folder), '--root', str(root))
        self.assertNotEqual(code, 0); self.assertEqual(out, ''); self.assertTrue(err)

    def test_legacy_numerical_catalog_still_separate(self):
        from research_harness.task_contracts import list_tasks
        code, out, err = self.cli('task', 'list')
        self.assertEqual(code, 0, err); self.assertEqual(json.loads(out), list_tasks())


if __name__ == '__main__':
    unittest.main()
