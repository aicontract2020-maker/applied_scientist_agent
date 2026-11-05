"""Software regression tests, no papers/model calls/benchmark inference."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_harness.intervention_review import fingerprint, validate_semantic, review_intervention, catalog
import test_autonomy as fixtures

ROOT=Path(__file__).resolve().parents[1]

class InterventionReviewTests(unittest.TestCase):
    def test_new_published_stop_is_automatically_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'tasks/image_super_resolution/g99';(folder/'evidence').mkdir(parents=True)
            (folder/'evidence/result.json').write_text('{"status":"STOP","measurement_valid":true}')
            (folder/'candidate.py').write_text('def enhance(lr,sr): return sr*.99')
            (folder/'research.json').write_text('{"hypothesis":"fixture","stop_route":"fixture route"}')
            routes=catalog(root,[])
            self.assertEqual([r['id'] for r in routes],['G99'])
            self.assertIn('fixture route',routes[0]['mechanism'])

    def test_numeric_retune_and_rename_match_stopped_implementation(self):
        source=(ROOT/'tasks/image_super_resolution/g4/candidate.py').read_text()
        changed=source.replace('0.005','0.012').replace('center','renamed_center').replace('delta','correction')
        self.assertEqual(fingerprint(source),fingerprint(changed))

    def test_actual_adapter_rejects_identity_clip_and_rounding_noops(self):
        try: import numpy
        except ImportError: self.skipTest('numpy not installed')
        for expression in ('sr.copy()', 'np.clip(sr,0,1)', 'np.round(np.clip(sr,0,1)*255)/255'):
            with self.subTest(expression=expression), tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp);(p/'candidate.py').write_text('import numpy as np\ndef enhance(lr,sr): return '+expression+'\n')
                out=p/'out';out.mkdir()
                result=subprocess.run([sys.executable,str(ROOT/'research_harness/autonomous_candidate.py'),'--candidate',str(p/'candidate.py'),'--inputs',str(p),'--output',str(out),'--intervention-probe'],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertFalse(json.loads((out/'probe.json').read_text())['observable_change'])

    def test_independent_verdict_must_bind_both_hashes_and_every_route(self):
        value={'decision':'PASS','candidate_sha256':'code','plan_sha256':'plan','nontrivial_after_conversion':True,'distinct_mechanism':True,'reason':'fixture','routes':[{'id':'old','reuses_route':False,'reason':'different cause'}]}
        validate_semantic(value,'code','plan',[{'id':'old'}])
        for changed in ({'candidate_sha256':'wrong'},{'routes':[]},{'distinct_mechanism':False},{'routes':[{'id':'old','reuses_route':True,'reason':'same cause'}]}):
            with self.assertRaises(ValueError):validate_semantic({**value,**changed},'code','plan',[{'id':'old'}])

class MandatoryGateTests(unittest.TestCase):
    setUp = fixtures.AutonomousBrokerTest.setUp
    write_plan = fixtures.AutonomousBrokerTest.write_plan

    def test_rejection_prevents_registration_experiment_and_retry(self):
        self.write_plan();self.study.policy['intervention_review']={'required':True}
        with patch('research_harness.intervention_review.review_intervention',return_value={'decision':'REJECT','reason':'no observable change'}):
            result=self.study.register()
        self.assertEqual(result['scientific_status'],'NOT_RUN')
        self.assertFalse((self.study.destination/'registered.json').exists())
        self.assertIsNone(self.study.registered)
        for action in (self.study.register,self.study.run_experiment,self.study.smoke):
            with self.assertRaises(ValueError):action()

    def test_known_stopped_route_rejects_without_candidate_or_model_execution(self):
        source=(ROOT/'tasks/image_super_resolution/g4/candidate.py').read_text()
        snapshot=self.study.control/'snapshot';snapshot.mkdir();(snapshot/'candidate.py').write_text(source.replace('0.005','0.02'))
        (self.study.study/'intervention-catalog.json').write_text(json.dumps([{'id':'G4','source':source}]))
        with patch.object(self.study,'candidate_run') as execute, patch('research_harness.intervention_review.semantic_review') as model:
            result=review_intervention(self.study,snapshot,self.plan)
        self.assertEqual(result['decision'],'REJECT');execute.assert_not_called();model.assert_not_called()

    def test_mutation_during_review_is_terminal(self):
        from research_harness.autonomy import sha
        self.write_plan();self.study.policy['intervention_review']={'required':True}
        def review(study,snapshot,plan):
            code_hash=sha(snapshot/'candidate.py');(study.actor/'candidate.py').write_text('changed')
            return {'decision':'PASS','candidate_sha256':code_hash}
        with patch('research_harness.intervention_review.review_intervention',side_effect=review):result=self.study.register()
        self.assertEqual(result['status'],'REJECTED');self.assertIsNone(self.study.registered)
