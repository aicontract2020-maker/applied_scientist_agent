"""Setup/lifecycle boundary tests only; no network, model calls or real image scores."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_harness.portable import new_study
from research_harness.autonomy import candidate_profile
from research_harness.onboarding import research, validate_workflow


class PortableStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        source=Path(__file__).resolve().parents[1]
        import shutil
        shutil.copytree(source/'templates',self.root/'templates')
        (self.root/'research_harness').mkdir();(self.root/'research_harness/code.py').write_text('trusted')
        for name in ['requirements-sr.txt','assets/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth','external/SwinIR/models/network_swinir.py','external/SwinIR/utils/util_calculate_psnr_ssim.py']:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
        folder=self.root/'external/SelfExSR/data/Urban100/image_SRF_2';folder.mkdir(parents=True)
        for i in range(1,101):
            for kind in ['LR','HR']:(folder/f'img_{i:03d}_SRF_2_{kind}.png').write_bytes(b'fixture only')
        self.verify=patch('research_harness.portable.verify_sources');self.verify.start();self.addCleanup(self.verify.stop)

    def test_new_studies_are_disjoint_and_reservations_cannot_overwrite(self):
        first=new_study('first',self.root);second=new_study('second',self.root)
        a=json.loads((first/'policy.json').read_text());b=json.loads((second/'policy.json').read_text())
        historical=json.loads((self.root/'templates/sr/history.json').read_text())['used_urban100_ids']
        self.assertTrue(set(a['observation_ids']).isdisjoint(b['observation_ids']))
        self.assertTrue(set(a['observation_ids']).isdisjoint(historical))
        self.assertEqual(a['minimum_effect'],.05);self.assertEqual(a['max_latency_ratio'],2.5)
        with self.assertRaisesRegex(ValueError,'already reserved'):new_study('first',self.root)
        with self.assertRaisesRegex(ValueError,'Study id'):new_study('../escape',self.root)

    def test_local_negative_route_and_read_sources_carry_forward(self):
        first=new_study('first',self.root);policy=json.loads((first/'policy.json').read_text())
        run=self.root/'runs/first';run.mkdir(parents=True)
        (run/'registered.json').write_text(json.dumps({'plan':{'hypothesis':'fixture hypothesis','stop_route':'fixture route','new_evidence':[{'source':'https://arxiv.org/abs/1234.56789v2'}]}}))
        (run/'result.json').write_text('{"status":"STOP"}')
        following=new_study('second',self.root);next_policy=json.loads((following/'policy.json').read_text())
        self.assertIn('1234.56789',next_policy['excluded_evidence_ids'])
        self.assertFalse(next_policy['stopped_route_compliance']['reuses_local_route_first'])
        self.assertIn('fixture route',(following/'TASK.md').read_text())

    def test_exhausted_holdout_stops_before_creating_directory(self):
        history=self.root/'templates/sr/history.json';history.write_text(json.dumps({'used_urban100_ids':[f'img_{i:03d}' for i in range(1,101)]}))
        with self.assertRaisesRegex(ValueError,'Fewer than 12'):new_study('empty',self.root)
        self.assertFalse((self.root/'local_studies/empty').exists())

    def test_candidate_profile_denies_repo_even_outside_users(self):
        from research_harness import autonomy
        with patch.object(autonomy,'ROOT',Path('/private/tmp/new clone')):
            policy=candidate_profile(Path('/tmp/control'),Path('/tmp/control/snapshot'),Path('/tmp/control/input'),Path('/tmp/control/out'),Path('/tmp/control/trusted'))
        self.assertIn('(subpath "/private/tmp/new clone")',policy)
        self.assertIn('(deny network*)',policy)

    def test_preflight_failure_prevents_reservation_or_model_call(self):
        with patch('research_harness.doctor.doctor',return_value={'ok':False,'checks':[{'name':'fixture','ok':False,'detail':'missing dependency'}]}),patch('research_harness.onboarding.new_study') as prepare,patch('research_harness.literature_study.LiteratureStudy') as agent:
            with self.assertRaisesRegex(ValueError,'Preflight failed'):research('blocked')
            prepare.assert_not_called();agent.assert_not_called()

    def test_doctor_failure_sets_command_exit_code(self):
        import subprocess,sys
        # Run on a supported interpreter but with no credentials/tools visible.
        import os
        env=dict(os.environ);env['PATH']='/nonexistent'
        result=subprocess.run([sys.executable,'-m','research_harness','doctor'],capture_output=True,text=True,env=env)
        self.assertEqual(result.returncode,1)
        self.assertFalse(json.loads(result.stdout)['ok'])
