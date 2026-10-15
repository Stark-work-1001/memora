"""Judge evaluation on the corpus of datasets/memory-eval-v1 (needs a running OpenAI-compatible server).

    python bench/judge_eval.py --model hf.co/Qwen/Qwen3-1.7B-GGUF:Q8_0 --out docs/eval/judge-qwen3-1.7b.json

What it measures, per response-format strategy:
- valid: share of replies that pass judge.parse (the rest fail closed and stay plain pending items)
- category agreement with the dataset's category labels (labels written by the dataset author, so
  this is agreement with one annotator, not accuracy against ground truth)
- instruction_like flags on the 6 memories tagged 'suspicious' (recall) and on the other 234 (false positives)
- latency per call
"""
import argparse, json, statistics, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory_merge.errors import MemoryMergeError
from memory_merge.providers import Provider

STRATEGIES = {
    'json_schema+no_think': dict(response_format='json_schema', no_think=True),
    'json_object+no_think': dict(response_format='json_object', no_think=True),
    'json_schema': dict(response_format='json_schema'),
    'json_object': dict(response_format='json_object'),
    'none+no_think': dict(response_format='none', no_think=True),
    'none (thinking)': dict(response_format='none'),
}


def pct(xs, p):
    xs = sorted(xs); return round(xs[min(len(xs) - 1, max(0, int(len(xs) * p / 100 + 0.5) - 1))], 1) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default='http://127.0.0.1:11434/v1'); ap.add_argument('--model', required=True)
    ap.add_argument('--dataset', default='datasets/memory-eval-v1'); ap.add_argument('--strategies', default=','.join(STRATEGIES))
    ap.add_argument('--limit', type=int, default=0, help='first N memories only (0 = all)'); ap.add_argument('--out')
    a = ap.parse_args()
    corpus = [json.loads(l) for l in open(Path(a.dataset) / 'corpus.jsonl', encoding='utf-8')]
    if a.limit: corpus = corpus[:a.limit]
    report = {'command': ' '.join(['python'] + sys.argv), 'model': a.model, 'memories': len(corpus), 'strategies': {}}
    for name in a.strategies.split(','):
        p = Provider(a.url, a.model, timeout=180, **STRATEGIES[name])
        rows, lat, errors = [], [], {}
        for d in corpus:
            t = time.perf_counter()
            try:
                r = p.judge(d['content']); ok = True
            except MemoryMergeError as e:
                r, ok = None, False; errors[e.code] = errors.get(e.code, 0) + 1
            lat.append((time.perf_counter() - t) * 1000)
            rows.append((d, r))
        valid = [(d, r) for d, r in rows if r]
        sus = [(d, r) for d, r in valid if 'suspicious' in d.get('tags', [])]
        clean = [(d, r) for d, r in valid if 'suspicious' not in d.get('tags', [])]
        res = {
            'valid': round(len(valid) / len(rows), 3), 'failed_closed': errors,
            'category_agreement': round(sum(r['category'] == d['category'] for d, r in valid) / max(1, len(valid)), 3),
            'injection_recall': f"{sum(bool(r.get('instruction_like')) for _, r in sus)}/{len(sus)}",
            'injection_false_positives': f"{sum(bool(r.get('instruction_like')) for _, r in clean)}/{len(clean)}",
            'sensitive_flags': sum(bool(r.get('sensitive')) for _, r in valid),
            'durability': {k: sum(r.get('durability') == k for _, r in valid) for k in ('durable', 'ephemeral', 'unclear', None)},
            'importance_mean_by_category': {c: round(statistics.fmean(r['importance'] for d, r in valid if d['category'] == c), 2)
                                            for c in sorted({d['category'] for d, _ in valid})},
            'latency_ms': {'p50': pct(lat, 50), 'p95': pct(lat, 95), 'mean': round(statistics.fmean(lat), 1)},
            'confusion': {},
        }
        for d, r in valid:
            key = f"{d['category']}->{r['category']}"
            res['confusion'][key] = res['confusion'].get(key, 0) + 1
        report['strategies'][name] = res
        print(name, json.dumps({k: v for k, v in res.items() if k != 'confusion'}, ensure_ascii=False), flush=True)
    if a.out: Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
