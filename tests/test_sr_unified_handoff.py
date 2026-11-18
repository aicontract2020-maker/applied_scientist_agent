"""Synthetic SR migration; never run a researcher or score real images."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from research_harness import memory as sm, sr_handoff as sr, tabular_handoff as th
from research_harness import tabular_memory as tm, data_blocks as db, airfoil_memory as am, proposal_memory as pm
from research_harness.core import digest
from research_harness.portable import new_study


class SRUnifiedHandoffTests(unittest.TestCase):
    def setUp(self):
        from test_memory import MemoryTests
        self.f = MemoryTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root = self.f.root.resolve(); self.receiver = self.root/'empty-receiver'
        self.block = {'dataset': {'id': 'fixture', 'version': '1', 'source': 'synthetic'},
                      'qualification_sha256': digest('qualification'), 'reviewer': 'SOFTWARE', 'reason': 'Synthetic pause'}

    def payload(self, state='RESERVED', name='synthetic-study'):
        value = sm.merge()
        field = 'scored_ids' if state in sm.MEASURED_STATES else 'reserved_ids'
        value[field] = ['img_013']
        value['studies'] = [{'id': name, 'policy_sha256': digest(name), 'state': state,
            'observation_ids': ['img_013'], 'plan_sha256': None, 'candidate_sha256': None}]
        return value

    def packet(self, value=None, version=4, name='packet.json', blocks=None):
        args = [tm.envelope([]), db._envelope([] if blocks is None else blocks)]
        if version >= 2: args.append(am.envelope([]))
        if version >= 3: args.append(pm.envelope([]))
        if version >= 4: args.append(sm.envelope(sm.merge() if value is None else value))
        packet = th.envelope(*args); path = self.root/name; path.write_bytes(th._encoded(packet))
        return path, packet

    def files(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()} if root.exists() else {}

    def test_roundtrip_reaches_existing_sr_preparation_and_excludes_private_material(self):
        peer = self.f.peer(); first, source = self.f.stopped()
        path = self.root/'all.json'; result = th.export(path, self.root)
        self.assertEqual(result['version'], 4); self.assertEqual(result['sr_studies'], 1)
        text = path.read_text()
        for marker in ('PRIVATE_FULL_TEXT_NOT_FOR_EXCHANGE', 'PRIVATE_ABSTRACT_NOT_FOR_EXCHANGE', 'PRIVATE_RAW_EVENT_NOT_FOR_EXCHANGE'):
            self.assertNotIn(marker, text)
        preview = th.preview(path, peer); th.import_state(path, peer, expect_preview=preview['preview_sha256'])
        self.assertEqual(sm.snapshot(peer), sm.snapshot(self.root))
        with self.assertRaisesRegex(ValueError, 'already reserved in shared'): new_study('peer-a-study', peer)
        second = new_study('next-study', peer)
        before = json.loads((first/'policy.json').read_text()); after = json.loads((second/'policy.json').read_text())
        self.assertTrue(set(before['observation_ids']).isdisjoint(after['observation_ids']))
        self.assertIn('1234.56789', after['excluded_evidence_ids'])
        self.assertIn('1299.12345', after['excluded_evidence_ids'])
        self.assertFalse(after['stopped_route_compliance']['reuses_local_route_peer-a-study'])
        self.assertTrue(any(r.get('source') == source for r in json.loads((second/'intervention-catalog.json').read_text())))
        self.assertEqual(sm.load_packet(second/'memory.json')['payload'], sm.snapshot(self.root))

    def test_missing_root_preview_has_no_writes_and_reports_all_sr_exclusions(self):
        value = self.payload(); value['paper_ids'] = ['1234.56789']
        value['routes'] = [sm._route('fixture', 'Synthetic stopped route', 'STOP')]
        path, _ = self.packet(value)
        with patch.object(th, 'research_lock', side_effect=AssertionError('No writing lock')):
            preview = th.preview(path, self.receiver)
        self.assertFalse(self.receiver.exists()); self.assertEqual(preview['missing_components'], [])
        self.assertEqual(preview['changes']['sr_memory']['after'], 4)
        self.assertFalse(preview['execution_authorized'])
        th.import_state(path, self.receiver, expect_preview=preview['preview_sha256'])
        self.assertEqual(sr.snapshot(self.receiver), value)
        self.assertFalse((self.receiver/'local_studies').exists()); self.assertFalse((self.receiver/'runs').exists())

    def test_same_count_reservation_to_terminal_change_is_visible_and_never_downgraded(self):
        initial, _ = self.packet(self.payload()); th.import_state(initial, self.receiver)
        final, _ = self.packet(self.payload('STOP'), name='final.json')
        preview = th.preview(final, self.receiver); delta = preview['changes']['sr_memory']
        self.assertEqual(delta['before'], delta['after']); self.assertEqual(delta['added'], [])
        self.assertEqual(delta['updated'], ['image:img_013', 'study:synthetic-study'])
        th.import_state(final, self.receiver, expect_preview=preview['preview_sha256'])
        th.import_state(initial, self.receiver)
        self.assertEqual(sr.snapshot(self.receiver), self.payload('STOP'))

    def test_all_nonmeasurement_states_retain_exclusions_without_inventing_stop(self):
        for state in sorted(sm.STATES):
            root = self.root/state; path, _ = self.packet(self.payload(state), name=state+'.json')
            th.import_state(path, root); result = sr.snapshot(root)
            self.assertEqual(result['studies'][0]['state'], state)
            self.assertEqual(result['routes'], [])
            self.assertEqual(set(result['scored_ids'] + result['reserved_ids']), {'img_013'})
        failed = self.payload('PROPOSAL_FAILURE')
        failed['routes'] = [sm._route('fixture', 'Published operator finding', 'REJECTED_PROPOSAL')]
        path, _ = self.packet(failed, name='proposal-failure.json'); th.import_state(path, self.root/'failure')
        self.assertEqual(sr.snapshot(self.root/'failure')['routes'][0]['disposition'], 'REJECTED_PROPOSAL')

    def test_legacy_versions_disclose_missing_sr_and_cannot_clear_it(self):
        full, _ = self.packet(self.payload('STOP')); th.import_state(full, self.receiver)
        for version in (1, 2, 3):
            path, _ = self.packet(version=version, name=f'v{version}.json')
            preview = th.preview(path, self.receiver)
            self.assertIn('sr_memory', preview['missing_components'])
            self.assertIsNone(preview['incoming']['sr_studies'])
            self.assertEqual(preview['current'], preview['merged_state'])
            th.import_state(path, self.receiver, expect_preview=preview['preview_sha256'])
        self.assertEqual(sr.snapshot(self.receiver), self.payload('STOP'))

    def test_old_sr_import_and_export_read_unified_state_and_reexport_together(self):
        peer = self.f.peer(); path, _ = self.packet(self.payload()); th.import_state(path, peer)
        old = self.root/'old-sr.json'; sm.export_memory(peer, old)
        self.assertEqual(sm.load_packet(old)['payload'], sm.snapshot(peer))
        value = sm.merge(); value['reserved_ids'] = ['img_014']
        old.write_text(json.dumps(sm.envelope(value))); sm.import_memory(peer, old)
        self.assertEqual(sm.snapshot(peer)['reserved_ids'], ['img_013', 'img_014'])
        combined = self.root/'forward.json'; th.export(combined, peer); th.import_state(combined, self.receiver)
        self.assertEqual(sr.snapshot(self.receiver), sm.snapshot(peer))
        with self.assertRaises(ValueError): sm.import_memory(peer, combined)

    def test_sr_identity_terminal_and_overlap_conflicts_reject_entire_packet(self):
        path, _ = self.packet(self.payload('STOP')); th.import_state(path, self.receiver)
        before = self.files(self.receiver)
        for i, change in enumerate(({'policy_sha256': digest('changed')}, {'state': 'CONTINUE'}, {'id': 'different-study'})):
            value = self.payload('STOP'); value['studies'][0].update(change)
            incoming, _ = self.packet(value, name=f'conflict-{i}.json', blocks=[self.block])
            for operation in (th.preview, th.import_state):
                with self.assertRaisesRegex(ValueError, 'Conflicting|Overlapping'): operation(incoming, self.receiver)
            self.assertEqual(db._load(self.receiver), []); self.assertEqual(self.files(self.receiver), before)

    def test_new_sr_constraint_invalidates_bound_preview(self):
        initial, _ = self.packet(); old = th.preview(initial, self.receiver)
        new, _ = self.packet(self.payload(), name='new.json'); th.import_state(new, self.receiver)
        before = self.files(self.receiver)
        with self.assertRaisesRegex(ValueError, 'preview changed'):
            th.import_state(initial, self.receiver, expect_preview=old['preview_sha256'])
        self.assertEqual(self.files(self.receiver), before)

    def test_wrong_task_missing_component_hash_and_reclamation_fail_before_writes(self):
        path, original = self.packet(self.payload())
        changes = [lambda p: p['payload'].pop('sr_memory'),
                   lambda p: p['payload']['sr_memory'].update(sha256='0'*64),
                   lambda p: p['payload']['sr_memory']['payload'].update(task='wrong-dataset'),
                   lambda p: p['payload']['sr_memory']['payload'].update(reserved_ids=[])]
        for change in changes:
            value = copy.deepcopy(original); change(value); value['sha256'] = digest(value['payload'])
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError): th.import_state(path, self.receiver)
            self.assertFalse(self.receiver.exists())

    def test_atomic_publication_failure_activates_neither_sr_nor_pause(self):
        path, _ = self.packet(self.payload(), blocks=[self.block])
        with patch.object(th.os, 'link', side_effect=OSError('publish failed')):
            with self.assertRaises(OSError): th.import_state(path, self.receiver)
        self.assertEqual(sr.snapshot(self.receiver), sm.merge()); self.assertEqual(db._load(self.receiver), [])
        self.assertEqual(list(th._folder(self.receiver).iterdir()), [])
        original = os.link
        def after_publish(src, dst): original(src, dst); raise OSError('after publish')
        with patch.object(th.os, 'link', side_effect=after_publish):
            with self.assertRaises(OSError): th.import_state(path, self.receiver)
        self.assertEqual(sr.snapshot(self.receiver), self.payload()); self.assertEqual(db._load(self.receiver), [self.block])
        self.assertEqual(th.import_state(path, self.receiver)['status'], 'ALREADY_IMPORTED')

    def test_corrupt_unified_store_blocks_sr_preparation_before_new_reservation(self):
        peer = self.f.peer(); path, packet = self.packet(self.payload()); th.import_state(path, peer)
        (th._folder(peer)/(packet['sha256']+'.json')).write_text('{}')
        with self.assertRaises(ValueError): new_study('must-not-start', peer)
        self.assertFalse((peer/'local_studies/must-not-start').exists())
        with self.assertRaises(ValueError): sm.snapshot(peer)

    def test_partial_templates_empty_reservations_and_linked_history_are_not_empty(self):
        for name in ('history.json', 'policy.json'):
            peer = self.f.peer(); (peer/'templates/sr'/name).unlink()
            with self.assertRaises((ValueError, OSError)): th.status(peer)
            shutil.rmtree(peer)
        peer = self.f.peer(); (peer/'local_studies/empty-reservation').mkdir(parents=True)
        with self.assertRaises((ValueError, OSError)): th.status(peer)
        shutil.rmtree(peer/'templates')
        with self.assertRaisesRegex(ValueError, 'Incomplete SR history'): th.status(peer)
        shutil.rmtree(peer)
        peer = self.f.peer(); path = peer/'templates/sr/history.json'; path.unlink()
        path.symlink_to(self.root/'templates/sr/history.json')
        with self.assertRaises(ValueError): th.status(peer)

    def test_legacy_sr_store_links_and_non_directory_fail_closed(self):
        store = self.receiver/'.research-memory/packets'; store.parent.mkdir(parents=True)
        store.write_text('not a directory')
        with self.assertRaises(ValueError): th.status(self.receiver)
        store.unlink(); store.symlink_to(self.root/'missing', target_is_directory=True)
        with self.assertRaises(ValueError): th.status(self.receiver)

    def test_merged_sr_limit_rejects_without_importing_other_components(self):
        def large(start):
            value = sm.merge(); value['routes'] = [sm._route(f'route-{i}', 'Fixture source text', 'STOP', 'x'*80000 + str(i)) for i in range(start, start+30)]
            return value
        first, _ = self.packet(large(0)); th.import_state(first, self.receiver)
        before = self.files(self.receiver)
        second, _ = self.packet(large(30), name='large-next.json', blocks=[self.block])
        for operation in (th.preview, th.import_state):
            with self.assertRaisesRegex(ValueError, 'component exceeds'): operation(second, self.receiver)
        self.assertEqual(self.files(self.receiver), before); self.assertEqual(db._load(self.receiver), [])

    def test_old_version_byte_ceilings_are_preserved(self):
        self.assertEqual(th.VERSION_LIMITS, {1: 12*1024**2, 2: 16*1024**2, 3: 20*1024**2, 4: 24*1024**2})
        path, _ = self.packet(version=3)
        raw = path.read_bytes(); path.write_bytes(raw + b' '*(th.VERSION_LIMITS[3]+1-len(raw)))
        with self.assertRaisesRegex(ValueError, 'Legacy v3'): th.load_packet(path)

    def test_cli_preview_and_import_without_models_or_scientific_dependencies(self):
        path, _ = self.packet(self.payload()); repo = str(Path(__file__).resolve().parents[1])
        def cli(*args):
            result = subprocess.run([sys.executable, '-m', 'research_harness', 'handoff', '--root', str(self.receiver), *args],
                cwd=self.root, env={**os.environ, 'PYTHONPATH': repo}, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr); return json.loads(result.stdout)
        before = cli('preview', str(path)); self.assertFalse(self.receiver.exists())
        cli('import', str(path), '--expect-preview', before['preview_sha256'])
        result = cli('status'); self.assertEqual(result['sr_reserved_originals'], 1)
        self.assertFalse(result['execution_authorized']); self.assertFalse((self.receiver/'runs').exists())
