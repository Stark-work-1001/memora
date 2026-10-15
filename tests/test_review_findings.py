"""Regression tests for the defects found by the independent review of the 0.2 upgrade (one test per
finding, numbered as in docs/REVIEW.md)."""
import json
import os
import sqlite3
import stat
import threading
import time
import unittest
from pathlib import Path

from memory_merge import ingest, mirror, ops, schema, sessions, text
from memory_merge.errors import InvalidInput, InvalidTransition, LimitExceeded, ProviderConfigError, SensitiveContent
from memory_merge.service import MemoryService
from memory_merge.store import Store
from memory_merge.web import make_server
from tests.helpers import FakeEmbedder, FakeJudge, tmpdir
from tests.legacy.store_v0_1 import Store as StoreV01
from tests.test_ops_web_cli import http

TOKEN = 'ghp_' + 'Q' * 36
GOOD = '{"category":"fact","importance":0.5,"reason":"r"}'


def files_containing(root, needle):
    return sorted(str(f.relative_to(root)) for f in Path(root).rglob('*') if f.is_file() and needle.encode() in f.read_bytes())


class ReviewFindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tmpdir(); self.root = Path(self.tmp.name); self.s = Store(self.root / 'data')

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_import_redacts_titles_headings_and_urls(self):
        d = self.root / 'docs'; d.mkdir()
        (d / 'n.md').write_text(f'# api_key = {TOKEN}\n\nbody text\n', encoding='utf-8')
        (d / 'b.html').write_text(f'<DL><DT><A HREF="https://bob:Hunter2Secret@x.io/?t={TOKEN}">link</A></DL>', encoding='utf-8')
        (d / 'h.jsonl').write_text(json.dumps({'text': 'quote', 'url': f'https://x.io/?token={TOKEN}', 'locator': {'note': TOKEN}}) + '\n', encoding='utf-8')
        ingest.import_path(self.s, 'p', d, approve=True)
        self.assertEqual(files_containing(self.root / 'data', TOKEN[:20]), [])
        self.assertEqual(files_containing(self.root / 'data', 'Hunter2Secret'), [])

    def test_02_capture_screens_source_tags_and_event_id(self):
        for kw in ({'source': 'api_key=' + TOKEN}, {'tags': [TOKEN]}, {'event_id': TOKEN}):
            args = dict({'source': 'test'}, **kw)
            with self.assertRaises(SensitiveContent): self.s.capture('p', 'harmless', args.pop('source'), **args)

    def test_03_viewer_never_serves_forgotten_rejected_or_pending_text(self):
        ids = {}
        for status in ('pending', 'rejected', 'deleted', 'approved'):
            m = self.s.capture('p', f'{status} body', 'test')
            if status != 'pending': self.s.review('p', m['id'], {'rejected': 'reject', 'deleted': 'forget', 'approved': 'approve'}[status])
            ids[status] = m['id']
        server = make_server(self.s, 0); threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            for status, mid in ids.items():
                code = http(base + f'/api/memory?project=p&id={mid}')[0]
                self.assertEqual(code, 200 if status == 'approved' else 404, status)
        finally:
            server.shutdown(); server.server_close()

    def test_04_agent_paths_are_checked_lexically(self):
        for bad in ['\\\\attacker\\share\\x.md', '//attacker/share/x.md', 'C:\\Windows\\x.md', 'C:x.md', '/etc/passwd', '../x.md', 'a/../../x.md', 'a\\..\\..\\x.md', '']:
            with self.assertRaises(InvalidInput, msg=bad): ingest.safe_relative(bad)
        self.assertEqual(ingest.safe_relative('notes/a.md'), 'notes/a.md')

    def test_05_reverted_file_becomes_current_again(self):
        d = self.root / 'docs'; d.mkdir(); f = d / 'v.md'
        for body in ('alpha text', 'bravo text', 'alpha text'):
            f.write_text(body, encoding='utf-8')
            ingest.import_path(self.s, 'p', d, approve=True)
        self.assertEqual([r['content'] for r in self.s.recall('p', 'text')], ['alpha text'])

    def test_06_inbox_leaves_no_plaintext_copy_after_purge(self):
        inbox = self.s.root / 'markdown' / 'inbox'; inbox.mkdir(parents=True)
        marker = 'INBOXMARKER' + 'k3' * 10
        (inbox / 'n.md').write_text(f'note {marker}', encoding='utf-8')
        mid = mirror.sync(self.s, 'p')['inbox_imported'][0]['id']
        self.s.review('p', mid, 'forget'); ops.purge(self.s, 'p', mid)
        self.assertEqual(files_containing(self.s.root, marker), [])

    def test_07_purge_retries_a_locked_mirror_file(self):
        m = self.s.capture('p', 'locked file body', 'test', mode='manual', confirmed=True); self.s.flush()
        f = self.s.root / 'markdown' / (m['id'] + '.md')
        os.chmod(f, stat.S_IREAD)  # deleting a read-only file fails on Windows, like an open handle
        locked = os.name == 'nt'
        try:
            res = self.s.purge('p', m['id'])
            if locked: self.assertFalse(res['mirror_file_removed'])
        finally:
            os.chmod(f, stat.S_IREAD | stat.S_IWRITE) if f.exists() else None
        self.s.flush()
        self.assertFalse(f.exists())

    def test_08_judge_refuses_removed_content_and_forget_drops_advice(self):
        m = self.s.capture('p', 'judge me', 'agent'); svc = MemoryService(self.s, judge=FakeJudge(GOOD))
        svc.judge('p', m['id'])
        with self.s.connect() as c: self.assertEqual(c.execute('SELECT count(*) FROM judgements').fetchone()[0], 1)
        self.s.review('p', m['id'], 'reject')
        with self.assertRaises(InvalidTransition): svc.judge('p', m['id'])
        with self.s.connect() as c: self.assertEqual(c.execute('SELECT count(*) FROM judgements').fetchone()[0], 1)  # calibration data
        self.s.review('p', m['id'], 'forget')
        with self.s.connect() as c: self.assertEqual(c.execute('SELECT count(*) FROM judgements').fetchone()[0], 0)

    def test_09_secret_heuristic_bypasses(self):
        for t in ['password = Envoy#2024xyz', 'password: $uperS3cret!', 'api_key=(Xk9pq77Lm)', 'password=hunter2env',
                  'ａｐｉ＿ｋｅｙ＝ｓｕｐｅｒｓｅｃｒｅｔ１２３']:
            self.assertTrue(text.secret_kinds(t), t)
        out, _ = text.redact('secret=https://admin:pa,ssw0rd-tail@host')
        self.assertNotIn('ssw0rd', out)

    def test_10_offset_beyond_pool_is_rejected_not_silently_empty(self):
        with self.assertRaises(LimitExceeded): MemoryService(self.s).recall('p', 'x', offset=200)
        for i in range(160): self.s.capture('p', f'match {i}', 'test', mode='manual', confirmed=True)
        self.assertEqual(len(MemoryService(self.s).recall('p', 'match', offset=150, limit=10)['results']), 10)

    def test_11_and_20_heal_rebuilds_indexes_after_old_writer_and_is_race_free(self):
        a = self.s.capture('p', 'alpha approved', 'test', mode='manual', confirmed=True)
        pend = self.s.capture('p', 'pending then approved by old code', 'test')
        MemoryService(self.s, FakeEmbedder()).index()
        old = StoreV01(self.s.root)
        old.review('p', pend['id'], 'approve'); old.review('p', a['id'], 'forget')
        errors = []
        def open_():
            try: Store(self.s.root)
            except Exception as e: errors.append(e)
        threads = [threading.Thread(target=open_) for _ in range(3)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])
        healed = Store(self.s.root)
        self.assertEqual([r['id'] for r in healed.recall('p', 'pending approved old code')], [pend['id']])
        with healed.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM memory_fts WHERE id=?', (a['id'],)).fetchone()[0], 0)
            self.assertEqual(c.execute('SELECT count(*) FROM embeddings WHERE id=?', (a['id'],)).fetchone()[0], 0)

    def test_12_normalisation_equal_edits_are_not_revisions(self):
        m = self.s.capture('p', 'Release V2 ships Friday', 'test', mode='manual', confirmed=True); self.s.flush()
        f = self.s.root / 'markdown' / (m['id'] + '.md')
        f.write_text(f.read_text(encoding='utf-8').replace('V2', 'v2'), encoding='utf-8')
        rep = mirror.sync(self.s)
        self.assertEqual((rep['proposed'], rep['unchanged']), ([], 1))
        self.assertEqual(self.s.support(m['id']), 1)
        crlf = self.s.capture('p', 'line one\r\nline two', 'test', mode='manual', confirmed=True); self.s.flush()
        self.assertEqual(mirror.sync(self.s)['proposed'], [])
        with self.assertRaises(Exception): self.s.capture('p', 'release v2 ships friday', 'x', supersedes=m['id'])

    def test_13_malformed_front_matter_is_reported_not_fatal(self):
        m = self.s.capture('p', 'first', 'test', mode='manual', confirmed=True); self.s.flush()
        bad = self.s.root / 'markdown' / (m['id'] + '.md')
        bad.write_text('---\nid: 7\nversion: "x"\n---\nedited', encoding='utf-8')
        inbox = self.s.root / 'markdown' / 'inbox'; inbox.mkdir()
        (inbox / 'x.md').write_text('---\ncategory: ["fact"]\n---\nbody', encoding='utf-8')
        (inbox / 'ok.md').write_text('a good note', encoding='utf-8')
        rep = mirror.sync(self.s, 'p')
        self.assertEqual(len(rep['errors']), 2); self.assertEqual(len(rep['inbox_imported']), 1)

    def test_14_recall_does_not_wait_for_another_writer(self):
        self.s.capture('p', 'busy database read', 'test', mode='manual', confirmed=True)
        blocker = sqlite3.connect(self.s.db, timeout=1); blocker.execute('BEGIN IMMEDIATE')
        try:
            t = time.perf_counter()
            res = MemoryService(self.s).recall('p', 'busy', record_access=True)
            self.assertLess(time.perf_counter() - t, 3); self.assertEqual(len(res['results']), 1)
        finally:
            blocker.rollback(); blocker.close()

    def test_15_blocked_checkpoint_is_reported(self):
        self.s.capture('p', 'x', 'test', mode='manual', confirmed=True)
        reader = sqlite3.connect(self.s.db); reader.execute('BEGIN'); reader.execute('SELECT count(*) FROM memories').fetchone()
        self.s.capture('p', 'y', 'test', mode='manual', confirmed=True)
        try:
            out = ops.compact(self.s, vacuum=False)
            self.assertIn('error', out)
        finally:
            reader.rollback(); reader.close()

    def test_16_sentence_transformers_needs_a_revision_before_loading(self):
        from memory_merge.providers import SentenceTransformersEmbedder
        with self.assertRaises(ProviderConfigError): SentenceTransformersEmbedder('Qwen/Qwen3-Embedding-0.6B')
        doc = ops.doctor(self.s, env={'MM_EMBED_BACKEND': 'sentence-transformers', 'MM_EMBED_MODEL': 'Qwen/Qwen3-Embedding-0.6B'})
        self.assertIn('not loaded', {c['check']: c['detail'] for c in doc['checks']}['embedding_config'])

    def test_18_confirmed_capture_approves_a_queued_duplicate(self):
        q = self.s.capture('p', 'Ship on Tuesdays', 'agent')
        r = self.s.capture('p', 'ship on tuesdays', 'user', mode='manual', confirmed=True)
        self.assertEqual((r['id'], r['status']), (q['id'], 'approved'))

    def test_21_session_metadata_redacted_and_bad_records_isolated(self):
        recs = [{'type': 'session', 'id': 's1', 'title': 'api_key=' + TOKEN, 'meta': {'note': TOKEN}},
                {'type': 'turn', 'session': 's1', 'seq': 1, 'role': 'user', 'content': 'ok', 'created': {'bad': 1}},
                {'type': 'turn', 'session': 's1', 'seq': 2, 'role': ['user'], 'content': 'bad role'},
                {'type': 'session', 'id': 's2', 'title': 'second session'}]
        rep = sessions.import_records(self.s, recs, 'p')
        self.assertEqual((rep['sessions'], len(rep['errors'])), (2, 2))
        self.assertEqual(files_containing(self.root / 'data', TOKEN[:20]), [])
        with self.assertRaises(InvalidInput): sessions.search(self.s, 'p', 'x', limit=-1)

    def test_22_forgotten_document_cannot_be_reapproved(self):
        d = self.root / 'docs'; d.mkdir(); (d / 'a.md').write_text('v1 body', encoding='utf-8')
        first = ingest.import_path(self.s, 'p', d)['imported'][0]['document']
        ingest.review_document(self.s, 'p', first, 'forget')
        with self.assertRaises(InvalidTransition): ingest.review_document(self.s, 'p', first, 'approve')

    def test_24_newer_database_untouched_and_unrecallable_vectors_not_migrated(self):
        db = self.root / 'newer' / 'memory.sqlite3'; db.parent.mkdir()
        c = sqlite3.connect(db); c.execute('CREATE TABLE t(x)'); c.execute('PRAGMA user_version=99'); c.close()
        raw = db.read_bytes()
        with self.assertRaises(Exception): Store(db.parent)
        self.assertEqual(db.read_bytes(), raw)
        v1 = self.root / 'v1'; old = StoreV01(v1)
        m = old.capture('p', 'rejected with vector', 'test'); old.review('p', m['id'], 'reject')
        with old.connect() as con: con.execute('INSERT INTO vectors VALUES(?,?,?,?,?)', (m['id'], 'x|m', 2, m['digest'], '[1, 0]'))
        with Store(v1).connect() as con: self.assertEqual(con.execute('SELECT count(*) FROM embeddings').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
