"""Airfoil memory migration software fixtures; no research runs or model calls."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_harness import airfoil_memory as am, airfoil_baseline as ab, airfoil_trial as at
from research_harness import tabular_handoff as th, tabular_memory as tm, data_blocks as db
from research_harness.core import digest


class AirfoilMemoryTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve(); self.base={'content':{'source':ab.FIXTURE}}

    def record(self, phase='candidate', state='RESERVED'):
        return {'phase':phase,'scope':(ab.scope if phase=='baseline' else at.scope)(self.base),
                'review_sha256':digest(['fixture',phase]),'mechanism':None if phase=='baseline' else at.MECHANISM,
                'state':state,'result_sha256':None if state=='RESERVED' else digest(['result',phase,state])}

    def packet(self, records, name='packet.json', blocks=None):
        packet=th.envelope(tm.envelope([]),db._envelope(blocks or []),am.envelope(records))
        path=self.root/name; path.write_bytes(th._encoded(packet)); return path,packet

    def local(self, phase='candidate', state=None):
        row=self.record(phase); folder=self.root/'.research-memory'/('airfoil-baseline' if phase=='baseline' else 'airfoil-trial')/row['scope']
        folder.mkdir(parents=True)
        reserved={'review_sha256':row['review_sha256'],'status':'RESERVED'}
        if phase=='candidate': reserved.update(scope=row['scope'],mechanism=row['mechanism'])
        (folder/'reservation.json').write_text(json.dumps(reserved))
        if state:
            decision={**reserved,'status':state,'result_sha256':digest(['result',phase,state])}
            if phase=='baseline': decision.update(status='STOP' if state=='INVALID' else state,measurement_valid=state!='INVALID')
            (folder/'decision.json').write_text(json.dumps(decision))
        return folder

    def build(self, phase):
        from test_data_blocks import DataBlockTests
        helper=DataBlockTests(); self.addCleanup(helper.doCleanups)
        if phase=='baseline':
            root,folder,prepared,_,_=helper.baseline(ab)
            return root,folder,prepared,lambda op:getattr(ab,op)(folder,root=root)
        candidate,f=helper.candidate(at)
        return f.root,f.folder,f.prepared,lambda op:candidate.invoke(f,op)

    def test_local_both_phases_export_terminal_and_invalid_without_reclaim(self):
        self.local('baseline','INVALID'); self.local('candidate','STOP')
        self.assertEqual(am.snapshot(self.root),am.merge([self.record('baseline','INVALID'),self.record('candidate','STOP')]))
        path=self.root/'export.json'; th.export(path,self.root)
        receiver=self.root/'receiver'; th.import_state(path,receiver)
        self.assertEqual(am.snapshot(receiver),am.snapshot(self.root))
        for phase in ('baseline','candidate'):
            with self.assertRaisesRegex(ValueError,'reserved/consumed'):
                am.assert_available(phase,self.record(phase)['scope'],receiver,at.MECHANISM)
        with self.assertRaisesRegex(ValueError,'Stopped'):
            am.assert_available('candidate',digest('fresh-data'),receiver,at.MECHANISM)

    def test_empty_reservation_directory_is_carried_conservatively(self):
        row=self.record(); folder=self.root/'.research-memory/airfoil-trial'/row['scope']; folder.mkdir(parents=True)
        records=am.snapshot(self.root); self.assertIsNone(records[0]['review_sha256'])
        self.assertEqual(records[0]['state'],'RESERVED')
        path=self.root/'export.json'; th.export(path,self.root)
        receiver=self.root/'receiver'; th.import_state(path,receiver)
        with self.assertRaisesRegex(ValueError,'reserved/consumed'): at.assert_available(receiver,self.base)

    def test_partial_or_changed_decision_blocks_snapshot_without_guessing(self):
        folder=self.local('candidate','STOP'); original=(folder/'decision.json').read_text()
        for field,value in (('scope','f'*64),('mechanism','other'),('review_sha256','e'*64),('status','RESERVED')):
            decision=json.loads(original); decision[field]=value; (folder/'decision.json').write_text(json.dumps(decision))
            with self.assertRaises(ValueError): am.snapshot(self.root)
        (folder/'decision.json').write_text(original); (folder/'reservation.json').unlink()
        with self.assertRaisesRegex(ValueError,'without reservation'): am.snapshot(self.root)

    def test_stale_merge_never_releases_terminal_and_enrichment_is_order_independent(self):
        row=self.record(state='STOP'); legacy={**row,'result_sha256':None}; reserved=self.record()
        unknown={**reserved,'review_sha256':None}
        for groups in ([unknown,reserved,legacy,row],[row,legacy,reserved,unknown]):
            self.assertEqual(am.merge(groups),[row])
        for field,value in (('state','CONTINUE'),('review_sha256','f'*64),('result_sha256','e'*64),('mechanism','different')):
            with self.assertRaisesRegex(ValueError,'Conflicting'): am.merge([row],[{**row,field:value}])

    def test_phases_are_distinct_and_invalid_does_not_claim_scientific_stop(self):
        path,_=self.packet([self.record('baseline','CONTINUE'),self.record('candidate','INVALID')])
        th.import_state(path,self.root/'receiver')
        am.assert_available('candidate',digest('new-dataset'),self.root/'receiver',at.MECHANISM)
        am.assert_available('baseline',digest('new-dataset'),self.root/'receiver')

    def test_v2_and_v1_compatibility_without_silent_airfoil_coverage(self):
        path,_=self.packet([self.record(state='STOP')]); receiver=self.root/'receiver'
        th.import_state(path,receiver)
        old=th.envelope(tm.envelope([]),db._envelope([])); v1=self.root/'v1.json'; v1.write_text(json.dumps(old))
        self.assertIsNone(th.verify(v1)['airfoil_records']); self.assertIn('NOT_INCLUDED',th.verify(v1)['scope'])
        th.import_state(v1,receiver); self.assertEqual(am.snapshot(receiver),[self.record(state='STOP')])
        out=self.root/'new.json'; th.export(out,receiver)
        self.assertEqual(th.verify(out)['version'],2); self.assertEqual(th.verify(out)['airfoil_records'],1)

    def test_airfoil_conflict_prevents_importing_new_pause(self):
        path,_=self.packet([self.record(state='STOP')]); receiver=self.root/'receiver'; th.import_state(path,receiver)
        block={'dataset':{'id':'fixture','version':'1','source':'synthetic'},'qualification_sha256':'a'*64,'reviewer':'SOFTWARE','reason':'not partially imported'}
        other,_=self.packet([self.record(state='CONTINUE')],name='conflict.json',blocks=[block])
        before=th.status(receiver)
        with self.assertRaises(ValueError): th.import_state(other,receiver)
        self.assertEqual(before,th.status(receiver)); self.assertEqual(db._load(receiver),[])

    def test_missing_or_corrupt_third_component_is_not_accepted_as_v1(self):
        path,original=self.packet([self.record()])
        for mutate in (lambda p:p['payload'].pop('airfoil_memory'),
                       lambda p:p['payload']['airfoil_memory'].update(sha256='0'*64),
                       lambda p:p['payload'].update(version=1)):
            packet=copy.deepcopy(original); mutate(packet); packet['sha256']=digest(packet['payload']); path.write_text(json.dumps(packet))
            with self.assertRaises(ValueError): th.import_state(path,self.root/'receiver')
            self.assertFalse((self.root/'receiver/.research-memory').exists())

    def test_imported_reservations_block_both_approved_execution_paths(self):
        for phase,module in (('baseline',ab),('candidate',at)):
            root,folder,prepared,invoke=self.build(phase)
            row={**self.record(phase),'review_sha256':prepared['sha256']}
            path,_=self.packet([row]); th.import_state(path,root)
            for operation in ('preflight','execute'):
                with patch.object(module,'environment') as env,patch('research_harness.tabular_sandbox.isolated_worker') as worker:
                    with self.assertRaisesRegex(ValueError,'reserved/consumed'): invoke(operation)
                    env.assert_not_called(); worker.assert_not_called()
            self.assertFalse((folder/'run').exists()); self.assertFalse((folder/'trial-run').exists())

    def test_probe_time_import_is_rechecked_before_reservation(self):
        for phase,module in (('baseline',ab),('candidate',at)):
            root,folder,prepared,invoke=self.build(phase)
            _,packet=self.packet([{**self.record(phase),'review_sha256':prepared['sha256']}])
            def probe(*args):
                # Normal import shares the checkout lock. Simulate an out-of-band publication.
                destination=th._folder(root); destination.mkdir(parents=True)
                th._publish(packet,destination/(packet['sha256']+'.json')); return {}
            with patch.object(module,'environment',return_value={}),patch('research_harness.tabular_sandbox.isolation_probe',side_effect=probe),patch('research_harness.tabular_sandbox.isolated_worker') as worker:
                with self.assertRaisesRegex(ValueError,'reserved/consumed'): invoke('execute')
                worker.assert_not_called()
            self.assertFalse((folder/'run').exists()); self.assertFalse((folder/'trial-run').exists())
            self.assertFalse((root/'.research-memory/airfoil-baseline').exists()); self.assertFalse((root/'.research-memory/airfoil-trial').exists())

    def test_public_baseline_prepare_checks_import_before_reading_raw_data(self):
        from examples.data_qualification.baseline import qualification,USE
        packet=qualification(self.root/'qualification',ab.ADAPTER,ab.SOURCE)
        scope=ab.scope({'content':{'source':ab.SOURCE}})
        path,_=self.packet([{**self.record('baseline'),'scope':scope}]); th.import_state(path,self.root)
        with patch.object(ab,'parse') as parse:
            with self.assertRaisesRegex(ValueError,'reserved/consumed'):
                ab.prepare('never-read',self.root/'output',self.root/'qualification/packet.json',USE,root=self.root)
            parse.assert_not_called()
        self.assertFalse((self.root/'output').exists())

    def test_linked_and_corrupt_stored_state_fail_all_three_readers(self):
        path,packet=self.packet([self.record()]); receiver=self.root/'receiver'; th.import_state(path,receiver)
        target=th._folder(receiver)/(packet['sha256']+'.json'); target.write_text('{}')
        for read in (am.snapshot,tm.snapshot,db._load):
            with self.assertRaises(ValueError): read(receiver)
        target.unlink(); target.symlink_to(path)
        with self.assertRaises(ValueError): am.snapshot(receiver)

    def test_published_a1_a2_exclusions_are_derived_read_only(self):
        paths=[ab.ROOT/'tasks/airfoil_noise'/name for name in ('a1/review-manifest.json','a1/reservation-decision.json','trial-history.json')]
        before={str(p):p.read_bytes() for p in paths}
        records=am._published(ab.ROOT)
        self.assertEqual({r['phase'] for r in records},{'baseline','candidate'})
        self.assertTrue(all(r['state']=='CONTINUE' for r in records))
        self.assertEqual(before,{str(p):p.read_bytes() for p in paths})

    def test_record_schema_and_limit_reject_unknown_or_unbounded_history(self):
        for mutate in (lambda r:r.update(phase='sr'),lambda r:r.update(state='RELEASED'),
                       lambda r:r.update(result_sha256='a'*64),lambda r:r.update(scope='bad'),
                       lambda r:r.update(phase='baseline'),lambda r:r.update(execution_authorized=True)):
            row=self.record(); mutate(row)
            with self.assertRaises(ValueError): am.envelope([row])
        with self.assertRaises(ValueError): am.envelope([{**self.record(),'scope':format(i,'064x')} for i in range(1001)])

    def test_import_blocks_new_preparation_and_approval_without_outputs(self):
        for phase,module in (('baseline',ab),('candidate',at)):
            root,folder,prepared,_=self.build(phase)
            path,_=self.packet([{**self.record(phase),'review_sha256':prepared['sha256']}]); th.import_state(path,root)
            with self.assertRaisesRegex(ValueError,'reserved/consumed'):
                module.approve(folder,prepared['sha256'],'SOFTWARE',root=root)
            output=root/'never-created'
            with self.assertRaisesRegex(ValueError,'reserved/consumed'):
                if phase=='baseline': ab.prepare_rows([],output,root=root)
                else: at.prepare(folder/'baseline','proposal-never-read',output,root=root)
            self.assertFalse(output.exists())

    def test_top_level_cli_and_legacy_alias_share_v2_state(self):
        path,_=self.packet([self.record()]); repo=str(Path(__file__).resolve().parents[1]); receiver=self.root/'cli-receiver'
        def cli(*args):
            return subprocess.run([sys.executable,'-m','research_harness',*args],cwd=self.root,
                                  env={**os.environ,'PYTHONPATH':repo},capture_output=True,text=True,timeout=15)
        result=cli('handoff','--root',str(receiver),'verify',str(path))
        self.assertEqual(result.returncode,0,result.stderr); self.assertFalse(receiver.exists())
        result=cli('handoff','--root',str(receiver),'import',str(path)); self.assertEqual(result.returncode,0,result.stderr)
        new=cli('handoff','--root',str(receiver),'status')
        old=cli('tabular','handoff','--root',str(receiver),'status')
        self.assertEqual(new.stdout,old.stdout); self.assertEqual(json.loads(new.stdout)['airfoil_records'],1)
        self.assertFalse(json.loads(new.stdout)['execution_authorized'])

    def test_v1_keeps_original_raw_byte_limit_after_v2_upgrade(self):
        path=self.root/'large-v1.json'
        small=th._encoded(th.envelope(tm.envelope([]),db._envelope([])))
        path.write_bytes(small+b' '*(12*1024*1024+1-len(small)))
        with self.assertRaisesRegex(ValueError,'Legacy v1'): th.import_state(path,self.root/'receiver')
        self.assertFalse((self.root/'receiver').exists())
