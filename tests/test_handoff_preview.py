"""Read-only handoff preview fixtures; no actor, dataset or research execution."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from research_harness import tabular_handoff as th, tabular_memory as tm
from research_harness import data_blocks as db, airfoil_memory as am, proposal_memory as pm
from research_harness.core import digest
from research_harness.state_lock import research_lock


class HandoffPreviewTests(unittest.TestCase):
    def setUp(self):
        from test_unified_handoff import UnifiedHandoffTests
        f=UnifiedHandoffTests(); f.setUp(); self.addCleanup(f.doCleanups)
        self.root=f.root; self.receiver=self.root/'new-receiver'
        self.trial=f.record; self.block=f.block
        self.airfoil={'phase':'baseline','scope':digest('airfoil'),'review_sha256':digest('review'),
                      'mechanism':None,'state':'RESERVED','result_sha256':None}
        self.proposal={'scope':digest('proposal'),'baseline_sha256':digest('baseline')}

    def packet(self, *, version=3, name='packet.json', trials=None, blocks=None, airfoil=None, proposals=None):
        args=[tm.envelope([self.trial] if trials is None else trials),db._envelope([self.block] if blocks is None else blocks)]
        if version>=2: args.append(am.envelope([self.airfoil] if airfoil is None else airfoil))
        if version>=3: args.append(pm.envelope([self.proposal] if proposals is None else proposals))
        p=th.envelope(*args); path=self.root/name; path.write_bytes(th._encoded(p)); return path,p

    def files(self, root):
        return {str(p.relative_to(root)):p.read_bytes() if p.is_file() else None for p in root.rglob('*')} if root.exists() else {}

    def local_proposal(self):
        folder=self.receiver/'.research-memory/tabular-proposer'/self.proposal['scope']; folder.mkdir(parents=True)
        (folder/'reservation.json').write_text(json.dumps({**self.proposal,'status':'RESERVED'}))
        return folder

    def test_preview_missing_root_is_read_only_and_matches_bound_import(self):
        path,_=self.packet()
        with patch.object(th,'research_lock',side_effect=AssertionError('Preview must not take a writing lock')):
            preview=th.preview(path,self.receiver)
        self.assertFalse(self.receiver.exists()); self.assertTrue(preview['read_only'])
        self.assertFalse(preview['execution_authorized']); self.assertEqual(preview['missing_components'],['sr_memory'])
        self.assertTrue(all(v['before']==0 and v['after']==1 and len(v['added'])==1 and not v['updated'] for k,v in preview['changes'].items() if k!='sr_memory'))
        self.assertEqual(preview['changes']['sr_memory'],{'before':0,'after':0,'added':[],'updated':[]})
        result=th.import_state(path,self.receiver,expect_preview=preview['preview_sha256'])
        self.assertTrue(result['preview_checked']); self.assertEqual(result['merged_state'],preview['merged_state'])
        self.assertEqual(th.status(self.receiver)['sha256'],preview['merged_state']['sha256'])

    def test_existing_checkout_preview_never_changes_bytes_or_creates_lock(self):
        self.local_proposal(); path,_=self.packet(); before=self.files(self.receiver)
        result=th.preview(path,self.receiver)
        self.assertEqual(self.files(self.receiver),before); self.assertFalse((self.receiver/'.cache').exists())
        self.assertEqual(result,th.preview(path,self.receiver))
        self.assertEqual(result['local_recovery_blocked_scopes'],[self.proposal['scope']])

    def test_local_only_to_imported_proposal_effect_visible_with_no_aggregate_change(self):
        self.local_proposal(); path,_=self.packet(trials=[],blocks=[],airfoil=[])
        before=th.preview(path,self.receiver)
        self.assertEqual(before['current'],before['merged_state'])
        self.assertFalse(before['changes']['proposal_memory']['added'])
        self.assertEqual(before['newly_imported_proposal_scopes'],[self.proposal['scope']])
        th.import_state(path,self.receiver,expect_preview=before['preview_sha256'])
        after=th.preview(path,self.receiver)
        self.assertEqual(after['current'],before['current'])
        self.assertNotEqual(after['preview_sha256'],before['preview_sha256'])
        self.assertEqual(after['local_recovery_blocked_scopes'],[])
        self.assertTrue(after['already_imported'])

    def test_same_count_terminal_update_is_reported_not_hidden_as_no_change(self):
        path,_=self.packet(); th.import_state(path,self.receiver)
        terminal={**self.airfoil,'state':'STOP','result_sha256':digest('result')}
        nextpath,_=self.packet(name='terminal.json',airfoil=[terminal])
        preview=th.preview(nextpath,self.receiver)
        delta=preview['changes']['airfoil_memory']
        self.assertEqual(delta['before'],delta['after']); self.assertEqual(delta['added'],[])
        self.assertEqual(delta['updated'],['baseline:'+self.airfoil['scope']])
        th.import_state(nextpath,self.receiver,expect_preview=preview['preview_sha256'])
        self.assertEqual(am.snapshot(self.receiver),[terminal])

    def test_unknown_proposal_binding_enrichment_is_an_update(self):
        path,_=self.packet(proposals=[{**self.proposal,'baseline_sha256':None}]); th.import_state(path,self.receiver)
        newer,_=self.packet(name='known.json'); result=th.preview(newer,self.receiver)
        self.assertEqual(result['changes']['proposal_memory']['updated'],[self.proposal['scope']])
        self.assertEqual(result['newly_imported_proposal_scopes'],[])

    def test_legacy_missing_components_do_not_suggest_deleting_local_records(self):
        full,_=self.packet(); th.import_state(full,self.receiver)
        for version,missing in ((1,['airfoil_memory','proposal_memory','sr_memory']),(2,['proposal_memory','sr_memory'])):
            path,_=self.packet(version=version,name=f'v{version}.json',trials=[],blocks=[],airfoil=[])
            result=th.preview(path,self.receiver)
            self.assertEqual(result['missing_components'],missing)
            self.assertEqual(result['current'],result['merged_state'])
            self.assertIsNone(result['incoming']['proposal_records'])
            th.import_state(path,self.receiver,expect_preview=result['preview_sha256'])
            self.assertEqual(pm.snapshot(self.receiver),[self.proposal])

    def test_stale_preview_after_pause_is_rejected_without_partial_import(self):
        path,_=self.packet(); preview=th.preview(path,self.receiver)
        db._save(self.receiver,[{**self.block,'reason':'new local pause'}]); before=self.files(self.receiver)
        with self.assertRaisesRegex(ValueError,'preview changed'):
            th.import_state(path,self.receiver,expect_preview=preview['preview_sha256'])
        self.assertEqual(tm.snapshot(self.receiver),[]); self.assertEqual(pm.snapshot(self.receiver),[])
        self.assertFalse(th._folder(self.receiver).exists())
        self.assertEqual({k:v for k,v in self.files(self.receiver).items() if not k.startswith('.cache')},before)

    def test_stale_preview_after_each_other_component_change_is_rejected(self):
        for component in ('trials','airfoil','proposals'):
            receiver=self.root/component
            path,_=self.packet(name=component+'-incoming.json'); old=th.preview(path,receiver)
            options={'trials':[],'blocks':[],'airfoil':[],'proposals':[]}
            options[component]=[{'trials':self.trial,'airfoil':self.airfoil,'proposals':self.proposal}[component]]
            new,_=self.packet(name=component+'-local.json',**options); th.import_state(new,receiver)
            before=self.files(receiver)
            with self.assertRaisesRegex(ValueError,'preview changed'):
                th.import_state(path,receiver,expect_preview=old['preview_sha256'])
            self.assertEqual(self.files(receiver),before)

    def test_changed_incoming_packet_or_checkout_cannot_use_old_preview(self):
        path,_=self.packet(); preview=th.preview(path,self.receiver)
        changed,_=self.packet(name='changed.json',blocks=[{**self.block,'reason':'changed packet'}])
        for incoming,root in ((changed,self.receiver),(path,self.root/'other-checkout')):
            with self.assertRaisesRegex(ValueError,'preview changed'):
                th.import_state(incoming,root,expect_preview=preview['preview_sha256'])
            self.assertFalse((root/'.research-memory').exists())

    def test_additional_empty_packet_invalidates_preview_even_with_same_counts(self):
        path,_=self.packet(); old=th.preview(path,self.receiver)
        empty,_=self.packet(name='empty.json',trials=[],blocks=[],airfoil=[],proposals=[])
        th.import_state(empty,self.receiver)
        fresh=th.preview(path,self.receiver)
        self.assertEqual(old['current'],fresh['current']); self.assertNotEqual(old['preview_sha256'],fresh['preview_sha256'])
        with self.assertRaisesRegex(ValueError,'preview changed'): th.import_state(path,self.receiver,expect_preview=old['preview_sha256'])

    def test_repeat_checked_import_requires_fresh_preview_and_legacy_remains_idempotent(self):
        path,_=self.packet(); old=th.preview(path,self.receiver)
        th.import_state(path,self.receiver,expect_preview=old['preview_sha256'])
        with self.assertRaisesRegex(ValueError,'preview changed'): th.import_state(path,self.receiver,expect_preview=old['preview_sha256'])
        fresh=th.preview(path,self.receiver)
        self.assertEqual(th.import_state(path,self.receiver,expect_preview=fresh['preview_sha256'])['status'],'ALREADY_IMPORTED')
        legacy=th.import_state(path,self.receiver)
        self.assertEqual(legacy['status'],'ALREADY_IMPORTED'); self.assertFalse(legacy['preview_checked'])

    def test_preview_and_import_reject_each_binding_conflict_identically(self):
        path,_=self.packet(); th.import_state(path,self.receiver)
        bad=[{'trials':[{**self.trial,'state':'CONTINUE','result_sha256':digest('conflict')}]},
             {'airfoil':[{**self.airfoil,'review_sha256':digest('conflict')}]},
             {'proposals':[{**self.proposal,'baseline_sha256':digest('conflict')}]}]
        for i,change in enumerate(bad):
            incoming,_=self.packet(name=f'conflict-{i}.json',**change); before=self.files(self.receiver)
            messages=[]
            for op in (th.preview,th.import_state):
                with self.assertRaises(ValueError) as error: op(incoming,self.receiver)
                messages.append(str(error.exception))
            self.assertEqual(messages[0],messages[1]); self.assertEqual(self.files(self.receiver),before)

    def test_preview_and_import_reject_merged_limit_identically(self):
        db._save(self.receiver,[{**self.block,'reason':str(i)} for i in range(db.LIMIT)])
        path,_=self.packet(); before=(self.receiver/'.research-memory/data-blocks.json').read_bytes()
        for op in (th.preview,th.import_state):
            with self.assertRaisesRegex(ValueError,'Too many'): op(path,self.receiver)
        self.assertEqual((self.receiver/'.research-memory/data-blocks.json').read_bytes(),before)
        self.assertFalse(th._folder(self.receiver).exists())

    def test_malformed_preview_input_never_creates_destination(self):
        path,_=self.packet()
        for raw in ('{}','{"payload":{},"payload":{}}','NaN'):
            path.write_text(raw)
            with self.assertRaises(ValueError): th.preview(path,self.receiver)
            self.assertFalse(self.receiver.exists())

    def test_corrupt_local_state_rejected_read_only_and_symlink_packet_refused(self):
        path,packet=self.packet(); th.import_state(path,self.receiver)
        target=th._folder(self.receiver)/(packet['sha256']+'.json'); target.write_text('{}')
        before=self.files(self.receiver)
        with self.assertRaises(ValueError): th.preview(path,self.receiver)
        self.assertEqual(self.files(self.receiver),before)
        link=self.root/'link.json'; link.symlink_to(path)
        with self.assertRaises(ValueError): th.preview(link,self.root/'untouched')
        self.assertFalse((self.root/'untouched').exists())

    def test_checked_import_recomputes_inside_existing_lock(self):
        path,_=self.packet(); old=th.preview(path,self.receiver); original=th.research_lock
        @contextmanager
        def changed_before_lock(root):
            db._save(root,[{**self.block,'reason':'change at lock acquisition'}])
            with original(root): yield
        with patch.object(th,'research_lock',changed_before_lock),patch.object(th,'_publish') as publish:
            with self.assertRaisesRegex(ValueError,'preview changed'):
                th.import_state(path,self.receiver,expect_preview=old['preview_sha256'])
            publish.assert_not_called()

    def test_lock_still_prevents_import_and_preview_is_only_an_observation(self):
        path,_=self.packet()
        with research_lock(self.receiver):
            old=th.preview(path,self.receiver)
            with self.assertRaisesRegex(ValueError,'lock'):
                th.import_state(path,self.receiver,expect_preview=old['preview_sha256'])
        self.assertFalse(th._folder(self.receiver).exists())

    def test_invalid_expected_digest_fails_before_creating_lock(self):
        path,_=self.packet()
        for value in ('',True,'bad','F'*64):
            with self.assertRaises(ValueError): th.import_state(path,self.receiver,expect_preview=value)
            self.assertFalse(self.receiver.exists())

    def test_alias_and_cli_round_trip_with_bound_digest(self):
        path,_=self.packet(); self.receiver.mkdir(); alias=self.root/'alias'; alias.symlink_to(self.receiver,target_is_directory=True)
        self.assertEqual(th.preview(path,self.receiver),th.preview(path,alias))
        repo=str(Path(__file__).resolve().parents[1])
        def cli(prefix,*args):
            return subprocess.run([sys.executable,'-m','research_harness',*prefix,'handoff','--root',str(self.receiver),*args],
                                  cwd=self.root,env={**os.environ,'PYTHONPATH':repo},capture_output=True,text=True,timeout=15)
        first=cli([],'preview',str(path)); second=cli(['tabular'],'preview',str(path))
        self.assertEqual(first.returncode,0,first.stderr); self.assertEqual(first.stdout,second.stdout)
        self.assertEqual(list(self.receiver.iterdir()),[])
        sha=json.loads(first.stdout)['preview_sha256']
        result=cli(['tabular'],'import',str(path),'--expect-preview',sha)
        self.assertEqual(result.returncode,0,result.stderr); self.assertTrue(json.loads(result.stdout)['preview_checked'])
        self.assertNotEqual(cli([],'import',str(path),'--expect-preview',sha).returncode,0)
        fresh=json.loads(cli([],'preview',str(path)).stdout)['preview_sha256']
        self.assertEqual(cli([],'import',str(path),'--expect-preview',fresh).returncode,0)
        self.assertFalse((self.receiver/'runs').exists())
