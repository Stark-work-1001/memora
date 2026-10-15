"""Command line. The CLI is the user's own terminal, so it is a trusted reviewer: it may confirm,
approve, import with --approve and purge. Output is JSON on stdout; errors are JSON on stderr with a
stable exit code per error class (memory_merge/errors.py)."""
import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__, config
from .errors import MemoryMergeError

RELATIONS = ['supports', 'contradicts', 'supersedes', 'related']
ACTIONS = ['approve', 'reject', 'forget', 'archive', 'restore']
WRITES = {'capture', 'remember', 'review', 'link', 'unlink', 'demo'}


def _console():
    # A Chinese-locale Windows console encodes stdout as GBK: printing a memory that contains emoji or
    # Thai would raise UnicodeEncodeError (0.1 crashed this way). Pipes get UTF-8; consoles get
    # escapes for what they cannot show.
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.isatty(): stream.reconfigure(errors='backslashreplace')
            else: stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str), flush=True)


def parser():
    p = argparse.ArgumentParser(prog='memora', description='Local-first memory entity for users and AI agents')
    p.add_argument('--data', default=None, help='data directory (default: MM_DATA or the platform data dir)')
    p.add_argument('--version', action='version', version=__version__)
    sub = p.add_subparsers(dest='cmd', required=True)
    def cmd(name, help_, project=False):
        s = sub.add_parser(name, help=help_)
        if project: s.add_argument('--project', default='default')
        return s

    for n, h in [('health', 'counts and integrity'), ('flush', 'export pending Markdown mirror files'), ('demo', 'load synthetic demo data'),
                 ('drill', 'prove backup+restore round-trips'), ('version', 'print version')]:
        cmd(n, h)
    s = cmd('doctor', 'diagnose the environment'); s.add_argument('--probe', action='store_true', help='also call configured providers')
    s = cmd('rebuild', 'rebuild derived state (FTS index and Markdown mirror)')
    s.add_argument('--fts-only', action='store_true'); s.add_argument('--mirror-only', action='store_true')
    s = cmd('backup', 'online backup (verified)'); s.add_argument('target', nargs='?')
    s = cmd('restore', 'restore a backup into a NEW data directory'); s.add_argument('backup'); s.add_argument('target_dir')
    s = cmd('maintain', 'integrity check, FTS optimize, ANALYZE'); s.add_argument('--compact', action='store_true', help='also checkpoint WAL and VACUUM')
    s = cmd('prune-vectors', 'drop vectors of other models'); s.add_argument('--keep', required=True)
    s = cmd('report', 'maintenance suggestions (stale, duplicates, conflicts)', True); s.add_argument('--stale-days', type=int, default=180)
    s = cmd('purge', 'irreversibly delete a memory and compact', True); s.add_argument('id'); s.add_argument('--yes', action='store_true')
    s = cmd('web', 'local mind-graph viewer'); s.add_argument('--port', type=int, default=8765)
    s.add_argument('--review', action='store_true', help='enable approve/reject buttons (token-protected)')
    s = cmd('agent', 'memory agent workbench (chat, model assembly, review and MCP companion)')
    s.add_argument('--port', type=int, default=8765)
    cmd('mcp', 'run the built-in MCP stdio server')
    s = cmd('bridge', 'authenticated loopback MCP Streamable HTTP gateway')
    s.add_argument('--port',type=int,default=8766)

    for name in ('capture', 'remember'):
        s = cmd(name, 'store a candidate (pending)' if name == 'capture' else 'store a memory you want kept', True)
        s.add_argument('content'); s.add_argument('--source', required=True); s.add_argument('--event-id')
        s.add_argument('--category'); s.add_argument('--tag', action='append'); s.add_argument('--polarity', choices=['positive', 'negative'])
        s.add_argument('--supersedes')
        if name == 'remember': s.add_argument('--confirmed', action='store_true', help='approve immediately')
    s = cmd('list', 'list memories (paginated)', True)
    s.add_argument('--status', choices=['pending', 'approved', 'rejected', 'deleted', 'archived', 'superseded'])
    s.add_argument('--limit', type=int, default=100); s.add_argument('--cursor'); s.add_argument('--category'); s.add_argument('--tag'); s.add_argument('--kind')
    s = cmd('show', 'one memory with edges and support', True); s.add_argument('id')
    for name in ('recall', 'rag'):
        s = cmd(name, 'retrieve memories' if name == 'recall' else 'evidence pack for an answer', True); s.add_argument('query')
        s.add_argument('--mode', choices=['auto', 'lexical', 'vector', 'hybrid'], default='auto'); s.add_argument('--limit', type=int, default=10)
        s.add_argument('--no-user', action='store_true', help='exclude the cross-project user scope'); s.add_argument('--category'); s.add_argument('--tag', action='append')
        if name == 'rag': s.add_argument('--budget', type=int, default=6000); s.add_argument('--max-tokens', type=int)
    s = cmd('review', 'approve/reject/forget/archive/restore', True); s.add_argument('id'); s.add_argument('action', choices=ACTIONS)
    s = cmd('queue', 'pending review queue with advice', True); s.add_argument('--limit', type=int, default=50)
    s = cmd('judge', 'advisory judge for one memory or the pending queue', True); s.add_argument('id', nargs='?')
    s.add_argument('--pending', action='store_true'); s.add_argument('--max', type=int, default=20)
    cmd('judge-calibration', 'how well judge importance predicts your decisions')
    s = cmd('index', 'embed memories for the configured model (incremental)'); s.add_argument('--project'); s.add_argument('--max', type=int)
    for name in ('link', 'unlink'):
        s = cmd(name, 'add a typed edge' if name == 'link' else 'remove a typed edge', True)
        s.add_argument('a'); s.add_argument('b'); s.add_argument('relation', choices=RELATIONS)
    s = cmd('import', 'import documents (md, txt, pdf, bookmarks html, jsonl)', True); s.add_argument('path')
    s.add_argument('--approve', action='store_true', help='approve immediately (you reviewed the files)'); s.add_argument('--source')
    s = cmd('docs', 'list or review imported documents', True); s.add_argument('action', choices=['list', 'approve', 'reject', 'forget'])
    s.add_argument('document', nargs='?')
    s = cmd('sync', 'turn Markdown mirror edits into pending revisions', True)
    s.add_argument('--watch', action='store_true'); s.add_argument('--interval', type=float, default=5.0)
    s = cmd('session', 'conversation archive', True)
    s.add_argument('action', choices=['import', 'list', 'show', 'search', 'purge', 'hook']); s.add_argument('arg', nargs='?')
    s.add_argument('--format', choices=['memory-merge', 'claude-code'], default='memory-merge'); s.add_argument('--yes', action='store_true')
    s = cmd('profile', 'cited user profile (preferences and prohibitions)'); s.add_argument('--project')
    s = cmd('briefing', 'cited start-of-task briefing', True); s.add_argument('--task'); s.add_argument('--max-tokens', type=int, default=1200)
    s = cmd('eval', 'retrieval evaluation on a labelled dataset'); s.add_argument('--dataset', required=True)
    s.add_argument('--modes', default='lexical', help='semicolon-separated, e.g. "baseline-v0.1;lexical;hybrid"'); s.add_argument('--split', default='test'); s.add_argument('--out'); s.add_argument('--k', type=int, default=10)
    s = cmd('setup', 'print MCP host configuration (nothing is written)')
    s.add_argument('host', choices=['claude-code', 'claude-desktop', 'codex', 'cursor', 'generic']); s.add_argument('--review', action='store_true')
    return p


DEMO = [  # 0-3 are the 0.1 demo rows (same event ids, so re-running on an old demo database is idempotent)
    ('demo', '选择 SQLite 作为事务真源', None, None, True), ('demo', 'Markdown 镜像支持人类审阅', None, None, True),
    ('demo', '自动记忆先进入待审队列', None, None, True), ('demo', 'RAG 召回必须附带来源', None, None, True),
    (':user', 'I prefer concise answers: code first, explanation after.', 'preference', None, True),
    ('demo', "Don't run a schema migration on the live database without a fresh, verified backup.", 'lesson', 'negative', True),
    ('demo', 'Candidate: the viewer could group nodes by category.', None, None, False),
]


def demo(store):
    rows = [store.capture(p, text_, 'demo:synthetic', mode='manual', confirmed=ok, event_id=str(i), category=cat, polarity=pol)
            for i, (p, text_, cat, pol, ok) in enumerate(DEMO)]
    store.link('demo', rows[0]['id'], rows[1]['id'], 'supports'); store.link('demo', rows[2]['id'], rows[3]['id'], 'supports')
    return {'synthetic_memories': len(rows), 'project': 'demo', 'pending': 1}


def setup_snippet(host, data, review=False):
    env = {'MM_DATA': str(data)}
    if review: env['MM_ENABLE_REVIEW'] = '1'
    server = {'command': sys.executable, 'args': ['-m', 'memory_merge.server'], 'env': env}
    name = 'memory-merge-review' if review else 'memory-merge'
    hook_cmd = f'"{sys.executable}" -m memory_merge --data "{data}" session hook'
    if host == 'codex':
        envs = ', '.join(f'{k} = {json.dumps(v)}' for k, v in env.items())
        return {'file': '~/.codex/config.toml', 'append': f'[mcp_servers.{name}]\ncommand = {json.dumps(sys.executable)}\nargs = ["-m", "memory_merge.server"]\nenv = {{ {envs} }}\n'}
    out = {'mcpServers': {name: server}}
    if host == 'claude-code':
        return {'file': '.mcp.json (project) or `claude mcp add-json`', 'json': out,
                'optional_hooks_for_settings_json': {'hooks': {'SessionEnd': [{'hooks': [{'type': 'command', 'command': hook_cmd}]}]}},
                'instructions_file': 'integrations/AGENT_INSTRUCTIONS.md (paste into CLAUDE.md)'}
    if host == 'claude-desktop': return {'file': 'claude_desktop_config.json', 'json': out}
    if host == 'cursor': return {'file': '~/.cursor/mcp.json or .cursor/mcp.json', 'json': out}
    return {'json': out}


def run(a):
    from .store import Store
    from .service import MemoryService
    from . import ingest, judge, mirror, ops, sessions
    data = Path(a.data) if a.data else config.default_data_dir()
    if a.cmd == 'version': return {'version': __version__}
    if a.cmd == 'setup': return setup_snippet(a.host, data.resolve(), a.review)
    if a.cmd == 'restore': return ops.restore(a.backup, a.target_dir)
    if a.cmd == 'eval':  # temp stores only; never touches the user's data
        from . import evaluation
        return evaluation.run_cli(a.dataset, [m.strip() for m in a.modes.split(';')], a.split, a.out, a.k, service_factory=MemoryService.from_env)
    if a.cmd == 'doctor' and not (data / 'memory.sqlite3').exists():
        return ops.doctor(None, probe=a.probe)
    store = Store(data)
    if a.cmd == 'session' and a.action == 'hook':
        print(json.dumps(sessions.hook(store, sys.stdin.read(), None if a.project == 'default' else a.project)), file=sys.stderr)
        return None
    service = MemoryService.from_env(store)
    if a.cmd == 'bridge':
        from .bridge import run
        run(store,service,a.port)
        return None
    if a.cmd == 'mcp':
        from .server import create_server, run_stdio
        run_stdio(create_server(store, service))
        return None
    if a.cmd in {'web', 'agent'}:
        from .web import make_server
        from .agent import Agent
        agent = Agent(store) if a.cmd == 'agent' else None
        server = make_server(store, a.port, review=True if agent else a.review, agent=agent)
        print(f'{"Memora" if agent else "Mind graph"}: http://127.0.0.1:{server.server_port}', flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally:
            if agent: agent.close()
            server.server_close()
        return None
    c = a.cmd
    out = _dispatch(a, c, store, service)
    if c in WRITES: store.flush()  # keep the Markdown mirror current after writes, as 0.1 did
    return out


def _dispatch(a, c, store, service):
    from . import ingest, judge, mirror, ops, sessions
    from .service import MemoryService
    if c == 'health': return dict(store.health(), version=__version__, data=str(store.root))
    if c == 'doctor': return ops.doctor(store, probe=a.probe)
    if c == 'flush': return store.flush()
    if c == 'rebuild': return store.rebuild(fts=not a.mirror_only, mirror_files=not a.fts_only)
    if c == 'backup': return store.backup(a.target)
    if c == 'drill': return ops.drill(store)
    if c == 'maintain':
        out = ops.maintain(store)
        if a.compact: out['compact'] = ops.compact(store)
        return out
    if c == 'prune-vectors': return ops.prune_vectors(store, a.keep)
    if c == 'report': return ops.report(store, a.project, a.stale_days)
    if c == 'purge':
        if not a.yes: raise SystemExit('purge is irreversible: re-run with --yes')
        return ops.purge(store, a.project, a.id)
    if c == 'demo': return demo(store)
    if c in ('capture', 'remember'):
        return store.capture(a.project, a.content, a.source, mode='manual' if c == 'remember' else 'auto', confirmed=getattr(a, 'confirmed', False),
                             event_id=a.event_id, category=a.category, tags=a.tag, polarity=a.polarity, supersedes=a.supersedes, actor='cli')
    if c == 'list': return store.page(a.project, a.status, a.limit, a.cursor, category=a.category, tag=a.tag, kind=a.kind)
    if c == 'show':
        m = store.get(a.project, a.id)
        return dict(m, edges=store.edges_of(a.project, [a.id]), support=store.support(a.id))
    if c == 'recall':
        return service.recall(a.project, a.query, limit=a.limit, mode=a.mode, include_user=not a.no_user, category=a.category, tags=a.tag)
    if c == 'rag':
        return service.rag(a.project, a.query, budget=a.budget, max_tokens=a.max_tokens, limit=a.limit, mode=a.mode,
                           include_user=not a.no_user, category=a.category, tags=a.tag)
    if c == 'review': return store.review(a.project, a.id, a.action, actor='cli')
    if c == 'queue': return service.review_queue(a.project, limit=a.limit)
    if c == 'judge':
        if a.pending: return service.judge_pending(a.project, a.max)
        if not a.id: raise SystemExit('judge needs an id or --pending')
        return service.judge(a.project, a.id)
    if c == 'judge-calibration': return judge.calibration(store)
    if c == 'index': return service.index(a.project, max_items=a.max)
    if c == 'link': return store.link(a.project, a.a, a.b, a.relation, actor='cli')
    if c == 'unlink': return store.unlink(a.project, a.a, a.b, a.relation, actor='cli')
    if c == 'import': return ingest.import_path(store, a.project, a.path, source=a.source, approve=a.approve, actor='cli')
    if c == 'docs':
        if a.action == 'list': return ingest.list_documents(store, a.project)
        if not a.document: raise SystemExit('docs approve/reject/forget needs a document id')
        return ingest.review_document(store, a.project, a.document, a.action)
    if c == 'sync':
        if a.watch:
            print(f'watching {store.root / "markdown"} every {a.interval}s (Ctrl+C to stop)', file=sys.stderr)
            try: mirror.watch(store, a.interval, a.project, on_report=emit)
            except KeyboardInterrupt: pass
            return None
        return mirror.sync(store, a.project)
    if c == 'session':
        if a.action == 'import':
            if not a.arg: raise SystemExit('session import needs a file')
            if a.format == 'claude-code': return sessions.import_claude_code(store, a.arg, a.project, actor='cli')
            return sessions.import_records(store, sessions.read_jsonl(a.arg), a.project, actor='cli')
        if a.action == 'list': return sessions.list_sessions(store, a.project)
        if a.action == 'show': return sessions.show(store, a.arg)
        if a.action == 'search': return sessions.search(store, a.project, a.arg or '')
        if a.action == 'purge':
            if not a.yes: raise SystemExit('session purge is irreversible: re-run with --yes')
            return sessions.purge(store, a.arg)
    if c == 'profile': return service.profile(a.project)
    if c == 'briefing': return service.briefing(a.project, task=a.task, max_tokens=a.max_tokens)
    raise SystemExit(f'unknown command {c}')


def main(argv=None):
    _console()
    a = parser().parse_args(argv)
    try:
        result = run(a)
    except MemoryMergeError as e:
        print(e.to_json(), file=sys.stderr)
        sys.exit(e.exit_code)
    if result is not None: emit(result)


if __name__ == '__main__':
    main()
