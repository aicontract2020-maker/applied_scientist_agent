"""Synthetic records only: historical audit, analytical screen and route closure."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_harness.core import digest, Workspace
from research_harness.tabular_baseline import prepare_rows, load_review, qualify, PACKAGES, RECIPE
from research_harness.tabular_audit import audit_baseline
from research_harness.tabular_screen import SCREEN_TEMPLATE, decision, screen, verify_screen, retain_screen, history_records
from research_harness.tabular_data import write_json
from research_harness.portable import ROOT


class TabularScreenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.base = self.root/'baseline'
        rows = [{'id': f'fixture-{i}', 'features':[float(i+j) for j in range(10)], 'target':float(i)} for i in range(150)]
        prepared = prepare_rows(rows,self.base,{'id':'synthetic-software-fixture'})
        packet,parts = load_review(self.base)
        write_json(self.base/'approval.json',{'sha256':prepared['sha256'],'reviewer':'SOFTWARE FIXTURE',
                   'scope':'One baseline qualification only; no candidate study or final holdout scoring'})
        self.run = self.base/'run'; self.run.mkdir()
        for name in ('inputs','output','trusted'): (self.run/name).mkdir()
        (self.run/'trusted/worker.py').write_bytes((ROOT/'research_harness/tabular_worker.py').read_bytes())
        write_json(self.run/'inputs/request.json',{'recipe':RECIPE,'train':parts['train.json'],'validation':parts['validation.json']})
        write_json(self.run/'preflight.json',{'environment':{'python':[3,12],'packages':PACKAGES},'isolation':
            {k:True for k in ('private_labels_denied','repo_denied','input_readonly','network_denied','output_writable')}})
        write_json(self.run/'process.json',{'error':None,'returncode':0})
        raw={'peak_rss_native':1,'results':[]}
        for seed in RECIPE['seeds']:
            for model,error in [('median',2),('ridge',1),('hgb',.01)]:
                raw['results'].append({'model':model,'seed':seed,'fit_seconds':.1,'predict_seconds':.01,
                    'predictions':[{'id':r['id'],'prediction':r['target']-error} for r in parts['validation-targets.json']]})
        write_json(self.run/'output/predictions.json',raw)
        result={**qualify(raw,parts['validation-targets.json']),'wall_seconds':1}
        write_json(self.run/'result.json',result)
        Workspace.append(self.run,{'event':'REGISTER','review_sha256':prepared['sha256']})
        Workspace.append(self.run,{'event':'BASELINE_STARTED','review_sha256':prepared['sha256']})
        Workspace.append(self.run,{'event':'DECISION','result':result})
        content=dict(SCREEN_TEMPLATE,id='fixture-screen',baseline_review_sha256=prepared['sha256'])
        self.protocol=self.root/'protocol.json'
        write_json(self.protocol,{'content':content,'sha256':digest(content)})

    def hashes(self):
        return {str(p.relative_to(self.base)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.base.rglob('*') if p.is_file()}

    def test_historical_audit_survives_upgrade_without_relaxing_execution(self):
        before=self.hashes()
        with patch('research_harness.tabular_baseline.source_hashes',return_value={}), \
             patch('research_harness.tabular_audit.source_hashes',return_value={}):
            with self.assertRaisesRegex(ValueError,'source changed'): load_review(self.base)
            checked=audit_baseline(self.base)
            self.assertTrue(checked['audit_ok']); self.assertFalse(checked['current_sources_match'])
        self.assertEqual(before,self.hashes())

    def test_changed_metrics_worker_inputs_and_events_are_rejected(self):
        for file,change in [
            ('result.json',lambda p:p.update(selected_baseline='ridge')),
            ('inputs/request.json',lambda p:p.update(holdout='forbidden')),
            ('process.json',lambda p:p.update(returncode=1)),
            ('preflight.json',lambda p:p['isolation'].update(network_denied=False))]:
            path=self.run/file; before=path.read_text(); value=json.loads(before);change(value);path.write_text(json.dumps(value))
            self.assertFalse(audit_baseline(self.base)['audit_ok'],file)
            path.write_text(before)
        (self.run/'trusted/worker.py').write_text('do not execute')
        self.assertFalse(audit_baseline(self.base)['audit_ok'])

    def test_noop_impossible_and_possible_have_distinct_meanings(self):
        self.assertEqual(decision(0,.05),('REJECTED','No-op'))
        for delta in (-.01,.01): self.assertEqual(decision(delta,.05)[0],'REJECTED')
        for delta in (-.1,.05,.1): self.assertEqual(decision(delta,.05)[0],'AWAITING_RESEARCH_REVIEW')
        with self.assertRaises(ValueError): decision(float('nan'),.05)
        for y in (-5,0,5):
            for pred in (-2,0,2):
                for delta in (-.1,0,.1):
                    self.assertLessEqual(abs(y-pred)-abs(y-(pred+delta)),abs(delta)+1e-12)

    def test_historical_source_remains_text_even_if_self_consistently_forged(self):
        # Integrity is not authentication. A coherent forged record must still never execute its source.
        marker=self.root/'MUST_NOT_EXIST'
        worker=self.run/'trusted/worker.py'
        worker.write_text(f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n')
        path=self.base/'bundle.json';packet=json.loads(path.read_text())
        packet['content']['sources']['research_harness/tabular_worker.py']=hashlib.sha256(worker.read_bytes()).hexdigest()
        packet['sha256']=digest(packet['content']);path.write_text(json.dumps(packet))
        path=self.base/'approval.json';approval=json.loads(path.read_text());approval['sha256']=packet['sha256'];path.write_text(json.dumps(approval))
        path=self.run/'ledger.jsonl';events=[json.loads(line) for line in path.read_text().splitlines()]
        for event in events[:2]: event['review_sha256']=packet['sha256']
        path.write_text('\n'.join(map(json.dumps,events))+'\n')
        self.assertTrue(audit_baseline(self.base)['audit_ok'])
        self.assertFalse(marker.exists())

    def test_screen_is_terminal_and_cannot_be_reopened_under_a_new_id(self):
        before=self.hashes(); out=self.root/'proposal'
        result=screen(self.base,self.protocol,out,root=self.root)
        self.assertEqual(result['status'],'REJECTED');self.assertFalse(result['final_holdout_scored'])
        self.assertLess(result['universal_mae_gain_upper_bound'],.05)
        verify_screen(self.base,out)
        self.assertEqual(before,self.hashes())
        packet=json.loads(self.protocol.read_text());packet['content']['id']='renamed'
        packet['sha256']=digest(packet['content']);self.protocol.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError,'already screened'): screen(self.base,self.protocol,self.root/'another',root=self.root)
        self.assertFalse((self.root/'another').exists())

    def test_weakened_threshold_is_rejected_before_reservation(self):
        packet=json.loads(self.protocol.read_text());packet['content']['minimum_effect']=.001
        packet['sha256']=digest(packet['content']);self.protocol.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError,'parameter rescue'): screen(self.base,self.protocol,self.root/'none',root=self.root)
        self.assertFalse((self.root/'.research-memory').exists())

    def test_seed_variability_prevents_calibration_before_reservation(self):
        from research_harness.tabular_audit import validated_baseline
        packet,parts,result,raw=validated_baseline(self.base)
        result['prediction_range']['hgb']=1e-12
        with patch('research_harness.tabular_screen.validated_baseline',return_value=(packet,parts,result,raw)):
            with self.assertRaisesRegex(ValueError,'identical baseline predictions'):
                screen(self.base,self.protocol,self.root/'none',root=self.root)
        self.assertFalse((self.root/'.research-memory').exists())

    def test_retain_old_record_is_idempotent_but_rejects_tampering(self):
        proposal=self.root/'proposal';screen(self.base,self.protocol,proposal,root=self.root/'first-checkout')
        second=self.root/'second-checkout'
        self.assertEqual(retain_screen(self.base,proposal,root=second)['status'],'RETAINED')
        self.assertEqual(retain_screen(self.base,proposal,root=second)['status'],'ALREADY_RETAINED')
        path=proposal/'screen-result.json';result=json.loads(path.read_text());result['delta']=.5;path.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError,'inconsistent'): retain_screen(self.base,proposal,root=self.root/'third-checkout')
        self.assertFalse((self.root/'third-checkout/.research-memory').exists())

    def test_partial_screen_keeps_reservation_and_linked_history_rejected(self):
        with patch('research_harness.tabular_screen._calculate',side_effect=ValueError('fixture failure')):
            with self.assertRaisesRegex(ValueError,'fixture failure'): screen(self.base,self.protocol,self.root/'partial',root=self.root)
        with self.assertRaisesRegex(ValueError,'already screened'): screen(self.base,self.protocol,self.root/'retry',root=self.root)
        other=self.root/'other';other.mkdir();(other/'.research-memory').symlink_to(self.root/'.research-memory')
        with self.assertRaisesRegex(ValueError,'symlink'): screen(self.base,self.protocol,self.root/'linked',root=other)

    def test_published_history_protects_fresh_checkout_and_rejects_conflicts(self):
        screen(self.base,self.protocol,self.root/'proposal',root=self.root)
        records=history_records(self.root)
        clone=self.root/'clone';folder=clone/'tasks/tabular_regression';folder.mkdir(parents=True)
        write_json(folder/'screen-history.json',records)
        with self.assertRaisesRegex(ValueError,'already screened'):
            screen(self.base,self.protocol,self.root/'repeat-in-clone',root=clone)
        self.assertFalse((clone/'.research-memory').exists())
        records.append(dict(records[0],status='AWAITING_RESEARCH_REVIEW'))
        (folder/'screen-history.json').write_text(json.dumps(records))
        with self.assertRaisesRegex(ValueError,'Conflicting'): history_records(clone)
