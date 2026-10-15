# Architecture

```text
 INGEST     MCP capture/remember | CLI | Markdown inbox + mirror edits | document import | session archive (hooks, JSONL)
              |                                  everything an agent or a file supplies enters as PENDING
              v
 NORMALIZE  validation and limits | secret screening (reject single memories, redact bulk imports)
            duplicate detection (normalised digest -> "sighting", independent support counted)
              v
 STORE      SQLite, WAL, schema v2 (single source of truth)
            memories (memory | chunk), documents, sessions + turns, edges, sightings, audit, outbox,
            embeddings (float32 BLOB + model fingerprint), models (descriptor + canary), judgements, meta
              |                     |                         |                          |
              v                     v                         v                          v
 DERIVED    Markdown mirror      memory_fts / turns_fts    vector matrix cache        review aids
            (outbox, atomic      (CJK bigram analyzer,     (generation counter       (judge advice cache,
             replace, retried)    approved states only)     maintained by triggers)   similar memories, calibration)
              |
 LIFECYCLE  pending -> approved | rejected;  approved -> archived | superseded;  -> deleted (forget) -> purged
            supersedes edges enforced on approval; contradictions surfaced, never auto-resolved
              v
 RETRIEVAL  lexical (FTS5 BM25)  +  vector (exact top-k, native or Python)  ->  RRF (vector-first, lexical backfill)
            scopes: project + ":user"; filters: category, tags, kind, polarity, status
              v
 SURFACE    MCP tools | CLI | evidence packs (nonce-fenced, cited) | briefing | profile | viewer | eval harness
```

The three commitments of 0.1 hold: SQLite is the only primary store; automatic capture is a
candidate, not a fact; the judge advises and never approves.

## Modules

| Module | Responsibility |
|---|---|
| `schema.py` | DDL, migration runner (refuse newer, verified backup, single transaction, heal after downgrade), FTS rebuild |
| `store.py` | Lifecycle, capture and dedupe, transitions, links, lexical recall, pagination, graph, purge |
| `text.py` | NFKC normalisation, the bigram analyzer and query builder, secret screening and redaction, injection markers, token estimate |
| `vectors.py` | float32 codec, Matryoshka truncation, exact top-k (Rust kernel when installed) |
| `providers.py` | OpenAI-compatible HTTP client, sentence-transformers and llama.cpp backends, fingerprints |
| `judge.py` | Prompt, schema, strict parser, calibration against review decisions |
| `service.py` | Incremental indexing, canary checks, hybrid recall, evidence packs, judge orchestration, review queue, profile, briefing |
| `ingest.py` | Markdown/text/PDF/bookmarks/JSONL import, document review |
| `sessions.py` | Session/turn archive, Claude Code transcripts, host hook |
| `mirror.py` | Mirror export, sync of edits into proposals, inbox |
| `ops.py` | Restore, drill, compaction, purge wrapper, maintenance, doctor |
| `evaluation.py` | Datasets, metrics, baseline comparison |
| `server.py`, `__main__.py`, `web.py` | MCP, CLI and viewer surfaces |
| `native/` | Optional Rust top-k kernel (PyO3) |

## Data model highlights

- **memories** keeps every 0.1 column (`id, project, content, source, event_id, digest, mode, status,
  category, tags, created, updated, version`) and adds `kind` (memory/chunk), `polarity`
  (positive/negative), `norm_digest`, `doc_id`, `session_id`, `locator` (citable provenance),
  `access_count`, `last_accessed`, `valid_until`. Columns were added with `ALTER TABLE`, so 0.1
  rows migrate in place.
- **Scopes.** A project is a namespace. The reserved scope `:user` holds durable personal
  preferences and is searched together with every project; project results are marked
  `scope: project` and take precedence in the profile. (`:` was invalid in 0.1 project names, so it
  cannot collide with existing data.)
- **Sightings** record each additional source that captured the same normalised content;
  `support` (distinct sources) is shown to reviewers and in the profile. It is a corroboration signal,
  not a truth score.
- **Edges** are explicit and typed. `supersedes` is enforced (the older memory becomes `superseded`
  once the newer one is approved); `contradicts` is surfaced in evidence packs and maintenance
  reports for a human to resolve.
- **Documents** group chunks for per-document review; re-importing a changed file creates a new
  version that supersedes the old one on approval.
- **Sessions/turns** are an archive (redacted, searchable, replayable) kept apart from curated memory.

## Retrieval

1. **Lexical.** Text is analysed by `text.analyze`: NFKC + casefold; runs of unspaced scripts (Han,
   kana, Hangul, Thai, ...) become overlapping bigrams plus unigrams in a separate column; other text
   stays as words. FTS5 with `porter unicode61` then indexes these terms. Queries are analysed the same
   way, drop function words (English stopwords, Chinese stop characters), add a prefix match for Latin
   words, and are OR-ed as quoted phrases (so user input is inert as FTS syntax). BM25 ranks, with
   column weights terms 1.0, chars 0.4, tags 1.5. Only approved/archived/superseded rows are in the
   index. This is not semantic search.
2. **Vector** (when configured). The query is embedded with the model's query template (Qwen3:
   `Instruct: {task}\nQuery:{text}`), compared exactly against the cached matrix of vectors whose
   fingerprint matches the configured model and whose digest matches the memory.
3. **Fusion.** RRF (k = 60) with weights lexical 0.01, vector 1.0, chosen on the dev split:
   effectively vector order, with lexical breaking ties and backfilling memories that have no vector
   yet. Each result reports `signals` (lexical rank, vector rank, similarity).
4. **Degradation is explicit.** If embeddings are unavailable, drifted, or cover only part of the
   scope, the response says so (`mode`, `warning`, `coverage`, `model_drift`) and lexical results are
   still returned.

## Model identity

A vector space is identified by `emb-` + SHA-256 of the backend's descriptor (backend, model,
revision, pooling, normalisation, document template, configured dimension) plus the observed output
dimension. Query templates are recorded but not part of the fingerprint: they change query quality,
not stored-vector compatibility. On first use per process, two canary texts (English and Chinese) are
re-embedded and compared with the vectors stored at first index (cosine >= 0.995); a mismatch means a
different model is being served under the same name, and the vector stage is disabled with a warning
instead of mixing spaces.

## What was not built from the suggested shape

Graph-walk retrieval, a reranking stage, automatic consolidation and automatic conflict resolution
are absent on purpose; see docs/DECISIONS.md. Salience and decay are recorded (access counts, dates)
and reported, but not used in ranking.
