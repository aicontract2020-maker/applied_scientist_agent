"""Software fixtures only; no empirical claim or real-data execution."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_harness.tabular_features import parse,evaluate,review
from research_harness.tabular_trial import prepare,load_trial,approve_trial,execute_trial,evaluate_trial,RECIPE
from research_harness.tabular_data import write_json
from research_harness.tabular_audit import validated_baseline

SOURCE='def augment(row):\n    return [row[3] * row[4]]\n'


def proposal():
    return {'id':'software-fixture','hypothesis':'Synthetic test only','mechanism':'feature interaction fixture',
        'why_new':'Different from prediction-offset calibration; software fixture only',
        'feature_rationale':'Product, no tuned parameter','candidate_source':SOURCE,
        'evidence':[{'url':'https://arxiv.org/abs/2207.08815','claim':'SOFTWARE FIXTURE, NOT VERIFIED'},
                    {'url':'https://arxiv.org/abs/2106.11959','claim':'SOFTWARE FIXTURE, NOT VERIFIED'}],
        'limitations':['Synthetic fixture is not a scientific proposal']}


class FeatureLanguageTests(unittest.TestCase):
    def test_closed_language_has_no_execution_or_fitting(self):
        self.assertEqual(evaluate(parse(SOURCE),list(range(10))),list(range(10))+[12.])
        bad=['import os\n'+SOURCE,'def augment(row):\n return [open("secret").read()]',
             'def augment(row):\n return [row.__class__]', 'def augment(row):\n return [x for x in row]',
             'def augment(row):\n return [row[3] ** row[4]]',
             'def augment(row):\n return [row[10]*row[3]]',
             '@print("unsafe")\ndef augment(row):\n return [row[3]*row[4]]']
        for source in bad:
            with self.subTest(source=source),self.assertRaises(ValueError): parse(source)

    def test_noops_single_column_and_undefined_features_rejected(self):
        for expression in ('row[3]','row[0]+row[1]+row[2]','row[0]+row[1]','row[3]+row[4]*0','row[3]-row[3]+row[4]-row[4]',
                           'row[3]/row[4]','row[3]*row[4],row[3]*row[4]'):
            with self.subTest(expression=expression),self.assertRaises(ValueError): review('def augment(row):\n return ['+expression+']')
        self.assertTrue(review(SOURCE)['synthetic_probe_passed'])
        self.assertEqual(review(SOURCE)['canonical'],review(SOURCE+'\n# whitespace rename is not novelty')['canonical'])

    def test_launcher_recovery_never_applies_after_agent_work(self):
        from research_harness.tabular_proposer import launch_failure_evidence
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp); (folder/'process').mkdir()
            write_json(folder/'process.json',{'returncode':-6})
            write_json(folder/'result.json',{'status':'INCOMPLETE'})
            stdout=folder/'process/stdout.log'; stdout.write_text('')
            (folder/'process/stderr.log').write_text('node::InitializeOncePerProcessInternal')
            self.assertIn('infrastructure',launch_failure_evidence(folder)['limit'])
            stdout.write_text('{"type":"thread.started"}\n')
            with self.assertRaises(ValueError): launch_failure_evidence(folder)
            stdout.write_text(''); (folder/'proposal.json').write_text('{}')
            with self.assertRaises(ValueError): launch_failure_evidence(folder)


class TrialTests(unittest.TestCase):
    def setUp(self):
        from test_tabular_screen import TabularScreenTests
        fixture=TabularScreenTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.root,self.base=fixture.root,fixture.base
        self.proposal=self.root/'proposal.json'; write_json(self.proposal,proposal())
        self.library=self.root/'library.json'
        write_json(self.library,[{'url':e['url'],'title':'SOFTWARE FIXTURE','full_text':'NOT VERIFIED','pdf_sha256':'a'*64} for e in proposal()['evidence']])
        self.review=self.root/'trial'
        self.prepared=prepare(self.base,self.proposal,self.review,self.library)

    def test_review_is_bound_and_cannot_use_baseline_approval(self):
        load_trial(self.review)
        with patch('research_harness.tabular_trial.environment') as env:
            with self.assertRaises(ValueError): execute_trial(self.review,root=self.root)
            env.assert_not_called()
        self.assertFalse((self.root/'.research-memory/tabular-trial').exists())
        with self.assertRaises(ValueError): approve_trial(self.review,'0'*64,'fixture')
        approve_trial(self.review,self.prepared['sha256'],'SOFTWARE TEST ONLY')
        with self.assertRaises(FileExistsError): approve_trial(self.review,self.prepared['sha256'],'fixture')
        (self.review/'candidate.py').write_text(SOURCE+'# changed')
        with self.assertRaisesRegex(ValueError,'Candidate changed'): load_trial(self.review)

    def test_source_change_blocks_trial_execution(self):
        with patch('research_harness.tabular_trial.source_hashes',return_value={}):
            with self.assertRaisesRegex(ValueError,'source changed'): load_trial(self.review)
            load_trial(self.review,current=False)

    def raw(self,gain):
        _,parts,_,qualified=validated_baseline(self.base)
        refs={r['seed']:{x['id']:x['prediction'] for x in r['predictions']} for r in qualified['results'] if r['model']=='hgb'}
        raw={'transform_train_seconds':.1,'peak_rss_native':1,'results':[]}
        for seed in RECIPE['seeds']:
            for kind,error in (('baseline',1),('candidate',1-gain)):
                raw['results'].append({'kind':kind,'seed':seed,'fit_seconds':.1,'batch_seconds':.01,'timing_seconds':[.01]*5,
                    'validation_predictions':[refs[seed][r['id']] for r in parts['validation.json']] if kind=='baseline' else None,
                    'predictions':[{'id':r['id'],'prediction':r['target']+error} for r in parts['holdout-targets.json']]})
        return raw,parts,qualified

    def test_same_effect_uncertainty_and_latency_gates(self):
        self.assertEqual(evaluate_trial(*self.raw(.1))['status'],'CONTINUE')
        self.assertEqual(evaluate_trial(*self.raw(.01))['status'],'STOP')
        raw,parts,qualified=self.raw(.1)
        for result in raw['results']:
            if result['kind']=='candidate': result.update(batch_seconds=.02,timing_seconds=[.02]*5)
        self.assertEqual(evaluate_trial(raw,parts,qualified)['status'],'STOP')

    def test_measurement_corruption_is_not_a_scientific_stop(self):
        for mutate in (lambda r:r['results'][0]['validation_predictions'].__setitem__(0,1e6),
                       lambda r:r['results'][0]['predictions'].pop(),
                       lambda r:r['results'][1]['predictions'][0].update(prediction=float('nan')),
                       lambda r:r['results'][1].update(batch_seconds=.02),
                       lambda r:r['results'][3]['predictions'][0].update(prediction=12345)):
            raw,parts,qualified=self.raw(.1); mutate(raw)
            with self.assertRaises(ValueError): evaluate_trial(raw,parts,qualified)

    def test_worker_failure_consumes_partition_even_under_a_new_review_id(self):
        approve_trial(self.review,self.prepared['sha256'],'SOFTWARE TEST ONLY')
        def failed(*args,**kwargs):
            args[5].mkdir(); return {'error':'fixture failure','returncode':1}
        with patch('research_harness.tabular_trial.environment',return_value={}), \
             patch('research_harness.tabular_sandbox.isolation_probe',return_value={}), \
             patch('research_harness.tabular_sandbox.isolated_worker',side_effect=failed):
            result=execute_trial(self.review,root=self.root)
        self.assertEqual(result['status'],'STOP'); self.assertFalse(result['measurement_valid'])
        self.assertFalse(result['final_holdout_scored'])
        other=self.root/'other-trial'; prepared=prepare(self.base,self.proposal,other,self.library)
        approve_trial(other,prepared['sha256'],'SOFTWARE TEST ONLY')
        with self.assertRaisesRegex(ValueError,'already reserved'): execute_trial(other,root=self.root)
