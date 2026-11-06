"""Synthetic-only handoff tests: exclusions survive copies; evidence never executes."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_harness.core import digest,Workspace
from research_harness.tabular_data import write_json
from research_harness.tabular_features import review as feature_review
from research_harness.tabular_memory import (envelope,merge,snapshot,assert_available,import_memory,
    export_memory,record_from_trial,family_hash,retain_trial)
from research_harness.tabular_trial import approve_trial,load_trial,audit_trial,evaluate_trial,prepare
from research_harness.tabular_baseline import PACKAGES
from research_harness.portable import ROOT
from research_harness.tabular_evidence import export,verify,unpack,load_packet


class HandoffTests(unittest.TestCase):
    def setUp(self):
        from test_tabular_trial import TrialTests
        fixture=TrialTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.root,self.trial=fixture.root,fixture.review
        packet,parts,qualified=load_trial(self.trial)
        approve_trial(self.trial,packet['sha256'],'SYNTHETIC SOFTWARE FIXTURE')
        raw,_,_=fixture.raw(.01); run=self.trial/'trial-run'; run.mkdir()
        for name in ('inputs','output','trusted'): (run/name).mkdir()
        for name in ('tabular_features.py','tabular_trial_worker.py'):
            shutil.copyfile(ROOT/'research_harness'/name,run/'trusted'/name)
        write_json(run/'inputs/request.json',{'train':parts['train.json'],'validation':parts['validation.json'],
            'holdout':parts['holdout.json'],'candidate':packet['content']['proposal']['candidate_source']})
        write_json(run/'output/predictions.json',raw)
        write_json(run/'preflight.json',{'platform':'darwin','environment':{'python':[3,12],'packages':PACKAGES},
            'isolation':{k:True for k in ('private_labels_denied','repo_denied','input_readonly','network_denied','output_writable')}})
        write_json(run/'process.json',{'error':None,'returncode':0,'wall_seconds':1})
        result=evaluate_trial(raw,parts,qualified)
        result.update(peak_rss_bytes=1,fit_seconds=sum(r['fit_seconds'] for r in raw['results']),transform_train_seconds=.1,
                      wall_seconds=2,holdout_exposed_to_worker=True,actual_local_cost_usd=None,model_calls=0,retained_bytes_before_report=1)
        write_json(run/'result.json',result)
        Workspace.append(run,{'event':'REGISTER','trial_sha256':packet['sha256']})
        Workspace.append(run,{'event':'EXPERIMENT_STARTED','trial_sha256':packet['sha256']})
        Workspace.append(run,{'event':'DECISION','result':result})
        self.assertTrue(audit_trial(self.trial)['audit_ok'])
        self.record=record_from_trial(self.trial)
        self.base_packet=json.loads((self.trial/'baseline/bundle.json').read_text()); self.parts=parts
        self.packet=self.root/'memory.json'; write_json(self.packet,envelope([self.record]))

    def test_memory_import_is_idempotent_and_stale_reservation_never_reclaims(self):
        clone=self.root/'clone'
        self.assertEqual(import_memory(self.packet,clone)['status'],'IMPORTED')
        self.assertEqual(import_memory(self.packet,clone)['status'],'ALREADY_IMPORTED')
        old=dict(self.record,state='RESERVED',result_sha256=None,family_sha256=None,data_keys=None,route=None)
        stale=self.root/'stale.json'; write_json(stale,envelope([old])); import_memory(stale,clone)
        self.assertEqual(snapshot(clone),[self.record])
        output=self.root/'export.json'; export_memory(output,clone)
        self.assertEqual(output.stat().st_mode & 0o777,0o600)
        with self.assertRaises(FileExistsError): export_memory(output,clone)

    def test_conflicts_and_foreign_tasks_leave_imported_state_unchanged(self):
        clone=self.root/'clone'; import_memory(self.packet,clone)
        bad=copy.deepcopy(self.record); bad['result_sha256']='0'*64
        path=self.root/'conflict.json'; write_json(path,envelope([bad]))
        with self.assertRaisesRegex(ValueError,'Conflicting'): import_memory(path,clone)
        self.assertEqual(snapshot(clone),[self.record])
        packet=envelope([self.record]); packet['payload']['kind']='swinir'
        packet['sha256']=digest(packet['payload']); (self.root/'foreign.json').write_text(json.dumps(packet))
        with self.assertRaises(ValueError): import_memory(self.root/'foreign.json',clone)

    def test_published_record_blocks_renaming_repartition_and_numeric_rescue(self):
        clone=self.root/'clone'; folder=clone/'tasks/tabular_regression'; folder.mkdir(parents=True)
        shutil.copyfile(self.packet,folder/'trial-history.json')
        renamed=copy.deepcopy(self.parts)
        for row in renamed['holdout.json']: row['id']='new-'+row['id']
        renamed['holdout.json'].reverse()
        changed=copy.deepcopy(self.base_packet); changed['content']['files']['train.json']='f'*64
        with self.assertRaisesRegex(ValueError,'already reserved'): assert_available(changed,renamed,clone)
        source='def augment(row):\n return [row[3]/max(row[4],0.000001)]'
        record={**self.record,'route':{'source':source,'mechanism':'fixture ratio'},'family_sha256':family_hash(source),
                'candidate_sha256':digest(feature_review(source)['canonical'])}
        (folder/'trial-history.json').write_text(json.dumps(envelope([record])))
        fresh=copy.deepcopy(renamed)
        for row in fresh['holdout.json']: row['features']=[x+10000 for x in row['features']]
        with self.assertRaisesRegex(ValueError,'Stopped tabular feature family'):
            assert_available(changed,fresh,clone,candidate=source.replace('0.000001','0.01'))

    def test_incomplete_legacy_reservation_and_linked_memory_fail_closed(self):
        root=self.root/'legacy'; folder=root/'.research-memory/tabular-trial'/self.record['scope'];folder.mkdir(parents=True)
        with self.assertRaises(ValueError): snapshot(root)
        write_json(folder/'reservation.json',{'scope':self.record['scope'],'trial_sha256':self.record['trial_sha256'],
            'canonical_candidate_sha256':self.record['candidate_sha256'],'status':'RESERVED'})
        with self.assertRaisesRegex(ValueError,'already reserved'): assert_available(self.base_packet,self.parts,root)
        changed=copy.deepcopy(self.base_packet); changed['content']['files']['train.json']='b'*64
        with self.assertRaisesRegex(ValueError,'Incomplete legacy'): assert_available(changed,self.parts,root)
        other=self.root/'linked';other.mkdir(); (other/'.research-memory').symlink_to(root/'.research-memory')
        with self.assertRaisesRegex(ValueError,'Linked'): snapshot(other)

    def test_direct_prepare_propose_and_unified_entry_reject_before_side_effects(self):
        root=self.root/'clone'; import_memory(self.packet,root)
        from research_harness.tabular_proposer import propose
        from research_harness.tabular_workflow import research
        with patch('research_harness.doctor.isolation_probe') as probe:
            with self.assertRaisesRegex(ValueError,'already reserved'):
                propose(self.trial/'baseline',root/'proposal',root=root)
            probe.assert_not_called()
        with patch('research_harness.tabular_proposer.propose') as actor:
            with self.assertRaisesRegex(ValueError,'already reserved'):
                research('renamed','propose',self.trial/'baseline',root=root)
            actor.assert_not_called()
        self.assertFalse((root/'runs').exists()); self.assertFalse((root/'proposal').exists())
        with self.assertRaisesRegex(ValueError,'already reserved'):
            prepare(self.trial/'baseline',self.root/'proposal.json',root/'review',self.root/'library.json',root=root)
        self.assertFalse((root/'review').exists())

    def test_retain_uses_completed_audit_and_preserves_originals(self):
        before={str(p.relative_to(self.trial)):p.read_bytes() for p in self.trial.rglob('*') if p.is_file()}
        root=self.root/'clone'; self.assertEqual(retain_trial(self.trial,root)['status'],'RETAINED')
        self.assertEqual(retain_trial(self.trial,root)['status'],'ALREADY_RETAINED')
        self.assertEqual(before,{str(p.relative_to(self.trial)):p.read_bytes() for p in self.trial.rglob('*') if p.is_file()})

    def test_unified_proposal_freezes_review_without_automatic_approval_or_execution(self):
        from research_harness.tabular_workflow import research
        def actor(baseline,output,root):
            output.mkdir()
            shutil.copyfile(self.root/'proposal.json',output/'proposal.json')
            shutil.copyfile(self.root/'library.json',output/'literature.json')
            return {'status':'AWAITING_RESEARCH_REVIEW'}
        with patch('research_harness.tabular_proposer.propose',side_effect=actor), \
             patch('research_harness.tabular_trial.execute_trial') as execute:
            result=research('workflow-fixture','propose',self.trial/'baseline',root=self.root)
            execute.assert_not_called()
        folder=self.root/'runs/workflow-fixture/review'
        self.assertEqual(result['status'],'AWAITING_RESEARCH_REVIEW')
        self.assertFalse((folder/'trial-approval.json').exists()); self.assertFalse((folder/'trial-run').exists())
        with patch('research_harness.tabular_trial.environment') as env:
            with self.assertRaises(ValueError): research('software-fixture','execute',review=folder,root=self.root)
            env.assert_not_called()
        with self.assertRaises(ValueError): research('wrong-id','execute',review=folder,root=self.root)

    @unittest.skipUnless(sys.version_info[:2]==(3,12),'Exact evidence requires pinned Python 3.12')
    def test_private_evidence_roundtrip_is_read_only_and_never_imports_memory(self):
        path=self.root/'evidence.json'; export(self.trial,path)
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertTrue(verify(path)['audit_ok'])
        copied=Path(unpack(path,self.root/'copy')['review'])
        self.assertTrue(audit_trial(copied)['audit_ok'])
        with self.assertRaisesRegex(ValueError,'review-only'): load_trial(copied)
        self.assertFalse((self.root/'copy/.research-memory').exists())
        with self.assertRaises(FileExistsError): unpack(path,self.root/'copy')
        with self.assertRaises(FileExistsError): export(self.trial,path)

    @unittest.skipUnless(sys.version_info[:2]==(3,12),'Exact evidence requires pinned Python 3.12')
    def test_evidence_rejects_paths_duplicates_tampering_and_nonfinite_json(self):
        path=self.root/'evidence.json'; export(self.trial,path)
        original=json.loads(path.read_text())
        for key in ('../escape','/tmp/escape','trial-run/../../escape'):
            value=copy.deepcopy(original); value['payload']['files'][key]={'content':'x','sha256':hashlib.sha256(b'x').hexdigest()}
            value['sha256']=digest(value['payload']); path.write_text(json.dumps(value))
            with self.assertRaises(ValueError): verify(path)
        value=copy.deepcopy(original); value['payload']['files']['trial-run/result.json']['content']='{}'
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'hash'): verify(path)
        for text in ('{"payload":{},"payload":{}}','{"payload":NaN}'):
            path.write_text(text)
            with self.assertRaises(ValueError): load_packet(path)

    def test_explicit_environment_error_does_not_relax_audit(self):
        with patch('research_harness.tabular_evidence.sys.version_info',(3,9)):
            with self.assertRaisesRegex(ValueError,'Python 3.12'): export(self.trial,self.root/'none.json')
        self.assertFalse((self.root/'none.json').exists())

    @unittest.skipUnless(sys.version_info[:2]==(3,12),'Exact evidence requires pinned Python 3.12')
    def test_coherent_forged_worker_is_still_only_text(self):
        path=self.root/'evidence.json'; export(self.trial,path)
        packet=json.loads(path.read_text()); files=packet['payload']['files']
        marker=self.root/'MUST_NOT_EXECUTE'
        source=f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n'
        files['trial-run/trusted/tabular_trial_worker.py']['content']=source
        trial=json.loads(files['trial.json']['content'])
        trial['content']['sources']['research_harness/tabular_trial_worker.py']=hashlib.sha256(source.encode()).hexdigest()
        trial['sha256']=digest(trial['content']); files['trial.json']['content']=json.dumps(trial)
        approval=json.loads(files['trial-approval.json']['content']);approval['sha256']=trial['sha256']
        files['trial-approval.json']['content']=json.dumps(approval)
        events=[json.loads(line) for line in files['trial-run/ledger.jsonl']['content'].splitlines()]
        for event in events[:2]: event['trial_sha256']=trial['sha256']
        files['trial-run/ledger.jsonl']['content']='\n'.join(map(json.dumps,events))+'\n'
        for item in files.values(): item['sha256']=hashlib.sha256(item['content'].encode()).hexdigest()
        packet['sha256']=digest(packet['payload']);path.write_text(json.dumps(packet))
        self.assertTrue(verify(path)['audit_ok'])  # Consistency is explicitly not authentication.
        self.assertFalse(marker.exists())
