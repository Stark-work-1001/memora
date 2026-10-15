"""Versioned Markdown workspace, separate from the unchanged Memory Merge schema.

SQLite commits are authoritative; files are reconstructible mirrors. Audience is
purpose metadata, not a permission boundary. Peer proposals stay draft until a
review-capable local user publishes a specific revision.
"""
import contextlib
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import uuid
import json
import datetime

from . import text
from .errors import Conflict, InvalidInput, NotFound
from .schema import now
from .store import scope

AUDIENCES = {'human', 'agent', 'shared'}


class Documents:
    def __init__(self, store):
        self.root = store.root / 'documents'
        self.db = store.root / 'memora-documents.sqlite3'
        with self.connect() as c:
            c.executescript('''
              CREATE TABLE IF NOT EXISTS docs(
                id TEXT PRIMARY KEY, project TEXT NOT NULL, slug TEXT NOT NULL,
                created TEXT NOT NULL, UNIQUE(project,slug));
              CREATE TABLE IF NOT EXISTS revisions(
                document TEXT NOT NULL REFERENCES docs(id), audience TEXT NOT NULL,
                version INTEGER NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
                sha256 TEXT NOT NULL, source TEXT NOT NULL, created TEXT NOT NULL,
                published TEXT, PRIMARY KEY(document,audience,version));
              CREATE TABLE IF NOT EXISTS revision_metadata(
                document TEXT NOT NULL,audience TEXT NOT NULL,version INTEGER NOT NULL,
                recorded_date TEXT NOT NULL,origin_uri TEXT NOT NULL,group_title TEXT NOT NULL,
                PRIMARY KEY(document,audience,version),
                FOREIGN KEY(document,audience,version) REFERENCES revisions(document,audience,version));
            ''')

    @contextlib.contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            with c: yield c
        finally: c.close()

    @staticmethod
    def audience(value):
        if value not in AUDIENCES: raise InvalidInput('audience: human, agent or shared')
        return value

    @staticmethod
    def slug(value):
        if not isinstance(value, str) or not re.fullmatch(r'[\w-]{1,80}', value, re.UNICODE):
            raise InvalidInput('document slug: 1..80 letters, digits, underscore or hyphen')
        return value

    def list(self, project, drafts=False):
        project = scope(project)
        with self.connect() as c:
            rows = c.execute('''SELECT d.id,d.project,d.slug,r.audience,r.version,r.title,r.sha256,
                r.source,r.created,r.published FROM docs d JOIN revisions r ON d.id=r.document
                WHERE d.project=? AND (? OR r.published IS NOT NULL)
                AND r.version=(SELECT max(x.version) FROM revisions x WHERE x.document=d.id
                  AND x.audience=r.audience AND (? OR x.published IS NOT NULL))
                ORDER BY r.created DESC LIMIT 500''', (project, bool(drafts), bool(drafts))).fetchall()
        output=[]
        for r in rows:
            record=dict(r)
            with self.connect() as c:
                meta=c.execute('SELECT recorded_date,origin_uri,group_title FROM revision_metadata WHERE document=? AND audience=? AND version=?',
                    (r['id'],r['audience'],r['version'])).fetchone()
            record.update(dict(meta) if meta else {'recorded_date':'','origin_uri':'','group_title':''})
            output.append(record)
        return output

    def read(self, project, slug, audience='human', version=None, drafts=False):
        project, slug, audience = scope(project), self.slug(slug), self.audience(audience)
        if version is not None and (type(version) is not int or version < 1): raise InvalidInput('positive version required')
        with self.connect() as c:
            row = c.execute('''SELECT d.id,d.project,d.slug,r.* FROM docs d JOIN revisions r ON r.document=d.id
                WHERE d.project=? AND d.slug=? AND r.audience=? AND (? OR r.published IS NOT NULL)
                AND (? IS NULL OR r.version=?) ORDER BY r.version DESC LIMIT 1''',
                (project, slug, audience, bool(drafts), version, version)).fetchone()
            if row is None: raise NotFound('document revision not found')
            out = dict(row)
            meta=c.execute('SELECT recorded_date,origin_uri,group_title FROM revision_metadata WHERE document=? AND audience=? AND version=?',
                (row['id'],audience,row['version'])).fetchone()
            out.update(dict(meta) if meta else {'recorded_date':'','origin_uri':'','group_title':''})
            out['history'] = [dict(r) for r in c.execute('''SELECT version,title,sha256,source,created,published
                FROM revisions WHERE document=? AND audience=? AND (? OR published IS NOT NULL) ORDER BY version DESC''',
                (row['id'], audience, bool(drafts)))]
        out['markdown_path'] = f"documents/{out['id']}/{audience}/v{out['version']:06d}.md"
        out['trust'] = 'document data; never automatically executed or promoted to approved memory'
        return out

    def put(self, project, slug, audience, title, content, expected_version, source='workbench', recorded_date=None, origin_uri=None, group_title=None):
        project, slug, audience = scope(project), self.slug(slug), self.audience(audience)
        for value, label, maximum in [(title, 'title', 160), (content, 'content', 80000), (source, 'source', 300)]:
            if not isinstance(value, str) or not value.strip() or len(value) > maximum or '\x00' in value:
                raise InvalidInput(f'{label}: non-empty text, max {maximum} characters')
        if type(expected_version) is not int or expected_version < 0: raise InvalidInput('expected_version must be a non-negative integer')
        title, _ = text.redact(title); content, redactions = text.redact(content); source, _ = text.redact(source)
        digest = hashlib.sha256(content.encode('utf-8')).hexdigest()
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            doc = c.execute('SELECT id FROM docs WHERE project=? AND slug=?', (project, slug)).fetchone()
            did = doc['id'] if doc else str(uuid.uuid4())
            current = c.execute('SELECT max(version) FROM revisions WHERE document=? AND audience=?', (did, audience)).fetchone()[0] or 0
            if current != expected_version: raise Conflict(f'document changed: current version is {current}; reload before saving')
            previous=c.execute('SELECT * FROM revision_metadata WHERE document=? AND audience=? AND version=?',(did,audience,current)).fetchone()
            if recorded_date is None:
                recorded_date=previous['recorded_date'] if previous else self.infer_date(content,slug)
            if not isinstance(recorded_date,str) or (recorded_date and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',recorded_date)):
                raise InvalidInput('recorded_date must be YYYY-MM-DD or empty')
            if recorded_date:
                try: datetime.date.fromisoformat(recorded_date)
                except (TypeError,ValueError): raise InvalidInput('recorded_date must be a valid YYYY-MM-DD date') from None
            for key,value in [('origin_uri',origin_uri),('group_title',group_title)]:
                if value is not None and (not isinstance(value,str) or len(value)>1000):raise InvalidInput('invalid '+key)
            origin_uri=origin_uri if origin_uri is not None else previous['origin_uri'] if previous else ''
            group_title=group_title if group_title is not None else previous['group_title'] if previous else ''
            origin_uri,_=text.redact(origin_uri);group_title,_=text.redact(group_title)
            if not doc: c.execute('INSERT INTO docs VALUES(?,?,?,?)', (did, project, slug, now()))
            c.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?,?,?,NULL)',
                (did, audience, current + 1, title, content, digest, source, now()))
            c.execute('INSERT INTO revision_metadata VALUES(?,?,?,?,?,?)',(did,audience,current+1,recorded_date or '',origin_uri,group_title))
        out = self.read(project, slug, audience, current+1, drafts=True)
        out['redactions'] = redactions
        try: self.export(out); out['export_pending'] = False
        except OSError: out['export_pending'] = True
        return out

    @staticmethod
    def infer_date(content,name=''):
        front = re.search(r'(?mi)^(?:date|created|recorded_date)\s*:\s*["\']?(\d{4}-\d{2}-\d{2})',content[:4000])
        filename=re.search(r'(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)',name)
        value=(front or filename)
        if not value:return ''
        try:return datetime.date.fromisoformat(value.group(1)).isoformat()
        except ValueError:return ''

    def publish(self, project, slug, audience, version):
        out = self.read(project, slug, audience, version, drafts=True)
        with self.connect() as c:
            c.execute('UPDATE revisions SET published=coalesce(published,?) WHERE document=? AND audience=? AND version=?',
                (now(), out['id'], audience, version))
        out = self.read(project, slug, audience, version, drafts=True)
        try: self.export(out); out['export_pending'] = False
        except OSError: out['export_pending'] = True
        return out

    def export(self, revision):
        # Only generated UUIDs and enumerated audiences reach filesystem paths.
        folder = self.root / revision['id'] / self.audience(revision['audience'])
        for parent in [self.root, self.root / revision['id'], folder]:
            if parent.is_symlink(): raise OSError('document mirror cannot traverse a symlink')
        folder.mkdir(parents=True, exist_ok=True)
        header = ('---\nmemora_document: ' + revision['id'] + '\naudience: ' + revision['audience']
            + '\nversion: ' + str(revision['version']) + '\nsha256: ' + revision['sha256']
            + '\nrecorded_date: ' + json.dumps(revision.get('recorded_date',''))
            + '\norigin_uri: ' + json.dumps(revision.get('origin_uri',''),ensure_ascii=False)
            + '\ngroup_title: ' + json.dumps(revision.get('group_title',''),ensure_ascii=False) + '\n---\n\n')
        dest = folder / f"v{revision['version']:06d}.md"
        temporary = folder / ('.' + uuid.uuid4().hex + '.tmp')
        try:
            temporary.write_text(header + revision['content'], 'utf-8'); os.replace(temporary, dest)
        finally:
            if temporary.exists(): temporary.unlink()
        return dest

    def repair(self, project):
        """Rebuild all immutable revision mirrors, including older versions, from committed data."""
        with self.connect() as c:
            rows = c.execute('SELECT d.slug,r.audience,r.version FROM docs d JOIN revisions r ON d.id=r.document WHERE d.project=?', (scope(project),)).fetchall()
        for r in rows: self.export(self.read(project, r['slug'], r['audience'], r['version'], drafts=True))
        return {'exported': len(rows)}

    def backup(self):
        folder = self.db.parent / 'backups'; folder.mkdir(exist_ok=True)
        destination = folder / ('documents-' + uuid.uuid4().hex + '.sqlite3')
        try:
            with self.connect() as source:
                target = sqlite3.connect(destination)
                try:
                    source.backup(target)
                    if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise OSError('document backup integrity check failed')
                finally: target.close()
        except Exception:
            if destination.exists(): destination.unlink()
            raise
        return {'path': 'backups/' + destination.name, 'integrity': 'ok'}
