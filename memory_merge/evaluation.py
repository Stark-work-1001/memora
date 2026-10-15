"""Retrieval evaluation. Measures, does not assert.

Dataset formats:
- Memory Merge: corpus.jsonl {id, project, content, category?, polarity?, tags?, lang?} and
  queries.jsonl {id, project, query, relevant: {memory_id: grade}, type?, lang?, split?}.
  Project "@user" maps to the cross-project user scope.
- BEIR: corpus.jsonl {_id, title?, text}, queries.jsonl {_id, text}, qrels/<split>.tsv. Loaded into
  one project; no types or languages.

Metrics per query, averaged: recall@k (share of relevant memories, grade >= 1, in the top k),
success@k (a grade-2 memory in the top k), MRR@k (first relevant), nDCG@k (gain 2^grade - 1), and
zero_result_rate (queries returning nothing at all -- the 'appears to work' failure). Latency is
wall time per recall call in this process (p50/p95), excluding index build.
"""
import importlib.util
import json
import math
import platform
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path

from . import __version__, vectors
from .errors import MemoryMergeError
from .store import USER_SCOPE, Store

REPO = Path(__file__).resolve().parents[1]
LEXICAL_VARIANTS = {'lexical': {}}  # defaults; ablations use 'lexical[unigrams=0,prefix=1,...]'


def _jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def load(path):
    path = Path(path)
    corpus, queries = _jsonl(path / 'corpus.jsonl'), _jsonl(path / 'queries.jsonl')
    if corpus and '_id' in corpus[0]:  # BEIR
        qrels = {}
        for split_file in sorted((path / 'qrels').glob('*.tsv')):
            for line in split_file.read_text(encoding='utf-8').splitlines()[1:]:
                qid, did, score = line.split('\t')[:3]
                if int(score) > 0: qrels.setdefault(qid, {})[did] = int(score); qrels[qid + '#split'] = split_file.stem
        corpus = [{'id': d['_id'], 'project': 'beir', 'content': ((d.get('title') or '') + '\n' + d['text']).strip()} for d in corpus]
        queries = [{'id': q['_id'], 'project': 'beir', 'query': q['text'], 'relevant': qrels[q['_id']], 'split': qrels.get(q['_id'] + '#split', 'test')}
                   for q in queries if q['_id'] in qrels]
    return corpus, queries


def _project(p):
    return USER_SCOPE if p == '@user' else p


def build(corpus, root):
    """Load the corpus as approved memories. Returns (store, memory id -> dataset ids, skipped)."""
    store = Store(root)
    back, skipped = {}, []
    for d in corpus:
        try:
            r = store.capture(_project(d['project']), d['content'], 'eval', mode='manual', confirmed=True, event_id=d['id'],
                              category=d.get('category'), tags=d.get('tags'), polarity=d.get('polarity'))
        except MemoryMergeError as e:
            skipped.append({'id': d['id'], 'error': e.code}); continue
        back.setdefault(r['id'], []).append(d['id'])
    return store, back, skipped


def legacy_retriever(corpus, root):
    """The published 0.1 retrieval code, loaded from tests/legacy/ in a source checkout. 0.1 had no
    user scope, so '@user' memories go to a separate project that is queried alongside (generous to
    the baseline)."""
    src = REPO / 'tests' / 'legacy' / 'store_v0_1.py'
    if not src.is_file(): return None
    spec = importlib.util.spec_from_file_location('mm_store_v0_1', src)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    s = mod.Store(root)
    back = {}
    for d in corpus:
        proj = 'user_scope' if d['project'] == '@user' else d['project']
        try:
            r = s.capture(proj, d['content'], 'eval', mode='manual', confirmed=True, event_id=d['id'])
        except ValueError:
            continue
        back.setdefault(r['id'], []).append(d['id'])
    def retrieve(project, query, k):
        rows = s.recall('user_scope' if project == '@user' else project, query, k)
        if project != '@user': rows += s.recall('user_scope', query, k)
        rows.sort(key=lambda r: r['score'], reverse=True)
        return [r['id'] for r in rows[:k]]
    return retrieve, back


def _metrics(ranked, relevant, k):
    rel = {d: g for d, g in relevant.items() if g >= 1}
    top = ranked[:k]
    found = [d for d in top if d in rel]
    rr = next((1 / i for i, d in enumerate(top, 1) if d in rel), 0.0)
    dcg = sum((2 ** rel[d] - 1) / math.log2(i + 1) for i, d in enumerate(top, 1) if d in rel)
    ideal = sum((2 ** g - 1) / math.log2(i + 1) for i, g in enumerate(sorted(rel.values(), reverse=True)[:k], 1))
    return {'recall': len(set(found)) / len(rel) if rel else 0.0, 'success': float(any(rel[d] >= 2 for d in found)),
            'mrr': rr, 'ndcg': dcg / ideal if ideal else 0.0, 'zero': float(not ranked)}


def _aggregate(rows):
    if not rows: return {}
    out = {m: round(statistics.fmean(r[m] for r in rows), 4) for m in ('recall', 'success', 'mrr', 'ndcg')}
    out['zero_result_rate'] = round(statistics.fmean(r['zero'] for r in rows), 4)
    out['n'] = len(rows)
    return out


def _pct(xs, p):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(math.ceil(p / 100 * len(xs))) - 1)], 2) if xs else None


def evaluate(retrieve, queries, k):
    per, lat = [], []
    for q in queries:
        t = time.perf_counter()
        ranked = retrieve(q['project'], q['query'], k)
        lat.append((time.perf_counter() - t) * 1000)
        m = _metrics(ranked, q['relevant'], k)
        per.append(dict(m, id=q['id'], type=q.get('type', 'all'), lang=q.get('lang', 'all')))
    by = lambda key: {v: _aggregate([r for r in per if r[key] == v]) for v in sorted({r[key] for r in per})}
    return {'overall': _aggregate(per), 'by_type': by('type'), 'by_lang': by('lang'),
            'latency_ms': {'p50': _pct(lat, 50), 'p95': _pct(lat, 95), 'mean': round(statistics.fmean(lat), 2) if lat else None},
            'per_query': per}


def _command():
    # Record how to reproduce the run without leaking this machine's paths.
    prog = Path(sys.argv[0]).name if sys.argv else ''
    prog = 'memory-merge' if prog in ('__main__.py', 'memory-merge', 'memory-merge.exe') else 'python ' + prog
    return ' '.join([prog] + sys.argv[1:])


def run(dataset, modes, split='test', k=10, embedding=None, service_factory=None):
    corpus, queries = load(dataset)
    if split != 'all': queries = [q for q in queries if q.get('split', 'test') == split]
    tmp = Path(tempfile.mkdtemp(prefix='mm-eval-'))
    store, back, skipped = build(corpus, tmp / 'current')
    def to_dataset(ids): return [d for i in ids for d in back.get(i, [])]
    report = {'dataset': {'path': str(dataset), 'corpus': len(corpus), 'queries': len(queries), 'split': split, 'k': k, 'skipped': skipped},
              'environment': {'memory_merge': __version__, 'python': platform.python_version(), 'sqlite': sqlite3.sqlite_version,
                              'platform': platform.platform(), 'machine': platform.machine(), 'processor': platform.processor(),
                              'vector_kernel': vectors.kernel()},
              'command': _command(), 'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'modes': {}}
    service = None
    for mode in modes:
        if mode == 'baseline-v0.1':
            legacy = legacy_retriever(corpus, tmp / 'legacy')
            if legacy is None: report['modes'][mode] = {'error': 'frozen 0.1 code not found (needs a source checkout)'}; continue
            fn, lback = legacy
            retrieve = lambda p, q, k, fn=fn, lback=lback: [d for i in fn(p, q, k) for d in lback.get(i, [])]
        elif mode in LEXICAL_VARIANTS or mode.startswith('lexical['):
            # 'lexical[unigrams=1,prefix=0]' runs an ablation without changing defaults
            opts = LEXICAL_VARIANTS.get(mode) or {kv.split('=')[0]: kv.split('=')[1] == '1' for kv in mode[8:-1].split(',') if kv}
            retrieve = lambda p, q, k, opts=opts: to_dataset(r['id'] for r in store.recall(_project(p), q, limit=k, **opts))
        elif mode in ('vector', 'hybrid'):
            if service is None:
                from .service import MemoryService
                service = service_factory(store) if service_factory else MemoryService(store, embedding)
                if service.embedding is None:
                    report['modes'][mode] = {'error': 'no embedding provider configured (see docs/MODELS.md)'}; service = None; continue
                t = time.perf_counter(); idx = service.index()
                report['index'] = dict(idx, seconds=round(time.perf_counter() - t, 2))
            retrieve = lambda p, q, k, mode=mode: to_dataset(r['id'] for r in service.recall(_project(p), q, limit=k, mode=mode)['results'])
        else:
            report['modes'][mode] = {'error': 'unknown mode'}; continue
        report['modes'][mode] = evaluate(retrieve, queries, k)
    return report


def markdown(report):
    k = report['dataset']['k']
    lines = [f"Dataset `{report['dataset']['path']}` split `{report['dataset']['split']}`: {report['dataset']['queries']} queries over "
             f"{report['dataset']['corpus']} memories, k={k}.", '',
             f'| mode | Recall@{k} | Success@{k} | MRR@{k} | nDCG@{k} | zero-result | p50 ms | p95 ms |', '|---|---|---|---|---|---|---|---|']
    for mode, r in report['modes'].items():
        if 'error' in r: lines.append(f"| {mode} | {r['error']} |||||||"); continue
        o, l = r['overall'], r['latency_ms']
        lines.append(f"| {mode} | {o['recall']:.3f} | {o['success']:.3f} | {o['mrr']:.3f} | {o['ndcg']:.3f} | {o['zero_result_rate']:.3f} | {l['p50']} | {l['p95']} |")
    types = sorted({t for r in report['modes'].values() if 'by_type' in r for t in r['by_type']})
    if len(types) > 1:
        lines += ['', f'nDCG@{k} by query type:', '', '| mode | ' + ' | '.join(types) + ' |', '|---' * (len(types) + 1) + '|']
        for mode, r in report['modes'].items():
            if 'by_type' in r:
                lines.append(f'| {mode} | ' + ' | '.join(f"{r['by_type'].get(t, {}).get('ndcg', 0):.3f}" for t in types) + ' |')
    return '\n'.join(lines)


def run_cli(dataset, modes, split, out, k, service_factory=None):
    report = run(dataset, modes, split, k, service_factory=service_factory)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    slim = {k_: v for k_, v in report.items() if k_ != 'modes'}
    slim['modes'] = {m: {k_: v for k_, v in r.items() if k_ != 'per_query'} for m, r in report['modes'].items()}
    slim['table'] = markdown(report)
    return slim
