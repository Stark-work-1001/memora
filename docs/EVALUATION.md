# Evaluation

## What "good" means here

Set before measuring, held to throughout:

1. **Retrieval quality is measured, not asserted**, on labelled data shaped like what this system
   stores (short multilingual engineering memories, personal preferences), with options chosen on a
   dev split and reported on a held-out test split.
2. **No silent failure.** A query with relevant memories should not return nothing (0.1's dominant
   failure), and any degraded mode must say so.
3. **Safety properties have tests**, including adversarial ones (forged evidence boundaries, CSRF,
   self-approval, purge leaving bytes behind).
4. **Upgrades never lose data**: migrations tested against databases written by the real 0.1 code.
5. **Every number has a command** that reproduces it, and every claim not backed by a measurement is
   listed under "Not verified".

## Dataset: `datasets/memory-eval-v1`

240 memories across four invented software projects plus a personal `@user` scope: 55% Simplified
Chinese written without spaces, 30% English, 10% mixed, 5% Japanese. It includes near-duplicates
(some across languages), 11 superseded/updated facts, 17 negative "do not" memories, the same topic
with different answers per project, and 6 planted prompt-injection notes. 160 queries with graded
relevance (2 = answers, 1 = useful context), typed: keyword 25, question 40, paraphrase 35,
cross-lingual 20, short 15, negative 10, scoped 15; split 64 dev / 96 test, evenly per type.

**Provenance and bias.** Written for this project by a separate agent that was given the use case
but not told how retrieval works, then frozen before any tuning (validated by
`tests/test_eval.py`). It is synthetic, from one annotator; grade-1 labels are subjective; cobalt has
42 queries and `@user` 18, so pooled scores lean towards cobalt. Treat absolute numbers as indicative
and comparisons between systems on the same data as the main signal. No real user data was available
or used.

## Protocol and metrics

`memory_merge/evaluation.py` loads the corpus into a fresh store (approved), runs every query
through a retrieval mode, and computes per query, averaged: Recall@10 (share of relevant memories in
the top 10), Success@10 (a grade-2 memory in the top 10), MRR@10, nDCG@10 (gain 2^grade - 1), the
zero-result rate, and wall-clock latency per recall call (p50/p95, index build excluded).
`baseline-v0.1` runs the frozen published 0.1 code (`tests/legacy/store_v0_1.py`); since 0.1 had no
user scope, `@user` memories are put in a separate project that the baseline also queries (generous
to the baseline).

Machine for all numbers: Windows 11, Intel i9-12900H, 64 GB RAM, RTX 3070 Ti Laptop (8 GB), Python
3.13.5, SQLite 3.50.2. The GPU was shared with other workloads during model runs, so model latencies
are pessimistic and varied between runs.

## Lexical retrieval (no model)

```bash
memory-merge eval --dataset datasets/memory-eval-v1 --split dev  --modes "baseline-v0.1;lexical;lexical[stop_words=0,unigrams=0,prefix=0];..." --out docs/eval/lexical-dev.json
memory-merge eval --dataset datasets/memory-eval-v1 --split test --modes "baseline-v0.1;lexical;lexical[unigrams=0,prefix=0,stop_words=0];lexical[unigrams=0,prefix=0,stop_words=1];lexical[unigrams=1,prefix=0,stop_words=1]" --out docs/eval/lexical-test.json
```

Dev split (64 queries), ablation grid used to choose the defaults:

| configuration | Recall@10 | MRR@10 | nDCG@10 | zero-result |
|---|---|---|---|---|
| 0.1 baseline | 0.393 | 0.398 | 0.362 | 40.6% |
| bigrams only | 0.702 | 0.673 | 0.614 | 1.6% |
| + prefix | 0.720 | 0.689 | 0.633 | 1.6% |
| + unigram backoff | 0.767 | 0.701 | 0.641 | 0% |
| + unigram + prefix | 0.772 | 0.733 | 0.673 | 0% |
| + stopwords | 0.694 | 0.693 | 0.630 | 3.1% |
| + stopwords + unigram | 0.759 | 0.720 | 0.657 | 1.6% |
| **+ stopwords + unigram + prefix (default)** | 0.749 | 0.735 | **0.674** | 1.6% |

The default was the best dev nDCG and MRR; its margin over the same configuration without stopwords
(0.673) is noise at 64 queries.

Test split (96 queries), run once:

| mode | Recall@10 | Success@10 | MRR@10 | nDCG@10 | zero-result | p50 ms |
|---|---|---|---|---|---|---|
| 0.1 baseline | 0.392 | 0.438 | 0.392 | 0.340 | 45.8% | 5.9 |
| **lexical (default)** | **0.754** | 0.802 | 0.697 | **0.649** | **0%** | 4.3 |
| bigrams only | 0.732 | 0.792 | 0.672 | 0.626 | 1.0% | 3.5 |
| bigrams + stopwords | 0.727 | 0.781 | 0.675 | 0.631 | 1.0% | 3.7 |
| bigrams + stopwords + unigrams | 0.741 | 0.792 | 0.703 | 0.640 | 0% | 3.8 |

nDCG@10 by query type, test split:

| mode | keyword | question | paraphrase | cross-lingual | short | negative | scoped |
|---|---|---|---|---|---|---|---|
| 0.1 baseline | 0.842 | 0.252 | 0.150 | 0.205 | 0.603 | 0.000 | 0.317 |
| lexical (default) | 0.975 | 0.675 | 0.403 | 0.479 | 0.740 | 0.597 | 0.782 |

Most of the gain comes from bigram segmentation itself (0.626); the dev-tuned options add about 0.02,
which is within noise at this size. Unigram backoff hurt cross-lingual queries on test (0.479 vs 0.541
without), helped paraphrase and short queries. Paraphrase and cross-lingual queries remain lexical's
weak spot, as expected of any lexical method.

The 0.1 baseline's 45.8% zero-result rate is the "appears to work" failure: natural Chinese questions
("cobalt的生产库现在是哪个版本的Postgres？") match neither its whitespace tokens nor its substring scan.

**Screening false positives found by this evaluation.** The first secret-screening rules rejected 3
of the 240 corpus memories (notes *about* passwords, e.g. "keep passwords in the password manager").
They were fixed before any test-split run; `tests/test_eval.py` now fails if any corpus memory is
rejected.

## Embeddings: Qwen3-Embedding-0.6B (Q8_0 GGUF via Ollama)

Model file verified byte-identical to the official `Qwen3-Embedding-0.6B-Q8_0.gguf`
(SHA-256 `06507c7b...c3e439`, see docs/MODELS.md).

```bash
python bench/embedding_eval.py --split dev  --out docs/eval/embedding-dev.json
python bench/embedding_eval.py --split test --configs default,dim512 --out docs/eval/embedding-test.json
```

Dev split, used for three decisions:

| configuration | vector nDCG@10 | hybrid nDCG@10 (equal-weight RRF) |
|---|---|---|
| query instruction, 1024 dims | 0.865 | 0.812 |
| no query instruction | 0.848 | 0.815 |
| instruction, 512 dims (MRL) | 0.878 | 0.819 |
| instruction, 256 dims | 0.858 | 0.813 |
| instruction, 128 dims | 0.840 | 0.822 |

Fusion weight (lexical weight in RRF, vector weight 1.0), dev nDCG@10:

| lexical weight | 1.0 | 0.5 | 0.3 | 0.2 | 0.1 | 0.05 | **0.01** | 0 |
|---|---|---|---|---|---|---|---|---|
| 1024 dims | 0.812 | 0.822 | 0.827 | 0.831 | 0.844 | 0.853 | **0.865** | 0.865 |
| 512 dims | 0.819 | 0.824 | 0.833 | 0.841 | 0.865 | 0.864 | **0.878** | 0.878 |

Decisions: keep the query instruction (+0.017, consistent with the model card's 1-5%); fuse with
lexical weight 0.01 (vector order, lexical breaks ties and backfills unindexed memories); MRL
dimension see below.

Test split, run once:

| mode | Recall@10 | Success@10 | MRR@10 | nDCG@10 | zero-result | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| 0.1 baseline | 0.392 | 0.438 | 0.392 | 0.340 | 45.8% | 10.5 | 15.8 |
| lexical | 0.754 | 0.802 | 0.697 | 0.649 | 0% | 7.3 | 10.4 |
| **vector / hybrid, 1024 dims** | **0.887** | **0.948** | **0.899** | **0.827** | 0% | 468 | 975 |
| vector / hybrid, 512 dims | 0.866 | 0.948 | 0.896 | 0.818 | 0% | 486 | 704 |

nDCG@10 by type (1024 dims): keyword 0.924, question 0.830, paraphrase 0.708, cross-lingual 0.914,
short 0.899, negative 0.629, scoped 0.882. Keyword queries are the one type where lexical retrieval
is better (0.975); a query-shape-aware fusion could exploit that, but tuning it would require the
test split, so it was not done.

**MRL dimension.** 512 dimensions was +0.013 on dev and -0.009 on test: no measurable difference at
this dataset size. The default stays at the model's native 1024; `MM_EMBED_DIM=512` halves vector
storage and scan time with no measured loss here.

**Latency.** Recall with embeddings is dominated by one HTTP round trip to the embedding server per
query (p50 200 ms in the dev runs, 470 ms in the test run with the GPU shared with other jobs).
Lexical recall stays at 4-11 ms. Index build for 240 memories: 6.6-23.6 s, batched 32 per request.

## Embedding implementation parity (Q8_0 GGUF vs fp32 reference)

`python bench/reference_parity.py ...` (docs/MODELS.md). Cosine between the served Q8_0 GGUF and the
official fp32 weights run by sentence-transformers: documents 0.9988-0.9995, queries 0.9990-0.9995.
Test-split nDCG@10 0.830 (reference) vs 0.827 (served). Quantisation and the serving path cost
nothing measurable here.

## Judge (Qwen3-1.7B Q8_0)

Full tables in docs/MODELS.md. In short: with thinking disabled every reply validated (100%) at about
1.3 s per memory; with thinking on, 48% failed closed by running out of tokens. Category agreement with
the dataset labels was 46% with the judge-v2 prompt, importance was flat (0.67-0.70 for every
category), and none of the 6 planted injection notes was flagged. A prompt comparison on corpus halves
(chosen on one half, reported on the other) found that the few-shot examples caused much of this: the
adopted judge-v3 prompt reached 71% held-out agreement with a real importance spread, but still
flagged only 1 of 3 held-out injections. The judge stays off by default.

## Vector search kernels

`python bench/vector_bench.py --out docs/eval/vector-bench.json`; see docs/NATIVE.md. Native exact
top-k: 2.0 ms at 10k x 1024, 13.6 ms at 100k x 1024; pure Python 185 ms and 1,694 ms; identical
rankings in every configuration.

## What the test suite proves

`python -m unittest discover -s tests` (100 tests; skipped: the symlink test on Windows without symlink
privilege, and the PDF test where `pypdf` is not installed). Beyond unit behaviour:

| Property | Test |
|---|---|
| The original 15 tests of 0.1 still pass, unmodified | `test_store`, `test_providers`, `test_operations`, `test_integration` |
| Upgrading a database written by the real 0.1 code preserves every row, the audit log and edges, takes a verified backup, and equals a fresh schema | `test_schema` |
| A newer database is refused byte-for-byte untouched; 0.1 reopening a new database is healed | `test_schema`, `test_review_findings` |
| Four processes opening a v1 database concurrently migrate exactly once | `test_schema` |
| No agent self-approval over a real MCP stdio connection; review tools absent without opt-in; structured errors never echo secrets | `test_mcp_v2` |
| Stored text cannot forge evidence boundaries or citation headers | `test_service` |
| A purged memory's text is in no file of the data directory afterwards | `test_lifecycle`, `test_review_findings` |
| Viewer review mode rejects wrong token, origin, content type or host | `test_ops_web_cli` |
| A model swap behind an unchanged name is detected and vectors are not mixed | `test_service` |
| Native, `sumprod` and `fsum` kernels return identical rankings, including ties | `test_text_vectors` |
| Lexical retrieval quality on the dev split does not regress; no corpus memory is rejected by screening | `test_eval` |
| Each of the 24 defects from the independent review stays fixed | `test_review_findings` |

The suite passed on Windows 11 with Python 3.11.15, 3.12.13, 3.13.5 and 3.14.5.

## Not verified

- **Other platforms.** Linux and macOS were not run locally; the CI workflow covering Linux, macOS and
  Windows on Python 3.11-3.13 is written but has not run.
- **Real user data.** All retrieval numbers come from one synthetic dataset by one annotator.
- **Scale.** No load test, no measurement above 100k vectors or with large real stores; the vector
  matrix is held in memory.
- **llama.cpp in-process backends** were not executed (build failure on the measurement machine,
  docs/MODELS.md).
- **PDF import** was tested on a generated two-page PDF only, not on real-world PDFs.
- **Host integrations.** The Claude Code hook was tested with a synthetic transcript in the format
  the code expects, not against a live Claude Code session; Claude Desktop, Codex and Cursor
  configurations were not exercised; only MCP over stdio from the Python SDK client was.
- **Calibration.** `judge-calibration` is tested with synthetic decisions; no real review history
  exists.
- **Judges other than Qwen3-1.7B**, quantisations other than Q8_0, rerankers: not measured.
- **Latency under load.** Model latencies were measured on a GPU shared with other work.
- **Erasure beyond the data directory** (backups, snapshots, SSD remnants) is out of reach by design.
