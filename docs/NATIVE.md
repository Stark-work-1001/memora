# Version 1.0.1 note

The Windows standalone now requires the compiled native module and verifies it in frozen-runtime smoke tests. This document below preserves the original retrieval design; current measurements and safety changes are in [RESEARCH_1.0.1.md](RESEARCH_1.0.1.md). Source-only Python fallback remains supported.

# Native code: where Rust earns its keep

Decision: one optional Rust extension, `memory_merge_native`, for exact top-k vector search.
Everything else stays Python. The pure-Python install path is unchanged and fully supported; the
extension is an accelerator, not a requirement.

## The candidates the brief listed, and the verdicts

| Candidate | Verdict | Why |
|---|---|---|
| Native tokenizer for unsegmented scripts | **No** | The real problem was segmentation, not speed. A Python bigram analyzer (Lucene's CJKBigramFilter scheme) lifted test-split nDCG@10 from 0.340 to 0.649 (docs/EVALUATION.md). Analysis is a per-character loop that runs at write and query time on texts of at most 16,000 characters; recall p50 is about 4 ms end to end. A compiled tokenizer as an FTS5 extension would also need `sqlite3.enable_load_extension`, which several Python builds disable. |
| ANN / vector-scan kernel via PyO3 | **Yes (exact scan, not ANN)** | Measured below: 85-125x faster than the best pure-Python path at 10k-100k vectors. Exact search keeps perfect recall and needs no index to build, persist or tune. |
| PyO3 bindings with Python orchestrating | **Yes** | That is the shape chosen: one function, `topk(matrix, query, dim, k)`, on a borrowed float32 buffer. |
| Compiled Markdown parser and sync watcher | **No** | Sync parses a few kilobytes of front matter per file and polls modification times; it is I/O-bound. Python's standard library is enough. |
| Batching and ONNX inference hosting in Rust | **No** | Embedding latency is dominated by the model, not the host language. The in-process paths reuse mature runtimes (sentence-transformers, llama.cpp); batching is implemented in Python. |
| Single-binary Rust MCP server | **No** | It would rewrite the whole system, drop the official Python MCP SDK, and multiply build targets, for no measured bottleneck. |

ANN (HNSW and similar) is not used either: at personal scale (thousands to low hundreds of thousands
of vectors) exact search answers in milliseconds natively (below), and ANN would add approximate
recall, index maintenance on every write and parameters to tune. Revisit above about a million
vectors.

## Measurements

```bash
python bench/vector_bench.py --out docs/eval/vector-bench.json
```

Synthetic unit vectors (seed 7), median per-query top-10 latency over 5 queries, single process,
Windows 11, Python 3.13.5, Intel i9-12900H. This measures speed and kernel agreement only.

| vectors x dim | native | Python >= 3.12 (`math.sumprod`) | Python 3.11 (`math.fsum`) | identical rankings |
|---|---|---|---|---|
| 1k x 256 | 0.29 ms | 4.5 ms | 19.2 ms | yes |
| 10k x 256 | 0.91 ms | 52.8 ms | 197.8 ms | yes |
| 100k x 256 | 4.08 ms | 528 ms | 2,086 ms | yes |
| 1k x 1024 | 1.17 ms | 18.6 ms | 82.6 ms | yes |
| 10k x 1024 | 1.99 ms | 185 ms | 784 ms | yes |
| 100k x 1024 | 13.6 ms | 1,694 ms | (skipped: minutes) | yes |

The storage format mattered as much as the kernel. 0.1 stored vectors as JSON text and decoded every
row on every query: decoding 10,000 x 1024 vectors took 3,075 ms against 25 ms for the float32 BLOBs
used now. The service also caches the decoded matrix between queries, invalidated by a generation
counter maintained by SQL triggers.

## Design

- **Exactness and agreement.** Products and sums in f64 (the Python kernel sums f64 values from
  float32 inputs), ties broken towards the lower row index in both kernels. `tests/test_text_vectors.py`
  checks that native, `sumprod` and `fsum` kernels return identical rankings, including exact ties.
- **No copies.** The kernel borrows the `array('f')` buffer through the buffer protocol (stable ABI
  since Python 3.11, hence `abi3-py311`: one wheel per platform for every CPython >= 3.11).
- **Parallelism without dependencies.** `std::thread::scope` splits rows across up to 8 threads above
  about a million floats; the GIL is released during the scan. No rayon, no BLAS.
- **Safety.** One `unsafe` block creates slices over the borrowed buffers after checking
  C-contiguity, float32 format and sizes; the buffers stay exported (so cannot be resized or freed)
  until the function returns.

## Build

```bash
pip install ./native        # needs a Rust toolchain; maturin is fetched as the build backend
python -c "import memory_merge_native, memory_merge.vectors as v; print(v.kernel())"   # -> native
```

Measured here: 32 s build, a 110 KB `cp311-abi3-win_amd64` wheel. CI builds and tests it on Linux,
macOS and Windows (`.github/workflows/ci.yml`, job `native`); that workflow has not run yet. Without
the extension, `memory-merge doctor` reports which Python kernel is active and warns when it is the
slow 3.11 path.

## Cost accepted

A second build system (Cargo + maturin) and a Rust toolchain for contributors who change the kernel.
The kernel is about 130 lines; the Python fallback is the specification it must match.
