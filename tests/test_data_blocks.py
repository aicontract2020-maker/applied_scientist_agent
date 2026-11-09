"""Software-only data pause tests. No model, dataset download or scientific run."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from examples.data_qualification.baseline import qualification, USE
from research_harness import data_blocks as db, data_admission as admission
from research_harness import tabular_baseline as tb, airfoil_baseline as ab
from research_harness import tabular_trial as tt, airfoil_trial as at
from research_harness.core import digest
from research_harness.state_lock import research_lock


class DataBlockTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def packet(self, name='qualification', adapter=tb.ADAPTER, source=tb.FIXTURE):
        snapshot = qualification(self.root/name, adapter, source)
        return self.root/name/'packet.json', snapshot['packet']['sha256']

    def pause(self, path, sha, root=None):
        return db.block(path, sha, 'SOFTWARE_REVIEWER', 'Synthetic data-use pause', root or self.root)

    def baseline(self, module):
        from test_data_admission import DataAdmissionTests
        fixture = DataAdmissionTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        folder, prepared, snapshot = fixture.build(module)
        module.approve(folder, prepared['sha256'], 'SOFTWARE_REVIEWER', root=fixture.root)
        return fixture.root, folder, prepared, snapshot, folder.parent/'qualification/packet.json'

    def candidate(self, module):
        from test_candidate_admission import CandidateAdmissionTests
        fixture = CandidateAdmissionTests(); self.addCleanup(fixture.doCleanups)
        f = fixture.build(module); fixture.approve(f)
        return fixture, f

    def test_missing_state_is_read_only_and_not_permission(self):
        target = self.root/'absent-checkout'
        result = db.status(target)
        self.assertEqual(result['content']['records'], [])
        self.assertFalse(result['execution_authorized'])
        db.assert_allowed({'id': 'x', 'version': '1', 'source': 'fixture'}, target)
        self.assertFalse(target.exists())

    def test_block_is_exact_hash_and_idempotent_without_changing_qualification(self):
        path, sha = self.packet()
        before = {p.name: p.read_bytes() for p in path.parent.iterdir() if p.is_file()}
        with self.assertRaisesRegex(ValueError, 'exact qualification hash'):
            self.pause(path, '0'*64)
        self.assertFalse((self.root/'.research-memory').exists())
        self.assertTrue(self.pause(path, sha)['added'])
        state = (self.root/'.research-memory/data-blocks.json').read_bytes()
        self.assertFalse(self.pause(path, sha)['added'])
        self.assertEqual(state, (self.root/'.research-memory/data-blocks.json').read_bytes())
        self.assertEqual(before, {p.name: p.read_bytes() for p in path.parent.iterdir() if p.is_file()})
        self.assertFalse(db.status(self.root)['execution_authorized'])

    def test_dataset_block_survives_new_qualification_use_and_adapter(self):
        path, sha = self.packet(); self.pause(path, sha)
        for adapter in admission.ADAPTERS:
            with self.subTest(adapter=adapter):
                replacement = qualification(self.root/adapter, adapter, tb.FIXTURE)
                # Altering use/acceptance is not a dataset identity change.
                new = copy.deepcopy(replacement)
                p, d = new['packet'], new['decision']
                p['content']['intended_use'] = 'new scope'; p['sha256'] = digest(p['content'])
                d['content']['packet_sha256'] = p['sha256']; d['sha256'] = digest(d['content'])
                admission.validate_snapshot(new, admission.context(adapter, tb.FIXTURE, 'new scope'))
                with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'):
                    admission.accepted_snapshot(self.root/adapter/'packet.json', adapter, tb.FIXTURE, USE, root=self.root)
        with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'):
            admission.trial_snapshot({'content': {'source': tb.FIXTURE}}, tt.ADAPTER, tb.FIXTURE, None, None, root=self.root)
        identity = admission.context(tb.ADAPTER, tb.FIXTURE, USE)['dataset']
        for key in identity:
            other = {**identity, key: identity[key]+'-other'}
            db.assert_allowed(other, self.root)  # Exact identity only; no claim of alias detection.

    def test_baseline_block_before_raw_data_read_and_output(self):
        for module, parser in ((tb, 'parse_abalone'), (ab, 'parse')):
            path, sha = self.packet(module.ADAPTER, module.ADAPTER, module.SOURCE)
            self.pause(path, sha)
            with patch.object(module, parser) as parse:
                with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'):
                    module.prepare('not-read', self.root/'no-output', path, USE, root=self.root)
                parse.assert_not_called()
            self.assertFalse((self.root/'no-output').exists())

    def test_both_baselines_old_approval_cannot_override_pause(self):
        for module in (tb, ab):
            root, folder, prepared, snapshot, path = self.baseline(module)
            before = {str(p): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
            self.pause(path, snapshot['packet']['sha256'], root)
            for operation in ('preflight', 'execute'):
                with patch.object(module, 'environment') as env, patch('research_harness.tabular_sandbox.isolated_worker') as worker:
                    with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'):
                        getattr(module, operation)(folder, root=root)
                    env.assert_not_called(); worker.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'):
                module.approve(folder, prepared['sha256'], 'OTHER', root=root)
            module.load_review(folder, **({'current': False} if module is ab else {'require_current_sources': False}))
            self.assertEqual(before, {str(p): p.read_bytes() for p in folder.rglob('*') if p.is_file()})
            self.assertFalse((root/'.research-memory/airfoil-baseline').exists())

    def test_both_candidates_pause_preserves_approval_and_historical_read(self):
        for module in (tt, at):
            helper, f = self.candidate(module)
            before = {str(p): p.read_bytes() for p in f.folder.rglob('*') if p.is_file()}
            self.pause(f.root/'candidate-qualification/packet.json', f.snapshot['packet']['sha256'], f.root)
            for operation in ('preflight', 'execute'):
                with patch.object(module, 'environment') as env, patch('research_harness.tabular_sandbox.isolated_worker') as worker:
                    with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'): helper.invoke(f, operation)
                    env.assert_not_called(); worker.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'): helper.approve(f)
            module.load_trial(f.folder, current=False)
            self.assertEqual(before, {str(p): p.read_bytes() for p in f.folder.rglob('*') if p.is_file()})
            self.assertFalse((f.root/'.research-memory/tabular-trial').exists())
            self.assertFalse((f.root/'.research-memory/airfoil-trial').exists())

    def test_four_execution_paths_recheck_pause_after_probe(self):
        for module in (tb, ab, tt, at):
            if module in (tb, ab):
                root, folder, _, snapshot, path = self.baseline(module)
                execute = lambda: module.execute(folder, root=root)
            else:
                helper, f = self.candidate(module)
                root, folder, snapshot = f.root, f.folder, f.snapshot
                execute = lambda: helper.invoke(f, 'execute')
            row = {'dataset': snapshot['packet']['content']['dataset'], 'qualification_sha256': snapshot['packet']['sha256'],
                   'reviewer': 'SOFTWARE', 'reason': 'Simulated out-of-band state change during probe'}
            def probe(*args):
                # A normal add/import would contend on the existing checkout lock.
                db._save(root, [row]); return {}
            with patch.object(module, 'environment', return_value={}), \
                 patch('research_harness.tabular_sandbox.isolation_probe', side_effect=probe), \
                 patch('research_harness.tabular_sandbox.isolated_worker') as worker:
                with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'): execute()
                worker.assert_not_called()
            self.assertFalse((folder/'trial-run').exists()); self.assertFalse((folder/'run').exists())
            for history in ('tabular-trial', 'airfoil-trial', 'airfoil-baseline'):
                self.assertFalse((root/'.research-memory'/history).exists())

    def test_proposal_and_candidate_preparation_block_without_actor_or_output(self):
        from research_harness import tabular_workflow as workflow, tabular_proposer as proposer
        for module in (tt, at):
            _, f = self.candidate(module)
            path = f.root/'candidate-qualification/packet.json'
            self.pause(path, f.snapshot['packet']['sha256'], f.root)
            args = (f.base, f.proposal, f.root/'no-output') + ((f.library,) if module is tt else ())
            with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'):
                module.prepare(*args, root=f.root, data_review=path, intended_use=USE)
            self.assertFalse((f.root/'no-output').exists())
            if module is at: continue
            with patch.object(proposer, 'propose') as actor:
                with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'):
                    workflow.research('blocked', 'propose', f.base, root=f.root, data_review=path, intended_use=USE)
                actor.assert_not_called()
            with patch.object(proposer, 'bounded_process') as actor, patch('research_harness.doctor.isolation_probe') as probe:
                with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'):
                    proposer.propose(f.base, f.root/'no-output', root=f.root, data_review=path, intended_use=USE)
                actor.assert_not_called(); probe.assert_not_called()
            self.assertFalse((f.root/'runs').exists()); self.assertFalse((f.root/'no-output').exists())
            self.assertFalse((f.root/'.research-memory/tabular-proposer').exists())

    def test_proposer_rechecks_after_isolation_probe(self):
        from research_harness import tabular_proposer as proposer
        _, f = self.candidate(tt)
        path = f.root/'candidate-qualification/packet.json'
        row = {'dataset': f.snapshot['packet']['content']['dataset'], 'qualification_sha256': f.snapshot['packet']['sha256'],
               'reviewer': 'SOFTWARE', 'reason': 'Synthetic probe-time pause'}
        def probe(**kwargs): db._save(f.root, [row]); return {}
        with patch('research_harness.doctor.isolation_probe', side_effect=probe), patch.object(proposer, 'bounded_process') as actor:
            with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'):
                proposer.propose(f.base, f.root/'no-actor', root=f.root, data_review=path, intended_use=USE)
            actor.assert_not_called()
        self.assertFalse((f.root/'no-actor').exists())
        self.assertFalse((f.root/'.research-memory/tabular-proposer').exists())

    def test_portable_union_cannot_erase_records_or_restore_research_memory(self):
        path, sha = self.packet(); self.pause(path, sha)
        packet = self.root/'handoff.json'; db.export(packet, self.root)
        target = self.root/'receiver'; target.mkdir()
        stop = target/'.research-memory/tabular-trial/consumed/reservation.json'
        stop.parent.mkdir(parents=True); stop.write_text('retained STOP fixture')
        other, other_sha = self.packet('other', ab.ADAPTER, ab.FIXTURE)
        self.pause(other, other_sha, target)
        self.assertEqual(db.import_blocks(packet, target)['added'], 1)
        before = (target/'.research-memory/data-blocks.json').read_bytes()
        self.assertEqual(db.import_blocks(packet, target)['added'], 0)
        empty = self.root/'empty.json'; empty.write_text(json.dumps(db._envelope([])))
        self.assertEqual(db.import_blocks(empty, target)['added'], 0)
        self.assertEqual(before, (target/'.research-memory/data-blocks.json').read_bytes())
        self.assertEqual(stop.read_text(), 'retained STOP fixture')
        for source in (tb.FIXTURE, ab.FIXTURE):
            with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'):
                admission.assert_source_allowed(source, target)
        with self.assertRaises(FileExistsError): db.export(packet, self.root)

    def test_corrupt_import_never_partially_merges(self):
        path, sha = self.packet(); self.pause(path, sha)
        original = (self.root/'.research-memory/data-blocks.json').read_bytes()
        records = db.status(self.root)['content']['records']
        mutations = [lambda p: p.update(sha256='0'*64),
                     lambda p: p['content'].update(version=True),
                     lambda p: p['content']['records'][0].update(unblock=True),
                     lambda p: p['content']['records'][0].update(reviewer=''),
                     lambda p: p['content']['records'].append(copy.deepcopy(p['content']['records'][0]))]
        for mutate in mutations:
            packet = db._envelope(copy.deepcopy(records)); mutate(packet)
            packet['sha256'] = digest(packet['content']) if packet['sha256'] != '0'*64 else packet['sha256']
            incoming = self.root/'invalid.json'; incoming.write_text(json.dumps(packet))
            with self.assertRaises(ValueError): db.import_blocks(incoming, self.root)
            self.assertEqual(original, (self.root/'.research-memory/data-blocks.json').read_bytes())

    def test_corrupt_state_fails_closed_and_historical_audit_is_independent(self):
        root, folder, _, _, _ = self.baseline(tb)
        state = root/'.research-memory/data-blocks.json'; state.parent.mkdir(exist_ok=True)
        for raw in ('{}', '{"content":{},"content":{}}', 'NaN', '[]'):
            state.write_text(raw)
            with self.assertRaises(ValueError): db.status(root)
            with patch.object(tb, 'environment') as env:
                with self.assertRaises(ValueError): tb.execute(folder, root=root)
                env.assert_not_called()
            tb.load_review(folder, require_current_sources=False)

    def test_symlinks_and_nonregular_state_are_rejected(self):
        state = self.root/'.research-memory/data-blocks.json'; state.parent.mkdir()
        state.symlink_to(self.root/'missing')
        with self.assertRaises(ValueError): db.status(self.root)
        state.unlink(); state.mkdir()
        with self.assertRaises((ValueError, OSError)): db.status(self.root)
        state.rmdir(); os.mkfifo(state)
        with self.assertRaises(ValueError): db.status(self.root)
        state.unlink(); state.parent.rmdir()
        external = self.root/'external'; external.mkdir(); state.parent.symlink_to(external, target_is_directory=True)
        with self.assertRaises(ValueError): db.status(self.root)

    def test_lock_conflict_cannot_write_pause_or_import(self):
        path, sha = self.packet(); exported = self.root/'empty.json'
        exported.write_text(json.dumps(db._envelope([])))
        with research_lock(self.root):
            with self.assertRaisesRegex(ValueError, 'lock'): self.pause(path, sha)
            with self.assertRaisesRegex(ValueError, 'lock'): db.import_blocks(exported, self.root)
        self.assertFalse((self.root/'.research-memory').exists())

    def test_cli_roundtrip_and_safe_defaults(self):
        path, sha = self.packet(); repo = str(Path(__file__).resolve().parents[1])
        def cli(*args):
            return subprocess.run([sys.executable, '-m', 'research_harness', 'data-blocks', '--root', str(self.root), *args],
                                  cwd=self.root, env={**os.environ, 'PYTHONPATH': repo}, capture_output=True, text=True, timeout=15)
        initial = cli('status'); self.assertEqual(initial.returncode, 0, initial.stderr)
        self.assertFalse((self.root/'.cache').exists()); self.assertFalse((self.root/'.research-memory').exists())
        add = cli('add', str(path), '--sha256', sha, '--reviewer', 'SOFTWARE', '--reason', 'Synthetic pause')
        self.assertEqual(add.returncode, 0, add.stderr); self.assertFalse(json.loads(add.stdout)['execution_authorized'])
        out = self.root/'export.json'
        self.assertEqual(cli('export', '--out', str(out)).returncode, 0)
        self.assertEqual(json.loads(cli('import', str(out)).stdout)['added'], 0)
        self.assertEqual(cli('unblock').returncode, 2)

    def test_checkout_alias_uses_same_state_without_following_memory_links(self):
        path, sha = self.packet(); self.pause(path, sha)
        alias = self.root/'checkout-alias'; alias.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(db.status(alias), db.status(self.root))
        with self.assertRaisesRegex(ValueError, 'DATA_USE_BLOCKED'):
            admission.assert_source_allowed(tb.FIXTURE, alias)
        not_directory = self.root/'file'; not_directory.write_text('not a checkout')
        with self.assertRaises(ValueError): db.status(not_directory)

    def test_record_and_byte_limits_preserve_existing_state(self):
        path, sha = self.packet(); self.pause(path, sha)
        state = self.root/'.research-memory/data-blocks.json'; original = state.read_bytes()
        row = db.status(self.root)['content']['records'][0]
        records = [{**row, 'reason': str(i)} for i in range(db.LIMIT+1)]
        incoming = self.root/'over-limit.json'; incoming.write_text(json.dumps(db._envelope(records)))
        with self.assertRaisesRegex(ValueError, 'Too many'): db.import_blocks(incoming, self.root)
        # Each incoming packet fits individually, but a combined snapshot must also fit.
        db._save(self.root, records[:db.LIMIT])
        full = state.read_bytes()
        incoming.write_text(json.dumps(db._envelope([records[-1]])))
        with self.assertRaisesRegex(ValueError, 'Too many'): db.import_blocks(incoming, self.root)
        self.assertEqual(full, state.read_bytes())
        state.write_bytes(original)
        big = [{**row, 'reason': str(i)+'x'*15990, 'reviewer': 'y'*16000} for i in range(140)]
        with self.assertRaisesRegex(ValueError, 'size limit'): db._save(self.root, big)
        self.assertEqual(original, state.read_bytes())
        incoming.write_bytes(b'x'*(4*1024*1024+1))
        with self.assertRaisesRegex(ValueError, 'size limit'): db.import_blocks(incoming, self.root)
        self.assertEqual(original, state.read_bytes())

    def test_failed_atomic_replace_keeps_prior_state_and_cleans_temp_file(self):
        path, sha = self.packet(); self.pause(path, sha)
        state = self.root/'.research-memory/data-blocks.json'; original = state.read_bytes()
        with patch.object(db.os, 'replace', side_effect=OSError('synthetic filesystem failure')):
            with self.assertRaisesRegex(OSError, 'filesystem failure'):
                db.block(path, sha, 'SECOND_REVIEWER', 'Another synthetic reason', self.root)
        self.assertEqual(original, state.read_bytes())
        self.assertEqual(list(state.parent.iterdir()), [state])
