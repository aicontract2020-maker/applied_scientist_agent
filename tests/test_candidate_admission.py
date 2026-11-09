"""Candidate admission software fixtures only; no real trials or model calls."""
import copy
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from examples.data_qualification.baseline import qualification, USE
from research_harness import airfoil_baseline as ab, airfoil_trial as at, tabular_trial as tt
from research_harness import data_admission as admission
from research_harness.core import digest
from research_harness.memory import read_json


class CandidateAdmissionTests(unittest.TestCase):
    def build(self, module):
        if module is tt:
            from test_tabular_trial import TrialTests
            fixture=TrialTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
            root=fixture.root.resolve(); base=fixture.base; proposal=fixture.proposal; library=fixture.library
            snapshot=qualification(root/'candidate-qualification',tt.ADAPTER,tt.FIXTURE)
            folder=root/'admitted-trial'
            prepared=tt.prepare(base,proposal,folder,library,root=root,
                                data_review=root/'candidate-qualification/packet.json',intended_use=USE)
        else:
            tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); root=Path(tmp.name).resolve()
            from test_airfoil_trial import AirfoilTrialTests
            f=AirfoilTrialTests(); f.setUp(); self.addCleanup(f.doCleanups)
            # The unit fixture substitutes only historical audit; integration scripts
            # independently exercise the real audit and isolated workers.
            rows=[{'id':r['id'],'features':r['features'],'target':r['target']} for r in f.parts['train.json']]
            for key in ('validation','holdout'):
                rows.extend({'id':r['id'],'features':r['features'],'target':t['target']}
                            for r,t in zip(f.parts[key+'.json'],f.parts[key+'-targets.json']))
            base=root/'baseline'; ab.prepare_rows(rows,base)
            for name in at.BASE_FILES:
                if name=='airfoil_self_noise.dat': continue
                path=base/name
                if not path.exists():
                    path.parent.mkdir(parents=True,exist_ok=True); path.write_text('{}')
            def qualified(path):
                packet,parts=ab.load_review(path,current=False)
                return packet,parts,f.reference
            mock=patch.object(at,'qualified',side_effect=qualified); mock.start(); self.addCleanup(mock.stop)
            proposal=root/'proposal.json'; proposal.write_text(json.dumps(f.proposal)); library=None
            snapshot=qualification(root/'candidate-qualification',at.ADAPTER,ab.FIXTURE)
            folder=root/'admitted-trial'
            prepared=at.prepare(base,proposal,folder,root=root,
                                data_review=root/'candidate-qualification/packet.json',intended_use=USE)
        return SimpleNamespace(module=module,root=root,base=base,proposal=proposal,library=library,
                               folder=folder,prepared=prepared,snapshot=snapshot)

    def approve(self,f):
        method=tt.approve_trial if f.module is tt else at.approve
        return method(f.folder,f.prepared['sha256'],'SYNTHETIC_REVIEWER',root=f.root)

    def invoke(self,f,operation):
        method=getattr(f.module, {'execute':'execute_trial','preflight':'preflight_trial'}.get(operation,operation)
                       if f.module is tt else operation)
        return method(f.folder,root=f.root)

    def rewrite(self,f,change):
        path=f.folder/'trial.json'; envelope=read_json(path)
        change(envelope['content']); envelope['sha256']=digest(envelope['content'])
        path.write_text(json.dumps(envelope)); return envelope

    def test_prepare_embeds_candidate_scope_but_requires_separate_execution_approval(self):
        for module in (tt,at):
            f=self.build(module)
            c=read_json(f.folder/'trial.json')['content']; base=read_json(f.base/'bundle.json')
            summary=admission.verify_trial(c,base,module.ADAPTER,required=True)
            self.assertEqual(summary['adapter'],module.ADAPTER); self.assertFalse(summary['execution_authorized'])
            with patch.object(module,'environment') as env:
                with self.assertRaises((OSError,ValueError)): self.invoke(f,'execute')
                env.assert_not_called()
            self.approve(f)
            before={str(p):p.read_bytes() for p in f.folder.rglob('*') if p.is_file()}
            with patch.object(module,'environment') as env:
                result=self.invoke(f,'preflight'); env.assert_not_called()
            self.assertTrue(result['read_only']); self.assertFalse(result['execution_authorized'])
            self.assertTrue(result['memory_checked']); self.assertFalse(result['isolation_checked'])
            self.assertEqual(before,{str(p):p.read_bytes() for p in f.folder.rglob('*') if p.is_file()})

    def test_baseline_qualification_and_wrong_candidate_scope_cannot_be_reused(self):
        for module in (tt,at):
            f=self.build(module); base=read_json(f.base/'bundle.json'); content=read_json(f.folder/'trial.json')['content']
            adapter='abalone-baseline-v1' if module is tt else ab.ADAPTER
            wrong=qualification(f.root/'baseline-qualification',adapter,base['content']['source'])
            with self.assertRaisesRegex(ValueError,'differs'):
                admission.bind_trial(wrong,module.ADAPTER,base,content,USE)
            with self.assertRaisesRegex(ValueError,'differs'):
                admission.bind_trial(f.snapshot,module.ADAPTER,base,content,'wider intended use')
            altered=copy.deepcopy(base); altered['content']['source']={'id':'different'}
            with self.assertRaisesRegex(ValueError,'differs'):
                admission.bind_trial(f.snapshot,module.ADAPTER,altered,content,USE)

    def test_binding_changes_rejected_even_with_recomputed_outer_digest(self):
        for module in (tt,at):
            f=self.build(module); self.approve(f); original=(f.folder/'trial.json').read_bytes()
            mutations=[lambda c:c['data_admission']['qualification']['packet']['content']['evidence']['note'].update(content='changed'),
                       lambda c:c['data_admission']['qualification']['decision']['content'].update(reviewer='changed'),
                       lambda c:c['data_admission']['context']['dataset'].update(version='2'),
                       lambda c:c['data_admission']['data_files'].update(**{'holdout.json':'0'*64}),
                       lambda c:c['data_admission'].update(kind=admission.KIND),
                       lambda c:c['proposal'].update(hypothesis='Changed hypothesis'),
                       lambda c:c.update(baseline_sha256='0'*64)]
            for mutate in mutations:
                self.rewrite(f,mutate)
                with patch.object(module,'environment') as env,patch('research_harness.tabular_sandbox.isolated_worker') as worker:
                    with self.assertRaises(ValueError): self.invoke(f,'execute')
                    env.assert_not_called(); worker.assert_not_called()
                self.assertFalse((f.folder/'trial-run').exists()); (f.folder/'trial.json').write_bytes(original)

    def test_candidate_snapshot_binds_exact_baseline_even_when_source_and_rows_match(self):
        f=self.build(tt); content=read_json(f.folder/'trial.json')['content']; base=read_json(f.base/'bundle.json')
        changed=copy.deepcopy(base); changed['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'binding changed'):
            admission.verify_trial(content,changed,tt.ADAPTER,required=True)

    def test_no_legacy_downgrade_and_historical_read_still_checks_present_admission(self):
        for module in (tt,at):
            f=self.build(module); content=read_json(f.folder/'trial.json')['content']; base=read_json(f.base/'bundle.json')
            content.pop('data_admission')
            with self.assertRaisesRegex(ValueError,'audit-only'):
                admission.verify_trial(content,base,module.ADAPTER,required=True)
            self.assertIsNone(admission.verify_trial(content,base,module.ADAPTER,required=False))
            self.rewrite(f,lambda c:c['data_admission'].update(recipe_sha256='0'*64))
            with self.assertRaises(ValueError): module.load_trial(f.folder,current=False)

    def test_unresolved_or_rejected_candidate_qualification_is_not_accepted(self):
        f=self.build(tt); base=read_json(f.base/'bundle.json'); content=read_json(f.folder/'trial.json')['content']
        for state in ('unresolved','incompatible','reject'):
            snapshot=copy.deepcopy(f.snapshot); p=snapshot['packet']; d=snapshot['decision']
            if state=='reject': d['content']['decision']='reject'
            else: p['content']['criteria']['holdout_history']['state']=state
            p['sha256']=digest(p['content']); d['content']['packet_sha256']=p['sha256']; d['sha256']=digest(d['content'])
            with self.assertRaises(ValueError): admission.bind_trial(snapshot,tt.ADAPTER,base,content,USE)

    def test_probe_rechecks_approval_before_reservation_and_worker(self):
        for module in (tt,at):
            f=self.build(module); self.approve(f)
            def probe(*args):
                path=f.folder/'trial-approval.json'; value=read_json(path); value['reviewer']='CHANGED'; path.write_text(json.dumps(value)); return {}
            with patch.object(module,'environment',return_value={}),patch('research_harness.tabular_sandbox.isolation_probe',side_effect=probe), \
                 patch('research_harness.tabular_sandbox.isolated_worker') as worker:
                with self.assertRaisesRegex(ValueError,'changed during preflight'): self.invoke(f,'execute')
                worker.assert_not_called()
            self.assertFalse((f.folder/'trial-run').exists())
            self.assertFalse((f.root/'.research-memory/tabular-trial').exists())
            self.assertFalse((f.root/'.research-memory/airfoil-trial').exists())

    def test_new_stop_or_reservation_during_probe_is_rechecked(self):
        for module in (tt,at):
            f=self.build(module); self.approve(f)
            c=read_json(f.folder/'trial.json')['content']
            history=f.root/('.research-memory/tabular-trial' if module is tt else '.research-memory/airfoil-trial')/c['scope']
            def probe(*args): history.mkdir(parents=True); return {}
            with patch.object(module,'environment',return_value={}),patch('research_harness.tabular_sandbox.isolation_probe',side_effect=probe), \
                 patch('research_harness.tabular_sandbox.isolated_worker') as worker:
                with self.assertRaisesRegex(ValueError,'reserved'): self.invoke(f,'execute')
                worker.assert_not_called()
            self.assertFalse((f.folder/'trial-run').exists())

    def test_accepted_qualification_cannot_override_published_stopped_route(self):
        for module in (tt,at):
            f=self.build(module); self.approve(f)
            if module is at:
                path=f.root/'tasks/airfoil_noise/trial-history.json'; path.parent.mkdir(parents=True)
                path.write_text(json.dumps([{'scope':'f'*64,'mechanism':at.MECHANISM,'review_sha256':'e'*64,'status':'STOP'}]))
                target='research_harness.airfoil_trial.assert_available'
            else: target='research_harness.tabular_memory.assert_available'
            with patch.object(module,'environment') as env:
                if module is at:
                    with self.assertRaisesRegex(ValueError,'stopped'): self.invoke(f,'execute')
                else:
                    with patch(target,side_effect=ValueError('stopped route')):
                        with self.assertRaisesRegex(ValueError,'stopped'): self.invoke(f,'execute')
                env.assert_not_called()

    def test_proposal_entry_blocks_missing_real_qualification_before_output_or_actor(self):
        from research_harness import tabular_workflow as workflow,tabular_proposer as proposer
        from research_harness.tabular_data import SOURCE
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); root=Path(tmp.name).resolve()
        state=({'content':{'source':SOURCE}}, {}, {'status':'CONTINUE','selected_baseline':'hgb'}, {})
        with patch.object(workflow,'validated_baseline',return_value=state),patch.object(proposer,'propose') as actor:
            with self.assertRaisesRegex(ValueError,'qualification'): workflow.research('no-call','propose','base',root=root)
            actor.assert_not_called()
        self.assertFalse((root/'runs').exists())
        with patch.object(proposer,'validated_baseline',return_value=state),patch.object(proposer,'bounded_process') as actor:
            with self.assertRaisesRegex(ValueError,'qualification'): proposer.propose('base',root/'proposal',root=root)
            actor.assert_not_called()
        self.assertFalse((root/'proposal').exists())
        with self.assertRaisesRegex(ValueError,'runtime override'):
            workflow.research('no-call','execute',review='base',root=root,data_review='override')

    def test_cli_preflight_and_required_candidate_arguments(self):
        f=self.build(tt); self.approve(f); repo=str(Path(__file__).resolve().parents[1])
        def cli(*args):
            return subprocess.run([sys.executable,'-m','research_harness',*args],cwd=f.root,
                                  env={**os.environ,'PYTHONPATH':repo},capture_output=True,text=True,timeout=15)
        for name in ('tabular','airfoil'):
            args=[name,'prepare-trial','--baseline','unused','--proposal','unused','--out','unused']
            if name=='tabular': args+=['--literature','unused']
            result=cli(*args); self.assertEqual(result.returncode,2); self.assertIn('--data-review',result.stderr)
        result=cli('tabular','preflight-trial','--review',str(f.folder))
        self.assertEqual(result.returncode,0,result.stderr); self.assertFalse(json.loads(result.stdout)['execution_authorized'])
        self.assertFalse((f.folder/'trial-run').exists())

    def test_unified_proposal_preserves_candidate_qualification_through_freeze(self):
        from research_harness.tabular_workflow import research
        f=self.build(tt); path=f.root/'candidate-qualification/packet.json'
        def actor(baseline,output,root,*,data_review,intended_use):
            self.assertEqual(data_review,path); self.assertEqual(intended_use,USE)
            output.mkdir(); shutil.copyfile(f.proposal,output/'proposal.json'); shutil.copyfile(f.library,output/'literature.json')
            return {'status':'AWAITING_RESEARCH_REVIEW'}
        with patch('research_harness.tabular_proposer.propose',side_effect=actor),patch.object(tt,'execute_trial') as execute:
            result=research('admitted-proposal','propose',f.base,root=f.root,data_review=path,intended_use=USE)
            execute.assert_not_called()
        self.assertEqual(result['status'],'AWAITING_RESEARCH_REVIEW')
        review=f.root/'runs/admitted-proposal/review'
        packet,_,_=tt.load_trial(review)
        self.assertEqual(packet['content']['data_admission']['qualification'],f.snapshot)
        self.assertFalse((review/'trial-approval.json').exists())

    def test_real_legacy_trial_cannot_reach_environment_after_removing_admission(self):
        from research_harness.tabular_data import SOURCE as tabular_source
        for module in (tt,at):
            f=self.build(module); self.rewrite(f,lambda c:c.pop('data_admission'))
            if module is tt:
                state=list(tt.validated_baseline(f.folder/'baseline')); state[0]=copy.deepcopy(state[0])
                state[0]['content']['source']=tabular_source; target='validated_baseline'
            else:
                state=list(at.qualified(f.folder/'baseline')); state[0]=copy.deepcopy(state[0])
                state[0]['content']['source']=ab.SOURCE; target='qualified'
            with patch.object(module,target,return_value=tuple(state)),patch.object(module,'environment') as env:
                with self.assertRaisesRegex(ValueError,'audit-only'): self.invoke(f,'execute')
                env.assert_not_called()

    def test_updated_accepted_evidence_does_not_refresh_old_execution_approval(self):
        for module in (tt,at):
            f=self.build(module); self.approve(f)
            def change(c):
                e=c['data_admission']; e['context']['intended_use']+=' revised'
                p=e['qualification']['packet']; d=e['qualification']['decision']
                p['content']['intended_use']=e['context']['intended_use']; p['sha256']=digest(p['content'])
                d['content']['packet_sha256']=p['sha256']; d['sha256']=digest(d['content'])
            self.rewrite(f,change)
            with patch.object(module,'environment') as env:
                with self.assertRaisesRegex(ValueError,'approval'): self.invoke(f,'execute')
                env.assert_not_called()
