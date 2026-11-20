"""Frozen synthetic files only; never launch a real actor or score an image."""
import copy
import io
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

from research_harness import sr_preflight as sp, memory as sm, tabular_handoff as th
from research_harness import tabular_memory as tm, data_blocks as db, airfoil_memory as am, proposal_memory as pm
from research_harness.core import digest
from research_harness.portable import new_study
from research_harness.state_lock import research_lock


class SRPreflightTests(unittest.TestCase):
    def setUp(self):
        from test_portable import PortableStudyTests
        f = PortableStudyTests(); f.setUp(); self.addCleanup(f.doCleanups)
        self.root = f.root.resolve(); self.study = new_study('prepared', self.root)
        self.output = self.root/'runs/prepared'

    def files(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def check(self):
        return sp.preflight(self.study, self.output, root=self.root)

    def import_sr(self, value):
        packet = th.envelope(tm.envelope([]), db._envelope([]), am.envelope([]), pm.envelope([]), sm.envelope(value))
        path = self.root/'incoming.json'; path.write_bytes(th._encoded(packet)); th.import_state(path, root=self.root)

    def test_valid_self_reservation_is_read_only_and_not_execution_approval(self):
        before = self.files()
        with patch('research_harness.doctor.doctor') as doctor, patch('subprocess.Popen') as process:
            result = self.check()
            self.assertEqual(result, self.check()); self.assertFalse(result['execution_authorized'])
            self.assertTrue(result['read_only']); doctor.assert_not_called(); process.assert_not_called()
        self.assertEqual(self.files(), before); self.assertFalse(self.output.exists())

    def test_new_reservation_after_preparation_blocks_old_study(self):
        new_study('later', self.root)
        with self.assertRaisesRegex(ValueError, 'constraints changed'): self.check()
        self.assertFalse(self.output.exists()); self.assertTrue(self.study.exists())

    def test_new_paper_and_stopped_route_via_v4_block_before_actor(self):
        for kind in ('paper', 'route'):
            value = sm.merge()
            if kind == 'paper': value['paper_ids'] = ['1299.12345']
            else: value['routes'] = [sm._route('synthetic', 'new stopped mechanism', 'STOP')]
            self.import_sr(value)
            with patch.object(sp, 'ROOT', self.root), patch('research_harness.doctor.doctor') as doctor, \
                 patch('research_harness.autonomy.AutonomousStudy') as actor:
                with self.assertRaisesRegex(ValueError, 'constraints changed'): sp.launch(self.output, self.study)
                doctor.assert_not_called(); actor.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_unrelated_legacy_component_import_does_not_invent_sr_change(self):
        before = self.check()
        path = self.root/'legacy.json'; path.write_bytes(th._encoded(th.envelope(tm.envelope([]), db._envelope([]))))
        th.import_state(path, root=self.root)
        self.assertEqual(before, self.check())

    def test_imported_self_terminal_or_scored_original_cannot_restart(self):
        current = sm.snapshot(self.root); own = current['studies'][0]
        value = sm.merge(); value['scored_ids'] = own['observation_ids']; self.import_sr(value)
        with self.assertRaisesRegex(ValueError, 'no longer unexecuted'): self.check()
        value['studies'] = [{**own, 'state': 'STOP'}]; self.import_sr(value)
        with self.assertRaisesRegex(ValueError, 'no longer unexecuted'): self.check()

    def test_historical_copy_foreign_root_and_renamed_study_refused(self):
        historical = self.root/'tasks/history'; shutil.copytree(self.study, historical)
        with self.assertRaisesRegex(ValueError, 'local_studies'): sp.preflight(historical, root=self.root)
        renamed = self.root/'local_studies/renamed'; shutil.copytree(self.study, renamed)
        with self.assertRaisesRegex(ValueError, 'identity'): sp.preflight(renamed, root=self.root)
        with self.assertRaisesRegex(ValueError, 'local_studies'): sp.preflight(self.study, root=self.root/'other')
        self.assertFalse(self.output.exists())

    def test_alternate_or_existing_output_refused(self):
        with self.assertRaisesRegex(ValueError, 'runs/ID'):
            sp.preflight(self.study, self.root/'elsewhere', root=self.root)
        self.output.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'already exists'): self.check()

    def test_copied_checkout_or_missing_provenance_cannot_authorize_launch(self):
        peer = self.root/'peer'; peer.mkdir()
        for name in ('templates', 'research_harness', 'assets', 'external', 'local_studies'):
            shutil.copytree(self.root/name, peer/name)
        shutil.copyfile(self.root/'requirements-sr.txt', peer/'requirements-sr.txt')
        with self.assertRaisesRegex(ValueError, 'another checkout'):
            sp.preflight(peer/'local_studies/prepared', root=peer)
        path = self.study/'inputs.lock.json'; value = json.loads(path.read_text()); value['runtime'].pop('checkout')
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'lacks launch provenance'): self.check()

    def test_evidence_markers_and_symlinks_refused(self):
        marker = self.study/'EVIDENCE_ONLY.json'; marker.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'read-only'): self.check()
        marker.unlink(); marker.symlink_to(self.root/'absent')
        with self.assertRaisesRegex(ValueError, 'read-only'): self.check()
        marker.unlink(); source = self.study/'TASK.md'; text = source.read_text(); source.unlink()
        target = self.root/'text'; target.write_text(text); source.symlink_to(target)
        with self.assertRaises(ValueError): self.check()

    def test_changed_policy_source_or_added_module_refused(self):
        for file in (self.study/'policy.json', self.root/'research_harness/code.py'):
            original = file.read_bytes(); file.write_bytes(original + b' ')
            with self.assertRaisesRegex(ValueError, 'Frozen trusted input changed'): self.check()
            file.write_bytes(original)
        (self.root/'research_harness/new_module.py').write_text('new source')
        with self.assertRaisesRegex(ValueError, 'file inventory'): self.check()

    def test_incomplete_unsafe_lock_and_inconsistent_selection_refused(self):
        path = self.study/'inputs.lock.json'; original = json.loads(path.read_text())
        for change in ('missing', 'traversal', 'hash'):
            value = copy.deepcopy(original)
            if change == 'missing': value['files'].pop('local_studies/prepared/memory.json')
            elif change == 'traversal': value['files']['../outside'] = 'a'*64
            else: value['files']['research_harness/code.py'] = 'invalid'
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError): self.check()
        path.write_text(json.dumps(original))
        selection = self.study/'selection.json'; value = json.loads(selection.read_text()); value['selected_ids'] = []
        selection.write_text(json.dumps(value))
        import hashlib
        original['files']['local_studies/prepared/selection.json'] = hashlib.sha256(selection.read_bytes()).hexdigest()
        path.write_text(json.dumps(original))
        with self.assertRaisesRegex(ValueError, 'selection differs'): self.check()

    def test_incomplete_other_reservation_blocks_without_releasing_own(self):
        (self.root/'local_studies/broken').mkdir()
        with self.assertRaises((OSError, ValueError)): self.check()
        self.assertTrue(self.study.exists()); self.assertFalse(self.output.exists())

    def test_lock_conflict_prevents_doctor_and_actor(self):
        with patch.object(sp, 'ROOT', self.root), research_lock(self.root), \
             patch('research_harness.doctor.doctor') as doctor, patch('research_harness.autonomy.AutonomousStudy') as actor:
            with self.assertRaisesRegex(ValueError, 'checkout lock'): sp.launch(self.output, self.study)
            doctor.assert_not_called(); actor.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_environment_failure_creates_no_run_or_actor(self):
        with patch.object(sp, 'ROOT', self.root), patch('research_harness.doctor.doctor', return_value={'ok': False}), \
             patch('research_harness.autonomy.AutonomousStudy') as actor:
            with self.assertRaisesRegex(ValueError, 'environment/isolation'): sp.launch(self.output, self.study)
            actor.assert_not_called()
        self.assertFalse(self.output.exists()); self.assertTrue(self.study.exists())

    def test_state_change_during_environment_probe_rechecked(self):
        def probe():
            # Simulate a noncooperating writer; normal import is prevented by the lock.
            (self.root/'research_harness/code.py').write_text('changed during probe')
            return {'ok': True}
        with patch.object(sp, 'ROOT', self.root), patch('research_harness.doctor.doctor', side_effect=probe), \
             patch('research_harness.autonomy.AutonomousStudy') as actor:
            with self.assertRaisesRegex(ValueError, 'Frozen trusted input'): sp.launch(self.output, self.study)
            actor.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_valid_launch_holds_lock_through_actor_and_both_controller_types(self):
        def fake_launch():
            with self.assertRaisesRegex(ValueError, 'checkout lock'):
                with research_lock(self.root): pass
            return {'status': 'SYNTHETIC_ONLY'}
        for literature, module in ((False, 'autonomy.AutonomousStudy'), (True, 'literature_study.LiteratureStudy')):
            with patch.object(sp, 'ROOT', self.root), patch('research_harness.doctor.doctor', return_value={'ok': True}), \
                 patch('research_harness.'+module) as controller:
                controller.return_value.launch.side_effect = fake_launch
                self.assertEqual(sp.launch(self.output, self.study, literature=literature)['status'], 'SYNTHETIC_ONLY')
                controller.assert_called_once_with(self.output, self.study)

    def test_missing_explicit_study_never_creates_lock_or_actor(self):
        with patch.object(sp, 'research_lock') as lock:
            with self.assertRaisesRegex(ValueError, 'Explicit prepared'): sp.launch(self.output)
            lock.assert_not_called()

    def test_cli_preflight_and_autonomous_use_guard(self):
        from research_harness.cli import main
        with patch.object(sp, 'preflight', return_value={'read_only': True}) as check, \
             patch('sys.argv', ['rh', 'sr-preflight', '--study', str(self.study)]), patch('sys.stdout', io.StringIO()):
            main(); check.assert_called_once_with(str(self.study), None)
        with patch.object(sp, 'launch', return_value={'status': 'SYNTHETIC_ONLY'}) as launch, \
             patch('sys.argv', ['rh', 'autonomous', '--study', str(self.study), '--out', str(self.output), '--literature']), \
             patch('sys.stdout', io.StringIO()):
            main(); launch.assert_called_once_with(str(self.output), str(self.study), literature=True)

    def test_direct_module_entry_uses_same_guard(self):
        from research_harness import autonomy
        with patch.object(sp, 'launch', return_value={'status': 'SYNTHETIC_ONLY'}) as launch, \
             patch('sys.argv', ['autonomy', '--study', str(self.study), '--out', str(self.output)]), \
             patch('sys.stdout', io.StringIO()):
            autonomy.main(); launch.assert_called_once_with(str(self.output), str(self.study))

    def test_unified_research_reuses_checked_health_inside_existing_lock(self):
        from research_harness import onboarding
        output = self.root/'runs/unified'
        with patch.object(onboarding, 'ROOT', self.root), patch('research_harness.doctor.doctor', return_value={'ok': True}) as doctor, \
             patch('research_harness.literature_study.LiteratureStudy') as actor, \
             patch.object(onboarding, 'validate_workflow', return_value={'workflow_completed': True}):
            def fake_launch():
                with self.assertRaisesRegex(ValueError, 'checkout lock'):
                    with research_lock(self.root): pass
                return {'status': 'STOP'}
            actor.return_value.launch.side_effect = fake_launch
            result = onboarding.research('unified')
            self.assertTrue(result['workflow_completed']); doctor.assert_called_once()
            actor.assert_called_once_with(output, self.root/'local_studies/unified')
