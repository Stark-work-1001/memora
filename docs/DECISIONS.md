# Decisions

Each entry: what was decided, the alternatives, and the evidence. Measurements are in
docs/EVALUATION.md and docs/NATIVE.md.

## D1. Fix unspaced-script retrieval with a Python bigram analyzer, not a tokenizer extension

FTS5's `unicode61` turned an unspaced Chinese sentence into one token; 0.1 compensated with a
substring scan that fails on natural questions. Alternatives: FTS5 `trigram` (cannot match
two-character words, which are the most common Chinese words), a dictionary segmenter such as jieba
(a dependency and a dictionary, and segmentation errors become retrieval errors), a compiled FTS5
tokenizer (needs loadable extensions, disabled in several Python builds). Chosen: pre-segment into
overlapping bigrams (plus unigrams in a separate column) in Python, the scheme Lucene's
CJKBigramFilter uses. Measured: test-split nDCG@10 0.340 -> 0.649; queries with zero results
45.8% -> 0%.

## D2. Tune on dev, report on test

The labelled dataset is split 64 dev / 96 test queries. Every retrieval option (stopwords, unigrams,
prefix matching, fusion weights, MRL dimension, query instruction) was chosen on dev; test was run
once per configuration family afterwards. Where dev and test disagree (512 dimensions), the docs say
so instead of picking the better number.

## D3. Vector-first fusion

Equal-weight RRF made hybrid worse than vector-only (dev nDCG 0.812 vs 0.865). Every lexical weight
above about 0.01 lowered dev nDCG. Chosen: weights 0.01 / 1.0, which keeps vector order while
lexical breaks ties and backfills memories without vectors (fresh captures stay reachable before
re-indexing). Overridable with `MM_FUSION_LEXICAL_WEIGHT`. Not done: query-shape-aware fusion, even
though keyword queries are the one type where lexical beat vector on test (0.975 vs 0.924); tuning it
would have needed the test split.

## D4. Exact vector search with an optional Rust kernel; no ANN, no sqlite-vec

See docs/NATIVE.md. Exact search is fast enough at personal scale natively (13.6 ms at 100k x 1024)
and has perfect recall. sqlite-vec needs loadable extensions; ANN adds approximation and index
maintenance.

## D5. Immutable model fingerprints plus canaries

0.1 identified a model as `endpoint|model`, which a server can change underneath. Fingerprints now
hash backend, model, revision, pooling, normalisation, document template and observed dimension, and
canary vectors detect a different model behind an unchanged name. Vectors from other fingerprints
are kept (so switching back is free) but never searched; `prune-vectors` removes them.

## D6. No automatic approval, and no agent self-approval

Kept from 0.1 and extended: 0.1 let an agent pass `confirmed=True`; now only an operator-set
`MM_TRUST_AGENT_CONFIRM=1` allows it. Judge scores never approve, at any value.

## D7. The judge is optional, advisory and off the hot path

It is never called during recall or capture. It runs on demand (`judge ID`, `judge --pending`,
`memory_judge_pending`) and is cached per (content digest, judge fingerprint), so unchanged content is
never re-judged. Importance is treated as uncalibrated until `judge-calibration` has 30 or more
reviewed decisions; only then does the queue show an empirical P(approve). Measured value of a
1.7B judge: see docs/MODELS.md. The recommendation that follows from it is to leave the judge off.

## D8. Reviews per document for imports; redact rather than reject in bulk

Nobody reviews 400 chunks one by one. Single memories are still rejected on detected secrets (the
writer can redact knowingly); imports redact so one token does not block a whole document.

## D9. Two-way Markdown as proposals, not as a second source of truth

Any process can write the mirror, so edits are proposals with `supersedes`. A real two-way merge
would make Markdown a second primary store, which 0.1 ruled out.

## D10. Sessions are an archive, not memory

Transcripts are large, noisy and sensitive. They are archived (redacted, searchable, replayable) but
excluded from recall; durable facts still go through capture and review.

## D11. Recorded but unused salience

Access counts and dates are recorded and power the `report` command (stale, never-recalled
memories). They do not affect ranking: boosting what is retrieved would let early retrieval decide
later retrieval, and there was no data to show a benefit.

## D12. Not built

| Not built | Why |
|---|---|
| Reranking stage (e.g. Qwen3-Reranker) | Vector-only already reaches test nDCG 0.827 on this dataset; a reranker adds a model and per-query latency, and was not measured. |
| Graph-walk retrieval, automatic entity extraction | Needs an extraction model whose errors would become stored "facts"; explicit typed links instead. |
| Automatic consolidation / merging / conflict resolution | Each would change approved memory without review. Duplicates are prevented at capture, near-duplicates and contradictions are surfaced for a human. |
| Decay that deletes or demotes | Never automatic; `report` suggests archiving. |
| Encryption at rest (SQLCipher) | A compiled dependency with platform-specific builds; full-disk encryption covers the same threat for one user on one machine. |
| Multi-machine sync, multi-tenancy, hosted mode | Out of scope for one user on one machine. Backup/restore covers moving machines. |
| PyPI publication, GitHub release | Outward-facing; prepared (`pyproject.toml`, `tools/release.py`) but not done. |
| Adapters for hosts other than Claude Code | Their transcript formats were not verified; the generic session JSONL format covers them. |

## Constraints from the brief (section 6)

| # | Constraint | Status | Notes |
|---|---|---|---|
| 1 | SQLite is the source of truth; Markdown regenerable | **Honoured** | Mirror edits become proposals, never writes (D9). |
| 2 | Retrieved memory is evidence | **Honoured, strengthened** | Nonce-fenced evidence blocks, injection flags, instruction text in every pack. |
| 3 | Automatic capture stays pending; no score auto-approves | **Honoured, strengthened** | Agent self-confirmation closed (D6). Trusted CLI confirmation can approve a queued duplicate: an explicit user act, not a score. |
| 4 | Malformed judge output fails closed | **Honoured** | Stricter: unknown keys rejected too. One relaxation: a bare leading `</think>` (a server artifact) is stripped. |
| 5 | Lexical works without embeddings and says it fell back | **Honoured** | `mode`, `warning`, `coverage`, `model_drift` in every recall. |
| 6 | Incompatible vectors never mixed; immutable fingerprint | **Honoured** | D5. |
| 7 | Say so if erasure is not cryptographic | **Honoured** | Purge is physical deletion with measured limits; no crypto-shredding; documented in THREAT_MODEL T6. |
| 8 | No silent egress | **Honoured** | Also applied to hub downloads by sentence-transformers. |
| 9 | Secrets never reach the database | **Adapted** | Screening widened and de-noised, but it is pattern matching: unmatched secrets can still reach the database (THREAT_MODEL T4). |
| 10 | New capability arrives with a test and an honest note | **Honoured** | 100 tests; docs/EVALUATION.md "not verified" list. |
| 11 | Local-first, single user | **Honoured** | |
| 12 | Boring, inspectable technology | **Adapted** | Standard library + SQLite + hand-written SVG still. One optional compiled component (D4), justified by measurement; optional model runtimes are extras, never required. |
