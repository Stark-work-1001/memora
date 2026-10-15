"""Vector search kernels: latency and agreement. Synthetic unit vectors (seeded), so this measures
speed and kernel equivalence only -- not retrieval quality.

    python bench/vector_bench.py --out docs/eval/vector-bench.json
"""
import argparse, json, math, platform, random, statistics, sys, time
from array import array
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory_merge import vectors


def unit(rng, d):
    v = [rng.gauss(0, 1) for _ in range(d)]
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def timed(fn, reps):
    out, ts = None, []
    for _ in range(reps):
        t = time.perf_counter(); out = fn(); ts.append((time.perf_counter() - t) * 1000)
    return out, statistics.median(ts)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out'); ap.add_argument('--sizes', default='1000,10000,100000'); ap.add_argument('--dims', default='256,1024')
    a = ap.parse_args()
    rng = random.Random(7)
    native, sumprod = vectors._native, vectors._sumprod
    rows = []
    for d in map(int, a.dims.split(',')):
        for n in map(int, a.sizes.split(',')):
            m = vectors.Matrix(d)
            blobs = [vectors.pack(unit(rng, d)) for _ in range(n)]
            for i, b in enumerate(blobs): m.add(str(i), b)
            queries = [unit(rng, d) for _ in range(5)]
            # 0.1 stored JSON text and decoded every row on every query
            js = [json.dumps(list(vectors.unpack(b))) for b in blobs[:min(n, 10000)]]
            _, t_json = timed(lambda: [json.loads(s) for s in js], 1)
            _, t_blob = timed(lambda: [vectors.unpack(b) for b in blobs[:min(n, 10000)]], 1)
            row = {'dim': d, 'vectors': n, 'decode_10k_json_ms': round(t_json, 1), 'decode_10k_blob_ms': round(t_blob, 1)}
            results = {}
            kernels = [('native', native, sumprod)] if native else []
            kernels += [('python-sumprod', None, sumprod)] if sumprod else []
            kernels += [('python-fsum', None, None)]
            for name, nat, sp in kernels:
                vectors._native, vectors._sumprod = nat, sp
                if nat is None and n * d > 30_000_000 and name == 'python-fsum':
                    row[name + '_ms'] = None; continue  # minutes per query; skipped
                reps = 3 if nat is None and n >= 100000 else 7
                res, ms = timed(lambda: [m.topk(q, 10) for q in queries], reps)
                row[name + '_ms'] = round(ms / len(queries), 2)
                results[name] = [[i for _, i in r] for r in res]
            vectors._native, vectors._sumprod = native, sumprod
            ref = next(iter(results.values()))
            row['rankings_identical'] = all(r == ref for r in results.values())
            rows.append(row); print(json.dumps(row), flush=True)
    report = {'command': ' '.join(['python'] + sys.argv), 'python': platform.python_version(), 'platform': platform.platform(),
              'processor': platform.processor(), 'note': 'median per-query top-10 latency in ms over 5 queries; single process', 'rows': rows}
    if a.out: Path(a.out).write_text(json.dumps(report, indent=2), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
