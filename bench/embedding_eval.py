"""Embedding configuration grid on the labelled dataset (needs a running embedding server).

    python bench/embedding_eval.py --split dev  --out docs/eval/embedding-dev.json
    python bench/embedding_eval.py --split test --configs default --out docs/eval/embedding-test.json

Defaults point at Ollama's OpenAI-compatible endpoint with qwen3-embedding:0.6b (whose blob is
byte-identical to the official Qwen3-Embedding-0.6B Q8_0 GGUF, see docs/MODELS.md).
"""
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory_merge import evaluation
from memory_merge.providers import Provider

CONFIGS = {
    'default': dict(preset='qwen3-embedding'),                         # instruction on, 1024 dims
    'no-instruction': dict(preset='qwen3-embedding', query_template='{text}'),
    'dim512': dict(preset='qwen3-embedding', dimensions=512),
    'dim256': dict(preset='qwen3-embedding', dimensions=256),
    'dim128': dict(preset='qwen3-embedding', dimensions=128),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default='http://127.0.0.1:11434/v1'); ap.add_argument('--model', default='qwen3-embedding:0.6b')
    ap.add_argument('--dataset', default='datasets/memory-eval-v1'); ap.add_argument('--split', default='dev')
    ap.add_argument('--configs', default=','.join(CONFIGS)); ap.add_argument('--out')
    a = ap.parse_args()
    out = {'command': ' '.join(['python'] + sys.argv), 'model': a.model, 'url': a.url, 'split': a.split, 'runs': {}}
    first = True
    for name in a.configs.split(','):
        p = Provider(a.url, a.model, **CONFIGS[name])
        modes = (['baseline-v0.1', 'lexical'] if first else []) + ['vector', 'hybrid']
        t = time.perf_counter()
        r = evaluation.run(a.dataset, modes, split=a.split, embedding=p)
        r['wall_seconds'] = round(time.perf_counter() - t, 1)
        out['runs'][name] = r
        print(f'## {name} (index {r.get("index", {}).get("seconds")} s, dim {r.get("index", {}).get("dim")})')
        print(evaluation.markdown(r), flush=True)
        first = False
    if a.out:
        for r in out['runs'].values():
            for m in r['modes'].values(): m.pop('per_query', None)
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
