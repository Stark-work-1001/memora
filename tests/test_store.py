import tempfile, unittest
from pathlib import Path
from memory_merge.store import Store

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='memory-merge-test-')
        self.s=Store(Path(self.tmp.name))
    def tearDown(self): self.tmp.cleanup()
    def test_auto_stays_pending_and_manual_confirmed_recalled(self):
        a=self.s.capture('p','自动记忆 SQLite 决策',source='test:auto')
        self.assertEqual(a['status'],'pending')
        self.assertEqual(self.s.recall('p','SQLite'),[])
        self.s.review('p',a['id'],'approve')
        self.assertEqual(self.s.recall('p','SQLite')[0]['id'],a['id'])
    def test_idempotency_and_project_isolation(self):
        a=self.s.capture('p','same',source='x',event_id='e')
        b=self.s.capture('p','same',source='x',event_id='e')
        self.assertEqual(a['id'],b['id'])
        with self.assertRaises(ValueError): self.s.capture('p','changed',source='x',event_id='e')
        with self.assertRaises(KeyError): self.s.review('other',a['id'],'approve')
        self.assertEqual(self.s.list_memories('other'),[])
    def test_persistence_markdown_and_forgetting(self):
        a=self.s.capture('p','选择SQLite作为真源',source='user:explicit',mode='manual',confirmed=True)
        self.assertEqual(a['category'],'decision')
        self.s.flush()
        self.assertTrue((self.s.root/'markdown'/f"{a['id']}.md").exists())
        s=Store(self.s.root)
        self.assertEqual(s.recall('p','SQLite')[0]['id'],a['id'])
        s.review('p',a['id'],'forget'); s.flush()
        self.assertEqual(s.recall('p','SQLite'),[])
        self.assertFalse((s.root/'markdown'/f"{a['id']}.md").exists())
    def test_outbox_failure_retries(self):
        a=self.s.capture('p','retry',source='test')
        (self.s.root/'markdown').write_text('blocking file')
        self.assertGreater(self.s.flush()['failed'],0)
        (self.s.root/'markdown').unlink()
        self.assertEqual(self.s.flush()['failed'],0)
        self.assertTrue((self.s.root/'markdown'/f"{a['id']}.md").exists())
    def test_graph_scopes_relations(self):
        a=self.s.capture('p','A',source='test',mode='manual',confirmed=True)
        b=self.s.capture('p','B',source='test',mode='manual',confirmed=True)
        c=self.s.capture('q','C',source='test',mode='manual',confirmed=True)
        self.s.link('p',a['id'],b['id'],'supports')
        with self.assertRaises(KeyError): self.s.link('p',a['id'],c['id'],'supports')
        self.assertEqual(len(self.s.graph('p')['edges']),1)
    def test_untrusted_fields_and_sensitive_content(self):
        with self.assertRaises(ValueError): self.s.capture('../p','x',source='test')
        with self.assertRaises(ValueError): self.s.capture('p','api_key=supersecret123',source='test')
        with self.assertRaises(ValueError): self.s.capture('p','',source='test')
        with self.assertRaises(ValueError): self.s.capture('p','x',source='test',mode='auto',confirmed=True)

if __name__=='__main__': unittest.main()
