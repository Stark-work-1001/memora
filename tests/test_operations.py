import concurrent.futures,tempfile,unittest
from pathlib import Path
from memory_merge.store import Store

class OperationsTests(unittest.TestCase):
    def test_parallel_retry_single_row(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(d)
            def put(_): return Store(d).capture('p','retry-safe',source='test',event_id='same')['id']
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: ids=list(pool.map(put,range(12)))
            self.assertEqual(len(set(ids)),1)
            self.assertEqual(len(s.list_memories('p')),1)
    def test_rebuild_and_backup(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'live'); r=s.capture('p','persistent',source='test',mode='manual',confirmed=True)
            s.flush(); (s.root/'markdown'/f"{r['id']}.md").unlink()
            s.rebuild(); self.assertTrue((s.root/'markdown'/f"{r['id']}.md").exists())
            target=Path(d)/'backup.sqlite3'; s.backup(target)
            self.assertGreater(target.stat().st_size,0)
            with self.assertRaises(FileExistsError):s.backup(target)
