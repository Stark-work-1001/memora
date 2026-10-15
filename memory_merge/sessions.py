"""Session archive: conversations as sessions and ordered turns, separate from curated memories.

Turns are an archive, not memory: they are searchable on request (session search) and replayable
(session show), but never enter recall or evidence packs. Curated memories may point at the session
they came from (memories.session_id), so a memory can be traced back to its conversation.

Formats (docs/DATA_FORMATS.md):
- Memory Merge session JSONL: {"type":"session",...}, {"type":"turn",...}, {"type":"memory",...}
- Claude Code transcript JSONL (the file a hook receives as transcript_path)
Imports are idempotent: sessions are keyed (project, agent, external id), turns (session, seq).
Turn text is redacted for secrets before storage; tool results are not archived (size, sensitivity).
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
import uuid
from pathlib import Path

from . import text
from .errors import InvalidInput, MemoryMergeError, NotFound
from .schema import now
from .store import scope

ROLES = {'user', 'assistant', 'system', 'tool'}
MAX_TURN = 32000


def _opt_str(value, name, limit=300):
    if value is None: return None
    if not isinstance(value, str): raise InvalidInput(f'{name} must be a string')
    return value[:limit]


def _session(c, project, agent, external_id, title=None, started=None, ended=None, meta=None):
    title, _ = text.redact(_opt_str(title, 'title') or '') if title else (None, 0)
    started, ended = _opt_str(started, 'started', 64), _opt_str(ended, 'ended', 64)
    if meta is not None and not isinstance(meta, dict): raise InvalidInput('meta must be an object')
    meta, _ = text.redact_value(meta or {})
    row = c.execute('SELECT id FROM sessions WHERE project=? AND agent=? AND external_id=?', (project, agent, external_id)).fetchone()
    if row:
        c.execute('UPDATE sessions SET title=COALESCE(?, title), started=COALESCE(started, ?), ended=COALESCE(?, ended) WHERE id=?',
                  (title, started, ended, row['id']))
        return row['id'], False
    sid = str(uuid.uuid4())
    c.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?)', (sid, project, agent, external_id, title, started, ended, now(),
                                                              json.dumps(meta or {}, ensure_ascii=False)))
    return sid, True


def _turn(c, sid, seq, role, content, created=None):
    if not isinstance(role, str) or role not in ROLES: raise InvalidInput(f'turn role must be one of {sorted(ROLES)}')
    created = _opt_str(created, 'created', 64)
    content, kinds = text.redact(content[:MAX_TURN])
    if c.execute('SELECT 1 FROM turns WHERE session_id=? AND seq=?', (sid, seq)).fetchone(): return 0, 0
    c.execute('INSERT INTO turns VALUES(?,?,?,?,?,?,?)', (sid, seq, role, content, created, text.digest(content), len(kinds)))
    terms, chars = text.analyze(content)
    c.execute('INSERT INTO turns_fts(terms, chars, session_id, seq) VALUES(?,?,?,?)', (terms, chars, sid, seq))
    return 1, len(kinds)


def import_records(store, records, default_project, agent='generic', actor='import'):
    """Import Memory Merge session JSONL records (already parsed). Returns a report."""
    rep = {'sessions': 0, 'turns': 0, 'redactions': 0, 'memories': [], 'errors': []}
    ids = {}
    with store.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        for n, r in enumerate(records, 1):
            try:
                if not isinstance(r, dict): raise InvalidInput('record must be an object')
                kind = r.get('type')
                if kind == 'session':
                    ext = r.get('id')
                    if not isinstance(ext, (str, int)) or isinstance(ext, bool) or not str(ext): raise InvalidInput('session id required (string)')
                    ext = str(ext)[:200]
                    project = scope(r.get('project') or default_project)
                    sid, new = _session(c, project, str(r.get('agent') or agent)[:80], ext, r.get('title'), r.get('started'), r.get('ended'), r.get('meta'))
                    ids[ext] = (sid, project); rep['sessions'] += new
                elif kind == 'turn':
                    sid, _ = ids.get(str(r.get('session')), (None, None))
                    if not sid: raise InvalidInput('turn refers to an unknown session (sessions must come first)')
                    if not isinstance(r.get('seq'), int) or not isinstance(r.get('content'), str): raise InvalidInput('turn needs integer seq and string content')
                    added, red = _turn(c, sid, r['seq'], r.get('role', 'user'), r['content'], r.get('created'))
                    rep['turns'] += added; rep['redactions'] += red
                elif kind == 'memory':
                    rep['memories'].append((n, r))
                else:
                    raise InvalidInput('type must be session, turn or memory')
            except MemoryMergeError as e:
                rep['errors'].append({'record': n, 'error': e.code, 'message': e.message})
            except (TypeError, ValueError, sqlite3.Error) as e:  # malformed record: report it, keep the rest
                rep['errors'].append({'record': n, 'error': 'invalid_input', 'message': type(e).__name__})
    pending = rep.pop('memories'); rep['memories'] = []
    for n, r in pending:  # through the normal capture path: screening, dedupe, pending status
        try:
            sid, project = ids.get(str(r.get('session')), (None, default_project))
            m = store.capture(project, r.get('content'), 'session:' + (r.get('session') or 'unknown')[:200], event_id=f'session-memory:{n}:' + text.digest(str(r.get('content')))[:16],
                              category=r.get('category'), tags=r.get('tags'), session_id=sid, actor=actor)
            rep['memories'].append(m['id'])
        except MemoryMergeError as e:
            rep['errors'].append({'record': n, 'error': e.code, 'message': e.message})
    store.flush()
    return rep


def read_jsonl(path):
    out = []
    with open(path, encoding='utf-8') as f:
        for n, line in enumerate(f, 1):
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    raise InvalidInput(f'line {n}: not JSON') from None
    return out


def _cc_text(content):
    """Claude Code message content -> archived text. Text parts are kept; tool calls are summarised
    by name; tool results and images are left out of the archive."""
    if isinstance(content, str): return content
    parts = []
    for p in content if isinstance(content, list) else []:
        if not isinstance(p, dict): continue
        if p.get('type') == 'text' and isinstance(p.get('text'), str): parts.append(p['text'])
        elif p.get('type') == 'tool_use': parts.append(f"[tool_use: {str(p.get('name'))[:60]}]")
        elif p.get('type') == 'tool_result': parts.append('[tool_result omitted]')
    return '\n'.join(parts)


def import_claude_code(store, transcript, project, actor='hook'):
    """Archive a Claude Code transcript (JSONL). Re-running on a longer transcript appends new turns."""
    scope(project)
    entries = read_jsonl(transcript)
    session_ext = next((e.get('sessionId') for e in entries if isinstance(e, dict) and e.get('sessionId')), None) or Path(transcript).stem
    records = [{'type': 'session', 'id': session_ext, 'project': project, 'agent': 'claude-code',
                'started': next((e.get('timestamp') for e in entries if isinstance(e, dict) and e.get('timestamp')), None),
                'title': next((e.get('summary') for e in entries if isinstance(e, dict) and e.get('type') == 'summary'), None)}]
    seq = 0
    for e in entries:
        if not isinstance(e, dict) or e.get('type') not in ('user', 'assistant') or not isinstance(e.get('message'), dict): continue
        body = _cc_text(e['message'].get('content')).strip()
        if not body or body == '[tool_result omitted]': continue
        seq += 1
        records.append({'type': 'turn', 'session': session_ext, 'seq': seq, 'role': e['message'].get('role') or e['type'],
                        'content': body, 'created': e.get('timestamp')})
    return import_records(store, records, project, agent='claude-code', actor=actor)


def hook(store, payload, project=None):
    """Entry point for host hooks (e.g. Claude Code SessionEnd/PreCompact). Never raises: a memory
    failure must not break the host session. Diagnostics go to stderr only."""
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
        transcript = data.get('transcript_path')
        if not transcript or not Path(transcript).is_file(): return {'archived': False, 'reason': 'no transcript_path'}
        proj = project or os.environ.get('MM_PROJECT') or re.sub(r'[^\w-]', '-', Path(data.get('cwd') or 'default').name)[:80] or 'default'
        rep = import_claude_code(store, transcript, proj)
        return {'archived': True, 'project': proj, 'turns': rep['turns'], 'errors': len(rep['errors'])}
    except Exception as e:  # noqa: BLE001 - see docstring
        print(f'memory-merge hook: {type(e).__name__}: {e}', file=sys.stderr)
        return {'archived': False, 'reason': type(e).__name__}


def show(store, session_id, limit=500):
    with store.connect() as c:
        s = c.execute('SELECT * FROM sessions WHERE id=? OR external_id=?', (session_id, session_id)).fetchone()
        if s is None: raise NotFound('session not found', id=session_id)
        turns = [dict(r) for r in c.execute('SELECT seq, role, content, created, redactions FROM turns WHERE session_id=? ORDER BY seq LIMIT ?', (s['id'], limit))]
        mems = [r['id'] for r in c.execute('SELECT id FROM memories WHERE session_id=?', (s['id'],))]
    return dict(dict(s), meta=json.loads(s['meta']), turns=turns, memories=mems)


def list_sessions(store, project, limit=100):
    with store.connect() as c:
        return [dict(r) for r in c.execute('''SELECT s.id, s.agent, s.external_id, s.title, s.started, s.ended, s.created, s.meta,
            (SELECT count(*) FROM turns t WHERE t.session_id=s.id) AS turns FROM sessions s WHERE s.project=?
            ORDER BY s.created DESC LIMIT ?''', (scope(project), limit))]


def search(store, project, query, limit=20):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100: raise InvalidInput('limit must be 1..100')
    if not isinstance(query, str) or not 1 <= len(query) <= 1000: raise InvalidInput('query must contain 1-1000 characters')
    terms = text.query_terms(query)
    if not terms: return []
    with store.connect() as c:
        rows = c.execute('''SELECT t.session_id, t.seq, t.role, t.content, bm25(turns_fts) AS rank FROM turns_fts
            JOIN turns t ON t.session_id=turns_fts.session_id AND t.seq=turns_fts.seq JOIN sessions s ON s.id=t.session_id
            WHERE turns_fts MATCH ? AND s.project=? ORDER BY rank LIMIT ?''', (text.fts_query(terms), scope(project), limit)).fetchall()
    return [dict(session=r['session_id'], seq=r['seq'], role=r['role'], content=r['content'][:500], score=round(-r['rank'], 4)) for r in rows]


def purge(store, session_id):
    with store.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        s = c.execute('SELECT id FROM sessions WHERE id=?', (session_id,)).fetchone()
        if s is None: raise NotFound('session not found', id=session_id)
        c.execute('DELETE FROM turns_fts WHERE session_id=?', (session_id,))
        c.execute('UPDATE memories SET session_id=NULL WHERE session_id=?', (session_id,))
        c.execute('DELETE FROM sessions WHERE id=?', (session_id,))  # turns cascade
        c.execute("INSERT INTO turns_fts(turns_fts) VALUES('rebuild')")
    return {'purged_session': session_id}
