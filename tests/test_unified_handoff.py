"""Synthetic state transfer only; no research process or scientific measurement."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_harness import tabular_handoff as th, tabular_memory as tm, data_blocks as db
from research_harness import data_admission as admission, tabular_baseline as tb
from research_harness.core import digest
from research_harness.state_lock import research_lock
from research_harness.tabular_features import review


class UnifiedHandoffTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve(); self.sender=self.root/'sender'; self.receiver=self.root/'receiver'
        self.sender.mkdir(); self.receiver.mkdir()
        source='def augment(row):\n    return [row[3]*row[4]]\n'
        self.record={'scope':digest('scope'), 'trial_sha256':digest('trial'),
                     'candidate_sha256':digest(review(source)['canonical']), 'family_sha256':tm.family_hash(source),
                     'data_keys':[digest({'task':'tabular-regression','features':['synthetic']})], 'route':{'source':source,'mechanism':'synthetic fixture'},
                     'state':'STOP','result_sha256':digest('synthetic-result')}
        self.block={'dataset':admission.context(tb.ADAPTER,tb.FIXTURE,'synthetic')['dataset'],
                    'qualification_sha256':digest('synthetic-qualification'),'reviewer':'SOFTWARE',
                    'reason':'Synthetic pause only'}

    def packet(self, rows=None, blocks=None, name='packet.json'):
        packet=th.envelope(tm.envelope([self.record] if rows is None else rows),
                           db._envelope([self.block] if blocks is None else blocks))
        path=self.root/name; path.write_bytes(th._encoded(packet)); return path,packet

    def test_one_import_is_visible_to_both_old_readers_and_reexport(self):
        path,packet=self.packet()
        result=th.import_state(path,self.receiver)
        self.assertEqual(result['status'],'IMPORTED'); self.assertFalse(result['execution_authorized'])
        self.assertEqual(tm.snapshot(self.receiver),[self.record]); self.assertEqual(db._load(self.receiver),[self.block])
        with self.assertRaisesRegex(ValueError,'DATA_USE_BLOCKED'):
            admission.assert_source_allowed(tb.FIXTURE,self.receiver)
        with self.assertRaisesRegex(ValueError,'reserved/consumed'):
            tm.assert_available({'content':{'source':{},'files':{}}},{'holdout.json':[{'features':['synthetic']} ]},self.receiver)

    def test_export_includes_legacy_local_records_and_no_private_evidence(self):
        memory=self.root/'memory.json'; memory.write_text(json.dumps(tm.envelope([self.record])))
        tm.import_memory(memory,self.sender); db._save(self.sender,[self.block])
        path=self.root/'combined.json'; th.export(path,self.sender); packet=th.load_packet(path)
        self.assertEqual(packet['payload']['tabular_memory'],tm.envelope([self.record]))
        self.assertEqual(packet['payload']['data_blocks'],db._envelope([self.block]))
        self.assertEqual(set(packet['payload']),{'kind','version','tabular_memory','data_blocks','airfoil_memory'})
        self.assertEqual(packet['payload']['version'],2)
        self.assertEqual(packet['payload']['airfoil_memory']['content']['records'],[])
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        th.import_state(path,self.receiver)
        out=self.root/'forward.json'; th.export(out,self.receiver)
        self.assertEqual(th.load_packet(out),packet)
        old_memory=self.root/'old-memory.json'; tm.export_memory(old_memory,self.receiver)
        old_blocks=self.root/'old-blocks.json'; db.export(old_blocks,self.receiver)
        self.assertEqual(tm.load_packet(old_memory),packet['payload']['tabular_memory'])
        self.assertEqual(db._validate(json.loads(old_blocks.read_text())),[self.block])
        with self.assertRaises(FileExistsError): th.export(path,self.sender)

    def test_repeat_and_stale_packets_cannot_downgrade_either_component(self):
        path,packet=self.packet(); th.import_state(path,self.receiver)
        before={str(p):p.read_bytes() for p in (self.receiver/'.research-memory').rglob('*.json')}
        self.assertEqual(th.import_state(path,self.receiver)['status'],'ALREADY_IMPORTED')
        self.assertEqual(before,{str(p):p.read_bytes() for p in (self.receiver/'.research-memory').rglob('*.json')})
        old={**self.record,'state':'RESERVED','result_sha256':None}
        stale,_=self.packet([old],[],name='stale.json'); th.import_state(stale,self.receiver)
        empty,_=self.packet([],[],name='empty.json'); th.import_state(empty,self.receiver)
        self.assertEqual(tm.snapshot(self.receiver),[self.record]); self.assertEqual(db._load(self.receiver),[self.block])

    def test_verify_and_status_are_read_only_and_never_authorize(self):
        path,_=self.packet(); target=self.root/'missing'
        state=th.status(target); result=th.verify(path)
        self.assertTrue(state['read_only']); self.assertTrue(result['read_only'])
        self.assertFalse(result['execution_authorized']); self.assertFalse(target.exists())
        self.assertEqual(tm.snapshot(self.receiver),[]); self.assertEqual(db._load(self.receiver),[])
        self.assertFalse((self.receiver/'.cache').exists())

    def test_conflict_in_memory_prevents_new_pause_import(self):
        first,_=self.packet(); th.import_state(first,self.receiver)
        before={str(p):p.read_bytes() for p in (self.receiver/'.research-memory').rglob('*') if p.is_file()}
        conflict={**self.record,'state':'CONTINUE','result_sha256':digest('conflicting-result')}
        newblock={**self.block,'reason':'must not be partially imported'}
        incoming,_=self.packet([conflict],[newblock],name='conflict.json')
        with self.assertRaisesRegex(ValueError,'Conflicting terminal'): th.import_state(incoming,self.receiver)
        self.assertEqual(before,{str(p):p.read_bytes() for p in (self.receiver/'.research-memory').rglob('*') if p.is_file()})

    def test_block_merge_limit_prevents_new_memory_import(self):
        db._save(self.receiver,[{**self.block,'reason':str(i)} for i in range(db.LIMIT)])
        path,_=self.packet()
        before=(self.receiver/'.research-memory/data-blocks.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'Too many'): th.import_state(path,self.receiver)
        self.assertEqual(tm.snapshot(self.receiver),[])
        self.assertFalse((self.receiver/'.research-memory/tabular-state-handoff').exists())
        self.assertEqual(before,(self.receiver/'.research-memory/data-blocks.json').read_bytes())

    def test_malformed_or_missing_component_has_no_partial_import(self):
        path,original=self.packet()
        mutations=[lambda p:p['payload'].pop('data_blocks'),
                   lambda p:p['payload'].update(approval={'approved':True}),
                   lambda p:p['payload'].update(version=True),
                   lambda p:p['payload']['data_blocks'].update(sha256='0'*64),
                   lambda p:p['payload']['tabular_memory'].update(sha256='0'*64)]
        for mutation in mutations:
            packet=copy.deepcopy(original); mutation(packet); packet['sha256']=digest(packet['payload'])
            path.write_text(json.dumps(packet))
            with self.assertRaises(ValueError): th.import_state(path,self.receiver)
            self.assertFalse((self.receiver/'.research-memory').exists())

    def test_old_importers_cannot_accept_only_half_of_combined_format(self):
        path,_=self.packet()
        with self.assertRaises(ValueError): tm.import_memory(path,self.receiver)
        with self.assertRaises(ValueError): db.import_blocks(path,self.receiver)
        self.assertFalse((self.receiver/'.research-memory').exists())

    def test_failed_atomic_publish_leaves_neither_component_active(self):
        path,_=self.packet()
        with patch.object(th.os,'link',side_effect=OSError('synthetic publish failure')):
            with self.assertRaisesRegex(OSError,'publish failure'): th.import_state(path,self.receiver)
        self.assertEqual(tm.snapshot(self.receiver),[]); self.assertEqual(db._load(self.receiver),[])
        self.assertEqual(list((self.receiver/'.research-memory/tabular-state-handoff').iterdir()),[])

    def test_error_after_publish_keeps_both_components_and_retry_is_idempotent(self):
        path,_=self.packet(); original_link=os.link
        def publish_then_fail(source,target):
            original_link(source,target); raise OSError('synthetic post-publish interruption')
        with patch.object(th.os,'link',side_effect=publish_then_fail):
            with self.assertRaises(OSError): th.import_state(path,self.receiver)
        self.assertEqual(tm.snapshot(self.receiver),[self.record]); self.assertEqual(db._load(self.receiver),[self.block])
        self.assertEqual(th.import_state(path,self.receiver)['status'],'ALREADY_IMPORTED')

    def test_corrupt_stored_packet_blocks_both_consumers_and_legacy_mutations(self):
        path,packet=self.packet(); th.import_state(path,self.receiver)
        stored=self.receiver/'.research-memory/tabular-state-handoff'/(packet['sha256']+'.json')
        stored.write_text('{}')
        for read in (tm.snapshot,db._load,th.status):
            with self.assertRaises(ValueError): read(self.receiver)
        legacy=self.root/'legacy.json'; legacy.write_text(json.dumps(tm.envelope([])))
        with self.assertRaises(ValueError): tm.import_memory(legacy,self.receiver)
        self.assertFalse((self.receiver/'.research-memory/tabular-handoff').exists())
        pauses=self.root/'pauses.json'; pauses.write_text(json.dumps(db._envelope([])))
        with self.assertRaises(ValueError): db.import_blocks(pauses,self.receiver)
        self.assertFalse((self.receiver/'.research-memory/data-blocks.json').exists())

    def test_links_filename_tampering_and_nonregular_packet_rejected(self):
        path,packet=self.packet(); link=self.root/'linked.json'; link.symlink_to(path)
        with self.assertRaises(ValueError): th.import_state(link,self.receiver)
        th.import_state(path,self.receiver)
        folder=self.receiver/'.research-memory/tabular-state-handoff'; stored=folder/(packet['sha256']+'.json')
        stored.rename(folder/('0'*64+'.json'))
        with self.assertRaisesRegex(ValueError,'filename'): th.status(self.receiver)
        (folder/('0'*64+'.json')).unlink(); folder.rmdir(); folder.symlink_to(self.sender,target_is_directory=True)
        with self.assertRaises(ValueError): th.import_state(path,self.receiver)
        fifo=self.root/'pipe.json'; os.mkfifo(fifo)
        with self.assertRaises(ValueError): th.verify(fifo)

    def test_json_and_size_limits_reject_before_state_changes(self):
        path,_=self.packet()
        for raw in (b'{"payload":{},"payload":{}}',b'NaN',b'\xff',b'x'*(th.PACKET_LIMIT+1)):
            path.write_bytes(raw)
            with self.assertRaises(ValueError): th.import_state(path,self.receiver)
            self.assertFalse((self.receiver/'.research-memory').exists())

    def test_lock_conflict_and_checkout_alias(self):
        path,_=self.packet()
        with research_lock(self.receiver):
            with self.assertRaisesRegex(ValueError,'lock'): th.import_state(path,self.receiver)
        self.assertFalse((self.receiver/'.research-memory').exists())
        th.import_state(path,self.receiver)
        alias=self.root/'alias'; alias.symlink_to(self.receiver,target_is_directory=True)
        self.assertEqual(th.status(alias),th.status(self.receiver))

    def test_cli_transfer_no_model_or_worker_and_no_automatic_approval(self):
        path,_=self.packet(); repo=str(Path(__file__).resolve().parents[1])
        def cli(*args):
            return subprocess.run([sys.executable,'-m','research_harness','tabular','handoff','--root',str(self.receiver),*args],
                                  cwd=self.root,env={**os.environ,'PYTHONPATH':repo},capture_output=True,text=True,timeout=15)
        before=cli('verify',str(path)); self.assertEqual(before.returncode,0,before.stderr)
        self.assertFalse((self.receiver/'.research-memory').exists())
        imported=cli('import',str(path)); self.assertEqual(imported.returncode,0,imported.stderr)
        state=json.loads(cli('status').stdout); self.assertEqual(state['tabular_records'],1)
        self.assertEqual(state['data_block_records'],1); self.assertFalse(state['execution_authorized'])
        self.assertFalse((self.receiver/'runs').exists())

    def test_combined_pause_reaches_all_four_execution_entries(self):
        from test_data_blocks import DataBlockTests
        from research_harness import airfoil_baseline as ab, tabular_trial as tt, airfoil_trial as at
        helper=DataBlockTests(); self.addCleanup(helper.doCleanups)
        for module in (tb,ab,tt,at):
            if module in (tb,ab):
                root,folder,_,snapshot,_=helper.baseline(module)
                def invoke(operation): return getattr(module,operation)(folder,root=root)
            else:
                candidate,f=helper.candidate(module); root,folder,snapshot=f.root,f.folder,f.snapshot
                def invoke(operation): return candidate.invoke(f,operation)
            row={**self.block,'dataset':snapshot['packet']['content']['dataset'],
                 'qualification_sha256':snapshot['packet']['sha256']}
            path,_=self.packet([], [row]); th.import_state(path,root)
            for operation in ('preflight','execute'):
                with patch.object(module,'environment') as env, patch('research_harness.tabular_sandbox.isolated_worker') as worker:
                    with self.assertRaisesRegex(ValueError,'DATA_USE_BLOCKED'): invoke(operation)
                    env.assert_not_called(); worker.assert_not_called()
            self.assertFalse((folder/'trial-run').exists()); self.assertFalse((folder/'run').exists())

    def test_legacy_imports_merge_with_combined_state_without_erasing_it(self):
        path,_=self.packet(); th.import_state(path,self.receiver)
        record={**self.record,'scope':digest('second-scope'),'trial_sha256':digest('second-trial'),
                'data_keys':[digest('second-row')]}
        memory=self.root/'legacy-memory.json'; memory.write_text(json.dumps(tm.envelope([record])))
        tm.import_memory(memory,self.receiver)
        block={**self.block,'reason':'second independent pause record'}
        pause=self.root/'legacy-pause.json'; pause.write_text(json.dumps(db._envelope([block])))
        db.import_blocks(pause,self.receiver)
        self.assertEqual(tm.snapshot(self.receiver),tm.merge([self.record,record]))
        self.assertEqual(db._load(self.receiver),db.merge([self.block,block]))
        newer=self.root/'newer.json'; th.export(newer,self.receiver)
        third=self.root/'third'; third.mkdir(); th.import_state(newer,third)
        self.assertEqual(tm.snapshot(third),tm.snapshot(self.receiver)); self.assertEqual(db._load(third),db._load(self.receiver))

    def test_combined_memory_byte_limit_has_no_partial_import(self):
        records=[{**self.record,'scope':digest(['scope',i]),'trial_sha256':digest(['trial',i]),
                  'data_keys':[format(j,'064x') for j in range(i*10000,(i+1)*10000)]} for i in range(6)]
        first,_=self.packet(records[:3],[],name='first-large.json')
        second,_=self.packet(records[3:],[self.block],name='second-large.json')
        th.import_state(first,self.receiver)
        before=tm.snapshot(self.receiver)
        with self.assertRaisesRegex(ValueError,'component exceeds'): th.import_state(second,self.receiver)
        self.assertEqual(tm.snapshot(self.receiver),before); self.assertEqual(db._load(self.receiver),[])
