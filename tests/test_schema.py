import json
import sqlite3
import threading
import unittest
from pathlib import Path

from memory_merge import schema
from memory_merge.errors import SchemaTooNew
from memory_merge.store import Store
from tests.helpers import tmpdir
from tests.legacy.store_v0_1 import Store as StoreV01


def v1_database(root):
    """A database written by the real 0.1.0 code, exercising every 0.1 table."""
    s = StoreV01(root)
    a = s.capture('p', '选择 SQLite 作为事务真源', 'user:explicit', mode='manual', confirmed=True)
    b = s.capture('p', 'Markdown mirror is derived', 'agent', event_id='e1')
    c = s.capture('q', 'other project', 'agent')
    s.review('p', b['id'], 'approve'); s.review('q', c['id'], 'reject')
    s.link('p', a['id'], b['id'], 'supports')
    with s.connect() as con:
        con.execute('INSERT INTO vectors VALUES(?,?,?,?,?)', (a['id'], 'http://127.0.0.1:1/v1|m', 2, a['digest'], json.dumps([3, 4])))
        con.execute('INSERT INTO vectors VALUES(?,?,?,?,?)', (b['id'], 'http://127.0.0.1:1/v1|m', 2, b['digest'], 'not json'))
    s.flush()
    return s, a, b, c


def snapshot(db, sql):
    c = sqlite3.connect(db)
    try: return c.execute(sql).fetchall()
    finally: c.close()


class MigrationTests(unittest.TestCase):
    def test_v1_upgrade_preserves_data_and_takes_verified_backup(self):
        with tmpdir() as d:
            old, a, b, c = v1_database(d)
            before = snapshot(old.db, 'SELECT id, project, content, source, event_id, digest, mode, status, category, tags, created, version FROM memories ORDER BY id')
            audit_before = snapshot(old.db, 'SELECT seq, id, action, digest FROM audit ORDER BY seq')
            s = Store(d)
            step = s.migration['migrations'][0]
            self.assertEqual((step['from'], step['to']), (1, 2))
            self.assertEqual((step['vectors_converted'], step['vectors_skipped']), (1, 1))
            after = snapshot(s.db, 'SELECT id, project, content, source, event_id, digest, mode, status, category, tags, created, version FROM memories ORDER BY id')
            self.assertEqual(before, after)
            self.assertEqual(audit_before, snapshot(s.db, 'SELECT seq, id, action, digest FROM audit ORDER BY seq'))
            self.assertEqual(snapshot(s.db, 'PRAGMA user_version')[0][0], schema.LATEST)
            backup = Path(step['backup'])
            self.assertTrue(backup.is_file())
            self.assertEqual(snapshot(backup, 'PRAGMA user_version')[0][0], 1)
            self.assertEqual(len(snapshot(backup, 'SELECT id FROM memories')), 3)
            # CJK recall works on migrated rows; the 0.1 vector is quarantined under a legacy fingerprint
            self.assertEqual(s.recall('p', '事务的真源是什么')[0]['id'], a['id'])
            self.assertTrue(snapshot(s.db, 'SELECT fingerprint FROM embeddings')[0][0].startswith('legacy-'))
            self.assertEqual(len(s.graph('p')['edges']), 1)

    def test_fresh_and_migrated_schemas_are_identical(self):
        with tmpdir() as d1, tmpdir() as d2:
            v1_database(d1); migrated = Store(d1); fresh = Store(d2)
            q = "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
            norm = lambda rows: [(t, n, ' '.join((s or '').split())) for t, n, s in rows]
            self.assertEqual(norm(snapshot(migrated.db, q)), norm(snapshot(fresh.db, q)))

    def test_reopen_is_a_no_op(self):
        with tmpdir() as d:
            v1_database(d); Store(d)
            again = Store(d)
            self.assertEqual(again.migration['migrations'], [])
            self.assertEqual(len(list((Path(d) / 'backups').glob('*.sqlite3'))), 1)

    def test_newer_database_is_refused_untouched(self):
        with tmpdir() as d:
            s = Store(d)
            con = sqlite3.connect(s.db); con.execute('PRAGMA user_version=99'); con.close()
            raw = s.db.read_bytes()
            with self.assertRaises(SchemaTooNew): Store(d)
            self.assertEqual(raw, s.db.read_bytes())

    def test_old_code_downgrading_user_version_is_healed(self):
        with tmpdir() as d:
            s = Store(d); m = s.capture('p', 'kept', 'test', mode='manual', confirmed=True)
            StoreV01(d)  # 0.1 stamps user_version=1 and recreates its empty legacy tables
            self.assertEqual(snapshot(s.db, 'PRAGMA user_version')[0][0], 1)
            with self.assertRaises(sqlite3.OperationalError): StoreV01(d).capture('p', 'old writer', 'x')
            healed = Store(d)
            self.assertTrue(healed.migration['healed_user_version'])
            self.assertEqual(snapshot(s.db, 'PRAGMA user_version')[0][0], schema.LATEST)
            self.assertEqual(healed.recall('p', 'kept')[0]['id'], m['id'])
            names = {r[0] for r in snapshot(s.db, "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn('vectors', names); self.assertNotIn('memories_fts', names)

    def test_concurrent_openers_migrate_once(self):
        with tmpdir() as d:
            v1_database(d)
            infos, errors = [], []
            def open_():
                try: infos.append(Store(d).migration)
                except Exception as e: errors.append(e)
            threads = [threading.Thread(target=open_) for _ in range(4)]
            for t in threads: t.start()
            for t in threads: t.join()
            self.assertEqual(errors, [])
            self.assertEqual(sum(len(i['migrations']) for i in infos), 1)

    def test_analyzer_change_rebuilds_index(self):
        with tmpdir() as d:
            s = Store(d); s.capture('p', '真源', 'test', mode='manual', confirmed=True)
            con = sqlite3.connect(s.db); con.execute("UPDATE meta SET value='old-analyzer' WHERE key='analyzer'"); con.execute('DELETE FROM memory_fts'); con.commit(); con.close()
            again = Store(d)
            self.assertTrue(again.migration['fts_rebuilt'])
            self.assertEqual(len(again.recall('p', '真源')), 1)


if __name__ == '__main__':
    unittest.main()
