"""Installation diagnostics with fake runtimes; no scientific experiments."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_harness import tabular_doctor as td
from research_harness.tabular_baseline import PACKAGES


class TabularDoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.python = self.root/'.venv-tabular/bin/python'
        self.python.parent.mkdir(parents=True); self.python.write_text('synthetic executable, never run')
        self.python.chmod(0o700)
        self.version = {'python': [3, 12], 'packages': PACKAGES}
        self.imports = {'prefix': str(self.python.parent.parent), 'imports_ok': True}
        self.probe_result = {key: True for key in td._PROBE_KEYS}
        self.env = self.mock('environment', return_value=self.version)
        self.process = self.mock('subprocess.check_output', return_value=json.dumps(self.imports))
        self.probe = self.mock('isolation_probe', return_value=self.probe_result)
        self.mock('sys.platform', 'darwin'); self.mock('platform.machine', return_value='arm64')
        self.which = self.mock('shutil.which', return_value='/usr/bin/sandbox-exec')

    def mock(self, name, *args, **kwargs):
        mock = patch('research_harness.tabular_doctor.'+name, *args, **kwargs)
        value = mock.start(); self.addCleanup(mock.stop); return value

    def run_check(self, probe=False):
        return td.doctor(probe_isolation=probe, root=self.root)

    def checks(self, result):
        return {item['name']: item for item in result['checks']}

    def files(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_default_checks_no_probe_no_research_state_or_authorization(self):
        before = self.files(); result = self.run_check()
        self.assertTrue(result['ok']); self.assertEqual(result['status'], 'ENVIRONMENT_CHECKS_PASSED')
        self.assertFalse(result['isolation_verified']); self.assertFalse(result['isolation_probe_attempted'])
        self.assertFalse(result['execution_authorized']); self.assertFalse(result['research_state_changed'])
        self.assertFalse(result['model_call_made']); self.assertFalse(result['research_data_read'])
        self.probe.assert_not_called(); self.assertEqual(before, self.files())
        self.env.assert_called_once_with(self.python)
        self.which.assert_called_once_with('sandbox-exec')

    def test_explicit_probe_reuses_native_checker_once(self):
        result = self.run_check(True)
        self.probe.assert_called_once_with(self.root, self.python)
        self.assertTrue(result['ok']); self.assertTrue(result['isolation_verified'])
        self.assertTrue(result['isolation_probe_attempted']); self.assertFalse(result['execution_authorized'])
        self.assertEqual(result['status'], 'ENVIRONMENT_AND_ISOLATION_CHECKS_PASSED')

    def test_missing_environment_blocks_without_subprocess_or_probe(self):
        self.python.unlink()
        result = self.run_check(True)
        self.assertFalse(result['ok']); self.env.assert_not_called(); self.process.assert_not_called()
        self.probe.assert_not_called()
        self.assertIn('bootstrap-tabular.sh', self.checks(result)['interpreter']['fix'])

    def test_nonexecutable_interpreter_is_reported(self):
        self.python.chmod(0o600)
        result = self.run_check(True)
        self.assertEqual(self.checks(result)['interpreter']['status'], 'FAIL')
        self.env.assert_not_called(); self.probe.assert_not_called()

    def test_wrong_pinned_versions_skip_imports_and_probe(self):
        self.env.side_effect = ValueError('Tabular environment differs from lock')
        result = self.run_check(True)
        self.assertFalse(result['ok']); self.assertEqual(self.checks(result)['locked_environment']['status'], 'FAIL')
        self.process.assert_not_called(); self.probe.assert_not_called()

    def test_native_environment_timeout_is_reported_not_retried(self):
        self.env.side_effect = subprocess.TimeoutExpired('synthetic runtime', 15)
        result = self.run_check(True)
        self.assertFalse(result['ok']); self.env.assert_called_once(); self.probe.assert_not_called()

    def test_import_error_blocks_even_with_matching_metadata(self):
        self.process.side_effect = subprocess.CalledProcessError(1, 'synthetic imports')
        result = self.run_check(True)
        self.assertFalse(result['ok']); self.assertEqual(self.checks(result)['scientific_imports']['status'], 'FAIL')
        self.probe.assert_not_called()

    def test_imports_run_in_fixed_venv_without_bytecode_or_user_path(self):
        self.run_check()
        args, kwargs = self.process.call_args
        self.assertEqual(args[0], [str(self.python), '-I', '-B', '-c', td._IMPORT_CHECK])
        self.assertEqual(kwargs['timeout'], 30)
        self.assertNotIn('fit(', td._IMPORT_CHECK); self.assertNotIn('predict(', td._IMPORT_CHECK)

    def test_wrong_environment_identity_is_rejected(self):
        self.process.return_value = json.dumps(dict(self.imports, prefix=str(self.root)))
        self.assertFalse(self.run_check(True)['ok']); self.probe.assert_not_called()

    def test_malformed_import_output_is_rejected(self):
        for output in ('not json', '[]', '{}', '{"imports_ok": false}'):
            self.process.return_value = output
            self.assertFalse(self.run_check(True)['ok'])
        self.probe.assert_not_called()

    def test_venv_executable_symlink_keeps_venv_path(self):
        executable = self.root/'base-python'; executable.write_text('synthetic'); executable.chmod(0o700)
        self.python.unlink(); self.python.symlink_to(executable)
        self.assertTrue(self.run_check(True)['ok'])
        self.env.assert_called_once_with(self.python)
        self.probe.assert_called_once_with(self.root, self.python)

    def test_unsupported_platforms_do_not_run_subprocess_or_probe(self):
        for os_name, arch in (('win32', 'AMD64'), ('darwin', 'x86_64'), ('linux', 'riscv64')):
            with patch.object(td.sys, 'platform', os_name), patch.object(td.platform, 'machine', return_value=arch):
                self.assertFalse(self.run_check(True)['ok'])
        self.env.assert_not_called(); self.process.assert_not_called(); self.probe.assert_not_called()

    def test_supported_linux_architectures_and_nonroot_check(self):
        for arch in ('x86_64', 'aarch64'):
            with patch.object(td.sys, 'platform', 'linux'), patch.object(td.platform, 'machine', return_value=arch), \
                 patch.object(td.os, 'geteuid', return_value=1000):
                result = self.run_check(True)
                self.assertTrue(result['ok']); self.assertEqual(self.checks(result)['ordinary_user']['status'], 'PASS')
        self.assertEqual(self.probe.call_count, 2)

    def test_root_linux_blocks_probe(self):
        with patch.object(td.sys, 'platform', 'linux'), patch.object(td.platform, 'machine', return_value='x86_64'), \
             patch.object(td.os, 'geteuid', return_value=0):
            result = self.run_check(True)
        self.assertFalse(result['ok']); self.assertEqual(self.checks(result)['ordinary_user']['status'], 'FAIL')
        self.probe.assert_not_called()

    def test_missing_isolation_tool_blocks_probe(self):
        self.which.return_value = None
        result = self.run_check(True)
        self.assertFalse(result['ok']); self.assertEqual(self.checks(result)['isolation_tool']['status'], 'FAIL')
        self.probe.assert_not_called()

    def test_probe_failure_is_final_for_this_diagnostic_call(self):
        self.probe.side_effect = ValueError('synthetic host denied namespace')
        result = self.run_check(True)
        self.assertFalse(result['ok']); self.assertTrue(result['isolation_probe_attempted'])
        self.assertFalse(result['isolation_verified']); self.probe.assert_called_once()
        self.assertEqual(result['status'], 'BLOCKED_ENVIRONMENT')

    def test_missing_false_or_nonboolean_probe_result_cannot_pass(self):
        for value in ({}, dict(self.probe_result, network_denied=False),
                      dict(self.probe_result, network_denied=1), dict(self.probe_result, extra=True), None):
            self.probe.return_value = value
            result = self.run_check(True)
            self.assertFalse(result['ok']); self.assertFalse(result['isolation_verified'])

    def test_multiple_failures_are_reported_together(self):
        self.python.unlink(); self.which.return_value = None
        result = self.run_check(True)
        self.assertEqual({c['name'] for c in result['checks'] if c['status'] == 'FAIL'},
                         {'interpreter', 'isolation_tool'})
        self.assertEqual(self.checks(result)['actual_isolation']['status'], 'SKIPPED')

    def test_cli_both_entrypoints_preserve_exit_status_and_explicit_probe(self):
        from research_harness.cli import main
        for command in ('tabular', 'airfoil'):
            for ok, probe in ((True, False), (False, True), (True, True)):
                report = {'ok': ok, 'execution_authorized': False}
                argv = ['research-harness', '--workspace', str(self.root/'unused'), command, 'doctor']
                if probe: argv.append('--probe-isolation')
                out = io.StringIO()
                with patch.object(sys, 'argv', argv), patch('sys.stdout', out), patch.object(td, 'doctor', return_value=report) as doctor:
                    self.assertEqual(main(), 0 if ok else 1)
                    self.assertEqual(json.loads(out.getvalue()), report)
                    doctor.assert_called_once_with(probe_isolation=probe)
        self.assertFalse((self.root/'unused').exists())

    def test_workflow_catalog_points_to_diagnostics_without_changing_scope(self):
        from research_harness.workflows import catalog
        for item in catalog()['workflows']:
            command = item['environment_check']
            if item['id'] == 'swinir-s-x2': self.assertEqual(command, 'doctor')
            elif item['id'].startswith('airfoil-'): self.assertEqual(command, 'airfoil doctor')
            else: self.assertEqual(command, 'tabular doctor')
            self.assertFalse(item['execution_authorized']); self.assertEqual(item['readiness'], 'NOT_CHECKED')


if __name__ == '__main__':
    unittest.main()
