"""Software boundary tests with synthetic files; never a research-model experiment."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_harness.autonomy import AutonomousStudy, actor_profile, candidate_profile


class AutonomousBrokerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Construct a synthetic controller without touching a real research policy.
        self.study = AutonomousStudy.__new__(AutonomousStudy)
        self.study.study = self.root
        self.study.destination = self.root/'archive'; self.study.destination.mkdir()
        self.study.actor = self.root/'agent'; self.study.actor.mkdir()
        self.study.control = self.root/'control'; self.study.control.mkdir()
        self.study.registered = None; self.study.closed = False; self.study.smoke_count = 0
        self.study.events = self.root/'ledger.jsonl'
        self.study.policy={'controls':['frozen'], 'minimum_effect':.05,'max_latency_ratio':2.5,
                           'bootstrap':{'resamples':1000,'seed':42,'confidence':.95},'observation_ids':[f'image-{i}' for i in range(14)]}
        self.study.hidden={'files':{}}
        (self.root/'literature.json').write_text(json.dumps([{'url':'https://example.test/primary'}]))
        (self.study.actor/'candidate.py').write_text('import numpy as np\ndef enhance(lr,sr):\n    return sr.copy()\n')
        self.plan={'hypothesis':'test claim','mechanism':'distinct operator','baseline':'strong reference','why_not_g1_retry':'different mechanism',
                   'stop_route':'stop this route','new_evidence':[{'source':'https://example.test/primary','claim':'source claim','why_distinct':'new route'}],
                   **self.study.policy}

    def write_plan(self):
        (self.study.actor/'research.json').write_text(json.dumps(self.plan))

    def test_registration_freezes_agent_code_once(self):
        self.write_plan()
        with patch('research_harness.autonomy.STUDY',self.root):
            result=self.study.register()
            self.assertEqual(result['status'],'REGISTERED')
            with self.assertRaises(ValueError):
                self.study.register()
        (self.study.actor/'candidate.py').write_text('changed after register')
        self.assertIn('return sr.copy()', (self.study.control/'registered-candidate/candidate.py').read_text())

    def test_cannot_lower_effect_or_change_holdout(self):
        self.plan['minimum_effect']=.001;self.write_plan()
        with self.assertRaisesRegex(ValueError,'decision field'):
            self.study.register()

    def test_new_evidence_required_after_stop(self):
        self.plan['new_evidence']=[];self.write_plan()
        with self.assertRaisesRegex(ValueError,'external evidence'):
            self.study.register()

    def test_imports_symlinks_and_syntax_invalidated(self):
        (self.study.actor/'candidate.py').write_text('import os\ndef enhance(lr,sr): return sr\n')
        with self.assertRaisesRegex(ValueError,'imports'):
            self.study.snapshot('bad')
        (self.study.actor/'candidate.py').unlink()
        (self.study.actor/'candidate.py').symlink_to(self.root/'literature.json')
        with self.assertRaisesRegex(ValueError,'regular'):
            self.study.snapshot('bad-link')

    def test_closed_experiment_and_smoke_cannot_restart(self):
        self.study.closed=True
        with self.assertRaises(ValueError):self.study.run_experiment()
        with self.assertRaises(ValueError):self.study.smoke()

    def test_unknown_rpc_operation_cannot_execute_a_command(self):
        path=self.root/'request.json';path.write_text(json.dumps({'operation':'shell','command':'touch SHOULD_NOT_EXIST'}))
        with self.assertRaisesRegex(ValueError,'Unknown'):
            self.study.serve_request(path)
        self.assertFalse((self.root/'SHOULD_NOT_EXIST').exists())

    def test_profiles_protect_control_and_candidate_network(self):
        actor=actor_profile(self.study.control,self.study.actor)
        self.assertIn(str(self.study.control),actor)
        candidate=candidate_profile(self.study.control,self.root/'snapshot',self.root/'inputs',self.root/'output',self.root/'trusted')
        self.assertIn('(deny network*)',candidate)
        self.assertIn('(subpath "/Users")',candidate)
        self.assertIn('deny file-write*',candidate)
