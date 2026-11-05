"""Software-only evidence handoff; never run candidate code or score images."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_harness.core import digest
from research_harness.evidence_bundle import export_bundle, verify_bundle, unpack_bundle, load_bundle, FILE_LIMIT, PACKET_LIMIT
from research_harness.study_inspection import audit_run
import test_study_inspection as fixtures


class EvidenceBundleTests(unittest.TestCase):
    setUp = fixtures.InspectionTests.setUp
    write = fixtures.InspectionTests.write
    ledger = fixtures.InspectionTests.ledger

    def bundle(self, name='evidence.json'):
        path=self.root/name
        export_bundle(self.run,path)
        return path

    def edit(self, path, change, resign=True):
        value=json.loads(path.read_text());change(value['payload'])
        if resign:value['sha256']=digest(value['payload'])
        path.write_text(json.dumps(value))

    def source_hashes(self):
        return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.run.iterdir() if p.is_file()}

    def test_roundtrip_offline_audited_negative_is_exact_and_source_unchanged(self):
        (self.run/'auth.json').write_text('AUTH_NOT_EXPORTED')
        (self.run/'agent-events.jsonl').write_text('RAW_MODEL_EVENT_NOT_EXPORTED')
        (self.run/'paper.pdf').write_text('PAPER_NOT_EXPORTED')
        (self.run/'candidate-array.npy').write_text('ARRAY_NOT_EXPORTED')
        before=self.source_hashes();packet=self.bundle();text=packet.read_text()
        for marker in ('AUTH_NOT_EXPORTED','RAW_MODEL_EVENT_NOT_EXPORTED','PAPER_NOT_EXPORTED','ARRAY_NOT_EXPORTED'):
            self.assertNotIn(marker,text)
        self.assertTrue(verify_bundle(packet)['audit_ok'])
        output=self.root/'review copy';result=unpack_bundle(packet,output)
        self.assertTrue(audit_run(result['run'])['audit_ok'])
        receipt=json.loads((output/'receipt.json').read_text())
        self.assertEqual(receipt['packet_sha256'],load_bundle(packet)['sha256'])
        again=self.root/'again.json';export_bundle(result['run'],again)
        self.assertEqual(load_bundle(again),load_bundle(packet))
        self.assertEqual(before,self.source_hashes())
        self.assertFalse((output/'local_studies').exists());self.assertFalse((output/'.research-memory').exists())
        if os.name!='nt':self.assertEqual(packet.stat().st_mode&0o777,0o600)

    def test_valid_positive_invalid_and_rejected_terminal_paths_can_be_shared(self):
        # Existing auditor determines consistency; handoff does not equate STOP with failure to export.
        invalid={'status':'STOP','measurement_valid':False,'reason':'synthetic execution failed; no retry'}
        self.write('result.json',invalid);self.events[-2]['result']=invalid;self.ledger()
        self.assertTrue(verify_bundle(self.bundle('invalid.json'))['audit_ok'])
        rejection={'status':'REJECTED','scientific_status':'NOT_RUN','measurement_valid':None,'experiment_started':False}
        self.write('result.json',rejection);(self.run/'registered.json').unlink()
        (self.run/'agent-REPORT.md').write_text('REJECTED / NOT_RUN')
        self.events=self.events[:3]+[{'event':'REGISTRATION_REJECTED','result':rejection},{'event':'AGENT_FINISHED','exit_code':0}]
        self.ledger()
        self.assertTrue(verify_bundle(self.bundle('rejected.json'))['audit_ok'])

    def test_audited_continue_is_not_labeled_scientific_authentication(self):
        from research_harness.observations import summarize
        for row in self.rows:row['candidate_score']=30.1
        self.result.update(status='CONTINUE',candidate_psnr_y=30.1,mean_gain_db=sum(r['candidate_score']-r['baseline_score'] for r in self.rows)/10,
                           **summarize(self.policy,self.rows))
        self.write('result.json',self.result);self.write('observations.json',self.rows)
        self.events[-2]['result']=self.result;self.ledger();(self.run/'agent-REPORT.md').write_text('CONTINUE')
        result=verify_bundle(self.bundle())
        self.assertTrue(result['audit_ok']);self.assertEqual(result['authenticity'],'UNVERIFIED')

    def test_checksum_tamper_and_valid_checksum_with_bad_decision_are_rejected(self):
        packet=self.bundle()
        self.edit(packet,lambda p:p['files']['candidate.py'].update(content='changed'),resign=False)
        with self.assertRaisesRegex(ValueError,'checksum'):verify_bundle(packet)
        packet=self.bundle('other.json')
        def corrupt(payload):
            result=json.loads(payload['files']['result.json']['content']);result['status']='CONTINUE'
            content=json.dumps(result)
            payload['files']['result.json']={'content':content,'sha256':hashlib.sha256(content.encode()).hexdigest()}
        self.edit(packet,corrupt)
        checked=verify_bundle(packet);self.assertTrue(checked['checksum_ok']);self.assertFalse(checked['audit_ok'])
        out=self.root/'must-not-exist'
        with self.assertRaisesRegex(ValueError,'audit'):unpack_bundle(packet,out)
        self.assertFalse(out.exists())

    def test_unknown_version_keys_path_traversal_and_duplicate_json_are_rejected(self):
        source=self.bundle();original=source.read_bytes()
        changes=[lambda p:p.update(version=2),lambda p:p.update(sender_path='/etc/passwd')]
        for name in ('../escape','/tmp/escape','sub/child','..\\escape','auth.json'):
            changes.append(lambda p,n=name:p['files'].update({n:{'content':'x','sha256':hashlib.sha256(b'x').hexdigest()}}))
        for change in changes:
            source.write_bytes(original);self.edit(source,change)
            with self.assertRaises(ValueError):unpack_bundle(source,self.root/'not-created')
            self.assertFalse((self.root/'not-created').exists())
        duplicate=self.root/'duplicate.json';duplicate.write_text('{"payload":{},"payload":{},"sha256":"x"}')
        with self.assertRaisesRegex(ValueError,'Duplicate'):load_bundle(duplicate)

    def test_existing_outputs_and_symlinks_are_never_overwritten(self):
        packet=self.bundle();before=packet.read_bytes()
        with self.assertRaises(FileExistsError):export_bundle(self.run,packet)
        self.assertEqual(packet.read_bytes(),before)
        output=self.root/'existing';output.mkdir();(output/'mine').write_text('KEEP')
        with self.assertRaises(FileExistsError):unpack_bundle(packet,output)
        self.assertEqual((output/'mine').read_text(),'KEEP')
        link=self.root/'link.json';link.symlink_to(packet)
        with self.assertRaises(ValueError):verify_bundle(link)
        candidate=self.run/'candidate.py';candidate.unlink();candidate.symlink_to(self.run/'agent-candidate.py')
        with self.assertRaises(ValueError):export_bundle(self.run,self.root/'no-export.json')
        self.assertFalse((self.root/'no-export.json').exists())

    def test_incomplete_or_changing_runs_do_not_export(self):
        from research_harness.evidence_bundle import _signature
        with patch('research_harness.evidence_bundle._signature',side_effect=lambda p: None if _signature(p) is None else object()):
            with self.assertRaisesRegex(ValueError,'changed'):export_bundle(self.run,self.root/'changed.json')
        self.assertFalse((self.root/'changed.json').exists())
        (self.run/'session.json').unlink()
        with self.assertRaisesRegex(ValueError,'audit'):export_bundle(self.run,self.root/'incomplete.json')
        self.assertFalse((self.root/'incomplete.json').exists())

    def test_partial_write_failure_cleans_only_owned_new_container(self):
        packet=self.bundle();out=self.root/'owned'
        from research_harness import evidence_bundle as module
        original=module._materialize;calls=[]
        def fail(bundle,directory):
            calls.append(directory)
            if len(calls)==2:
                (Path(directory)/'partial').write_text('partial')
                raise OSError('synthetic disk error')
            return original(bundle,directory)
        with patch.object(module,'_materialize',side_effect=fail):
            with self.assertRaisesRegex(OSError,'synthetic'):unpack_bundle(packet,out)
        self.assertFalse(out.exists());self.assertTrue(self.run.is_dir());self.assertTrue(packet.exists())

    def test_oversized_packet_and_content_are_rejected(self):
        packet=self.bundle()
        self.edit(packet,lambda p:p['files'].update({'REPORT.md':{'content':'x'*(FILE_LIMIT+1),'sha256':'x'}}))
        with self.assertRaisesRegex(ValueError,'limit'):verify_bundle(packet)
        huge=self.root/'huge.json'
        with huge.open('wb') as handle:handle.truncate(PACKET_LIMIT+1)
        with self.assertRaisesRegex(ValueError,'limit'):load_bundle(huge)

    def test_transferred_source_is_never_executed(self):
        marker=self.root/'SHOULD_NOT_EXIST'
        code=f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n'
        self.protocol['candidate_sha256']=hashlib.sha256(code.encode()).hexdigest()
        self.write('registered.json',self.protocol)
        for name in ('candidate.py','agent-candidate.py'):(self.run/name).write_text(code)
        self.events[3]['candidate_sha256']=self.protocol['candidate_sha256']
        self.events[5].update(candidate_sha256=self.protocol['candidate_sha256'],protocol_sha256=digest(self.protocol))
        self.events[7]['protocol_sha256']=digest(self.protocol);self.ledger()
        self.write('intervention-review.json',{'decision':'PASS','candidate_sha256':self.protocol['candidate_sha256'],'plan_sha256':digest(self.plan)})
        packet=self.bundle();verify_bundle(packet);unpack_bundle(packet,self.root/'safe')
        self.assertFalse(marker.exists())

    def test_actual_cli_handoff_works_without_model_or_asset_dependencies(self):
        packet=self.root/'cli.json';out=self.root/'cli review'
        def command(*args, expected=0):
            result=subprocess.run([sys.executable,'-m','research_harness','study',*args],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,expected,result.stderr)
            return json.loads(result.stdout)
        self.assertEqual(command('export','--run',str(self.run),'--out',str(packet))['status'],'EXPORTED')
        self.assertTrue(command('verify',str(packet))['audit_ok'])
        result=command('unpack',str(packet),'--out',str(out))
        self.assertTrue(command('audit','--run',result['run'])['audit_ok'])
