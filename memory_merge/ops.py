"""Operations: restore, restore drill, compaction, maintenance, diagnostics.

Nothing here overwrites a live database. Restore writes into a new, empty data directory, verifies
it, and leaves switching over to the user (stop writers, point MM_DATA at the new directory).
"""
import hashlib
import json
import os
import platform
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from . import __version__, schema, text, vectors
from .errors import InvalidInput, MemoryMergeError
from .schema import now


def _digests(db):
    c = sqlite3.connect(db)
    try:
        rows = c.execute('SELECT id, digest, status, version FROM memories ORDER BY id').fetchall()
        return hashlib.sha256(json.dumps(rows).encode()).hexdigest(), len(rows)
    finally:
        c.close()


def list_backups(store):
    folder = store.root / 'backups'
    if not folder.is_dir(): return []
    return [{'file': p.name, 'bytes': p.stat().st_size, 'modified': p.stat().st_mtime} for p in sorted(folder.glob('*.sqlite3'))]


def restore(backup, target_dir):
    """Restore a backup into a NEW data directory, migrate it if it is older, rebuild derived state,
    and verify. Refuses a non-empty target."""
    from .store import Store
    backup, target = Path(backup).resolve(), Path(target_dir).resolve()
    if not backup.is_file(): raise InvalidInput('backup file not found')
    if target.exists() and any(target.iterdir()): raise InvalidInput('restore target must be a new or empty directory')
    target.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f'file:{backup.as_posix()}?mode=ro', uri=True)
    dst = sqlite3.connect(target / 'memory.sqlite3')
    try:
        if src.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise InvalidInput('backup failed integrity_check')
        src.backup(dst)
    finally:
        dst.close(); src.close()
    store = Store(target)          # runs migrations if the backup predates this schema
    rebuilt = store.rebuild()      # FTS + Markdown mirror are derived: regenerate rather than trust
    h = store.health()
    return {'restored_to': str(target), 'migrations': store.migration['migrations'], 'integrity': h['integrity'],
            'memories': h['memories'], 'rebuilt': rebuilt}


def drill(store):
    """Prove that backup + restore round-trips: back up, restore into a temp dir, compare every
    memory id/digest/status/version. Returns pass/fail with counts; leaves no files behind."""
    tmp = Path(tempfile.mkdtemp(prefix='mm-drill-'))
    try:
        b = store.backup(tmp / 'backup.sqlite3')
        r = restore(b['backup'], tmp / 'restored')
        live_hash, live_n = _digests(store.db)
        back_hash, back_n = _digests(tmp / 'restored' / 'memory.sqlite3')
        ok = live_hash == back_hash and r['integrity'] == 'ok'
        return {'drill': 'pass' if ok else 'fail', 'memories': live_n, 'restored': back_n, 'integrity': r['integrity'],
                'note': 'compared id, digest, status and version of every memory; writes during the drill can cause a false fail'}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def compact(store, vacuum=True):
    """Make deletions physical: truncate the WAL (old page images live there until overwritten) and
    VACUUM (rewrites the file without free pages). Needs no other open connections for VACUUM."""
    out = {}
    c = sqlite3.connect(store.db, timeout=15, isolation_level=None)
    try:
        c.execute('PRAGMA secure_delete=ON')
        out['checkpoint'] = list(c.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone())
        if vacuum:
            c.execute('VACUUM')
            out['vacuum'] = 'done'
            out['checkpoint_after'] = list(c.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone())
        # busy=1 means a reader held an older snapshot: old page images may remain in the WAL.
        if out['checkpoint'][0] or out.get('checkpoint_after', [0])[0]:
            out['error'] = 'WAL checkpoint was blocked by another connection; deleted content may remain in the -wal file'
            out['hint'] = 'close other Memory Merge processes (MCP servers, viewer) and run: memory-merge maintain --compact'
    except sqlite3.OperationalError as e:
        out['error'] = str(e); out['hint'] = 'close other Memory Merge processes (MCP servers, viewer) and retry'
    finally:
        c.close()
    wal = Path(str(store.db) + '-wal')
    out['wal_bytes'] = wal.stat().st_size if wal.exists() else 0
    return out


def purge(store, project, id, actor='cli'):
    """Hard delete + compaction, with an honest list of what is still out of reach."""
    res = store.purge(project, id, actor)
    res['compaction'] = compact(store)
    res['complete'] = 'error' not in res['compaction'] and res.get('mirror_file_removed', True)
    res['backups_that_may_contain_it'] = len(list_backups(store))
    res['limits'] = ['existing backups are not modified', 'filesystem snapshots, cloud sync and SSD wear levelling may retain copies',
                     'copies already sent to a remote embedding or judge provider are outside this system']
    return res


def maintain(store, analyze=True, optimize=True, integrity=True):
    out = {}
    with store.connect() as c:
        if integrity: out['integrity'] = c.execute('PRAGMA integrity_check').fetchone()[0]
        if optimize:
            c.execute("INSERT INTO memory_fts(memory_fts) VALUES('optimize')")
            c.execute("INSERT INTO turns_fts(turns_fts) VALUES('optimize')")
            out['fts'] = 'optimized'
        if analyze: c.execute('ANALYZE'); out['analyze'] = 'done'
    return out


def prune_vectors(store, keep_fingerprint):
    """Delete vectors from other models once a re-index under the new fingerprint is complete."""
    with store.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        n = c.execute('DELETE FROM embeddings WHERE fingerprint != ?', (keep_fingerprint,)).rowcount
    return {'deleted_vectors': n, 'kept': keep_fingerprint}


def report(store, project, stale_days=180):
    """Maintenance suggestions; nothing is changed automatically."""
    from .store import scope
    scope(project)
    with store.connect() as c:
        stale = [dict(r) for r in c.execute("""SELECT id, substr(content,1,120) AS content, created, last_accessed FROM memories
            WHERE project=? AND status='approved' AND kind='memory' AND access_count=0 AND created < strftime('%Y-%m-%dT%H:%M:%S', 'now', ?)
            ORDER BY created LIMIT 50""", (project, f'-{int(stale_days)} days'))]
        dups = [dict(r) for r in c.execute("""SELECT norm_digest, count(*) AS n, group_concat(id) AS ids FROM memories
            WHERE project=? AND status IN ('approved','pending') GROUP BY norm_digest HAVING n > 1 LIMIT 50""", (project,))]
        conflicts = [dict(r) for r in c.execute("""SELECT e.a, e.b, ma.status AS a_status, mb.status AS b_status FROM edges e
            JOIN memories ma ON ma.id=e.a JOIN memories mb ON mb.id=e.b
            WHERE e.project=? AND e.relation='contradicts' AND ma.status='approved' AND mb.status='approved'""", (project,))]
        pending = c.execute("SELECT count(*) FROM memories WHERE project=? AND status='pending'", (project,)).fetchone()[0]
    return {'stale_never_recalled': stale, 'exact_duplicates': dups, 'unresolved_conflicts': conflicts, 'pending_reviews': pending,
            'note': 'suggestions only: archive, merge (supersede) or resolve via review; nothing was changed'}


def doctor(store=None, env=None, probe=False):
    """Diagnose the environment. Each check: ok | warn | fail, with a hint. probe=True contacts the
    configured providers (one embedding and one judge call); otherwise no network is used."""
    from . import config
    env = os.environ if env is None else env
    checks = []
    def add(name, status, detail, hint=None):
        checks.append({'check': name, 'status': status, 'detail': detail, **({'hint': hint} if hint else {})})
    add('python', 'ok' if sys.version_info >= (3, 11) else 'fail', platform.python_version(), 'Python 3.11+ required')
    add('sqlite', 'ok' if sqlite3.sqlite_version_info >= (3, 35) else 'warn', sqlite3.sqlite_version)
    try:
        m = sqlite3.connect(':memory:'); m.execute('CREATE VIRTUAL TABLE t USING fts5(x)'); m.execute("SELECT json('[1]')"); m.close()
        add('fts5_json', 'ok', 'FTS5 and JSON functions available')
    except sqlite3.Error as e:
        add('fts5_json', 'fail', str(e), 'use a Python build whose SQLite includes FTS5 (python.org and most distributions do)')
    add('vector_kernel', 'ok' if vectors.kernel() != 'python' else 'warn', vectors.kernel(),
        None if vectors.kernel() != 'python' else 'Python < 3.12 without the native kernel: vector search is slow above ~10k vectors')
    try:
        import mcp
        add('mcp_sdk', 'ok', getattr(mcp, '__version__', 'installed'))
    except ImportError:
        add('mcp_sdk', 'fail', 'not installed', 'pip install -r requirements-lock.txt')
    for name, loader in (('embedding_config', config.embedding_from_env), ('judge_config', config.judge_from_env)):
        backend = env.get('MM_EMBED_BACKEND' if name.startswith('emb') else 'MM_JUDGE_BACKEND')
        if backend and backend != 'openai' and not probe:
            # In-process backends load model weights on construction; only do that when asked to.
            add(name, 'ok', f'{backend} configured (not loaded; run doctor --probe to load and test it)')
            continue
        try:
            p = loader(env)
            add(name, 'ok', 'not configured (lexical only)' if p is None else json.dumps(p.descriptor() if hasattr(p, 'descriptor') and name.startswith('emb') else getattr(p, 'judge_descriptor', lambda: {})(), ensure_ascii=False))
            if probe and p is not None:
                try:
                    if name.startswith('emb'): add(name + '_probe', 'ok', f'dimension {len(p.embed("doctor probe"))}')
                    else: add(name + '_probe', 'ok', json.dumps(p.judge('doctor probe: the team decided to use SQLite'), ensure_ascii=False))
                except MemoryMergeError as e:
                    add(name + '_probe', 'fail', e.code + ': ' + e.message, e.hint)
        except MemoryMergeError as e:
            add(name, 'fail', e.message, e.hint)
    if store is not None:
        h = store.health()
        add('database', 'ok' if h['integrity'] == 'ok' else 'fail', f"schema v{h['schema']}, {h['memories']} memories, integrity {h['integrity']}")
        add('analyzer', 'ok' if h['analyzer'] == text.ANALYZER else 'warn', h['analyzer'])
        add('mirror_backlog', 'ok' if h['pending_exports'] == 0 else 'warn', f"{h['pending_exports']} pending exports", 'run: memory-merge flush')
        wal = Path(str(store.db) + '-wal')
        size = wal.stat().st_size if wal.exists() else 0
        add('wal', 'ok' if size < 64 * 2 ** 20 else 'warn', f'{size} bytes', 'run: memory-merge maintain --compact')
        backups = list_backups(store)
        add('backups', 'ok' if backups else 'warn', f'{len(backups)} in {store.root / "backups"}', 'run: memory-merge backup; then memory-merge drill')
        legacy = Path(__file__).resolve().parents[1] / 'data'
        if store.root == legacy.resolve():
            add('data_dir', 'warn', str(store.root), 'this is the 0.1 default inside the source tree; set MM_DATA to a directory outside the checkout')
        with store.connect() as c:
            fps = c.execute('SELECT fingerprint, count(*) FROM embeddings GROUP BY fingerprint').fetchall()
        if len(fps) > 1: add('vector_fingerprints', 'warn', json.dumps({r[0]: r[1] for r in fps}), 'after re-indexing, run: memory-merge prune-vectors --keep <fingerprint>')
    summary = config.summary(env)
    status = 'fail' if any(c['status'] == 'fail' for c in checks) else ('warn' if any(c['status'] == 'warn' for c in checks) else 'ok')
    return {'status': status, 'version': __version__, 'checks': checks, 'config': summary, 'checked': now()}
