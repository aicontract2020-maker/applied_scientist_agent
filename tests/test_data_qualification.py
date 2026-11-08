"""Synthetic metadata only: no real data qualification, models or experiments."""
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

from research_harness import data_qualification as dq
from research_harness.core import digest, validate_protocol


class DataQualificationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.draft = self.root / 'draft.json'
        self.packet = self.root / 'packet.json'
        self.receipt = self.root / 'packet.json.decision.json'
        dq.template(self.draft)
        self.content = json.loads(self.draft.read_text())
        self.content.update(id='synthetic-only', task='software-check', intended_use='Synthetic software verification only',
                            dataset={'id': 'synthetic', 'version': '1', 'source': 'generated fixture'})
        self.note = b'Synthetic metadata. Not real permission, independent data, or scientific evidence.\n'
        (self.root / 'note.txt').write_bytes(self.note)
        self.content['evidence'] = {'note': {'source': 'synthetic fixture', 'locator': 'entire note',
                                           'path': 'note.txt', 'sha256': hashlib.sha256(self.note).hexdigest()}}
        for item in self.content['criteria'].values():
            item.update(state='supported', rationale='Synthetic assertion for software test only', evidence=['note'])

    def prepare(self):
        self.draft.write_text(json.dumps(self.content))
        return dq.prepare(self.draft, self.packet)

    def decision(self, decision='accept', sha=None):
        return dq.decide(self.packet, sha or dq.inspect(self.packet)['sha256'], 'SYNTHETIC_REVIEWER',
                         decision, 'Software test only')

    def test_every_condition_blocks_acceptance_when_unresolved(self):
        for key in dq.CRITERIA:
            with self.subTest(key=key):
                self.content['criteria'][key]['state'] = 'unresolved'
                self.assertEqual(self.prepare()['status'], 'BLOCKED_DATA_QUALIFICATION')
                with self.assertRaisesRegex(ValueError, 'Cannot accept'): self.decision()
                self.assertFalse(self.receipt.exists())
                self.packet.unlink()
                self.content['criteria'][key]['state'] = 'supported'

    def test_incompatibility_dominates_unknown_and_can_never_be_accepted(self):
        self.content['criteria']['permission']['state'] = 'incompatible'
        self.content['criteria']['target']['state'] = 'unresolved'
        self.assertEqual(self.prepare()['status'], 'STOP_DATA_QUALIFICATION')
        with self.assertRaises(ValueError): self.decision()
        self.assertEqual(self.decision('reject')['status'], 'STOP_DATA_QUALIFICATION')

    def test_supported_is_pending_human_review_and_acceptance_never_allows_execution(self):
        self.assertEqual(self.prepare()['status'], 'AWAITING_DATA_REVIEW')
        result = self.decision()
        self.assertEqual(result['status'], 'QUALIFIED_FOR_PROTOCOL_DESIGN')
        self.assertFalse(result['execution_authorized'])
        self.assertEqual(result['authenticity'], 'UNVERIFIED')
        for path in (self.packet, self.receipt):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError): validate_protocol(json.loads(self.packet.read_text()))
        with self.assertRaises(FileExistsError): self.decision()

    def test_human_rejection_closes_supported_packet(self):
        self.prepare()
        self.assertEqual(self.decision('reject')['status'], 'STOP_DATA_QUALIFICATION')
        with self.assertRaises(FileExistsError): self.decision('accept')
        self.assertEqual(dq.inspect(self.packet)['status'], 'STOP_DATA_QUALIFICATION')

    def test_exact_hash_and_binding_prevent_cross_packet_decisions(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, 'exact frozen'): self.decision(sha='0' * 64)
        self.decision()
        self.packet.unlink()
        self.content['intended_use'] = 'Different intended use'
        self.prepare()
        with self.assertRaisesRegex(ValueError, 'different frozen'): dq.inspect(self.packet)

    def test_offline_copy_remains_inspectable_and_read_only(self):
        self.prepare()
        before = self.packet.read_bytes()
        self.draft.unlink()
        (self.root / 'note.txt').unlink()
        with patch('socket.socket', side_effect=AssertionError('network forbidden')), \
             patch('subprocess.Popen', side_effect=AssertionError('process forbidden')):
            self.assertEqual(dq.inspect(self.packet)['status'], 'AWAITING_DATA_REVIEW')
        self.assertEqual(self.packet.read_bytes(), before)
        self.assertEqual({p.name for p in self.root.iterdir()}, {'packet.json'})

    def test_source_and_packet_tampering_fail_without_output(self):
        (self.root / 'note.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'declared checksum'): self.prepare()
        self.assertFalse(self.packet.exists())
        (self.root / 'note.txt').write_bytes(self.note)
        self.prepare()
        packet = json.loads(self.packet.read_text())
        packet['content']['evidence']['note']['content'] += 'changed'
        self.packet.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, 'Frozen content'): dq.inspect(self.packet)
        packet['sha256'] = digest(packet['content'])
        self.packet.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, 'Evidence checksum'): dq.inspect(self.packet)

    def test_decision_tampering_or_fake_execution_scope_rejected(self):
        self.prepare(); self.decision()
        receipt = json.loads(self.receipt.read_text())
        receipt['content']['scope'] = 'execute'
        self.receipt.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'checksum'): dq.inspect(self.packet)
        receipt['sha256'] = digest(receipt['content'])
        self.receipt.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'scope'): dq.inspect(self.packet)

    def test_strict_schema_and_evidence_required(self):
        base = copy.deepcopy(self.content)
        mutations = [lambda c: c.update(command='echo must-not-execute'),
                     lambda c: c.update(version=True),
                     lambda c: c['criteria'].pop('permission'),
                     lambda c: c['criteria']['target'].update(state='waived'),
                     lambda c: c['criteria']['target'].update(rationale=' '),
                     lambda c: c['criteria']['target'].update(evidence=[]),
                     lambda c: c['criteria']['target'].update(evidence=['absent']),
                     lambda c: c['criteria']['target'].update(evidence=['note', 'note']),
                     lambda c: c['evidence'].update(unused=copy.deepcopy(c['evidence']['note']))]
        for change in mutations:
            self.content = copy.deepcopy(base); change(self.content)
            with self.assertRaises(ValueError): self.prepare()
            self.assertFalse(self.packet.exists())

    def test_traversal_symlinks_and_special_files_rejected(self):
        for path in ('../note.txt', '/etc/passwd', './note.txt', 'x//note.txt', 'x\\note.txt'):
            self.content['evidence']['note']['path'] = path
            with self.assertRaisesRegex(ValueError, 'relative path'): self.prepare()
        self.content['evidence']['note']['path'] = 'link.txt'
        (self.root / 'link.txt').symlink_to(self.root / 'note.txt')
        with self.assertRaisesRegex(ValueError, 'Symbolic'): self.prepare()
        (self.root / 'alias').symlink_to(self.root, target_is_directory=True)
        self.content['evidence']['note']['path'] = 'alias/note.txt'
        with self.assertRaisesRegex(ValueError, 'Symbolic'): self.prepare()
        if hasattr(os, 'mkfifo'):
            os.mkfifo(self.root / 'fifo')
            self.content['evidence']['note']['path'] = 'fifo'
            with self.assertRaisesRegex(ValueError, 'regular'): self.prepare()

    def test_limits_non_utf8_and_duplicate_keys_rejected(self):
        (self.root / 'note.txt').write_bytes(b'x' * (dq.FILE_LIMIT + 1))
        with self.assertRaisesRegex(ValueError, 'size limit'): self.prepare()
        (self.root / 'note.txt').write_bytes(b'\xff')
        self.content['evidence']['note']['sha256'] = hashlib.sha256(b'\xff').hexdigest()
        with self.assertRaisesRegex(ValueError, 'UTF-8'): self.prepare()
        for text in ('{"kind":1,"kind":2}', '{"value":NaN}'):
            self.draft.write_text(text)
            with self.assertRaises(ValueError): dq.prepare(self.draft, self.packet)
        self.assertFalse(self.packet.exists())

    def test_template_is_unfilled_and_cannot_overwrite(self):
        path = self.root / 'new-template.json'
        self.assertFalse(dq.template(path)['execution_authorized'])
        with self.assertRaises(ValueError): dq.prepare(path, self.packet)
        with self.assertRaises(FileExistsError): dq.template(path)
        self.prepare()
        before = self.packet.read_bytes()
        with self.assertRaises(FileExistsError): self.prepare()
        self.assertEqual(before, self.packet.read_bytes())

    def test_demo_has_only_synthetic_qualification_states(self):
        from examples.data_qualification.workflow import demonstrate
        output = self.root / 'demo'
        result = demonstrate(output)
        self.assertTrue(result['synthetic_only'])
        self.assertFalse(result['execution_authorized'])
        self.assertEqual(result['statuses'], {
            'missing': 'BLOCKED_DATA_QUALIFICATION', 'incompatible': 'STOP_DATA_QUALIFICATION',
            'supported': 'AWAITING_DATA_REVIEW', 'synthetic_acceptance': 'QUALIFIED_FOR_PROTOCOL_DESIGN'})
        with self.assertRaises(FileExistsError): demonstrate(output)

    def test_total_size_limit_and_unresolved_forged_acceptance(self):
        # Individually valid records may still exceed the aggregate bound.
        text = 'x' * dq.FILE_LIMIT
        for i in range(5):
            name = 'large-' + str(i)
            (self.root / (name + '.txt')).write_text(text)
            self.content['evidence'][name] = {'path': name + '.txt', 'source': 'synthetic',
                                            'locator': 'whole file', 'sha256': hashlib.sha256(text.encode()).hexdigest()}
            self.content['criteria']['target']['evidence'].append(name)
        with self.assertRaisesRegex(ValueError, 'total size'): self.prepare()
        self.assertFalse(self.packet.exists())
        self.content['evidence'] = {'note': self.content['evidence']['note']}
        self.content['criteria']['target'].update(evidence=['note'], state='unresolved')
        self.prepare()
        self.decision('reject')
        receipt = json.loads(self.receipt.read_text())
        receipt['content']['decision'] = 'accept'
        receipt['sha256'] = digest(receipt['content'])
        self.receipt.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'Cannot accept'): dq.inspect(self.packet)

    def test_cli_pending_accept_inspect_reject_and_no_workspace(self):
        repo = str(Path(__file__).resolve().parents[1])
        env = {**os.environ, 'PYTHONPATH': repo}

        def cli(*args):
            return subprocess.run([sys.executable, '-m', 'research_harness', 'data-review', *args],
                                  cwd=self.root, env=env, capture_output=True, text=True, timeout=10)

        self.draft.write_text(json.dumps(self.content))
        prepared = cli('prepare', str(self.draft), '--out', str(self.packet))
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        sha = json.loads(prepared.stdout)['sha256']
        accepted = cli('decide', str(self.packet), '--sha256', sha, '--reviewer', 'SYNTHETIC',
                       '--decision', 'accept', '--reason', 'software only')
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        inspected = cli('inspect', str(self.packet))
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertEqual(json.loads(inspected.stdout)['status'], 'QUALIFIED_FOR_PROTOCOL_DESIGN')
        self.assertFalse(json.loads(inspected.stdout)['execution_authorized'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        self.assertNotIn('Synthetic assertion', inspected.stdout)
        self.assertFalse((self.root / 'runs').exists())
        invalid = cli('inspect', str(self.draft))
        self.assertEqual(invalid.returncode, 1)
