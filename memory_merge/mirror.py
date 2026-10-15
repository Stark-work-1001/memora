"""Markdown mirror: export (database -> files) and sync (file edits -> pending proposals).

Export is the 0.1 outbox protocol unchanged in spirit: each queued id is written under the same
write lock that mutations take, via a temp file and atomic replace, so an older process cannot
overwrite a newer version and a failed write stays queued for retry.

Sync is deliberately not a two-way merge. Any process that can write files -- including an agent
with filesystem tools -- can edit the mirror, so an edit is evidence of intent, not intent. Each
edited body becomes a *pending* revision linked to the original with `supersedes`; approving it
retires the original. Edits to a stale file (the database moved on since it was written) are
reported and not proposed, because they would revert newer content.
"""
import json
import time
from pathlib import Path

from . import text
from .store import CATEGORIES

FIELDS = ['id', 'project', 'source', 'status', 'category', 'polarity', 'kind', 'tags', 'created', 'updated', 'version', 'digest']
HINT = '# Edit the body below and run `memory-merge sync`: changes become a pending revision for review.'


def render(r):
    fields = {k: r[k] for k in FIELDS}
    fields['tags'] = json.loads(r['tags'] or '[]')
    if r['locator']: fields['locator'] = json.loads(r['locator'])
    header = '---\n' + ''.join(f'{k}: {json.dumps(v, ensure_ascii=False)}\n' for k, v in fields.items()) + HINT + '\n---\n\n'
    return header + r['content'] + '\n'


def parse(raw):
    """-> (front matter dict, body). Raises ValueError on a malformed header."""
    raw = raw.replace('\r\n', '\n')
    if not raw.startswith('---\n'): return {}, raw.strip()
    end = raw.find('\n---\n', 4)
    if end < 0: raise ValueError('unterminated front matter')
    meta = {}
    for line in raw[4:end].split('\n'):
        if not line.strip() or line.lstrip().startswith('#'): continue
        key, sep, value = line.partition(':')
        if not sep: raise ValueError('bad front matter line')
        meta[key.strip()] = json.loads(value.strip())
    return meta, raw[end + 5:].strip()


def export_pending(store):
    result = {'written': 0, 'failed': 0}
    with store.connect() as c: items = [r['id'] for r in c.execute('SELECT id FROM outbox')]
    folder = store.root / 'markdown'
    for id in items:
        try:
            with store.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                r = c.execute('SELECT * FROM memories WHERE id=?', (id,)).fetchone()
                folder.mkdir(exist_ok=True)
                path = folder / (id + '.md')
                if r is None or r['status'] == 'deleted':
                    path.unlink(missing_ok=True)
                else:
                    temp = path.with_suffix('.tmp')
                    temp.write_text(render(r), encoding='utf-8', newline='\n')
                    temp.replace(path)
                c.execute('DELETE FROM outbox WHERE id=?', (id,))
                result['written'] += 1
        except OSError:
            result['failed'] += 1
    return result


def _meta_ok(meta):
    """Front matter comes from a file anyone can edit: check types before using any value."""
    for key, kind in (('id', str), ('project', str), ('category', str), ('version', int)):
        if key in meta and (not isinstance(meta[key], kind) or isinstance(meta[key], bool)): raise ValueError(f'front matter {key} has the wrong type')
    if 'tags' in meta and (not isinstance(meta['tags'], list) or not all(isinstance(t, str) for t in meta['tags'])):
        raise ValueError('front matter tags must be a list of strings')
    return meta


def sync(store, default_project='default', actor='markdown'):
    """Scan the mirror once. Returns a report; never modifies approved content directly."""
    folder = store.root / 'markdown'
    report = {'proposed': [], 'unchanged': 0, 'stale': [], 'orphans': [], 'removed': [], 'errors': [], 'inbox_imported': []}
    if not folder.is_dir(): return report
    for path in sorted(folder.glob('*.md')):
        try:
            meta, body = parse(path.read_text(encoding='utf-8'))
            _meta_ok(meta)
            id = meta.get('id') or path.stem
            with store.connect() as c:
                row = c.execute('SELECT * FROM memories WHERE id=?', (id,)).fetchone()
                purged = row is None and c.execute("SELECT 1 FROM audit WHERE id=? AND action='purge'", (id,)).fetchone()
            if row is None:
                if purged:  # a purge whose file deletion failed earlier (e.g. the file was open)
                    path.unlink(); report['removed'].append(path.name)
                else:
                    report['orphans'].append(path.name)
                continue
            # Equal after normalising case, width, whitespace and line endings: not a revision. (It
            # would deduplicate against the original itself.)
            if not body or text.norm_digest(body) == row['norm_digest']:
                report['unchanged'] += 1; continue
            if meta.get('version') != row['version']:
                report['stale'].append({'file': path.name, 'file_version': meta.get('version'), 'db_version': row['version']}); continue
            category = meta.get('category') if meta.get('category') in CATEGORIES else row['category']
            tags = meta.get('tags') if isinstance(meta.get('tags'), list) else json.loads(row['tags'])
            proposal = store.capture(row['project'], body, 'markdown-edit:' + id, mode='manual', event_id='edit:' + text.digest(body)[:32],
                                     category=category, tags=tags, supersedes=id, actor=actor)
            report['proposed'].append({'original': id, 'proposal': proposal['id'], 'status': proposal['status']})
        except Exception as e:  # one bad file must not stop the scan (or a --watch loop) for good
            report['errors'].append({'file': path.name, 'error': getattr(e, 'code', type(e).__name__), 'message': str(e)[:200]})
    inbox = folder / 'inbox'
    if inbox.is_dir():
        for path in sorted(p for p in inbox.iterdir() if p.is_file() and p.suffix in ('.md', '.txt')):
            try:
                meta, body = parse(path.read_text(encoding='utf-8'))
                _meta_ok(meta)
                if not body: continue
                r = store.capture(meta.get('project') or default_project, body, 'markdown-inbox:' + path.name[:200], mode='manual',
                                  event_id='inbox:' + text.digest(body)[:32], category=meta.get('category') if meta.get('category') in CATEGORIES else None,
                                  tags=meta.get('tags'), actor=actor)
                # The inbox is a drop folder: the note now lives in the database and its own mirror file.
                # Keeping an archive copy would leave plaintext behind that forget/purge cannot reach.
                path.unlink()
                report['inbox_imported'].append({'file': path.name, 'id': r['id'], 'status': r['status']})
            except Exception as e:
                report['errors'].append({'file': 'inbox/' + path.name, 'error': getattr(e, 'code', type(e).__name__), 'message': str(e)[:200]})
    store.flush()
    return report


def watch(store, interval=5.0, default_project='default', rounds=None, on_report=print):
    """Poll for changes (stdlib only, no watchdog dependency). Re-scans only when any mtime changes."""
    folder, seen, n = store.root / 'markdown', None, 0
    while rounds is None or n < rounds:
        state = sorted((p.name, p.stat().st_mtime_ns) for p in folder.rglob('*') if p.is_file()) if folder.is_dir() else []
        if state != seen:
            rep = sync(store, default_project)
            if rep['proposed'] or rep['inbox_imported'] or rep['errors']: on_report(rep)
            seen = sorted((p.name, p.stat().st_mtime_ns) for p in folder.rglob('*') if p.is_file()) if folder.is_dir() else []
        n += 1
        if rounds is None or n < rounds: time.sleep(interval)
