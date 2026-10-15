import unittest, tempfile
from pathlib import Path
from unittest.mock import patch
from memory_merge.providers import Provider, MemoryService
from memory_merge.store import Store

class ProviderTests(unittest.TestCase):
    def test_remote_requires_consent(self):
        with self.assertRaises(ValueError): Provider('https://example.com/v1','test')
        with self.assertRaises(ValueError): Provider('http://example.com/v1','test',allow_remote=True)
    def test_vectors_validate(self):
        p=Provider('http://127.0.0.1:1234/v1','fake')
        with patch.object(p,'post',return_value={'data':[{'embedding':[1,0]}]}):
            self.assertEqual(p.embed('hello'),[1.,0.])
        with patch.object(p,'post',return_value={'data':[{'embedding':[float('nan'),0]}]}):
            with self.assertRaises(ValueError): p.embed('hello')
    def test_judge_schema_not_authority(self):
        p=Provider('http://127.0.0.1:1234/v1','fake')
        with patch.object(p,'post',return_value={'choices':[{'message':{'content':'{"category":"fact","importance":0.6,"reason":"test"}'}}]}):
            self.assertEqual(p.judge('hi')['category'],'fact')
        with patch.object(p,'post',return_value={'choices':[{'message':{'content':'{"category":"admin","importance":2}'}}]}):
            with self.assertRaises(ValueError): p.judge('hi')
    def test_hybrid_vectors_and_dimension_guard(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)); p=Provider('http://127.0.0.1:1234/v1','fake')
            svc=MemoryService(store,p)
            r=store.capture('p','选择本地存储',source='test',mode='manual',confirmed=True)
            with patch.object(p,'embed',return_value=[1.,0.]):
                self.assertEqual(svc.index('p')['indexed'],1)
                found=svc.recall('p','local persistence')
                self.assertEqual(found['results'][0]['id'],r['id'])
                self.assertEqual(found['mode'],'hybrid')
            with patch.object(p,'embed',return_value=[1.,0.,0.]):
                found=svc.recall('p','local persistence')
                self.assertEqual(found['results'],[])
                self.assertGreater(found['incompatible_vectors'],0)
    def test_default_rag_returns_evidence_not_fake_answer(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(d); svc=MemoryService(s)
            s.capture('p','SQLite is selected',source='test',mode='manual',confirmed=True)
            result=svc.rag('p','SQLite')
            self.assertEqual(result['generation'],'client_required')
            self.assertIn('[memory:',result['context'])
            self.assertIn('untrusted',result['instruction'])
