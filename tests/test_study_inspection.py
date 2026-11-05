"""Read-only evidence checks, synthetic paired scores only; no research execution."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from research_harness.core import digest
from research_harness.observations import summarize
from research_harness.study_inspection import audit_run, run_status, list_studies, Evidence


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.run=self.root/'runs/fixture';self.run.mkdir(parents=True)
        self.code='def enhance(lr,sr): return sr.copy()\n'
        self.policy={'controls':['fixture'],'minimum_effect':.05,'max_latency_ratio':2.5,
                     'observation_ids':[f'fixture-{i}' for i in range(10)],
                     'primary_metric':{'direction':'higher'},'bootstrap':{'resamples':1000,'seed':42,'confidence':.95},
                     'intervention_review':{'required':True}}
        self.plan={k:v for k,v in self.policy.items() if k not in ('primary_metric','intervention_review')}
        self.protocol={'plan':self.plan,'policy':self.policy,'candidate_sha256':hashlib.sha256(self.code.encode()).hexdigest()}
        self.rows=[{'id':n,'baseline_score':30.,'candidate_score':29.9,'baseline_latency_ms':2.,'candidate_latency_ms':1.}
                   for n in self.policy['observation_ids']]
        self.result={'status':'STOP','measurement_valid':True,'baseline_psnr_y':30.,'candidate_psnr_y':29.9,
                     'mean_gain_db':sum(r['candidate_score']-r['baseline_score'] for r in self.rows)/10,
                     **summarize(self.policy,self.rows)}
        self.events=[{'event':'PRIMARY_READ_COMPLETED','full':True},{'event':'PRIMARY_READ_COMPLETED','full':False},
            {'event':'AGENT_REQUEST','operation':'register'},{'event':'INTERVENTION_REVIEW_STARTED','candidate_sha256':self.protocol['candidate_sha256']},
            {'event':'INTERVENTION_REVIEW_FINISHED','decision':'PASS'},
            {'event':'REGISTER','protocol_sha256':digest(self.protocol),'candidate_sha256':self.protocol['candidate_sha256']},
            {'event':'AGENT_REQUEST','operation':'run'},{'event':'EXPERIMENT_STARTED','protocol_sha256':digest(self.protocol)},
            {'event':'DECISION','result':self.result},{'event':'AGENT_FINISHED','exit_code':0}]
        self.write('result.json',self.result);self.write('registered.json',self.protocol)
        self.write('observations.json',self.rows);self.write('session.json',{'total_wall_seconds':1,'local_proxy_usd':1/3600})
        (self.run/'agent-events.jsonl').write_text('')
        self.write('search-records.json',[{'type':'web_search'}]);self.write('agent-research.json',self.plan)
        self.write('intervention-review.json',{'decision':'PASS','candidate_sha256':self.protocol['candidate_sha256'],'plan_sha256':digest(self.plan)})
        (self.run/'candidate.py').write_text(self.code);(self.run/'agent-candidate.py').write_text(self.code)
        (self.run/'agent-REPORT.md').write_text('STOP, synthetic fixture only')
        self.ledger()
    def write(self,name,value): (self.run/name).write_text(json.dumps(value))
    def ledger(self): (self.run/'ledger.jsonl').write_text('\n'.join(json.dumps(x) for x in self.events)+'\n')
    def hashes(self): return {str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}

    def test_valid_negative_is_audited_without_touching_files(self):
        before=self.hashes();result=audit_run(self.run)
        self.assertTrue(result['audit_ok'],result['errors']);self.assertEqual(result['stage'],'STOP')
        self.assertLess(result['recomputed']['mean_gain_db'],0)
        self.assertEqual(self.hashes(),before)

    def test_tampered_scores_summary_policy_code_review_and_decision_are_rejected(self):
        original={p.name:p.read_bytes() for p in self.run.iterdir()}
        cases=[('observations.json',lambda v:v[0].update(candidate_score=35)),
               ('result.json',lambda v:v.update(status='CONTINUE')),
               ('registered.json',lambda v:v['policy'].update(minimum_effect=.001)),
               ('intervention-review.json',lambda v:v.update(plan_sha256='f'*64)),
               ('observations.json',lambda v:v[0].update(id=v[1]['id']))]
        for filename,change in cases:
            with self.subTest(filename=filename):
                for name,data in original.items():(self.run/name).write_bytes(data)
                value=json.loads((self.run/filename).read_text());change(value);self.write(filename,value)
                self.assertFalse(audit_run(self.run)['audit_ok'])
        (self.run/'agent-candidate.py').write_text('changed')
        self.assertFalse(audit_run(self.run)['audit_ok'])

    def test_missing_corrupt_or_partial_evidence_returns_errors_not_a_crash(self):
        (self.run/'result.json').unlink()
        with (self.run/'ledger.jsonl').open('a') as f:f.write('{"event":')
        self.assertFalse(audit_run(self.run)['audit_ok'])
        status=run_status(self.run)
        self.assertEqual(status['liveness'],'UNKNOWN');self.assertTrue(status['errors'])
        (self.run/'result.json').write_text('[]')
        self.assertFalse(audit_run(self.run)['audit_ok'])
        self.assertTrue(run_status(self.run)['errors'])

    def test_invalid_measurement_can_be_consistent_but_is_not_scientific_success(self):
        invalid={'status':'STOP','measurement_valid':False,'reason':'fixture timeout; never retry'}
        self.write('result.json',invalid);self.events[-2]['result']=invalid;self.ledger()
        (self.run/'observations.json').unlink()
        result=audit_run(self.run)
        self.assertTrue(result['audit_ok'],result['errors']);self.assertEqual(result['stage'],'INVALID')
        self.assertIsNone(result['recomputed'])

    def test_rejection_requires_no_registration_or_run_and_exact_terminal_event(self):
        result={'status':'REJECTED','scientific_status':'NOT_RUN','measurement_valid':None,'experiment_started':False}
        self.write('result.json',result);(self.run/'registered.json').unlink()
        (self.run/'agent-REPORT.md').write_text('REJECTED / NOT_RUN')
        self.events=self.events[:3]+[{'event':'REGISTRATION_REJECTED','result':result},{'event':'AGENT_FINISHED','exit_code':0}]
        self.ledger();self.assertTrue(audit_run(self.run)['audit_ok'])
        self.events.insert(-1,{'event':'EXPERIMENT_STARTED'});self.ledger()
        self.assertFalse(audit_run(self.run)['audit_ok'])

    def test_unbounded_bootstrap_and_symlink_are_not_followed(self):
        self.protocol['policy']['bootstrap']['resamples']=10**9
        self.write('registered.json',self.protocol)
        self.assertFalse(audit_run(self.run)['audit_ok'])
        path=self.run/'result.json';path.unlink();path.symlink_to(self.run/'session.json')
        self.assertFalse(audit_run(self.run)['audit_ok'])

    def test_changing_snapshot_cannot_pass_audit(self):
        original=Evidence.stable
        def change(reader):
            (self.run/'result.json').write_text('{}')
            return original(reader)
        with patch.object(Evidence,'stable',change):result=audit_run(self.run)
        self.assertFalse(result['audit_ok']);self.assertFalse(result['snapshot_stable'])

    def test_new_research_completion_uses_strict_audit_instead_of_trusting_summary(self):
        from research_harness.onboarding import validate_workflow
        verdict=validate_workflow(self.run,require_integrity=True)
        self.assertTrue(verdict['workflow_completed'],verdict['errors'])
        self.assertTrue(verdict['completion_audit']['audit_ok'])
        self.rows[0]['candidate_score']=35;self.write('observations.json',self.rows)
        verdict=validate_workflow(self.run,require_integrity=True)
        self.assertFalse(verdict['workflow_completed'])
        self.assertFalse(verdict['completion_audit']['audit_ok'])

    def test_list_includes_reservation_and_cli_reports_bad_audit_nonzero(self):
        (self.root/'local_studies/reserved').mkdir(parents=True)
        trusted=self.root/'runs/trusted-script';trusted.mkdir()
        (trusted/'protocol.json').write_text('{}');(trusted/'ledger.jsonl').write_text('{"event":"REGISTER"}\n')
        rows=list_studies(self.root)['studies']
        self.assertEqual({r['id'] for r in rows},{'fixture','reserved'})
        self.assertEqual(next(r for r in rows if r['id']=='reserved')['stage'],'RESERVED')
        (self.run/'candidate.py').write_text('changed')
        result=subprocess.run([sys.executable,'-m','research_harness','study','audit','--run',str(self.run)],capture_output=True,text=True)
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertFalse(json.loads(result.stdout)['audit_ok'])
