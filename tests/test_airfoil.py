"""Synthetic-only checks for grouped intake, frozen review and one-attempt execution."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research_harness.airfoil_data import split_rows, condition, parse, fetch, SOURCE, FIXTURE
from research_harness import airfoil_baseline as ab
from research_harness.core import digest


def fixture_rows():
    return [{'id':f'fixture-{i:03}-{j}', 'features':[float(500*(j+1)),float(i),.1+.001*i,30.+i,.003],
             'target':100.+i*.2+j} for i in range(150) for j in range(3)]


class AirfoilTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.folder=self.root/'review'
        self.rows=fixture_rows(); self.prepared=ab.prepare_rows(self.rows,self.folder)

    def output(self, learned_error=1):
        _,parts=ab.load_review(self.folder); targets=parts['validation-targets.json']
        entries=[]
        for m in ab.RECIPE['models']:
            for s in ab.RECIPE['seeds']:
                entries.append({'model':m,'seed':s,'fit_seconds':.1,'predict_seconds':.01,
                    'predictions':[{'id':r['id'],'prediction':r['target']+(3 if m=='median' else learned_error)} for r in targets]})
        return {'results':entries,'peak_rss_native':10},targets

    def test_conditions_never_split_and_split_ignores_labels_frequency_order_ids(self):
        parts=split_rows(self.rows)
        membership={}
        for key in ('train','validation','holdout'):
            for row in parts[key+'.json']:
                self.assertNotIn(row['group'],{g for g,k in membership.items() if k!=key})
                membership[row['group']]=key
        changed=copy.deepcopy(self.rows)
        for row in changed:
            row['target']+=10000; row['id']='rename-'+row['id']; row['features'][0]*=2; row['features'][4]*=2
        other=split_rows(list(reversed(changed)))
        for key in ('train','validation','holdout'):
            self.assertEqual({r['group'] for r in parts[key+'.json']},{r['group'] for r in other[key+'.json']})
        with self.assertRaisesRegex(ValueError,'Insufficient'): split_rows(self.rows[:12])

    def test_download_and_parse_fail_closed(self):
        with patch('research_harness.airfoil_data.urllib.request.urlopen',return_value=io.BytesIO(b'wrong')):
            with self.assertRaisesRegex(ValueError,'archive'): fetch(self.root/'download')
        self.assertFalse((self.root/'download').exists())
        with patch('research_harness.airfoil_data.urllib.request.urlopen') as net:
            with self.assertRaisesRegex(ValueError,'exists'): fetch(self.folder)
            net.assert_not_called()
        path=self.root/'bad.dat'; path.write_text('1 2 3 4 5 6')
        with self.assertRaisesRegex(ValueError,'SHA-256'): parse(path)
        with self.assertRaisesRegex(ValueError,'pinned'): ab.prepare_rows(self.rows,self.root/'fake',SOURCE)

    def test_review_frozen_recipe_data_source_and_groups(self):
        self.assertFalse((self.folder/'approval.json').exists()); self.assertFalse((self.folder/'run').exists())
        with self.assertRaises(FileExistsError): ab.prepare_rows(self.rows,self.folder)
        with patch('research_harness.airfoil_baseline.source_hashes',return_value={}):
            with self.assertRaisesRegex(ValueError,'source changed'): ab.load_review(self.folder)
            ab.load_review(self.folder,current=False)
        path=self.folder/'bundle.json'; original=path.read_text(); value=json.loads(original)
        value['content']['recipe']['minimum_gain_db']=0; value['sha256']=digest(value['content']); path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'recipe'): ab.load_review(self.folder)
        path.write_text(original)
        targets=self.folder/'validation-targets.json'; value=json.loads(targets.read_text()); value[0]['group']='fake'
        targets.write_text(json.dumps(value)); packet=json.loads(path.read_text()); packet['content']['files'][targets.name]=digest(value)
        packet['sha256']=digest(packet['content']); path.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError,'group'): ab.load_review(self.folder)

    def test_macro_metric_weights_conditions_not_rows(self):
        # One large zero-error group and 11 small groups with error 2.
        targets=[{'id':str(i),'target':0.,'group':'large' if i<100 else str(i)} for i in range(111)]
        raw={'peak_rss_native':1,'results':[]}
        for m in ab.RECIPE['models']:
            for s in ab.RECIPE['seeds']:
                raw['results'].append({'model':m,'seed':s,'fit_seconds':0.,'predict_seconds':0.,
                    'predictions':[{'id':r['id'],'prediction':4. if m=='median' else (0. if r['group']=='large' else 2.)} for r in targets]})
        result=ab.qualify(raw,targets)
        self.assertAlmostEqual(result['mean_condition_mae_db']['ridge'],22/12)
        self.assertEqual(result['validation_conditions'],12)
        self.assertEqual(result['fits'],15)

    def test_effect_stop_and_training_variation(self):
        raw,targets=self.output(); passed=ab.qualify(raw,targets)
        self.assertEqual(passed['status'],'CONTINUE'); self.assertEqual(passed['selected_baseline'],'ridge')
        raw,targets=self.output(2.5)
        self.assertEqual(ab.qualify(raw,targets)['status'],'STOP')
        raw,targets=self.output()
        for r in raw['results']:
            if r['model']=='extra_trees' and r['seed']==33: r['predictions'][0]['prediction']+=.1
        self.assertGreater(ab.qualify(raw,targets)['seed_mae_sample_std_db']['extra_trees'],0)
        raw['results'][0]['predictions'][0]['prediction']+=.1
        with self.assertRaisesRegex(ValueError,'repeatability'): ab.qualify(raw,targets)

    def test_invalid_predictions_and_incomplete_seeds(self):
        raw,targets=self.output()
        mutations=[lambda v:v['results'].pop(),lambda v:v['results'][0].update(seed=True),
            lambda v:v['results'][0]['predictions'].pop(),lambda v:v['results'][0]['predictions'][0].update(prediction=float('nan')),
            lambda v:v['results'][0].update(command='not allowed')]
        for mutate in mutations:
            value=copy.deepcopy(raw); mutate(value)
            with self.assertRaises(ValueError): ab.qualify(value,targets)

    def test_uncertainty_gate_and_no_switch_to_rescue_selected_model(self):
        raw,targets=self.output(1.5)
        for item in raw['results']:
            if item['model']=='extra_trees':
                error={11:.1,22:.1,33:2.9}[item['seed']]
                truth={r['id']:r['target'] for r in targets}
                for p in item['predictions']: p['prediction']=truth[p['id']]+error
        result=ab.qualify(raw,targets)
        self.assertEqual(result['selected_baseline'],'extra_trees')
        self.assertEqual(result['status'],'STOP')
        self.assertGreater(min(result['per_seed_gains_db']['ridge']),1)
        # Large variation among conditions can invalidate a positive mean gain.
        groups=sorted({r['group'] for r in targets}); lookup={r['id']:r for r in targets}
        for item in raw['results']:
            for p in item['predictions']:
                row=lookup[p['id']]; first=groups.index(row['group'])<len(groups)//2
                error=(20 if first else 1) if item['model']=='median' else (1 if first else 16)
                p['prediction']=row['target']+error
        result=ab.qualify(raw,targets)
        self.assertGreater(result['mean_gains_db']['ridge'],1)
        self.assertLess(result['group_bootstrap_intervals_db']['ridge'][0],0)
        self.assertEqual(result['status'],'STOP')

    def test_approval_and_failed_execution_reserve_across_copies(self):
        with patch('research_harness.airfoil_baseline.environment') as env:
            with self.assertRaises(ValueError): ab.execute(self.folder,root=self.root)
            env.assert_not_called()
        with self.assertRaises(ValueError): ab.approve(self.folder,'0'*64,'fixture',root=self.root)
        ab.approve(self.folder,self.prepared['sha256'],'fixture',root=self.root)
        def failed(*args,**kwargs):
            request=json.loads((args[4]/'request.json').read_text())
            self.assertEqual(set(request),{'train','validation'})
            self.assertTrue(all(set(r)=={'id','features','group'} for r in request['validation']))
            args[5].mkdir(); return {'error':'synthetic failure'}
        with patch('research_harness.airfoil_baseline.environment',return_value={}), \
             patch('research_harness.tabular_sandbox.isolation_probe',return_value={}), \
             patch('research_harness.tabular_sandbox.isolated_worker',side_effect=failed):
            result=ab.execute(self.folder,root=self.root)
        self.assertFalse(result['measurement_valid']); self.assertEqual(result['status'],'STOP')
        self.assertFalse(result['final_holdout_scored']); self.assertIsNone(result['actual_local_cost_usd'])
        second=self.root/'copy'; ab.prepare_rows(self.rows,second)
        with self.assertRaisesRegex(ValueError,'reserved'): ab.approve(second,self.prepared['sha256'],'fixture',root=self.root)
        with self.assertRaisesRegex(ValueError,'reserved'): ab.execute(self.folder,root=self.root)

    def test_isolation_failure_and_symlink_fail_before_reserving(self):
        ab.approve(self.folder,self.prepared['sha256'],'fixture',root=self.root)
        with patch('research_harness.airfoil_baseline.environment',return_value={}), \
             patch('research_harness.tabular_sandbox.isolation_probe',side_effect=ValueError('isolation blocked')):
            with self.assertRaisesRegex(ValueError,'isolation blocked'): ab.execute(self.folder,root=self.root)
        self.assertFalse((self.root/'.research-memory').exists()); self.assertFalse((self.folder/'run').exists())
        path=self.folder/'train.json'; path.unlink(); path.symlink_to(self.folder/'validation.json')
        with self.assertRaises(ValueError): ab.load_review(self.folder)
