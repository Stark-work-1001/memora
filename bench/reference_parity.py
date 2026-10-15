"""Does the served GGUF path reproduce the reference implementation?

Embeds the same texts with (a) sentence-transformers on the official safetensors -- the model card's
reference usage, through memory_merge's SentenceTransformersEmbedder -- and (b) an OpenAI-compatible
server (Ollama qwen3-embedding:0.6b, Q8_0 GGUF), then compares per-text cosine similarity and
retrieval quality on the test split. Needs sentence-transformers, so it runs in a separate venv:

    python bench/reference_parity.py --reference <snapshot dir> --out docs/eval/reference-parity.json
"""
import argparse, json, statistics, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory_merge import evaluation, vectors
from memory_merge.providers import Provider, SentenceTransformersEmbedder


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reference', required=True); ap.add_argument('--url', default='http://127.0.0.1:11434/v1')
    ap.add_argument('--model', default='qwen3-embedding:0.6b'); ap.add_argument('--dataset', default='datasets/memory-eval-v1'); ap.add_argument('--out')
    a = ap.parse_args()
    t = time.perf_counter(); ref = SentenceTransformersEmbedder(a.reference, preset='qwen3-embedding', device='cpu'); load_s = time.perf_counter() - t
    srv = Provider(a.url, a.model, preset='qwen3-embedding')
    corpus, queries = evaluation.load(a.dataset)
    docs = [d['content'] for d in corpus[:40]]
    qs = [ref.query_text(q['query']) for q in queries if q['split'] == 'test'][:20]
    out = {'command': ' '.join(['python'] + sys.argv), 'reference': {'path': a.reference, 'revision': ref.revision, 'load_seconds': round(load_s, 1)},
           'served': {'url': a.url, 'model': a.model}}
    for name, texts in (('documents', docs), ('queries_with_instruction', qs)):
        r = ref.embed_batch(texts); s = srv.embed_batch(texts)
        cos = [vectors.dot(x, y) for x, y in zip(r, s)]
        out[name] = {'n': len(cos), 'cosine_min': round(min(cos), 4), 'cosine_mean': round(statistics.fmean(cos), 4), 'cosine_max': round(max(cos), 4)}
        print(name, out[name], flush=True)
    lat = []
    for q in qs:
        t = time.perf_counter(); srv.embed(q); lat.append((time.perf_counter() - t) * 1000)
    out['served_query_embedding_ms'] = {'p50': round(statistics.median(lat), 1), 'max': round(max(lat), 1)}
    t = time.perf_counter(); rep = evaluation.run(a.dataset, ['vector'], split='test', embedding=ref)
    out['reference_test_split'] = dict(rep['modes']['vector']['overall'], seconds=round(time.perf_counter() - t, 1),
                                       latency_ms=rep['modes']['vector']['latency_ms'], by_type={k: v['ndcg'] for k, v in rep['modes']['vector']['by_type'].items()})
    print('reference (sentence-transformers, fp32 CPU) test split:', out['reference_test_split'], flush=True)
    if a.out: Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
