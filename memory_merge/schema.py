"""Schema versions and the migration runner.

Rules this module enforces:
- A fresh database is built by running the published v1 DDL and then every migration, so fresh and
  upgraded databases come from one code path and can be compared in tests.
- A database newer than this code is refused before anything is written. (0.1 stamped
  user_version=1 unconditionally, which silently downgraded newer databases.)
- Before migrating a database that holds data, a backup is written with SQLite's backup API and
  verified (integrity_check + row counts). If that fails the migration does not start.
- Each migration runs in one IMMEDIATE transaction; on any error SQLite rolls the DDL back too.
- The version is recorded twice, in user_version and in meta. If an older Memory Merge process
  reopens a newer database and stamps user_version back down, meta still holds the truth and the
  next open repairs user_version instead of re-running migrations.
"""
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import text, vectors
from .errors import SchemaError, SchemaTooNew

LATEST = 2
log = logging.getLogger('memory_merge.schema')

# Exactly the DDL published in 0.1.0 (memory_merge/store.py), minus its PRAGMA lines.
V1_DDL = [
    '''CREATE TABLE IF NOT EXISTS memories(
      id TEXT PRIMARY KEY, project TEXT NOT NULL, content TEXT NOT NULL,
      source TEXT NOT NULL, event_id TEXT, digest TEXT NOT NULL,
      mode TEXT NOT NULL, status TEXT NOT NULL, category TEXT NOT NULL,
      tags TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL,
      version INTEGER NOT NULL DEFAULT 1,
      UNIQUE(project,source,event_id))''',
    'CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, version INTEGER NOT NULL)',
    '''CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY, id TEXT, action TEXT,
      digest TEXT, created TEXT)''',
    '''CREATE TABLE IF NOT EXISTS edges(project TEXT, a TEXT, b TEXT, relation TEXT,
      PRIMARY KEY(project,a,b,relation), FOREIGN KEY(a) REFERENCES memories(id),
      FOREIGN KEY(b) REFERENCES memories(id))''',
    '''CREATE TABLE IF NOT EXISTS vectors(id TEXT PRIMARY KEY, model TEXT, dim INTEGER,
      digest TEXT, vector TEXT, FOREIGN KEY(id) REFERENCES memories(id))''',
    'CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(id UNINDEXED, content)',
    'CREATE INDEX IF NOT EXISTS memories_scope ON memories(project,status)',
]

FTS_TOKENIZE = "tokenize='porter unicode61 remove_diacritics 2'"
INDEXED_STATUSES = ('approved', 'archived', 'superseded')

_BUMP = "UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='generation'"
V2_DDL = [
    'CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)',
    '''CREATE TABLE documents(
      id TEXT PRIMARY KEY, project TEXT NOT NULL, uri TEXT NOT NULL, title TEXT NOT NULL,
      mime TEXT NOT NULL, digest TEXT NOT NULL, bytes INTEGER NOT NULL, status TEXT NOT NULL,
      source TEXT NOT NULL, chunks INTEGER NOT NULL DEFAULT 0, redactions INTEGER NOT NULL DEFAULT 0,
      created TEXT NOT NULL, updated TEXT NOT NULL)''',
    # Not unique on (uri, digest): a file reverted to an earlier version is imported again as a new
    # current version; the older rows stay as history.
    'CREATE INDEX documents_uri ON documents(project, uri)',
    '''CREATE TABLE sessions(
      id TEXT PRIMARY KEY, project TEXT NOT NULL, agent TEXT NOT NULL, external_id TEXT,
      title TEXT, started TEXT, ended TEXT, created TEXT NOT NULL, meta TEXT NOT NULL DEFAULT '{}',
      UNIQUE(project, agent, external_id))''',
    '''CREATE TABLE turns(
      session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, seq INTEGER NOT NULL,
      role TEXT NOT NULL, content TEXT NOT NULL, created TEXT, digest TEXT NOT NULL,
      redactions INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(session_id, seq))''',
    f'CREATE VIRTUAL TABLE turns_fts USING fts5(terms, chars, session_id UNINDEXED, seq UNINDEXED, {FTS_TOKENIZE})',
    "ALTER TABLE memories ADD COLUMN kind TEXT NOT NULL DEFAULT 'memory'",
    "ALTER TABLE memories ADD COLUMN polarity TEXT NOT NULL DEFAULT 'positive'",
    'ALTER TABLE memories ADD COLUMN norm_digest TEXT',
    'ALTER TABLE memories ADD COLUMN doc_id TEXT REFERENCES documents(id)',
    'ALTER TABLE memories ADD COLUMN session_id TEXT REFERENCES sessions(id)',
    'ALTER TABLE memories ADD COLUMN locator TEXT',
    'ALTER TABLE memories ADD COLUMN access_count INTEGER NOT NULL DEFAULT 0',
    'ALTER TABLE memories ADD COLUMN last_accessed TEXT',
    'ALTER TABLE memories ADD COLUMN valid_until TEXT',
    'ALTER TABLE edges ADD COLUMN created TEXT',
    'ALTER TABLE audit ADD COLUMN actor TEXT',
    '''CREATE TABLE sightings(memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
      source TEXT NOT NULL, event_id TEXT NOT NULL DEFAULT '', created TEXT NOT NULL,
      PRIMARY KEY(memory_id, source, event_id))''',
    'CREATE INDEX sightings_event ON sightings(source, event_id)',
    '''CREATE TABLE embeddings(id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
      fingerprint TEXT NOT NULL, dim INTEGER NOT NULL, digest TEXT NOT NULL, vector BLOB NOT NULL,
      created TEXT NOT NULL, PRIMARY KEY(id, fingerprint))''',
    'CREATE INDEX embeddings_fp ON embeddings(fingerprint)',
    '''CREATE TABLE models(fingerprint TEXT PRIMARY KEY, role TEXT NOT NULL, descriptor TEXT NOT NULL,
      canary BLOB, created TEXT NOT NULL)''',
    '''CREATE TABLE judgements(digest TEXT NOT NULL, fingerprint TEXT NOT NULL, result TEXT NOT NULL,
      latency_ms INTEGER, created TEXT NOT NULL, PRIMARY KEY(digest, fingerprint))''',
    f'CREATE VIRTUAL TABLE memory_fts USING fts5(terms, chars, tags, id UNINDEXED, {FTS_TOKENIZE})',
    'CREATE INDEX memories_norm ON memories(project, norm_digest)',
    'CREATE INDEX memories_doc ON memories(doc_id)',
    'CREATE INDEX memories_session ON memories(session_id)',
    'CREATE INDEX memories_created ON memories(project, created, id)',
    'CREATE INDEX edges_b ON edges(b)',
    "INSERT OR IGNORE INTO meta VALUES('generation','0')",
    # The generation counter lets long-lived processes cache derived state (the vector matrix) and
    # notice any change -- including changes made by another process. Pure SQL, so external tools
    # editing the database still work.
    f'CREATE TRIGGER mm_gen_mem_upd AFTER UPDATE OF status, digest, project ON memories BEGIN {_BUMP}; END',
    f'CREATE TRIGGER mm_gen_mem_del AFTER DELETE ON memories BEGIN {_BUMP}; END',
    f"CREATE TRIGGER mm_gen_mem_ins AFTER INSERT ON memories WHEN NEW.status IN {INDEXED_STATUSES} BEGIN {_BUMP}; END",
    f'CREATE TRIGGER mm_gen_emb_ins AFTER INSERT ON embeddings BEGIN {_BUMP}; END',
    f'CREATE TRIGGER mm_gen_emb_del AFTER DELETE ON embeddings BEGIN {_BUMP}; END',
    f'CREATE TRIGGER mm_gen_emb_upd AFTER UPDATE ON embeddings BEGIN {_BUMP}; END',
    'DROP TABLE memories_fts',
]


def now():
    return datetime.now(timezone.utc).isoformat()


def tags_text(tags_json):
    terms, chars = text.analyze(' '.join(json.loads(tags_json or '[]')))
    return (terms + ' ' + chars).strip()


def fts_insert(c, id, content, tags_json):
    terms, chars = text.analyze(content)
    c.execute('INSERT INTO memory_fts(terms, chars, tags, id) VALUES(?,?,?,?)', (terms, chars, tags_text(tags_json), id))


def fts_delete(c, id):
    c.execute('DELETE FROM memory_fts WHERE id=?', (id,))


def rebuild_fts(c):
    """Derived index: rebuilt from memories, never the other way round."""
    c.execute('DELETE FROM memory_fts')
    n = 0
    for r in c.execute(f'SELECT id, content, tags FROM memories WHERE status IN {INDEXED_STATUSES}').fetchall():
        fts_insert(c, r[0], r[1], r[2]); n += 1
    c.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
    c.execute("INSERT OR REPLACE INTO meta VALUES('analyzer', ?)", (text.ANALYZER,))
    return n


def _v1_to_v2(c):
    import hashlib
    for stmt in V2_DDL: c.execute(stmt)
    for id, content in c.execute('SELECT id, content FROM memories').fetchall():
        c.execute('UPDATE memories SET norm_digest=? WHERE id=?', (text.norm_digest(content), id))
    converted = skipped = 0
    for id, model, dim, digest, raw in c.execute(f'''SELECT v.id, v.model, v.dim, v.digest, v.vector FROM vectors v
            JOIN memories m ON m.id=v.id WHERE m.status IN {INDEXED_STATUSES}''').fetchall():
        # 0.1 identified models only as endpoint plus model name, so these vectors cannot be proven
        # compatible with anything configured now. They are kept under a 'legacy-' fingerprint (never
        # mixed into search) until a re-index replaces them.
        try:
            vec = json.loads(raw)
            if not isinstance(vec, list) or len(vec) != dim: raise ValueError
            blob = vectors.pack(vectors.normalize(vec))
        except (ValueError, TypeError):
            skipped += 1; continue
        fp = 'legacy-' + hashlib.sha256(str(model).encode()).hexdigest()[:20]
        c.execute('INSERT OR IGNORE INTO models VALUES(?,?,?,?,?)', (fp, 'embedding', json.dumps(
            {'legacy_identity': model, 'note': 'migrated from 0.1; model revision, pooling and templates unknown'}), None, now()))
        c.execute('INSERT OR REPLACE INTO embeddings VALUES(?,?,?,?,?,?)', (id, fp, dim, digest, blob, now()))
        converted += 1
    c.execute('DROP TABLE vectors')
    indexed = rebuild_fts(c)
    return {'vectors_converted': converted, 'vectors_skipped': skipped, 'fts_rows': indexed}


MIGRATIONS = {1: _v1_to_v2}


def _state(c):
    uv = c.execute('PRAGMA user_version').fetchone()[0]
    names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    meta_v = 0
    if 'meta' in names:
        row = c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        meta_v = int(row[0]) if row else 0
    return uv, meta_v, names


def _backup(db, root, frm, to):
    # Read through a second connection: the migrator holds the write lock, so this WAL snapshot is
    # exactly the state about to be migrated. (Backing up from the locked connection itself returns
    # SQLITE_LOCKED, which Python's backup() retries forever.)
    folder = Path(root) / 'backups'
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = folder / f'pre-migration-v{frm}-to-v{to}-{stamp}.sqlite3'
    with target.open('xb'): pass
    src, dest = sqlite3.connect(db, timeout=15), sqlite3.connect(target)
    try:
        src.backup(dest)
        ok = dest.execute('PRAGMA integrity_check').fetchone()[0]
        same = dest.execute('SELECT count(*) FROM memories').fetchone()[0] == src.execute('SELECT count(*) FROM memories').fetchone()[0]
    finally:
        dest.close(); src.close()
    if ok != 'ok' or not same:
        raise SchemaError('pre-migration backup failed verification; database left unchanged', backup=str(target))
    return str(target)


def ensure(db, root):
    """Bring the database at db to LATEST and return what was done (for logs and doctor)."""
    info = {'schema': LATEST, 'created': False, 'migrations': [], 'healed_user_version': False, 'fts_rebuilt': False}
    c = sqlite3.connect(db, timeout=15, isolation_level=None)  # explicit BEGIN/COMMIT below
    try:
        uv, meta_v, names = _state(c)  # read before writing anything, including the journal mode
        if max(uv, meta_v) > LATEST:
            raise SchemaTooNew(f'database schema v{max(uv, meta_v)} is newer than this Memory Merge (v{LATEST})',
                               hint='upgrade memory-merge; the database was not modified')
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('PRAGMA foreign_keys=ON')
        if max(uv, meta_v) < LATEST:
            c.execute('BEGIN IMMEDIATE')  # one migrator at a time; re-check under the lock
            try:
                _migrate_locked(c, db, root, info)
                c.execute('COMMIT')
            except BaseException:
                c.execute('ROLLBACK')
                raise
        elif uv < meta_v:
            # An older Memory Merge opened this database and stamped user_version back down. Its
            # writes fail on the newer tables, but its CREATE TABLE IF NOT EXISTS leaves empty legacy
            # tables behind: drop those and restore the version marker.
            # 0.1's inserts fail on the newer tables, but its plain UPDATEs (review) succeed and bypass
            # index maintenance, so derived state is rebuilt rather than trusted.
            c.execute('BEGIN IMMEDIATE')
            try:
                uv, meta_v, names = _state(c)  # re-check under the lock: another opener may have healed it
                if uv < meta_v:
                    for legacy in ('memories_fts', 'vectors'):
                        if legacy in names: c.execute(f'DROP TABLE {legacy}')
                    c.execute(f'DELETE FROM embeddings WHERE id IN (SELECT id FROM memories WHERE status NOT IN {INDEXED_STATUSES})')
                    rebuild_fts(c)
                    c.execute(f'PRAGMA user_version={LATEST}')
                    info['healed_user_version'] = True
                    log.warning('restored user_version=%s and rebuilt indexes after the database was opened by an older Memory Merge', LATEST)
                c.execute('COMMIT')
            except BaseException:
                c.execute('ROLLBACK')
                raise
        row = c.execute("SELECT value FROM meta WHERE key='analyzer'").fetchone()
        if not row or row[0] != text.ANALYZER:
            c.execute('BEGIN IMMEDIATE')
            rebuild_fts(c)
            c.execute('COMMIT')
            info['fts_rebuilt'] = True
        return info
    finally:
        c.close()


def _migrate_locked(c, db, root, info):
    uv, meta_v, names = _state(c)
    current = max(uv, meta_v)
    if current >= LATEST: return  # another process finished first
    fresh = 'memories' not in names
    if fresh:
        for stmt in V1_DDL: c.execute(stmt)
        info['created'] = True
    current = max(current, 1)
    has_rows = not fresh and c.execute('SELECT count(*) FROM memories').fetchone()[0] > 0
    backup = _backup(db, root, current, LATEST) if has_rows else None
    for v in range(current, LATEST):
        detail = MIGRATIONS[v](c)
        if not fresh:
            step = dict(detail, at=now(), backup=backup)
            step['from'], step['to'] = v, v + 1
            info['migrations'].append(step)
            log.warning('migrated schema %s', step)
    row = c.execute("SELECT value FROM meta WHERE key='history'").fetchone()
    history = json.loads(row[0]) if row else []
    history.extend(info['migrations'])
    c.execute("INSERT OR REPLACE INTO meta VALUES('history', ?)", (json.dumps(history),))
    c.execute("INSERT OR REPLACE INTO meta VALUES('schema_version', ?)", (str(LATEST),))
    c.execute(f'PRAGMA user_version={LATEST}')
    bad = c.execute('PRAGMA foreign_key_check').fetchall()
    if bad: info['foreign_key_violations'] = len(bad)
