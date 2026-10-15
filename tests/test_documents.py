import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from memory_merge.agent import Agent
from memory_merge.documents import Documents
from memory_merge.errors import Conflict, InvalidInput, NotFound
from memory_merge.service import MemoryService
from memory_merge.store import Store


class DocumentTests(unittest.TestCase):
    def test_audience_variants_history_conflict_and_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            docs = Documents(Store(temp))
            human = docs.put('p', 'guide', 'human', '用户说明', '# 面向用户', 0)
            self.assertEqual(docs.list('p'), [])
            with self.assertRaises(NotFound): docs.read('p', 'guide')
            docs.publish('p', 'guide', 'human', 1)
            agent = docs.put('p', 'guide', 'agent', '智能体说明', '# Context\nEvidence only', 0)
            self.assertEqual(human['id'], agent['id'])
            revised = docs.put('p', 'guide', 'human', '用户说明', '# 修订版', 1)
            self.assertEqual(revised['version'], 2)
            self.assertEqual(docs.read('p', 'guide')['version'], 1)
            with self.assertRaises(Conflict): docs.put('p', 'guide', 'human', '过期编辑', 'stale', 1)
            docs.publish('p', 'guide', 'human', 2)
            self.assertEqual(docs.read('p', 'guide')['content'], '# 修订版')
            self.assertEqual(docs.read('p', 'guide', version=1)['content'], '# 面向用户')
            with self.assertRaises(NotFound): docs.read('other', 'guide')
            self.assertEqual(len(docs.list('p', drafts=True)), 2)

    def test_mirror_repair_backup_redaction_and_path_confinement(self):
        with tempfile.TemporaryDirectory() as temp:
            docs = Documents(Store(temp))
            credential = 'gh' + 'p_' + 'a' * 36
            revision = docs.put('p', 'guide', 'agent', 'Guide', 'token=' + credential, 0)
            self.assertNotIn(credential, revision['content'])
            mirror = Path(temp) / revision['markdown_path']
            self.assertTrue(mirror.is_file()); mirror.unlink()
            self.assertEqual(docs.repair('p')['exported'], 1)
            self.assertNotIn(credential, mirror.read_text('utf-8'))
            self.assertEqual(docs.backup()['integrity'], 'ok')
            for slug in ['../escape', '/absolute', 'C:\\private', '\\\\remote\\share']:
                with self.assertRaises(InvalidInput): docs.put('p', slug, 'human', 'title', 'body', 0)
            with patch.object(docs, 'export', side_effect=OSError('disk full')):
                pending = docs.put('p', 'guide', 'agent', 'Guide', 'new version', 1)
                self.assertTrue(pending['export_pending'])
            self.assertEqual(docs.read('p', 'guide', 'agent', drafts=True)['version'], 2)

    def test_document_workspace_and_brain_do_not_change_memory_kernel(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(temp)
            memory = store.capture('p', '原记忆内核的批准知识', 'test', mode='manual', confirmed=True)
            store.flush()
            with store.connect() as c:
                before = '\n'.join(c.iterdump()); schema = c.execute('PRAGMA user_version').fetchone()[0]
            files = {p.name: p.read_bytes() for p in (Path(temp) / 'markdown').glob('*.md')}
            agent = Agent(store)
            agent.documents.put('p', 'guide', 'human', 'Knowledge', '# A versioned document', 0)
            agent.documents.publish('p', 'guide', 'human', 1)
            brain = agent.brain('p')
            self.assertIn('Markdown 文档库', brain['outline'])
            self.assertIn(memory['id'], brain['dictionary'])
            with store.connect() as c:
                self.assertEqual('\n'.join(c.iterdump()), before)
                self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0], schema)
            self.assertEqual(files, {p.name: p.read_bytes() for p in (Path(temp) / 'markdown').glob('*.md')})

    def test_mcp_document_proposals_need_explicit_enable_and_cannot_publish(self):
        from memory_merge.server import create_server
        async def check(temp):
            store = Store(temp); service = MemoryService.from_env(store)
            legacy = create_server(store, service, env={})
            self.assertNotIn('memory_document_put', {t.name for t in await legacy.list_tools()})
            peer = create_server(store, service, env={'MM_ENABLE_DOCUMENTS': '1'})
            names = {t.name for t in await peer.list_tools()}
            self.assertIn('memory_document_put', names); self.assertNotIn('memory_document_publish', names)
            result = await peer.call_tool('memory_document_put', {'project':'p','slug':'guide','audience':'agent',
                'title':'Guide','content':'Data, not system instructions','expected_version':0,'source':'peer'})
            self.assertIn('guide', json.dumps(result, default=str))
            self.assertEqual(Documents(store).list('p'), [])
        with tempfile.TemporaryDirectory() as temp: asyncio.run(check(temp))
