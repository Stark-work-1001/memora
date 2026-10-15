"""SQLite is authoritative; Markdown is a retryable materialized view.

Lifecycle (TRANSITIONS below is the single source of truth):
  pending -> approved | rejected        approved -> archived | superseded | rejected
  archived | superseded -> approved     any -> deleted (forget, soft)    deleted -> purged (hard)
Only approved records are recalled by default; archived and superseded ones on request. Pending,
rejected and deleted content is never in the full-text index or the vector table, so it cannot leak
into retrieval through a filter bug.
"""
import base64
import contextlib
import json
import re
import sqlite3
import uuid
from pathlib import Path

from . import schema, text
from .errors import Conflict, InvalidInput, InvalidTransition, LimitExceeded, NotFound, SensitiveContent, StorageBusy
from .schema import INDEXED_STATUSES, now

CATEGORIES = {'fact', 'decision', 'preference', 'procedure', 'lesson', 'knowledge'}
RELATIONS = {'supports', 'contradicts', 'supersedes', 'related'}
STATUSES = ('pending', 'approved', 'rejected', 'deleted', 'archived', 'superseded')
POLARITIES = ('positive', 'negative')
KINDS = ('memory', 'chunk')
# Durable personal preferences live in this reserved scope and are recalled alongside every project.
# The leading colon was invalid in 0.1 project names, so it cannot collide with existing data.
USER_SCOPE = ':user'
MAX_CONTENT, MAX_QUERY, MAX_PAGE, MAX_RECALL = 16000, 1000, 1000, 50

# action -> (states it may start from, resulting state)
TRANSITIONS = {
    'approve': ({'pending', 'rejected'}, 'approved'),
    'reject': ({'pending', 'approved'}, 'rejected'),
    'archive': ({'approved'}, 'archived'),
    'restore': ({'archived', 'superseded'}, 'approved'),
    'forget': (set(STATUSES) - {'deleted'}, 'deleted'),
}
# BM25 column weights for memory_fts(terms, chars, tags, id). Tuned on the dev split only.
BM25_WEIGHTS = (1.0, 0.4, 1.5, 0.0)


def scope(project):
    if project == USER_SCOPE: return project
    if not isinstance(project, str) or not re.fullmatch(r'[\w-]{1,80}', project):
        raise InvalidInput('project must be 1-80 letters, digits, underscore or hyphen (or ":user")')
    return project


def classify(text_):
    t = text_.lower()
    if any(x in t for x in ['选择', '决定', '决策', 'chose', 'decision', 'decided']): return 'decision'
    if any(x in t for x in ['偏好', '喜欢', 'prefer']): return 'preference'
    if any(x in t for x in ['步骤', 'procedure', 'steps to', 'how to']): return 'procedure'
    if any(x in t for x in ['教训', '踩坑', 'lesson', 'learned']): return 'lesson'
    return 'fact'


_NEGATIVE = re.compile(r"^\s*(?:(?:do not|don'?t|never|avoid|stop)\b|(?:不要|别再?|禁止|切勿|避免|千万别|不能|不可以))", re.I)


def detect_polarity(text_):
    """'negative' = a do-not-repeat memory. Only a leading prohibition counts; callers can override."""
    return 'negative' if _NEGATIVE.search(text_) else 'positive'


def validate_content(content):
    if not isinstance(content, str) or not 1 <= len(content.strip()) <= MAX_CONTENT:
        raise InvalidInput(f'content must contain 1-{MAX_CONTENT} characters')
    _screen(content, 'content')
    return content.strip()


def _screen(value, field):
    kinds = text.secret_kinds(value)
    if kinds:
        raise SensitiveContent(f'possible credential in {field}: redact before capture',
                               hint='replace the secret with a placeholder such as <API_KEY>', kinds=kinds, field=field)


def _source(source):
    if not isinstance(source, str) or not 1 <= len(source) <= 300 or any(ch in source for ch in '\r\n\x00'):
        raise InvalidInput('source required: one line, max 300 characters')
    _screen(source, 'source')
    return source


def _tags(tags):
    tags = tags or []
    if not isinstance(tags, list) or len(tags) > 20 or any(not isinstance(t, str) or not 1 <= len(t.strip()) <= 60 for t in tags):
        raise InvalidInput('tags: up to 20 strings of 1-60 characters')
    for t in tags: _screen(t, 'tags')
    return sorted({t.strip() for t in tags})


def _limit(value, lo, hi, name):
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise LimitExceeded(f'{name} must be an integer {lo}..{hi}')
    return value


def public(row):
    """Row -> API dict. JSON columns are decoded; the internal duplicate digest is dropped."""
    d = dict(row)
    d.pop('norm_digest', None)
    d['tags'] = json.loads(d.get('tags') or '[]')
    if d.get('locator'): d['locator'] = json.loads(d['locator'])
    return d


def _cursor_encode(created, id):
    return base64.urlsafe_b64encode(json.dumps([created, id]).encode()).decode().rstrip('=')


def _cursor_decode(cursor):
    try:
        created, id = json.loads(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)))
        if not isinstance(created, str) or not isinstance(id, str): raise ValueError
        return created, id
    except (ValueError, TypeError) as e:
        raise InvalidInput('invalid cursor') from e


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'memory.sqlite3'
        self.migration = schema.ensure(self.db, self.root)

    @contextlib.contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        # Zero freed pages so forgotten/purged content does not linger in free space. FTS5 shadow
        # tables need more than this; purge() rebuilds the index as well (see docs/OPERATIONS.md).
        c.execute('PRAGMA secure_delete=ON')
        try:
            with c: yield c
        except sqlite3.OperationalError as e:
            if 'locked' in str(e) or 'busy' in str(e):
                raise StorageBusy('database is busy: another process holds the write lock', hint='retry shortly') from e
            raise
        finally:
            c.close()

    # --- internals ------------------------------------------------------------------------------
    def _audit(self, c, id, action, digest, actor='local'):
        c.execute('INSERT INTO audit(id, action, digest, created, actor) VALUES(?,?,?,?,?)', (id, action, digest, now(), actor))

    def _outbox(self, c, id, version):
        c.execute('INSERT OR REPLACE INTO outbox VALUES(?,?)', (id, version))

    def _get(self, c, project, id):
        row = c.execute('SELECT * FROM memories WHERE project=? AND id=?', (scope(project), id)).fetchone()
        if row is None: raise NotFound('memory not found in project', id=id)
        return row

    def get(self, project, id):
        with self.connect() as c: return public(self._get(c, project, id))

    def _insert(self, c, project, content, source, *, mode, status, category, tags, event_id=None,
                kind='memory', polarity='positive', doc_id=None, session_id=None, locator=None, actor='local'):
        """Insert one validated row inside the caller's transaction and maintain derived state."""
        id, t, d = str(uuid.uuid4()), now(), text.digest(content)
        c.execute('''INSERT INTO memories(id, project, content, source, event_id, digest, mode, status, category,
            tags, created, updated, version, kind, polarity, norm_digest, doc_id, session_id, locator)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?,?,?,?)''',
            (id, project, content, source, event_id, d, mode, status, category, json.dumps(tags, ensure_ascii=False),
             t, t, kind, polarity, text.norm_digest(content), doc_id, session_id,
             json.dumps(locator, ensure_ascii=False) if locator else None))
        if status in INDEXED_STATUSES: schema.fts_insert(c, id, content, json.dumps(tags))
        self._outbox(c, id, 1)
        self._audit(c, id, 'capture' if kind == 'memory' else 'import', d, actor)
        return c.execute('SELECT * FROM memories WHERE id=?', (id,)).fetchone()

    def _by_event(self, c, project, source, event_id):
        row = c.execute('SELECT * FROM memories WHERE project=? AND source=? AND event_id=?', (project, source, event_id)).fetchone()
        if row: return row, False
        row = c.execute('''SELECT m.* FROM sightings s JOIN memories m ON m.id=s.memory_id
            WHERE m.project=? AND s.source=? AND s.event_id=?''', (project, source, event_id)).fetchone()
        return row, True

    # --- capture --------------------------------------------------------------------------------
    def capture(self, project, content, source, mode='auto', confirmed=False, event_id=None, category=None,
                tags=None, polarity=None, supersedes=None, session_id=None, locator=None, actor='local'):
        """Store a candidate. Automatic capture is always pending; only an explicit manual capture
        may be confirmed. An exact or whitespace/case-variant duplicate in the same project is not
        stored twice: the new source is recorded as a sighting (independent support) instead."""
        scope(project); content = validate_content(content)
        if mode not in {'auto', 'manual'} or (confirmed and mode != 'manual'):
            raise InvalidInput('only explicit manual capture may be confirmed')
        source = _source(source)
        if event_id is not None and (not isinstance(event_id, str) or not 1 <= len(event_id) <= 200):
            raise InvalidInput('bad event_id: 1-200 characters')
        if event_id is not None: _screen(event_id, 'event_id')
        category = category or classify(content)
        if category not in CATEGORIES: raise InvalidInput('unknown category', allowed=sorted(CATEGORIES))
        polarity = polarity or detect_polarity(content)
        if polarity not in POLARITIES: raise InvalidInput('polarity must be positive or negative')
        tags = _tags(tags)
        if locator is not None and not isinstance(locator, dict): raise InvalidInput('locator must be an object')
        d, nd = text.digest(content), text.norm_digest(content)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if event_id:
                old, via_sighting = self._by_event(c, project, source, event_id)
                if old:
                    same = old['norm_digest'] == nd if via_sighting else old['digest'] == d
                    if not same: raise Conflict('event_id reused with different content', id=old['id'])
                    return public(old)
            dup = c.execute("""SELECT * FROM memories WHERE project=? AND norm_digest=? AND status!='deleted'
                ORDER BY created LIMIT 1""", (project, nd)).fetchone()
            if dup:
                if supersedes is not None:
                    raise Conflict('this revision duplicates an existing memory (after normalising case and whitespace)',
                                   hint='link the existing memory with relation supersedes instead', id=dup['id'])
                c.execute('INSERT OR IGNORE INTO sightings VALUES(?,?,?,?)', (dup['id'], source, event_id or '', now()))
                self._audit(c, dup['id'], 'sighting', dup['digest'], actor)
                if confirmed and dup['status'] in ('pending', 'rejected'):
                    # An explicit, trusted confirmation of content that is already queued (or was rejected
                    # earlier) approves that record rather than being silently absorbed into it.
                    self._set_status(c, dup, 'approved', 'approve', actor)
                    dup = c.execute('SELECT * FROM memories WHERE id=?', (dup['id'],)).fetchone()
                return dict(public(dup), deduplicated=True, support=self._support(c, dup['id']))
            if supersedes is not None: self._get(c, project, supersedes)
            if session_id is not None and not c.execute('SELECT 1 FROM sessions WHERE id=? AND project=?', (session_id, project)).fetchone():
                raise NotFound('session not found in project', id=session_id)
            row = self._insert(c, project, content, source, mode=mode, status='approved' if confirmed else 'pending',
                               category=category, tags=tags, event_id=event_id, polarity=polarity,
                               session_id=session_id, locator=locator, actor=actor)
            if supersedes is not None:
                c.execute('INSERT OR IGNORE INTO edges(project, a, b, relation, created) VALUES(?,?,?,?,?)',
                          (project, row['id'], supersedes, 'supersedes', now()))
                if row['status'] == 'approved': self._enforce_supersedes(c, project, row['id'], actor)
            return public(row)

    def _support(self, c, id):
        """Distinct sources that asserted this content, including the original capture."""
        return 1 + c.execute('''SELECT count(DISTINCT source) FROM sightings
            WHERE memory_id=? AND source != (SELECT source FROM memories WHERE id=?)''', (id, id)).fetchone()[0]

    # --- lifecycle ------------------------------------------------------------------------------
    def _set_status(self, c, r, to, action, actor):
        was, will = r['status'] in INDEXED_STATUSES, to in INDEXED_STATUSES
        valid_until = now() if to in ('superseded', 'archived') else (None if to == 'approved' else r['valid_until'])
        v = r['version'] + 1
        c.execute('UPDATE memories SET status=?, updated=?, version=?, valid_until=? WHERE id=?', (to, now(), v, valid_until, r['id']))
        if was and not will: schema.fts_delete(c, r['id'])
        if will and not was: schema.fts_insert(c, r['id'], r['content'], r['tags'])
        if to in ('deleted', 'rejected'):
            # Derived copies of content the user removed must not outlive it.
            c.execute('DELETE FROM embeddings WHERE id=?', (r['id'],))
        if to == 'deleted' and not c.execute("SELECT 1 FROM memories WHERE digest=? AND id!=? AND status!='deleted'", (r['digest'], r['id'])).fetchone():
            # Judge advice paraphrases content. Rejected memories keep theirs: it is the calibration data.
            c.execute('DELETE FROM judgements WHERE digest=?', (r['digest'],))
        self._outbox(c, r['id'], v)
        self._audit(c, r['id'], action, r['digest'], actor)

    def _enforce_supersedes(self, c, project, id, actor):
        """Once the newer record is approved, approved records it supersedes leave default recall."""
        for e in c.execute("SELECT b FROM edges WHERE project=? AND a=? AND relation='supersedes'", (project, id)).fetchall():
            old = c.execute('SELECT * FROM memories WHERE id=?', (e['b'],)).fetchone()
            if old and old['status'] == 'approved': self._set_status(c, old, 'superseded', 'supersede', actor)

    def review(self, project, id, action, actor='local'):
        if action not in TRANSITIONS: raise InvalidInput('action must be one of ' + ', '.join(TRANSITIONS))
        allowed, to = TRANSITIONS[action]
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE'); r = self._get(c, project, id)
            if r['status'] == to: return public(r)  # idempotent retries
            if r['status'] == 'deleted': raise InvalidTransition('deleted memory cannot be silently restored')
            if r['status'] not in allowed: raise InvalidTransition(f"cannot {action} a {r['status']} memory")
            self._set_status(c, r, to, action, actor)
            if to == 'approved': self._enforce_supersedes(c, project, id, actor)
            return public(self._get(c, project, id))

    def link(self, project, a, b, relation, actor='local'):
        if relation not in RELATIONS or a == b: raise InvalidInput('invalid relation', allowed=sorted(RELATIONS))
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            ra = self._get(c, project, a); self._get(c, project, b)
            cur = c.execute('INSERT OR IGNORE INTO edges(project, a, b, relation, created) VALUES(?,?,?,?,?)', (project, a, b, relation, now()))
            if cur.rowcount: self._audit(c, a, 'link:' + relation, b, actor)
            if relation == 'supersedes' and ra['status'] == 'approved': self._enforce_supersedes(c, project, a, actor)
        return {'a': a, 'b': b, 'relation': relation}

    def unlink(self, project, a, b, relation, actor='local'):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            n = c.execute('DELETE FROM edges WHERE project=? AND a=? AND b=? AND relation=?', (scope(project), a, b, relation)).rowcount
            if not n: raise NotFound('relation not found')
            self._audit(c, a, 'unlink:' + relation, b, actor)
        return {'a': a, 'b': b, 'relation': relation, 'removed': True}

    def edges_of(self, project, ids):
        if not ids: return []
        marks = ','.join('?' * len(ids))
        with self.connect() as c:
            rows = c.execute(f'SELECT project, a, b, relation, created FROM edges WHERE project=? AND (a IN ({marks}) OR b IN ({marks}))',
                             [scope(project)] + list(ids) + list(ids))
            return [dict(r) for r in rows]

    # --- reads ----------------------------------------------------------------------------------
    def list_memories(self, project, status=None, limit=200):
        return self.page(project, status=status, limit=limit)['items']

    def page(self, project, status=None, limit=100, cursor=None, category=None, tag=None, kind=None):
        """Keyset pagination, newest first. next_cursor is None on the last page."""
        scope(project); _limit(limit, 1, MAX_PAGE, 'limit')
        sql, args = 'SELECT * FROM memories WHERE project=?', [project]
        if status:
            if status not in STATUSES: raise InvalidInput('unknown status', allowed=list(STATUSES))
            sql += ' AND status=?'; args.append(status)
        if category: sql += ' AND category=?'; args.append(category)
        if kind: sql += ' AND kind=?'; args.append(kind)
        if tag: sql += ' AND EXISTS (SELECT 1 FROM json_each(memories.tags) WHERE value=?)'; args.append(tag)
        if cursor:
            sql += ' AND (created, id) < (?, ?)'; args.extend(_cursor_decode(cursor))
        sql += ' ORDER BY created DESC, id DESC LIMIT ?'; args.append(limit + 1)
        with self.connect() as c: rows = c.execute(sql, args).fetchall()
        more = len(rows) > limit; rows = rows[:limit]
        return {'items': [public(r) for r in rows],
                'next_cursor': _cursor_encode(rows[-1]['created'], rows[-1]['id']) if more else None}

    def recall(self, project, query, limit=10, offset=0, include_user=True, statuses=('approved',),
               category=None, tags=None, kind=None, polarity=None, stop_chars=True, unigrams=True, stop_words=True, prefix=True):
        """Lexical retrieval: FTS5 BM25 over analysed text. Not semantic: a paraphrase that shares no
        terms with a memory is not found here -- that is what the optional embedding stage is for."""
        scope(project)
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= MAX_QUERY:
            raise InvalidInput(f'query must contain 1-{MAX_QUERY} characters')
        _limit(limit, 1, MAX_RECALL * 4, 'limit'); _limit(offset, 0, 500, 'offset')
        if set(statuses) - set(INDEXED_STATUSES): raise InvalidInput('only approved, archived or superseded memories are recallable')
        opts = dict(unigrams=unigrams, prefix=prefix)
        terms = text.query_terms(query, stop_chars=stop_chars, stop_words=stop_words, **opts)
        if not terms: terms = text.query_terms(query, stop_chars=False, stop_words=False, **opts)  # a query of only function words
        if not terms: return []
        projects = [project] + ([USER_SCOPE] if include_user and project != USER_SCOPE else [])
        weights = ', '.join(map(str, BM25_WEIGHTS))
        sql = (f'SELECT m.*, bm25(memory_fts, {weights}) AS rank FROM memory_fts JOIN memories m ON m.id = memory_fts.id '
               f"WHERE memory_fts MATCH ? AND m.project IN ({','.join('?' * len(projects))}) "
               f"AND m.status IN ({','.join('?' * len(statuses))})")
        args = [text.fts_query(terms)] + projects + list(statuses)
        if category: sql += ' AND m.category=?'; args.append(category)
        if kind: sql += ' AND m.kind=?'; args.append(kind)
        if polarity: sql += ' AND m.polarity=?'; args.append(polarity)
        for t in tags or []:
            sql += ' AND EXISTS (SELECT 1 FROM json_each(m.tags) WHERE value=?)'; args.append(t)
        sql += ' ORDER BY rank LIMIT ?'; args.append(offset + limit)
        with self.connect() as c: rows = c.execute(sql, args).fetchall()
        out = []
        for r in rows[offset:]:
            d = public(r); rank = d.pop('rank')
            d.update(score=round(-rank, 6), retrieval='lexical', scope='user' if r['project'] == USER_SCOPE else 'project')
            out.append(d)
        return out

    def record_access(self, ids):
        """Access statistics feed maintenance reports (stale or never-used memories), not ranking:
        boosting what is already retrieved would let early retrieval decide future retrieval.
        Best effort: a read must never wait on, or fail because of, another process's write lock."""
        if not ids: return False
        c = sqlite3.connect(self.db, timeout=0.2)
        try:
            with c:
                c.executemany('UPDATE memories SET access_count=access_count+1, last_accessed=? WHERE id=?', [(now(), i) for i in ids])
            return True
        except sqlite3.OperationalError:
            return False
        finally:
            c.close()

    def graph(self, project, limit=1000, statuses=('approved',), category=None, tag=None, include_user=False):
        scope(project); _limit(limit, 1, 5000, 'limit')
        projects = [project] + ([USER_SCOPE] if include_user and project != USER_SCOPE else [])
        where = f"project IN ({','.join('?' * len(projects))}) AND status IN ({','.join('?' * len(statuses))})"
        args = projects + list(statuses)
        if category: where += ' AND category=?'; args.append(category)
        if tag: where += ' AND EXISTS (SELECT 1 FROM json_each(memories.tags) WHERE value=?)'; args.append(tag)
        with self.connect() as c:
            total = c.execute(f'SELECT count(*) FROM memories WHERE {where}', args).fetchone()[0]
            nodes = [public(r) for r in c.execute(f'SELECT * FROM memories WHERE {where} ORDER BY created DESC, id DESC LIMIT ?', args + [limit])]
            ids = {n['id'] for n in nodes}
            marks = ','.join('?' * len(projects))
            edges = [dict(r) for r in c.execute(f'SELECT project, a, b, relation, created FROM edges WHERE project IN ({marks})', projects)
                     if r['a'] in ids and r['b'] in ids]
        return {'nodes': nodes, 'edges': edges, 'limit': limit, 'total': total, 'truncated': total > len(nodes),
                'semantics': 'explicit typed links, not automatically proven causality'}

    def support(self, id):
        with self.connect() as c: return self._support(c, id)

    # --- erasure --------------------------------------------------------------------------------
    def purge(self, project, id, actor='local'):
        """Hard delete one memory and every derived copy the database holds. Call ops.compact()
        afterwards to checkpoint the WAL and VACUUM; see docs/OPERATIONS.md for what this cannot
        reach (existing backups, filesystem snapshots, SSD wear levelling)."""
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            r = self._get(c, project, id)
            c.execute('DELETE FROM edges WHERE a=? OR b=?', (id, id))
            # Tombstone: the mirror export deletes the file and retries if it is locked (e.g. open in
            # an editor on Windows), so a failed unlink cannot leave a copy behind for good.
            c.execute('INSERT OR REPLACE INTO outbox VALUES(?, 0)', (id,))
            schema.fts_delete(c, id)
            if not c.execute('SELECT 1 FROM memories WHERE digest=? AND id!=?', (r['digest'], id)).fetchone():
                c.execute('DELETE FROM judgements WHERE digest=?', (r['digest'],))
            c.execute('DELETE FROM memories WHERE id=?', (id,))  # embeddings and sightings cascade
            # A content digest of a short secret is brute-forceable, so audit rows keep the event, not the hash.
            c.execute('UPDATE audit SET digest=NULL WHERE id=?', (id,))
            self._audit(c, id, 'purge', None, actor)
            # Old FTS segments can still hold the deleted terms until they are merged away.
            c.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
        mirror = self.flush()
        return {'purged': id, 'mirror_file_removed': mirror['failed'] == 0}

    # --- mirror, maintenance --------------------------------------------------------------------
    def flush(self):
        from . import mirror
        return mirror.export_pending(self)

    def rebuild(self, fts=True, mirror_files=True):
        """Rebuild derived state from the database: the full-text index and the Markdown mirror.
        (0.1 named the mirror-only operation rebuild; it now rebuilds everything derived.)"""
        out = {}
        if fts:
            with self.connect() as c:
                c.execute('BEGIN IMMEDIATE'); out['fts_rows'] = schema.rebuild_fts(c)
        if mirror_files:
            with self.connect() as c:
                c.execute('INSERT OR REPLACE INTO outbox SELECT id, version FROM memories')
            out.update(self.flush())
        return out

    def backup(self, target=None):
        """Online backup via SQLite's backup API, then verified. Refuses to replace an existing file."""
        if target is None:
            folder = self.root / 'backups'; folder.mkdir(exist_ok=True)
            target = folder / ('memory-' + now().replace(':', '').replace('-', '').split('.')[0] + 'Z.sqlite3')
        target = Path(target).resolve()
        with target.open('xb'): pass  # exclusive creation prevents accidental replacement
        dest = sqlite3.connect(target)
        try:
            with self.connect() as source: source.backup(dest)
            ok = dest.execute('PRAGMA integrity_check').fetchone()[0]
            n = dest.execute('SELECT count(*) FROM memories').fetchone()[0]
        finally:
            dest.close()
        return {'backup': str(target), 'integrity': ok, 'memories': n}

    def health(self):
        with self.connect() as c:
            one = lambda sql, *a: c.execute(sql, a).fetchone()[0]
            by_status = {r[0]: r[1] for r in c.execute('SELECT status, count(*) FROM memories GROUP BY status')}
            return {'schema': one('PRAGMA user_version'), 'analyzer': one("SELECT value FROM meta WHERE key='analyzer'"),
                    'integrity': one('PRAGMA quick_check'), 'pending_exports': one('SELECT count(*) FROM outbox'),
                    'memories': one('SELECT count(*) FROM memories'), 'by_status': by_status,
                    'fts_rows': one('SELECT count(*) FROM memory_fts'), 'embeddings': one('SELECT count(*) FROM embeddings'),
                    'documents': one('SELECT count(*) FROM documents'), 'sessions': one('SELECT count(*) FROM sessions'),
                    'default_retrieval': 'lexical', 'network': 'disabled unless provider explicitly configured'}
