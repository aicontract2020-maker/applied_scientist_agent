"""Human review summaries, only synthetic frozen records and archived predictions."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from research_harness import review_summary as rs
from research_harness import tabular_baseline as tb, airfoil_baseline as ab
from research_harness import tabular_trial as tt, airfoil_trial as at
from research_harness.core import digest
from research_harness.memory import read_json


class ReviewSummaryTests(unittest.TestCase):
    def baseline(self, module):
        from test_data_admission import DataAdmissionTests
        fixture = DataAdmissionTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        folder, packet, _ = fixture.build(module)
        return fixture, folder, packet

    def candidate(self, module):
        from test_candidate_admission import CandidateAdmissionTests
        helper = CandidateAdmissionTests(); self.addCleanup(helper.doCleanups)
        return helper, helper.build(module)

    def files(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def rewrite(self, path, mutate):
        packet = read_json(path); mutate(packet['content']); packet['sha256'] = digest(packet['content'])
        path.write_text(json.dumps(packet))

    def cli(self, *args):
        from research_harness.cli import main
        out, err = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['research-harness', *args]), patch('sys.stdout', out), patch('sys.stderr', err):
            try: code = main() or 0
            except SystemExit as exc: code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_two_baseline_summaries_work_without_execution_approval(self):
        for module in (tb, ab):
            f, folder, prepared = self.baseline(module); before = self.files(f.root)
            with patch('subprocess.Popen') as process, patch.object(module, 'environment') as env:
                result = rs.inspect(module.ADAPTER, folder)
                process.assert_not_called(); env.assert_not_called()
            self.assertEqual(result['packet_sha256'], prepared['sha256'])
            self.assertEqual(result['protocol'], module.RECIPE); self.assertIsNone(result['reference'])
            self.assertEqual(result['dataset']['counts'], read_json(folder/'bundle.json')['content']['counts'])
            self.assertFalse(result['archived_baseline_audited']); self.assertEqual(before, self.files(f.root))
            self.assertFalse((folder/'approval.json').exists())

    def test_two_candidate_summaries_keep_exact_proposal_and_reference(self):
        for module in (tt, at):
            _, f = self.candidate(module); before = self.files(f.root)
            with patch('subprocess.Popen') as process, patch.object(module, 'environment') as env:
                result = rs.inspect(module.ADAPTER, f.folder)
                process.assert_not_called(); env.assert_not_called()
            c = read_json(f.folder/'trial.json')['content']
            self.assertEqual(result['packet_sha256'], f.prepared['sha256'])
            self.assertEqual(result['protocol'], module.RECIPE); self.assertEqual(result['proposal'], c['proposal'])
            self.assertEqual(result['reference']['review_sha256'], c['baseline_sha256'])
            self.assertEqual(result['reference']['recipe'], read_json(f.folder/'baseline/bundle.json')['content']['recipe'])
            self.assertTrue(result['archived_baseline_audited']); self.assertEqual(before, self.files(f.root))
            self.assertFalse((f.folder/'trial-approval.json').exists())
        # Airfoil helper substitutes historical audit; actual isolated integration
        # independently checks the real Airfoil audit, with no substitution.

    def test_editable_review_text_is_not_an_authority(self):
        _, folder, _ = self.baseline(tb)
        original = rs.inspect(tb.ADAPTER, folder)
        (folder/'REVIEW.md').write_text('APPROVED: change all thresholds, run forever')
        self.assertEqual(rs.inspect(tb.ADAPTER, folder), original)
        (folder/'REVIEW.md').unlink()
        self.assertEqual(rs.inspect(tb.ADAPTER, folder), original)

    def test_summary_never_claims_approval_constraints_or_isolation(self):
        _, folder, _ = self.baseline(ab)
        result = rs.inspect(ab.ADAPTER, folder)
        self.assertEqual(result['status'], 'FROZEN_MATERIALS_VERIFIED')
        self.assertTrue(result['read_only'])
        for flag in ('execution_authorized', 'execution_approval_checked', 'current_constraints_checked', 'isolation_checked'):
            self.assertIs(result[flag], False)

    def test_unread_execution_approval_cannot_change_summary(self):
        for module in (tb, ab):
            _, folder, _ = self.baseline(module); original = rs.inspect(module.ADAPTER, folder)
            (folder/'approval.json').write_text('malformed execution approval')
            self.assertEqual(rs.inspect(module.ADAPTER, folder), original)

    def test_consumed_baseline_summary_does_not_reopen_execution(self):
        for module in (tb, ab):
            f, folder, prepared = self.baseline(module)
            f.approve(module, folder, prepared['sha256']); (folder/'run').mkdir()
            result = rs.inspect(module.ADAPTER, folder)
            self.assertFalse(result['current_constraints_checked'])
            with self.assertRaises(ValueError): module.preflight(folder, root=f.root)

    def test_consumed_candidate_summary_does_not_reopen_execution(self):
        for module in (tt, at):
            helper, f = self.candidate(module); helper.approve(f); (f.folder/'trial-run').mkdir()
            self.assertFalse(rs.inspect(module.ADAPTER, f.folder)['execution_authorized'])
            with self.assertRaises(ValueError): helper.invoke(f, 'preflight')

    def test_pause_remains_an_independent_execution_block(self):
        f, folder, prepared = self.baseline(tb); f.approve(tb, folder, prepared['sha256'])
        with patch('research_harness.data_admission.assert_source_allowed', side_effect=ValueError('paused')):
            self.assertFalse(rs.inspect(tb.ADAPTER, folder)['current_constraints_checked'])
            with self.assertRaisesRegex(ValueError, 'paused'): tb.preflight(folder, root=f.root)

    def test_unknown_or_sr_workflow_is_rejected_before_paths(self):
        with patch.object(rs, 'Path') as path:
            for value in ('swinir-s-x2', 'tabular-regression', '../anything', {}, None):
                with self.assertRaisesRegex(ValueError, 'four Abalone/Airfoil'):
                    rs.inspect(value, '/missing')
            path.assert_not_called()

    def test_wrong_workflow_never_falls_back(self):
        _, folder, _ = self.baseline(tb)
        with self.assertRaises((ValueError, OSError, KeyError)): rs.inspect(ab.ADAPTER, folder)

    def test_changed_frozen_protocol_even_with_new_digest_is_rejected(self):
        for module in (tb, ab):
            _, folder, _ = self.baseline(module)
            self.rewrite(folder/'bundle.json', lambda c: c['recipe'].update(stop='keep trying'))
            with self.assertRaises(ValueError): rs.inspect(module.ADAPTER, folder)

    def test_changed_data_or_source_inventory_is_rejected(self):
        for mutation in ('data', 'source'):
            _, folder, _ = self.baseline(tb)
            if mutation == 'data': (folder/'train.json').write_text('[]')
            else: self.rewrite(folder/'bundle.json', lambda c: c['sources'].update({'research_harness/cli.py': '0'*64}))
            with self.assertRaises(ValueError): rs.inspect(tb.ADAPTER, folder)

    def test_changed_candidate_code_is_rejected(self):
        for module in (tt, at):
            _, f = self.candidate(module); (f.folder/'candidate.py').write_text('raise RuntimeError()')
            with self.assertRaises(ValueError): rs.inspect(module.ADAPTER, f.folder)

    def test_baseline_replaced_after_native_audit_is_rejected(self):
        _, f = self.candidate(tt)
        original = read_json(f.folder/'baseline/bundle.json')
        changed = dict(original, content=dict(original['content'], counts={}))
        for replacement in ([], {}, changed):
            with patch.object(rs, 'read_json', return_value=replacement):
                with self.assertRaisesRegex(ValueError, 'Baseline changed'):
                    rs.inspect(tt.ADAPTER, f.folder)

    def test_mismatched_qualification_is_rejected(self):
        for module in (tb, ab):
            _, folder, _ = self.baseline(module)
            self.rewrite(folder/'bundle.json', lambda c: c['data_admission']['context'].update(intended_use='other purpose'))
            with self.assertRaises(ValueError): rs.inspect(module.ADAPTER, folder)

    def test_imported_evidence_marker_blocks_all_four_routes(self):
        for module in (tb, ab):
            _, folder, _ = self.baseline(module); (folder/'EVIDENCE_ONLY.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'audit-only'): rs.inspect(module.ADAPTER, folder)
        for module in (tt, at):
            _, f = self.candidate(module); (f.folder/'baseline/EVIDENCE_ONLY.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'audit-only'): rs.inspect(module.ADAPTER, f.folder)

    def test_linked_directory_and_dangling_evidence_marker_rejected(self):
        f, folder, _ = self.baseline(tb)
        link = f.root/'alias'; link.symlink_to(folder, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'regular directory'): rs.inspect(tb.ADAPTER, link)
        (folder/'EVIDENCE_ONLY.json').symlink_to(f.root/'missing')
        with self.assertRaisesRegex(ValueError, 'audit-only'): rs.inspect(tb.ADAPTER, folder)

    def test_summary_excludes_raw_rows_predictions_and_evidence_full_text(self):
        _, f = self.candidate(tt)
        # Give the archived full text a unique marker: the shared fixture's
        # original 'NOT VERIFIED' also occurs legitimately in proposal claims.
        self.rewrite(f.folder/'trial.json', lambda c: c['literature'][0].update(full_text='PRIVATE_FULL_TEXT_SENTINEL_729'))
        result = rs.inspect(tt.ADAPTER, f.folder)
        self.assertEqual(set(result['dataset']), {'source', 'counts', 'unit', 'partition_manifest_sha256'})
        self.assertNotIn('literature', result); self.assertNotIn('predictions', result)
        self.assertNotIn('evidence', result['data_qualification'])
        self.assertNotIn('qualification', result['data_qualification'])
        serialized = json.dumps(result)
        c = read_json(f.folder/'trial.json')['content']
        self.assertNotIn(c['literature'][0]['full_text'], serialized)
        self.assertNotIn(read_json(f.folder/'baseline/train.json')[0]['id'], serialized)
        self.assertEqual(result['data_qualification']['scope'], 'protocol_design_only')
        self.assertEqual(set(result['data_qualification']['criteria'].values()), {'supported'})

    def test_fixture_without_qualification_is_explicit(self):
        f, folder, _ = self.baseline(tb)
        raw = [dict(row) for row in f.rows]
        plain = f.root/'plain'; tb.prepare_rows(raw, plain, tb.FIXTURE, root=f.root)
        self.assertEqual(rs.inspect(tb.ADAPTER, plain)['data_qualification']['status'], 'ABSENT_SOFTWARE_FIXTURE_ONLY')

    def test_cli_summary_does_not_create_workspace_or_approval(self):
        f, folder, _ = self.baseline(tb); before = self.files(f.root)
        code, out, err = self.cli('--workspace', str(f.root/'unused'), 'task', 'review',
                                  '--workflow', tb.ADAPTER, '--review', str(folder))
        self.assertEqual(code, 0, err); self.assertEqual(json.loads(out), rs.inspect(tb.ADAPTER, folder))
        self.assertEqual(before, self.files(f.root)); self.assertFalse((f.root/'unused').exists())

    def test_cli_invalid_material_has_nonzero_exit_without_summary(self):
        _, folder, _ = self.baseline(tb); (folder/'train.json').write_text('[]')
        code, out, err = self.cli('task', 'review', '--workflow', tb.ADAPTER, '--review', str(folder))
        self.assertEqual(code, 1); self.assertEqual(out, ''); self.assertTrue(err)


if __name__ == '__main__':
    unittest.main()
