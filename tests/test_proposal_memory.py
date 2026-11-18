"""Proposal occupancy fixtures only: no model, search, training or scored data."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research_harness import proposal_memory as pm, tabular_handoff as th
from research_harness import tabular_memory as tm, airfoil_memory as am, data_blocks as db
from research_harness import tabular_proposer as proposer, tabular_workflow as workflow
from research_harness.core import digest
from research_harness.tabular_trial import scope_for


class ProposalMemoryTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve()
        self.record={'scope':digest('scope'),'baseline_sha256':digest('baseline')}

    def local(self, root=None, record=None, empty=False):
        row=record or self.record; root=root or self.root
        folder=root/'.research-memory/tabular-proposer'/row['scope']; folder.mkdir(parents=True)
        if not empty:
            (folder/'reservation.json').write_text(json.dumps({**row,'status':'RESERVED'}))
        return folder

    def packet(self, rows=None, name='packet.json', blocks=None):
        packet=th.envelope(tm.envelope([]),db._envelope(blocks or []),am.envelope([]),
                           pm.envelope([self.record] if rows is None else rows))
        path=self.root/name; path.write_bytes(th._encoded(packet)); return path,packet

    def baseline(self):
        from test_tabular_trial import TrialTests
        f=TrialTests(); f.setUp(); self.addCleanup(f.doCleanups)
        packet,_,_,_=proposer.validated_baseline(f.base)
        return f,packet,{'scope':scope_for(packet),'baseline_sha256':packet['sha256']}

    def test_empty_and_completed_reservations_stay_occupied_without_result_claims(self):
        folder=self.local(empty=True)
        self.assertEqual(pm.snapshot(self.root),[{**self.record,'baseline_sha256':None}])
        path=self.root/'handoff.json'; th.export(path,self.root)
        receiver=self.root/'receiver'; th.import_state(path,receiver)
        with self.assertRaisesRegex(ValueError,'Imported proposal'): pm.assert_available(self.record['scope'],receiver)
        (folder/'reservation.json').write_text(json.dumps({**self.record,'status':'RESERVED'}))
        # Result files are deliberately not treated as scientific decisions or exported.
        (folder/'decision.json').write_text(json.dumps({'status':'REJECTED','reason':'private actor text'}))
        newer=self.root/'newer.json'; th.export(newer,self.root); th.import_state(newer,receiver)
        self.assertEqual(pm.snapshot(receiver),[self.record])
        self.assertNotIn('private actor text',newer.read_text())

    def test_binding_enrichment_is_order_independent_and_conflicts_rejected(self):
        unknown={**self.record,'baseline_sha256':None}
        for rows in ([unknown,self.record],[self.record,unknown]):
            self.assertEqual(pm.merge(rows),[self.record])
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            pm.merge([self.record],[{**self.record,'baseline_sha256':digest('other')}])

    def test_repeat_and_legacy_import_cannot_clear_occupancy(self):
        path,_=self.packet(); receiver=self.root/'receiver'; th.import_state(path,receiver)
        self.assertEqual(th.import_state(path,receiver)['status'],'ALREADY_IMPORTED')
        for args in ((tm.envelope([]),db._envelope([])),(tm.envelope([]),db._envelope([]),am.envelope([]))):
            old=th.envelope(*args); legacy=self.root/'legacy.json'; legacy.write_bytes(th._encoded(old))
            self.assertIsNone(th.verify(legacy)['proposal_records'])
            self.assertIn('proposer NOT_INCLUDED',th.verify(legacy)['scope'])
            th.import_state(legacy,receiver)
            self.assertEqual(pm.snapshot(receiver),[self.record])
        out=self.root/'forward.json'; th.export(out,receiver)
        self.assertEqual(th.verify(out)['version'],4)
        self.assertEqual(th.verify(out)['proposal_records'],1)

    def test_conflicting_fourth_component_prevents_new_pause(self):
        path,_=self.packet(); receiver=self.root/'receiver'; th.import_state(path,receiver)
        block={'dataset':{'id':'synthetic','version':'1','source':'fixture'},'qualification_sha256':'a'*64,
               'reviewer':'SOFTWARE','reason':'Must not import on conflict'}
        bad,_=self.packet([{**self.record,'baseline_sha256':digest('other')}],name='conflict.json',blocks=[block])
        before=th.status(receiver)
        with self.assertRaisesRegex(ValueError,'Conflicting'): th.import_state(bad,receiver)
        self.assertEqual(th.status(receiver),before); self.assertEqual(db._load(receiver),[])

    def test_missing_corrupt_or_downgraded_component_rejected_before_import(self):
        path,original=self.packet()
        for mutate in (lambda p:p['payload'].pop('proposal_memory'),
                       lambda p:p['payload']['proposal_memory'].update(sha256='0'*64),
                       lambda p:p['payload'].update(version=2),
                       lambda p:p['payload'].update(version=True)):
            p=copy.deepcopy(original); mutate(p); p['sha256']=digest(p['payload']); path.write_bytes(th._encoded(p))
            with self.assertRaises(ValueError): th.import_state(path,self.root/'receiver')
            self.assertFalse((self.root/'receiver').exists())

    def test_failed_publish_and_postpublish_interruption_keep_all_or_none(self):
        path,_=self.packet(); receiver=self.root/'receiver'
        with patch.object(th.os,'link',side_effect=OSError('fixture interruption')):
            with self.assertRaises(OSError): th.import_state(path,receiver)
        self.assertEqual(pm.snapshot(receiver),[])
        link=os.link
        def interrupted(source,target): link(source,target); raise OSError('after publication')
        with patch.object(th.os,'link',side_effect=interrupted):
            with self.assertRaises(OSError): th.import_state(path,receiver)
        self.assertEqual(pm.snapshot(receiver),[self.record])
        self.assertEqual(th.import_state(path,receiver)['status'],'ALREADY_IMPORTED')

    def test_malformed_linked_and_nonregular_local_reservation_fail_closed(self):
        folder=self.local(); path=folder/'reservation.json'; original=path.read_text()
        for raw in ('{}','{',original.replace(self.record['scope'],'f'*64),original.replace('RESERVED','RELEASED')):
            path.write_text(raw)
            with self.assertRaises(ValueError): pm.snapshot(self.root)
        path.unlink(); other=self.root/'original.json'; other.write_text(original); path.symlink_to(other)
        with self.assertRaises(ValueError): pm.snapshot(self.root)
        path.unlink(); folder.rmdir(); folder.write_text('not a directory')
        with self.assertRaises(ValueError): pm.snapshot(self.root)

    def test_corrupt_combined_state_blocks_every_reader(self):
        path,packet=self.packet(); receiver=self.root/'receiver'; th.import_state(path,receiver)
        target=th._folder(receiver)/(packet['sha256']+'.json'); target.write_text('{}')
        for read in (pm.snapshot,tm.snapshot,am.snapshot,db._load):
            with self.assertRaises(ValueError): read(receiver)

    def test_schema_and_history_bounds_never_accept_recovery_authority(self):
        for mutate in (lambda r:r.update(scope='bad'),lambda r:r.update(state='STOP'),
                       lambda r:r.update(baseline_sha256=True),lambda r:r.update(recovery_authorized=True)):
            row=dict(self.record); mutate(row)
            with self.assertRaises(ValueError): pm.envelope([row])
        with self.assertRaises(ValueError): pm.envelope([{**self.record,'scope':format(i,'064x')} for i in range(1001)])
        for v in (True,2):
            packet=pm.envelope([]); packet['content']['version']=v; packet['sha256']=digest(packet['content'])
            with self.assertRaises(ValueError): pm.validate_packet(packet)

    def test_v2_original_raw_size_ceiling_survives_v3(self):
        path=self.root/'large.json'; raw=th._encoded(th.envelope(tm.envelope([]),db._envelope([]),am.envelope([])))
        path.write_bytes(raw+b' '*(16*1024*1024+1-len(raw)))
        with self.assertRaisesRegex(ValueError,'Legacy v2'): th.import_state(path,self.root/'receiver')
        self.assertFalse((self.root/'receiver').exists())

    def test_direct_and_unified_proposal_reject_import_before_probe_or_outputs(self):
        f,packet,row=self.baseline(); path,_=self.packet([row]); th.import_state(path,f.root)
        with patch('research_harness.doctor.isolation_probe') as probe,patch.object(proposer,'bounded_process') as actor:
            with self.assertRaisesRegex(ValueError,'Imported proposal'):
                proposer.propose(f.base,f.root/'renamed-proposal',root=f.root)
            probe.assert_not_called(); actor.assert_not_called()
        with patch.object(proposer,'propose') as actor:
            with self.assertRaisesRegex(ValueError,'Imported proposal'):
                workflow.research('renamed','propose',f.base,root=f.root)
            actor.assert_not_called()
        self.assertFalse((f.root/'renamed-proposal').exists()); self.assertFalse((f.root/'runs').exists())

    def test_import_during_probe_is_rejected_before_reservation_or_actor(self):
        f,packet,row=self.baseline(); _,handoff=self.packet([row])
        def probe(**kwargs):
            # Normal importer takes the same lock; emulate out-of-band publication.
            folder=th._folder(f.root); folder.mkdir(parents=True)
            th._publish(handoff,folder/(handoff['sha256']+'.json')); return {}
        with patch('research_harness.doctor.isolation_probe',side_effect=probe),patch.object(proposer,'bounded_process') as actor:
            with self.assertRaisesRegex(ValueError,'Imported proposal'): proposer.propose(f.base,f.root/'out',root=f.root)
            actor.assert_not_called()
        self.assertFalse((f.root/'out').exists()); self.assertFalse((f.root/'.research-memory/tabular-proposer').exists())

    def test_local_reservation_during_probe_is_also_rechecked(self):
        f,packet,row=self.baseline()
        def probe(**kwargs): self.local(f.root,row,empty=True); return {}
        with patch('research_harness.doctor.isolation_probe',side_effect=probe),patch.object(proposer,'bounded_process') as actor:
            with self.assertRaisesRegex(ValueError,'already reserved'): proposer.propose(f.base,f.root/'out',root=f.root)
            actor.assert_not_called()
        self.assertFalse((f.root/'out').exists())

    def recovery(self):
        f,packet,row=self.baseline(); reservation=self.local(f.root,row)
        folder=f.root/'original-failure'; (folder/'process').mkdir(parents=True)
        (folder/'process.json').write_text(json.dumps({'returncode':-6}))
        result={'status':'INCOMPLETE'}
        (folder/'result.json').write_text(json.dumps(result)); (reservation/'decision.json').write_text(json.dumps(result))
        (folder/'process/stdout.log').write_text('')
        (folder/'process/stderr.log').write_text('node::InitializeOncePerProcessInternal')
        return f,packet,row,reservation,folder

    def test_original_local_recovery_remains_evidence_bound_and_one_time(self):
        f,packet,row,reservation,folder=self.recovery()
        with patch('sys.platform','darwin'):
            self.assertEqual(proposer.checked_attempt(packet,f.root,folder)[0],reservation)
            (reservation/'launch-recovery.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'already consumed'): proposer.checked_attempt(packet,f.root,folder)
            (reservation/'launch-recovery.json').unlink()
            (folder/'process/stdout.log').write_text('{"type":"thread.started"}\n')
            with self.assertRaisesRegex(ValueError,'pre-agent'): proposer.checked_attempt(packet,f.root,folder)
        with patch('sys.platform','linux'):
            with self.assertRaisesRegex(ValueError,'only to macOS'): proposer.checked_attempt(packet,f.root,folder)

    def test_imported_recovery_cannot_bypass_even_with_matching_local_evidence(self):
        f,packet,row,reservation,folder=self.recovery(); path,_=self.packet([row]); th.import_state(path,f.root)
        with patch('sys.platform','darwin'),patch('research_harness.doctor.isolation_probe') as probe:
            with self.assertRaisesRegex(ValueError,'transferred recovery'):
                proposer.propose(f.base,f.root/'new',root=f.root,recover_launch=folder)
            probe.assert_not_called()
        self.assertFalse((f.root/'new').exists()); self.assertFalse((reservation/'launch-recovery.json').exists())

    def test_recovery_evidence_is_rechecked_after_probe(self):
        f,packet,row,reservation,folder=self.recovery()
        def probe(**kwargs):
            (folder/'process/stdout.log').write_text('{"type":"thread.started"}\n'); return {}
        with patch('sys.platform','darwin'),patch('research_harness.doctor.isolation_probe',side_effect=probe),patch.object(proposer,'bounded_process') as actor:
            with self.assertRaisesRegex(ValueError,'pre-agent'):
                proposer.propose(f.base,f.root/'out',root=f.root,recover_launch=folder)
            actor.assert_not_called()
        self.assertFalse((f.root/'out').exists()); self.assertFalse((reservation/'launch-recovery.json').exists())

    def test_occupancy_does_not_mark_holdout_consumed_or_block_candidate_review(self):
        from research_harness import tabular_trial as tt
        f,packet,row=self.baseline(); path,_=self.packet([row]); th.import_state(path,f.root)
        self.assertEqual(tm.snapshot(f.root),[])
        review=f.root/'another-review'; prepared=tt.prepare(f.base,f.proposal,review,f.library,root=f.root)
        tt.approve_trial(review,prepared['sha256'],'SOFTWARE',root=f.root)
        self.assertTrue(tt.preflight_trial(review,root=f.root)['read_only'])
        self.assertFalse((review/'trial-run').exists())

    def test_unrelated_scope_remains_available_and_status_is_read_only(self):
        path,_=self.packet(); receiver=self.root/'receiver'
        self.assertTrue(th.verify(path)['read_only']); self.assertFalse(receiver.exists())
        th.import_state(path,receiver); pm.assert_available(digest('fresh'),receiver)
        untouched=self.root/'untouched'; result=th.status(untouched)
        self.assertEqual(result['proposal_records'],0); self.assertFalse(result['execution_authorized'])
        self.assertFalse(untouched.exists())
