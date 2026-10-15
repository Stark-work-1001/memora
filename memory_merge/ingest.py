"""Document ingestion: Markdown, plain text, PDF (optional pypdf), browser bookmarks, JSONL records.

Trust model: an imported document is untrusted content. Chunks enter as kind='chunk',
category='knowledge' and are reviewed per *document* (approving 400 chunks one by one is not a
review anyone performs). Imports are pending unless the caller is the local CLI with --approve.
Detected secrets are redacted (not rejected) so one stray token does not block a whole document.
Provenance is precise enough to cite: the locator holds path, heading path and line range, or page.

Hostile-input limits: file size, chunk count, path confinement to the import root, no symlink
traversal, UTF-8 only for text formats, binary detection.
"""
import hashlib
import html.parser
import json
import re
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath

from . import text
from .errors import DependencyMissing, InvalidInput, InvalidTransition, LimitExceeded, NotFound
from .schema import now
from .store import CATEGORIES, scope

SUFFIXES = {'.md': 'text/markdown', '.markdown': 'text/markdown', '.txt': 'text/plain', '.pdf': 'application/pdf',
            '.html': 'text/html', '.htm': 'text/html', '.jsonl': 'application/jsonl'}
SKIP_DIRS = {'.git', '.hg', '.svn', 'node_modules', '.obsidian', '.trash', '__pycache__', '.venv', 'venv'}
MAX_BYTES, MAX_CHUNKS, CHUNK_TOKENS = 20 * 1024 * 1024, 5000, 350
_HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
_FENCE = re.compile(r'^\s*(```|~~~)')


def _pack(paragraphs, limit=CHUNK_TOKENS):
    """Greedy-pack (text, first_line, last_line) paragraphs into chunks of at most `limit` est. tokens.
    An oversized paragraph is split on sentence ends, then hard-split as a last resort."""
    out, buf, start, end, used = [], [], None, None, 0
    def flush():
        nonlocal buf, start, used
        if buf: out.append(('\n\n'.join(buf), start, end))
        buf, start, used = [], None, 0
    for para, a, b in paragraphs:
        pieces = [para]
        if text.estimate_tokens(para) > limit:
            pieces = [s for s in re.split(r'(?<=[。！？.!?])\s*', para) if s]
            hard = []
            for s in pieces:
                while text.estimate_tokens(s) > limit:
                    cut = max(1, len(s) * limit // max(1, text.estimate_tokens(s)))
                    hard.append(s[:cut]); s = s[cut:]
                hard.append(s)
            pieces = hard
        for p in pieces:
            t = text.estimate_tokens(p)
            if buf and used + t > limit: flush()
            if start is None: start = a
            buf.append(p); end = b; used += t
    flush()
    return out


def _paragraphs(lines, offset=1):
    """Blank-line separated paragraphs with 1-based line numbers; fenced code stays in one piece."""
    paras, buf, first, fence = [], [], None, None
    for i, line in enumerate(lines, offset):
        m = _FENCE.match(line)
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
        if not line.strip() and fence is None:
            if buf: paras.append(('\n'.join(buf).strip(), first, i - 1)); buf, first = [], None
            continue
        if first is None: first = i
        buf.append(line)
    if buf: paras.append(('\n'.join(buf).strip(), first, offset + len(lines) - 1))
    return [p for p in paras if p[0]]


def parse_markdown(raw):
    lines = raw.replace('\r\n', '\n').split('\n')
    title, start = None, 0
    if lines and lines[0].strip() == '---':  # front matter is metadata, not content
        for j in range(1, min(len(lines), 200)):
            if lines[j].strip() == '---':
                for fm in lines[1:j]:
                    if fm.lower().startswith('title:'): title = fm.split(':', 1)[1].strip().strip('"\'') or None
                start = j + 1; break
    sections, heads, seg, seg_start, fence = [], [], [], start + 1, None
    for i in range(start, len(lines)):
        line = lines[i]
        if _FENCE.match(line): fence = None if fence else True
        h = _HEADING.match(line) if not fence else None
        if h:
            sections.append((list(heads), seg, seg_start))
            level = len(h.group(1)); heads = heads[:level - 1] + [h.group(2)]
            if level == 1 and title is None: title = h.group(2)
            seg, seg_start = [], i + 2
        else:
            seg.append(line)
    sections.append((list(heads), seg, seg_start))
    chunks = []
    for path, seg, first in sections:
        for body, a, b in _pack(_paragraphs(seg, first)):
            prefix = ' > '.join(path)
            chunks.append(((prefix + '\n' + body) if prefix else body, {'heading': path, 'lines': [a, b]}))
    return title, chunks


def parse_text(raw):
    lines = raw.replace('\r\n', '\n').split('\n')
    return None, [(body, {'lines': [a, b]}) for body, a, b in _pack(_paragraphs(lines))]


def parse_pdf(data):
    try:
        import pypdf
    except ImportError as e:
        raise DependencyMissing('PDF import needs pypdf', hint="pip install 'memory-merge-local[pdf]'") from e
    import io
    reader = pypdf.PdfReader(io.BytesIO(data))
    if len(reader.pages) > 2000: raise LimitExceeded('PDF has more than 2000 pages')
    title = (reader.metadata or {}).get('/Title') if reader.metadata else None
    chunks = []
    for n, page in enumerate(reader.pages, 1):
        body = page.extract_text() or ''
        for part, _, _ in _pack(_paragraphs(body.split('\n'))):
            chunks.append((part, {'page': n}))
    return (str(title) if title else None), chunks


class _Bookmarks(html.parser.HTMLParser):
    """Netscape bookmark export (all major browsers): <DT><A HREF=...>title</A> [<DD>note], folders as <H3>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items, self.folders, self._mode, self._buf, self._href, self._pending_folder = [], [], None, '', None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'a': self._mode, self._buf, self._href = 'a', '', a.get('href', '')
        elif tag == 'h3': self._mode, self._buf = 'h3', ''
        elif tag == 'dd': self._mode, self._buf = 'dd', ''
        elif tag == 'dl' and self._pending_folder is not None: self.folders.append(self._pending_folder); self._pending_folder = None

    def handle_endtag(self, tag):
        if tag == 'a' and self._mode == 'a':
            self.items.append({'title': self._buf.strip(), 'url': self._href, 'folder': list(self.folders), 'note': ''}); self._mode = None
        elif tag == 'h3' and self._mode == 'h3': self._pending_folder = self._buf.strip(); self._mode = None
        elif tag == 'dl' and self.folders: self.folders.pop()

    def handle_data(self, data):
        if self._mode in ('a', 'h3'): self._buf += data
        elif self._mode == 'dd' and self.items: self.items[-1]['note'] += data.strip()


def parse_bookmarks(raw):
    p = _Bookmarks(); p.feed(raw)
    chunks = []
    for it in p.items:
        if not it['url'].startswith(('http://', 'https://')): continue
        body = '\n'.join(x for x in [it['title'], it['url'], it['note']] if x)
        chunks.append((body, {'url': it['url'], 'folder': it['folder']}))
    return 'Bookmarks', chunks


def parse_jsonl(raw):
    """Generic records (highlights, clippings, exported notes): one JSON object per line with
    "text" and optional "title", "url", "locator" (object), "tags". See docs/DATA_FORMATS.md."""
    chunks = []
    for n, line in enumerate(raw.splitlines(), 1):
        if not line.strip(): continue
        try:
            r = json.loads(line)
        except ValueError:
            raise InvalidInput(f'line {n}: not JSON') from None
        if not isinstance(r, dict) or not isinstance(r.get('text'), str) or not r['text'].strip():
            raise InvalidInput(f'line {n}: object with a non-empty "text" required')
        loc = r.get('locator') if isinstance(r.get('locator'), dict) else {}
        loc = dict(loc, record=n, **({'url': r['url']} if isinstance(r.get('url'), str) else {}))
        body = (r['title'].strip() + '\n' if isinstance(r.get('title'), str) and r['title'].strip() else '') + r['text'].strip()
        chunks.append((body, loc))
    return None, chunks


def _decode(data, name):
    if b'\x00' in data[:8192]: raise InvalidInput(f'{name}: binary content')
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise InvalidInput(f'{name}: not UTF-8 text') from None


def parse(data, suffix, name):
    if suffix == '.pdf': return parse_pdf(data)
    raw = _decode(data, name)
    if suffix in ('.md', '.markdown'): return parse_markdown(raw)
    if suffix in ('.html', '.htm'): return parse_bookmarks(raw)
    if suffix == '.jsonl': return parse_jsonl(raw)
    return parse_text(raw)


def safe_relative(path):
    """Validate a path supplied by an untrusted caller (an MCP agent) *lexically*, before any
    filesystem call: on Windows even resolving a UNC path such as //host/share opens an SMB
    connection, which can leak the user's NTLM credentials to that host."""
    if not isinstance(path, str) or not path or '\x00' in path: raise InvalidInput('path required')
    for pure in (PureWindowsPath(path), PurePosixPath(path)):
        if pure.drive or pure.root or pure.anchor or '..' in pure.parts:
            raise InvalidInput('path must be relative to the import root, without .. or drive/UNC prefixes')
    return path


def import_file(store, project, path, uri, source=None, approve=False, actor='cli', default_title=None):
    scope(project)
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUFFIXES: raise InvalidInput(f'unsupported file type {suffix}', supported=sorted(SUFFIXES))
    if path.stat().st_size > MAX_BYTES: raise LimitExceeded(f'{uri}: larger than {MAX_BYTES} bytes')
    data = path.read_bytes()
    if len(data) > MAX_BYTES: raise LimitExceeded(f'{uri}: larger than {MAX_BYTES} bytes')
    digest = hashlib.sha256(data).hexdigest()
    with store.connect() as c:
        same = c.execute("SELECT id, status FROM documents WHERE project=? AND uri=? AND digest=? AND status IN ('approved','pending')",
                         (project, uri, digest)).fetchone()
    if same: return {'uri': uri, 'document': same['id'], 'status': same['status'], 'result': 'unchanged'}
    title, chunks = parse(data, suffix, uri)
    title, title_redactions = text.redact_value((title or default_title or Path(uri).name)[:300])
    if len(chunks) > MAX_CHUNKS: raise LimitExceeded(f'{uri}: more than {MAX_CHUNKS} chunks')
    status = 'approved' if approve else 'pending'
    doc_id, redactions = str(uuid.uuid4()), title_redactions
    with store.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (doc_id, project, uri, title, SUFFIXES[suffix], digest, len(data),
                   status, (source or 'import:' + uri)[:300], len(chunks), 0, now(), now()))
        for body, loc in chunks:
            body, kinds = text.redact(body)
            loc, loc_redactions = text.redact_value(dict(loc, path=uri))  # headings, URLs, titles too
            redactions += len(kinds) + loc_redactions
            body = body.strip()[:16000]
            if not body: continue
            store._insert(c, project, body, (source or 'import:' + uri)[:300], mode='import', status=status, category='knowledge',
                          tags=[], kind='chunk', doc_id=doc_id, locator=loc, actor=actor)
        c.execute('UPDATE documents SET redactions=? WHERE id=?', (redactions, doc_id))
        if status == 'approved': _supersede_older(store, c, project, uri, doc_id, actor)
    return {'uri': uri, 'document': doc_id, 'status': status, 'chunks': len(chunks), 'redactions': redactions, 'result': 'imported'}


def import_path(store, project, target, source=None, approve=False, actor='cli', root=None):
    """Import a file or a directory tree. `root` confines what may be read (defaults to target)."""
    target = Path(target).resolve()
    root = Path(root).resolve() if root else (target if target.is_dir() else target.parent)
    if not target.is_relative_to(root): raise InvalidInput('path is outside the allowed import root')
    files = [target] if target.is_file() else sorted(
        p for p in target.rglob('*') if p.suffix.lower() in SUFFIXES and not (set(p.relative_to(target).parts[:-1]) & SKIP_DIRS))
    report = {'imported': [], 'unchanged': 0, 'skipped': [], 'errors': []}
    for f in files:
        rel = f.relative_to(root).as_posix()
        if f.is_symlink() or not f.resolve().is_relative_to(root):
            report['skipped'].append({'uri': rel, 'reason': 'symlink or outside root'}); continue
        try:
            r = import_file(store, project, f, rel, source=source, approve=approve, actor=actor)
        except (InvalidInput, LimitExceeded, DependencyMissing, OSError) as e:
            report['errors'].append({'uri': rel, 'error': getattr(e, 'code', type(e).__name__), 'message': str(e)[:200]}); continue
        if r['result'] == 'unchanged': report['unchanged'] += 1
        else: report['imported'].append(r)
    store.flush()
    return report


def _supersede_older(store, c, project, uri, keep, actor):
    for old in c.execute("SELECT id FROM documents WHERE project=? AND uri=? AND id!=? AND status='approved'", (project, uri, keep)).fetchall():
        c.execute("UPDATE documents SET status='superseded', updated=? WHERE id=?", (now(), old['id']))
        for r in c.execute("SELECT * FROM memories WHERE doc_id=? AND status='approved'", (old['id'],)).fetchall():
            store._set_status(c, r, 'superseded', 'supersede', actor)


DOC_ACTIONS = {'approve': 'approved', 'reject': 'rejected', 'forget': 'deleted'}
DOC_FROM = {'approve': {'pending', 'rejected', 'superseded'}, 'reject': {'pending', 'approved'},
            'forget': {'pending', 'approved', 'rejected', 'superseded'}}


def review_document(store, project, doc_id, action, actor='cli'):
    """Apply one review decision to a document and all of its chunks."""
    if action not in DOC_ACTIONS: raise InvalidInput('action must be approve, reject or forget')
    to = DOC_ACTIONS[action]
    with store.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        d = c.execute('SELECT * FROM documents WHERE id=? AND project=?', (doc_id, scope(project))).fetchone()
        if d is None: raise NotFound('document not found in project', id=doc_id)
        if d['status'] == to: return {'document': doc_id, 'status': to, 'chunks_changed': 0}
        if d['status'] not in DOC_FROM[action]: raise InvalidTransition(f"cannot {action} a {d['status']} document")
        n = 0
        for r in c.execute('SELECT * FROM memories WHERE doc_id=?', (doc_id,)).fetchall():
            if r['status'] == to or r['status'] == 'deleted': continue
            store._set_status(c, r, to, action, actor); n += 1
        c.execute('UPDATE documents SET status=?, updated=? WHERE id=?', (to, now(), doc_id))
        if to == 'approved': _supersede_older(store, c, project, d['uri'], doc_id, actor)
    store.flush()
    return {'document': doc_id, 'status': to, 'chunks_changed': n}


def list_documents(store, project, status=None):
    with store.connect() as c:
        sql, args = 'SELECT * FROM documents WHERE project=?', [scope(project)]
        if status: sql += ' AND status=?'; args.append(status)
        return [dict(r) for r in c.execute(sql + ' ORDER BY created DESC', args)]
