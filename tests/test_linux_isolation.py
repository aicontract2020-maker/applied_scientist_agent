"""Command construction unit tests, not substitutes for Linux kernel probes."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_harness.linux_isolation import bwrap_base, linux_actor_command, linux_candidate_command


class LinuxBoundaryCommands(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.root=self.base/'repo with spaces';self.root.mkdir()
        self.actor=self.base/'agent';self.actor.mkdir();(self.actor/'responses').mkdir()
        self.state=self.base/'codex-state';self.state.mkdir()
        self.snapshot=self.base/'snapshot';self.snapshot.mkdir()
        self.inputs=self.base/'inputs';self.inputs.mkdir()
        self.output=self.base/'output';self.output.mkdir()
        self.trusted=self.base/'trusted';self.trusted.mkdir()
        self.which=patch('research_harness.linux_isolation.shutil.which',return_value='/usr/bin/bwrap');self.which.start();self.addCleanup(self.which.stop)
        self.uid=patch('research_harness.linux_isolation.os.geteuid',return_value=1000);self.uid.start();self.addCleanup(self.uid.stop)

    def test_missing_backend_and_root_fail_closed(self):
        with patch('research_harness.linux_isolation.shutil.which',return_value=None):
            with self.assertRaisesRegex(ValueError,'requires bubblewrap'):bwrap_base(False)
        with patch('research_harness.linux_isolation.os.geteuid',return_value=0):
            with self.assertRaisesRegex(ValueError,'never root'):bwrap_base(False)

    def test_candidate_cannot_receive_host_root_or_network_or_secrets(self):
        argv=linux_candidate_command([sys.executable,'-B','runner.py'],self.root,Path(sys.executable),self.snapshot,self.inputs,self.output,self.trusted)
        for flag in ['--unshare-user','--unshare-pid','--unshare-net','--cap-drop','--die-with-parent','--new-session','--clearenv']:
            self.assertIn(flag,argv)
        binds=[argv[i+1:i+3] for i,x in enumerate(argv) if x=='--bind']
        self.assertEqual(binds,[[str(self.output),str(self.output)]])
        self.assertNotIn(['/', '/'],[argv[i+1:i+3] for i,x in enumerate(argv) if x=='--ro-bind'])
        self.assertIn(str(self.root),argv);self.assertIn(str(self.inputs),argv)

    def test_actor_has_readonly_responses_but_no_control_mount(self):
        def runtime(command):
            command.extend(['--ro-bind','/usr','/usr'])
            return '/usr/bin/codex','/usr/bin:/bin'
        with patch('research_harness.linux_isolation.codex_runtime',side_effect=runtime),patch.dict(os.environ,{'CODEX_HOME':str(self.state)}):
            argv=linux_actor_command(['codex','exec','a single prompt'],self.root,self.base/'control',self.actor)
        self.assertNotIn('--unshare-net',argv)
        self.assertNotIn(str(self.base/'control'),argv)
        index=argv.index(str(self.actor/'responses'))
        self.assertEqual(argv[index-1],'--ro-bind')
        self.assertGreater(argv.index('--tmpfs'),argv.index('--ro-bind'))
        self.assertEqual(argv[-3:],['/usr/bin/codex','exec','a single prompt'])
