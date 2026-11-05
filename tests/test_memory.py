"""Synthetic cross-checkout migration only: no images, model calls or science."""
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_harness.core import digest
from research_harness.memory import (MAX_BYTES, envelope, export_memory, import_memory,
                                     load_packet, merge, snapshot, status, validate)
from research_harness.portable import new_study
from research_harness.state_lock import research_lock
import test_portable as fixtures


class MemoryTests(unittest.TestCase):
    setUp = fixtures.PortableStudyTests.setUp

    def peer(self):
        peer = self.root/'peer'
        peer.mkdir()
        for name in ('templates', 'research_harness', 'assets', 'external'):
            shutil.copytree(self.root/name, peer/name)
        shutil.copyfile(self.root/'requirements-sr.txt', peer/'requirements-sr.txt')
        return peer

    def stopped(self, name='peer-a-study'):
        study = new_study(name, self.root)
        run = self.root/'runs'/name; run.mkdir(parents=True)
        source = 'import numpy as np\ndef enhance(lr,sr): return sr * np.float32(.99)\n'
        plan = {'hypothesis': 'Fixture distinct hypothesis', 'stop_route': 'Fixture operator stopped',
                'new_evidence': [{'source': 'https://arxiv.org/abs/1234.56789v2'}]}
        (run/'candidate.py').write_text(source)
        (run/'registered.json').write_text(json.dumps({'plan': plan, 'candidate_sha256': hashlib.sha256(source.encode()).hexdigest()}))
        (run/'result.json').write_text('{"status":"STOP","measurement_valid":true}')
        (run/'library.json').write_text(json.dumps([{'url': 'https://arxiv.org/abs/1299.12345',
            'full_text': 'PRIVATE_FULL_TEXT_NOT_FOR_EXCHANGE', 'abstract': 'PRIVATE_ABSTRACT_NOT_FOR_EXCHANGE'}]))
        (run/'agent-events.jsonl').write_text('PRIVATE_RAW_EVENT_NOT_FOR_EXCHANGE')
        return study, source

    def packet(self, path=None):
        path = path or self.root/'exchange.json'
        export_memory(self.root, path)
        return path

    def write_packet(self, value, path=None):
        path = path or self.root/'changed.json'
        path.write_text(json.dumps(envelope(value)))
        return path

    def test_stopped_study_transfers_code_papers_and_disjoint_new_reservation(self):
        peer = self.peer()
        first, source = self.stopped()
        packet = self.packet()
        before = status(peer)
        self.assertEqual(import_memory(peer, packet)['status'], 'IMPORTED')
        self.assertEqual(import_memory(peer, packet)['status'], 'ALREADY_IMPORTED')
        after = status(peer)
        self.assertEqual(after['scored_originals'], before['scored_originals']+12)
        with self.assertRaisesRegex(ValueError, 'already reserved in shared'):
            new_study('peer-a-study', peer)
        self.assertFalse((peer/'local_studies/peer-a-study').exists())
        second = new_study('peer-b-study', peer)
        a = json.loads((first/'policy.json').read_text()); b = json.loads((second/'policy.json').read_text())
        self.assertTrue(set(a['observation_ids']).isdisjoint(b['observation_ids']))
        self.assertIn('1234.56789', b['excluded_evidence_ids'])
        self.assertIn('1299.12345', b['excluded_evidence_ids'])
        self.assertFalse(b['stopped_route_compliance']['reuses_local_route_peer-a-study'])
        self.assertIn('Fixture operator stopped', (second/'TASK.md').read_text())
        catalog = json.loads((second/'intervention-catalog.json').read_text())
        self.assertTrue(any(x.get('source') == source for x in catalog))
        frozen = load_packet(second/'memory.json')
        self.assertEqual(frozen['payload']['studies'][0]['state'], 'STOP')
        lock = json.loads((second/'inputs.lock.json').read_text())['files']
        self.assertIn('local_studies/peer-b-study/memory.json', lock)

    def test_reserved_snapshot_can_upgrade_to_terminal_without_reclaiming(self):
        peer = self.peer()
        new_study('peer-a-study', self.root)
        initial = self.packet(self.root/'reserved.json')
        import_memory(peer, initial)
        self.assertEqual(status(peer)['reserved_unscored_originals'], 12)
        # Complete the same frozen reservation with a synthetic trusted result.
        run = self.root/'runs/peer-a-study'; run.mkdir(parents=True)
        (run/'result.json').write_text('{"status":"STOP","measurement_valid":true}')
        final = self.packet(self.root/'final.json')
        import_memory(peer, final)
        self.assertEqual(status(peer)['reserved_unscored_originals'], 0)
        self.assertEqual(status(peer)['scored_originals'], 24)
        # Reimporting the older reservation cannot downgrade the final decision.
        self.assertEqual(import_memory(peer, initial)['status'], 'ALREADY_IMPORTED')
        self.assertEqual(status(peer)['studies'][0]['state'], 'STOP')

    def test_rejected_and_incomplete_studies_keep_reservations_and_read_papers(self):
        for index, outcome in enumerate(({'status':'REJECTED','measurement_valid':None}, None)):
            name = 'closed-'+str(index); new_study(name, self.root)
            run = self.root/'runs'/name; run.mkdir(parents=True)
            if outcome: (run/'result.json').write_text(json.dumps(outcome))
            (run/'library.json').write_text('[{"url":"https://arxiv.org/abs/1234.56789v1"}]')
            (run/'agent-research.json').write_text('{"hypothesis":"fixture","stop_route":"fixture proposal","new_evidence":[]}')
            (run/'agent-candidate.py').write_text('def enhance(lr,sr): return sr')
        value = snapshot(self.root)
        self.assertEqual(len(value['reserved_ids']), 24)
        self.assertEqual(len(value['scored_ids']), 12)
        self.assertIn('1234.56789', value['paper_ids'])
        self.assertEqual({s['state'] for s in value['studies']}, {'REJECTED','INCOMPLETE'})
        proposal = next(x for x in value['routes'] if x['label'] == 'study:closed-0')
        self.assertEqual(proposal['disposition'], 'REJECTED_PROPOSAL')
        peer = self.peer(); import_memory(peer, self.packet())
        self.assertEqual(status(peer)['reserved_unscored_originals'], 24)

    def test_existing_operator_proposal_failure_keeps_scored_ids_without_scientific_stop(self):
        self.stopped()
        run=self.root/'runs/peer-a-study'
        registration=json.loads((run/'registered.json').read_text())
        evidence=self.root/'tasks/image_super_resolution/g6/evidence';evidence.mkdir(parents=True)
        (evidence/'registered.json').write_text(json.dumps({'candidate_sha256':registration['candidate_sha256']}))
        (evidence/'operator-audit.json').write_text('{"scientific_new_intervention_requirement_met":false}')
        value=snapshot(self.root)
        self.assertEqual(value['studies'][0]['state'],'PROPOSAL_FAILURE')
        self.assertEqual(len(value['scored_ids']),24)
        route=next(x for x in value['routes'] if x['label']=='study:peer-a-study')
        self.assertEqual(route['disposition'],'REJECTED_PROPOSAL')
        self.assertEqual(json.loads((run/'result.json').read_text())['status'],'STOP')

    def test_conflicting_identity_terminal_decision_or_overlap_has_no_partial_import(self):
        peer = self.peer(); self.stopped(); packet = self.packet(); import_memory(peer, packet)
        original = load_packet(packet)['payload']; store = peer/'.research-memory/packets'
        before = {p.name:p.read_bytes() for p in store.glob('*.json')}
        changes = ({'policy_sha256':'a'*64}, {'state':'CONTINUE'}, {'id':'independent-study'})
        for index, change in enumerate(changes):
            value = copy.deepcopy(original); value['studies'][0].update(change)
            bad = self.write_packet(value, self.root/f'conflict-{index}.json')
            with self.assertRaisesRegex(ValueError, 'Conflicting|Overlapping'):
                import_memory(peer, bad)
            self.assertEqual({p.name:p.read_bytes() for p in store.glob('*.json')}, before)

    def test_integrity_closed_schema_and_reclamation_fail_before_store_creation(self):
        peer = self.peer(); self.stopped(); packet = self.packet()
        base = json.loads(packet.read_text())
        variants = []
        bad = copy.deepcopy(base); bad['payload']['paper_ids'].append('1299.12346'); variants.append(bad)
        bad = copy.deepcopy(base); bad['payload']['schema_version']=2; bad['sha256']=digest(bad['payload']); variants.append(bad)
        bad = copy.deepcopy(base); bad['payload']['external_path']='/etc/passwd'; bad['sha256']=digest(bad['payload']); variants.append(bad)
        bad = copy.deepcopy(base); bad['payload']['scored_ids']=[]; bad['sha256']=digest(bad['payload']); variants.append(bad)
        for index, value in enumerate(variants):
            path = self.root/f'invalid-{index}.json'; path.write_text(json.dumps(value))
            with self.assertRaises(ValueError): import_memory(peer, path)
            self.assertFalse((peer/'.research-memory').exists())

    def test_source_hash_tamper_and_stored_packet_corruption_fail_closed(self):
        peer = self.peer(); self.stopped(); packet = self.packet()
        value = json.loads(packet.read_text())
        value['payload']['routes'][0]['source'] += '\n# Changed'
        value['sha256'] = digest(value['payload'])
        broken = self.root/'bad-source.json'; broken.write_text(json.dumps(value))
        with self.assertRaises(ValueError): import_memory(peer, broken)
        import_memory(peer, packet)
        stored = next((peer/'.research-memory/packets').glob('*.json')); stored.write_text('{}')
        with self.assertRaises(ValueError): new_study('must-not-reserve', peer)
        self.assertFalse((peer/'local_studies/must-not-reserve').exists())

    def test_exchange_omits_papers_events_credentials_and_does_not_execute_source(self):
        self.stopped()
        packet = self.packet(); text = packet.read_text()
        for marker in ('PRIVATE_FULL_TEXT_NOT_FOR_EXCHANGE','PRIVATE_ABSTRACT_NOT_FOR_EXCHANGE','PRIVATE_RAW_EVENT_NOT_FOR_EXCHANGE'):
            self.assertNotIn(marker, text)
        payload = load_packet(packet)['payload']
        from research_harness.memory import _route
        marker = self.root/'SHOULD_NOT_EXIST'
        payload['routes'].append(_route('malicious-text-fixture','Trusted text is never executed','REJECTED_PROPOSAL',
            f'from pathlib import Path\nPath({str(marker)!r}).write_text("bad")\n'))
        peer = self.peer(); import_memory(peer, self.write_packet(payload))
        new_study('safe-preparation', peer)
        self.assertFalse(marker.exists())

    def test_export_never_overwrites_and_packet_reader_rejects_links_duplicates_and_oversize(self):
        packet = self.packet(); original = packet.read_bytes()
        with self.assertRaises(FileExistsError): export_memory(self.root, packet)
        self.assertEqual(packet.read_bytes(), original)
        link = self.root/'link.json'; link.symlink_to(packet)
        with self.assertRaises(ValueError): load_packet(link)
        duplicate = self.root/'duplicate.json'; duplicate.write_text('{"payload":{},"payload":{},"sha256":"a"}')
        with self.assertRaisesRegex(ValueError, 'Duplicate'): load_packet(duplicate)
        huge = self.root/'huge.json'; huge.write_bytes(b' '*(MAX_BYTES+1))
        with self.assertRaisesRegex(ValueError, '4 MiB'): load_packet(huge)

    def test_cli_migration_without_scientific_dependencies_or_login(self):
        peer = self.peer(); self.stopped()
        out = self.root/'cli-memory.json'
        def command(root, *args):
            result = subprocess.run([sys.executable,'-m','research_harness','memory','--root',str(root),*args],
                                    capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            return json.loads(result.stdout)
        self.assertEqual(command(self.root,'export','--out',str(out))['status'],'EXPORTED')
        self.assertEqual(command(peer,'import',str(out))['status'],'IMPORTED')
        self.assertEqual(command(peer,'status')['scored_originals'],24)

    def test_live_lock_contention_blocks_research_import_and_reservation_then_releases(self):
        packet = self.packet()
        code = ('import sys\nfrom research_harness.state_lock import research_lock\n'
                'with research_lock(sys.argv[1]):\n print("LOCKED",flush=True)\n sys.stdin.read()\n')
        process = subprocess.Popen([sys.executable,'-c',code,str(self.root)],stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        self.assertEqual(process.stdout.readline().strip(),'LOCKED')
        try:
            with self.assertRaisesRegex(ValueError,'checkout lock'): new_study('blocked', self.root)
            with self.assertRaisesRegex(ValueError,'checkout lock'): import_memory(self.root, packet)
            with patch('research_harness.onboarding.ROOT',self.root), patch('research_harness.doctor.doctor') as doctor:
                from research_harness.onboarding import research
                with self.assertRaisesRegex(ValueError,'checkout lock'): research('blocked')
                doctor.assert_not_called()
            self.assertFalse((self.root/'local_studies/blocked').exists())
        finally:
            process.kill(); process.communicate(timeout=10)
        # A stale lock file is harmless; killing its process releases the OS lock.
        new_study('after-lock-release', self.root)
        self.assertTrue((self.root/'local_studies/after-lock-release/policy.json').exists())
