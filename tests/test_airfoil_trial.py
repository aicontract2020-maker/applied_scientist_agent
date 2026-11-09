"""Software fixtures only; never evaluate the real A2 candidate."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research_harness import airfoil_trial as at
from research_harness.airfoil_candidate import augment,review,SOURCE
from research_harness.airfoil_data import split_rows,FIXTURE
from research_harness.core import digest


class AirfoilTrialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name)
        rows=[{'id':f'r-{i:03}-{j}','features':[500.+j*500.,float(i),.1+i*.001,30.+i,.003],
               'target':100.+i*.2+j} for i in range(150) for j in range(3)]
        self.parts=split_rows(rows)
        self.reference={'results':[{'model':'extra_trees','seed':s,'predictions':[{'id':r['id'],'prediction':1.} for r in self.parts['validation.json']]} for s in (11,22,33)]}
        self.proposal=json.loads((Path(at.ROOT)/'tasks/airfoil_noise/a2/proposal.json').read_text())
        self.base={'content':{'source':FIXTURE},'sha256':'a'*64}

    def raw(self,error=.5,latency=1.):
        result={'results':[],'transform_train_seconds':.01,'peak_rss_native':100}
        for seed in (11,22,33):
            for kind in ('baseline','candidate'):
                t=1. if kind=='baseline' else latency
                result['results'].append({'kind':kind,'seed':seed,'fit_seconds':.1,
                    'batch_seconds':t,'timing_seconds':[t]*5,
                    'validation_predictions':[1.]*len(self.parts['validation.json']) if kind=='baseline' else None,
                    'predictions':[{'id':r['id'],'prediction':r['target']+(1. if kind=='baseline' else error)} for r in self.parts['holdout-targets.json']]})
        return result

    def test_fixed_feature_noop_rejections_and_units(self):
        self.assertEqual(augment([1000.,0.,.1,50.,.005]),[1000.,0.,.1,50.,.005,.1])
        self.assertTrue(review()['synthetic_probe_passed'])
        for source in ('def augment(row): return row',SOURCE.replace('row[4]','row[3]'),SOURCE+'# changed'):
            with self.assertRaises(ValueError): review(source)
        for row in ([1.,2.], [1000.,0.,.1,0.,.01], [float('inf'),0.,.1,20.,.01]):
            with self.assertRaises(ValueError): augment(row)
        bad=copy.deepcopy(self.proposal); bad['mechanism']='old-route'
        with self.assertRaises(ValueError): at.validate_proposal(bad)

    def test_effect_uncertainty_latency_and_all_seed_gates(self):
        result=at.evaluate(self.raw(),self.parts,self.reference)
        self.assertEqual(result['status'],'CONTINUE'); self.assertAlmostEqual(result['mean_gain_db'],.5)
        self.assertEqual(at.evaluate(self.raw(.9),self.parts,self.reference)['status'],'STOP')
        self.assertEqual(at.evaluate(self.raw(latency=1.2),self.parts,self.reference)['status'],'STOP')
        raw=self.raw(); raw['results'][-1]['predictions']=[{'id':r['id'],'prediction':r['target']+.9} for r in self.parts['holdout-targets.json']]
        result=at.evaluate(raw,self.parts,self.reference)
        self.assertGreater(result['mean_gain_db'],.2); self.assertEqual(result['status'],'STOP')
        raw=self.raw(); groups=sorted({r['group'] for r in self.parts['holdout-targets.json']})
        for entry in raw['results']:
            for p,t in zip(entry['predictions'],self.parts['holdout-targets.json']):
                first=groups.index(t['group'])<len(groups)//2
                p['prediction']=t['target']+((20 if first else 1) if entry['kind']=='baseline' else (1 if first else 16))
        result=at.evaluate(raw,self.parts,self.reference)
        self.assertGreater(result['mean_gain_db'],.2); self.assertLess(result['summary']['bootstrap_interval'][0],0)
        self.assertEqual(result['status'],'STOP')

    def test_reproduction_before_label_use_and_invalid_outputs(self):
        raw=self.raw(); raw['results'][0]['validation_predictions'][0]+=1
        parts=dict(self.parts); parts['holdout-targets.json']=None
        with self.assertRaisesRegex(ValueError,'reproduction'): at.evaluate(raw,parts,self.reference)
        mutations=[lambda r:r['results'].pop(),lambda r:r['results'][0].update(seed=True),
            lambda r:r['results'][0]['predictions'].pop(),
            lambda r:r['results'][0]['predictions'][0].update(prediction=float('nan')),
            lambda r:r['results'][0].update(batch_seconds=2.),
            lambda r:r['results'][1].update(validation_predictions=[0.])]
        for mutation in mutations:
            raw=self.raw(); mutation(raw)
            with self.assertRaises(ValueError): at.evaluate(raw,self.parts,self.reference)

    def test_local_and_published_consumption_or_stopped_route_block(self):
        at.assert_available(self.root,self.base)
        p=at.history_path(self.root,self.base); p.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'reserved'): at.assert_available(self.root,self.base)
        other=self.root/'clone'; history=other/'tasks/airfoil_noise/trial-history.json'; history.parent.mkdir(parents=True)
        history.write_text(json.dumps([{'scope':at.scope(self.base),'mechanism':at.MECHANISM,'review_sha256':'f'*64,'status':'CONTINUE'}]))
        with self.assertRaisesRegex(ValueError,'Published'): at.assert_available(other,self.base)
        history.write_text(json.dumps([{'scope':'b'*64,'mechanism':at.MECHANISM,'review_sha256':'f'*64,'status':'STOP'}]))
        with self.assertRaisesRegex(ValueError,'Published'): at.assert_available(other,self.base)

    def test_missing_stale_approval_and_worker_failure_keep_reservation(self):
        folder=self.root/'trial';folder.mkdir()
        packet={'sha256':'c'*64,'content':{'sources':at.source_hashes()}}
        state=(packet,self.base,self.parts,self.reference)
        with patch.object(at,'load_trial',return_value=state),patch.object(at,'environment') as env:
            with self.assertRaises(ValueError): at.execute(folder,root=self.root)
            env.assert_not_called()
            (folder/'trial-approval.json').write_text(json.dumps({'sha256':'d'*64,'reviewer':'fixture','scope':at.SCOPE}))
            with self.assertRaisesRegex(ValueError,'stale'): at.execute(folder,root=self.root)
            env.assert_not_called()
        (folder/'trial-approval.json').write_text(json.dumps({'sha256':packet['sha256'],'reviewer':'fixture','scope':at.SCOPE}))
        def failed(*args,**kwargs):
            req=json.loads((args[4]/'request.json').read_text())
            self.assertEqual(set(req),{'train','validation','holdout'})
            for key in ('validation','holdout'): self.assertTrue(all(set(r)=={'id','features','group'} for r in req[key]))
            args[5].mkdir(); return {'error':'synthetic failure','returncode':1}
        with patch.object(at,'load_trial',return_value=state),patch.object(at,'environment',return_value={}), \
             patch('research_harness.tabular_sandbox.isolation_probe',return_value={}), \
             patch('research_harness.tabular_sandbox.isolated_worker',side_effect=failed):
            result=at.execute(folder,root=self.root)
        self.assertFalse(result['measurement_valid']);self.assertTrue(result['holdout_exposed']);self.assertFalse(result['final_holdout_scored'])
        with self.assertRaisesRegex(ValueError,'reserved'): at.assert_available(self.root,self.base)

    def test_prepare_blocks_consumed_before_creating_output(self):
        p=at.history_path(self.root,self.base);p.mkdir(parents=True)
        with patch.object(at,'qualified',return_value=(self.base,self.parts,self.reference)):
            with self.assertRaisesRegex(ValueError,'reserved'):
                at.prepare('unused','unused',self.root/'new',root=self.root)
        self.assertFalse((self.root/'new').exists())

    def test_review_change_during_preflight_blocks_before_reservation(self):
        folder=self.root/'trial';folder.mkdir()
        packet={'sha256':'c'*64,'content':{'sources':at.source_hashes()}}
        changed=copy.deepcopy(packet);changed['sha256']='d'*64
        (folder/'trial-approval.json').write_text(json.dumps({'sha256':packet['sha256'],'reviewer':'fixture','scope':at.SCOPE}))
        states=[(packet,self.base,self.parts,self.reference),(changed,self.base,self.parts,self.reference)]
        with patch.object(at,'load_trial',side_effect=states),patch.object(at,'environment',return_value={}), \
             patch('research_harness.tabular_sandbox.isolation_probe',return_value={}):
            # Full revalidation now detects the stale approval before comparing snapshots.
            with self.assertRaisesRegex(ValueError,'stale'): at.execute(folder,root=self.root)
        self.assertFalse((folder/'trial-run').exists()); self.assertFalse(at.history_path(self.root,self.base).exists())

    def test_frozen_review_rejects_source_candidate_and_protocol_changes(self):
        folder=self.root/'frozen';(folder/'baseline').mkdir(parents=True)
        content={'recipe':at.RECIPE,'proposal':self.proposal,'feature_review':at.validate_proposal(self.proposal),
            'baseline_sha256':self.base['sha256'],'scope':at.scope(self.base),'counts':at.baseline.counts(self.parts),
            'sources':at.source_hashes(),'status':'AWAITING_RESEARCH_REVIEW'}
        packet={'content':content,'sha256':digest(content)}
        (folder/'trial.json').write_text(json.dumps(packet));(folder/'candidate.py').write_text(SOURCE)
        with patch.object(at,'qualified',return_value=(self.base,self.parts,self.reference)):
            at.load_trial(folder)
            with patch.object(at,'source_hashes',return_value={}):
                with self.assertRaisesRegex(ValueError,'source changed'): at.load_trial(folder)
                at.load_trial(folder,current=False)
            (folder/'candidate.py').write_text('def augment(row): return row')
            with self.assertRaisesRegex(ValueError,'Candidate changed'): at.load_trial(folder)
            (folder/'candidate.py').write_text(SOURCE)
            changed=copy.deepcopy(packet);changed['content']['recipe']['minimum_effect']=0
            changed['sha256']=digest(changed['content']);(folder/'trial.json').write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,'protocol'): at.load_trial(folder)
