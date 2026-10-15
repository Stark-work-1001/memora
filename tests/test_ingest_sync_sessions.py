import json
import os
import unittest
from pathlib import Path

from memory_merge import ingest, mirror, sessions
from memory_merge.errors import InvalidInput, LimitExceeded
from memory_merge.store import Store
from tests.helpers import tmpdir

DOC = """---
title: Atlas runbook
---
# Atlas

Intro paragraph.

## Deploy

Run `cargo dist build` then upload.

```bash
cargo dist build

cargo dist upload
```

## Secrets

The upload token is api_key=supersecret123 for now.
"""


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tmpdir(); self.root = Path(self.tmp.name); self.s = Store(self.root / 'data')
        self.docs = self.root / 'docs'; self.docs.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def chunks(self, doc_id):
        with self.s.connect() as c:
            return [dict(r) for r in c.execute('SELECT * FROM memories WHERE doc_id=? ORDER BY created', (doc_id,))]

    def test_markdown_chunks_cite_heading_and_lines_and_redact(self):
        (self.docs / 'runbook.md').write_text(DOC, encoding='utf-8')
        rep = ingest.import_path(self.s, 'atlas', self.docs)
        doc = rep['imported'][0]
        self.assertEqual((doc['status'], doc['redactions']), ('pending', 1))
        chunks = self.chunks(doc['document'])
        locs = [json.loads(c['locator']) for c in chunks]
        self.assertEqual(locs[0], {'heading': ['Atlas'], 'lines': [6, 6], 'path': 'runbook.md'})
        deploy = next(c for c, l in zip(chunks, locs) if l['heading'] == ['Atlas', 'Deploy'])
        self.assertIn('cargo dist upload', deploy['content'])  # fenced code kept with its section
        self.assertTrue(deploy['content'].startswith('Atlas > Deploy'))
        self.assertTrue(all('supersecret123' not in c['content'] for c in chunks))
        self.assertEqual(self.s.recall('atlas', 'cargo dist'), [])  # pending documents are not recalled
        ingest.review_document(self.s, 'atlas', doc['document'], 'approve')
        hit = self.s.recall('atlas', 'cargo dist upload')[0]
        self.assertEqual((hit['kind'], hit['category']), ('chunk', 'knowledge'))
        self.assertEqual(hit['locator']['heading'], ['Atlas', 'Deploy'])

    def test_reimport_unchanged_and_new_version_supersedes_on_approval(self):
        f = self.docs / 'notes.md'; f.write_text('# Notes\n\nversion one text\n', encoding='utf-8')
        first = ingest.import_path(self.s, 'p', self.docs, approve=True)['imported'][0]
        self.assertEqual(ingest.import_path(self.s, 'p', self.docs)['unchanged'], 1)
        f.write_text('# Notes\n\nversion two text\n', encoding='utf-8')
        second = ingest.import_path(self.s, 'p', self.docs)['imported'][0]
        self.assertEqual(len(self.s.recall('p', 'version text')), 1)  # pending v2 changes nothing yet
        ingest.review_document(self.s, 'p', second['document'], 'approve')
        self.assertEqual([r['content'] for r in self.s.recall('p', 'version text')], ['Notes\nversion two text'])
        self.assertEqual({d['id']: d['status'] for d in ingest.list_documents(self.s, 'p')}[first['document']], 'superseded')

    def test_formats_and_hostile_input(self):
        (self.docs / 'b.html').write_text('<DL><DT><H3>Dev</H3><DL><DT><A HREF="https://sqlite.org/fts5.html">FTS5</A><DD>tokenizers</DL>'
                                          '<DT><A HREF="javascript:alert(1)">bad</A></DL>', encoding='utf-8')
        (self.docs / 'h.jsonl').write_text(json.dumps({'title': 'Book', 'text': 'a highlighted line', 'locator': {'page': 12}}) + '\n', encoding='utf-8')
        (self.docs / 'bin.txt').write_bytes(b'\x00\x01binary')
        (self.docs / 'latin1.txt').write_bytes('caf\xe9'.encode('latin-1'))
        rep = ingest.import_path(self.s, 'p', self.docs, approve=True)
        self.assertEqual({e['uri'] for e in rep['errors']}, {'bin.txt', 'latin1.txt'})
        bm = self.s.recall('p', 'FTS5 tokenizers')[0]
        self.assertEqual(bm['locator']['folder'], ['Dev']); self.assertNotIn('javascript', json.dumps(self.s.list_memories('p')))
        self.assertEqual(self.s.recall('p', 'highlighted')[0]['locator']['page'], 12)
        with self.assertRaises(InvalidInput): ingest.import_path(self.s, 'p', self.root / 'docs' / 'b.html', root=self.root / 'elsewhere')
        old = ingest.MAX_BYTES; ingest.MAX_BYTES = 10
        try:
            with self.assertRaises(LimitExceeded): ingest.import_file(self.s, 'p', self.docs / 'h.jsonl', 'h2.jsonl')
        finally:
            ingest.MAX_BYTES = old

    def test_symlinks_are_not_followed(self):
        outside = self.root / 'secret.md'; outside.write_text('outside the import root', encoding='utf-8')
        try:
            os.symlink(outside, self.docs / 'link.md')
        except (OSError, NotImplementedError):
            self.skipTest('symlinks need privileges on this platform')
        rep = ingest.import_path(self.s, 'p', self.docs)
        self.assertEqual(rep['skipped'][0]['uri'], 'link.md'); self.assertEqual(rep['imported'], [])


class MirrorSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tmpdir(); self.s = Store(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_edits_become_pending_revisions(self):
        m = self.s.capture('p', 'Deploys happen on Tuesday', 'test', mode='manual', confirmed=True, tags=['ops']); self.s.flush()
        f = self.s.root / 'markdown' / (m['id'] + '.md')
        meta, body = mirror.parse(f.read_text(encoding='utf-8'))
        self.assertEqual((meta['id'], meta['tags'], body), (m['id'], ['ops'], 'Deploys happen on Tuesday'))
        f.write_text(f.read_text(encoding='utf-8').replace('\n', '\r\n'), encoding='utf-8', newline='')  # editor converts EOLs
        self.assertEqual(mirror.sync(self.s)['proposed'], [])
        f.write_text(f.read_text(encoding='utf-8').replace('Tuesday', 'Thursday'), encoding='utf-8')
        rep = mirror.sync(self.s); self.assertEqual(len(rep['proposed']), 1)
        self.assertEqual(mirror.sync(self.s)['proposed'][0]['proposal'], rep['proposed'][0]['proposal'])  # idempotent
        self.assertEqual(self.s.get('p', m['id'])['status'], 'approved')  # nothing changed until review
        self.s.review('p', rep['proposed'][0]['proposal'], 'approve')
        self.assertEqual(self.s.get('p', m['id'])['status'], 'superseded')
        self.assertEqual(self.s.recall('p', 'deploys')[0]['content'], 'Deploys happen on Thursday')

    def test_stale_files_are_not_proposed_and_inbox_imports(self):
        m = self.s.capture('p', 'original body', 'test', mode='manual', confirmed=True); self.s.flush()
        f = self.s.root / 'markdown' / (m['id'] + '.md')
        stale = f.read_text(encoding='utf-8').replace('original body', 'edited old copy')
        self.s.review('p', m['id'], 'archive'); self.s.flush()  # database moves on
        f.write_text(stale, encoding='utf-8')
        rep = mirror.sync(self.s)
        self.assertEqual(rep['proposed'], []); self.assertEqual(rep['stale'][0]['db_version'], 2)
        inbox = self.s.root / 'markdown' / 'inbox'; inbox.mkdir()
        (inbox / 'idea.md').write_text('---\nproject: "p"\n---\nA dropped note', encoding='utf-8')
        rep = mirror.sync(self.s)
        self.assertEqual(rep['inbox_imported'][0]['status'], 'pending')
        self.assertFalse((inbox / 'idea.md').exists())


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tmpdir(); self.s = Store(Path(self.tmp.name) / 'data')

    def tearDown(self):
        self.tmp.cleanup()

    def test_records_import_is_idempotent_and_redacted(self):
        recs = [{'type': 'session', 'id': 's1', 'project': 'p', 'agent': 'codex', 'title': 'migration chat'},
                {'type': 'turn', 'session': 's1', 'seq': 1, 'role': 'user', 'content': 'my token is api_key=supersecret123'},
                {'type': 'turn', 'session': 's1', 'seq': 2, 'role': 'assistant', 'content': 'Use alembic for the migration'},
                {'type': 'memory', 'session': 's1', 'content': 'Use alembic for migrations', 'category': 'decision'},
                {'type': 'turn', 'session': 'nope', 'seq': 1, 'role': 'user', 'content': 'orphan'}]
        rep = sessions.import_records(self.s, recs, 'p')
        self.assertEqual((rep['sessions'], rep['turns'], rep['redactions'], len(rep['memories']), len(rep['errors'])), (1, 2, 1, 1, 1))
        again = sessions.import_records(self.s, recs, 'p')
        self.assertEqual((again['sessions'], again['turns']), (0, 0)); self.assertEqual(again['memories'], rep['memories'])
        sid = sessions.list_sessions(self.s, 'p')[0]['id']
        shown = sessions.show(self.s, sid)
        self.assertNotIn('supersecret123', json.dumps(shown)); self.assertEqual(shown['memories'], rep['memories'])
        self.assertEqual(self.s.get('p', rep['memories'][0])['session_id'], sid)
        self.assertEqual(sessions.search(self.s, 'p', 'alembic')[0]['seq'], 2)
        self.assertEqual(self.s.recall('p', 'alembic'), [])  # archive and pending memory never enter recall
        sessions.purge(self.s, sid)
        self.assertEqual(sessions.search(self.s, 'p', 'alembic'), [])

    def test_claude_code_transcript_and_hook(self):
        t = Path(self.tmp.name) / 'transcript.jsonl'
        lines = [{'type': 'summary', 'summary': 'Fix flaky test'},
                 {'type': 'user', 'sessionId': 'abc', 'timestamp': '2026-10-01T10:00:00Z', 'message': {'role': 'user', 'content': 'Why is test_x flaky?'}},
                 {'type': 'assistant', 'sessionId': 'abc', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': 'It depends on wall-clock time.'},
                                                                                                         {'type': 'tool_use', 'name': 'Bash', 'input': {'command': 'pytest'}}]}},
                 {'type': 'user', 'sessionId': 'abc', 'message': {'role': 'user', 'content': [{'type': 'tool_result', 'content': 'HUGE OUTPUT'}]}}]
        t.write_text('\n'.join(json.dumps(x) for x in lines), encoding='utf-8')
        out = sessions.hook(self.s, json.dumps({'transcript_path': str(t), 'cwd': '/work/my repo'}))
        self.assertEqual((out['archived'], out['project'], out['turns']), (True, 'my-repo', 2))
        shown = sessions.show(self.s, 'abc')
        self.assertEqual(shown['title'], 'Fix flaky test'); self.assertIn('[tool_use: Bash]', shown['turns'][1]['content'])
        self.assertNotIn('HUGE OUTPUT', json.dumps(shown))
        self.assertEqual(sessions.hook(self.s, 'not json')['archived'], False)  # never raises into the host
        self.assertEqual(sessions.hook(self.s, {'transcript_path': '/missing'})['archived'], False)


class PdfImportTests(unittest.TestCase):
    @staticmethod
    def minimal_pdf(pages):
        """A small valid PDF with one text line per page (Helvetica, no compression)."""
        objs = ['<< /Type /Catalog /Pages 2 0 R >>', None]
        kids = []
        for text in pages:
            stream = f'BT /F1 18 Tf 72 720 Td ({text}) Tj ET'.encode('latin-1')
            page_no, content_no = len(objs) + 1, len(objs) + 2
            kids.append(f'{page_no} 0 R')
            objs.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_no} 0 R /Resources << /Font << /F1 FONT 0 R >> >> >>')
            objs.append(('stream', stream))
        font_no = len(objs) + 1
        objs.append('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
        objs[1] = f'<< /Type /Pages /Kids [{" ".join(kids)}] /Count {len(pages)} >>'
        out, offsets = bytearray(b'%PDF-1.4\n'), []
        for i, obj in enumerate(objs, 1):
            offsets.append(len(out))
            if isinstance(obj, tuple):
                out += f'{i} 0 obj << /Length {len(obj[1])} >>\nstream\n'.encode() + obj[1] + b'\nendstream endobj\n'
            else:
                out += f'{i} 0 obj {obj.replace("FONT", str(font_no))} endobj\n'.encode()
        xref = len(out)
        out += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode() + ''.join(f'{o:010d} 00000 n \n' for o in offsets).encode()
        out += f'trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
        return bytes(out)

    def test_pdf_pages_become_cited_chunks(self):
        try:
            import pypdf  # noqa: F401
        except ImportError:
            self.skipTest('pypdf not installed (optional extra)')
        with tmpdir() as d:
            root = Path(d); docs = root / 'docs'; docs.mkdir()
            (docs / 'manual.pdf').write_bytes(self.minimal_pdf(['Backups run nightly at two', 'Restore drills happen monthly']))
            s = Store(root / 'data')
            rep = ingest.import_path(s, 'p', docs, approve=True)
            self.assertEqual((rep['errors'], rep['imported'][0]['chunks']), ([], 2))
            hit = s.recall('p', 'restore drills')[0]
            self.assertEqual((hit['locator']['page'], hit['locator']['path']), (2, 'manual.pdf'))

if __name__ == '__main__':
    unittest.main()
