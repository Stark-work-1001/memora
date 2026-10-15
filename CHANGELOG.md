# Changelog

## 1.0.1 — 2026-10-15

Rust native top-k buffer safety and RRF integration; peer heartbeat/task leases; resource catalogs and logical project threads; immutable Markdown record dates; model workflows with provenance and draft output; authenticated optional MCP HTTP bridge; 2D graph view, 3D camera focus, distance fog, layouts and directional flow; bilingual research/stack/operations docs; isolated sanitized source/standalone delivery. Original v2 memory schema and review APIs retained. SDK stdio transport now uses duplicated descriptors so shutdown cannot close the embedding host streams.

## 1.0.0 — 2026-10-15

Memora memory entity: model assembly, chat, dual 3D graph views, local agent sources, MCP delegation, preserved knowledge/Markdown/database core, Apache-2.0 distribution.

# Changelog

Versions follow PEP 440; git tags are `v` + version from 0.2 on.

## 0.2.0a1 (unreleased)

Upgrade of the 0.1 prototype into a complete local memory system. Measured on
`datasets/memory-eval-v1` (test split): nDCG@10 0.340 -> 0.649 lexical, 0.827 with local embeddings;
queries returning nothing 45.8% -> 0%. Details in docs/EVALUATION.md.

### Security and safety
- Agents can no longer approve their own memories: `memory_remember(confirmed=True)` stays pending
  unless `MM_TRUST_AGENT_CONFIRM=1`.
- Evidence packs fence each memory with a per-response nonce; stored text can no longer forge
  citation headers or block boundaries.
- Forgotten and rejected content leaves the full-text index, vector table and judge cache; pending,
  rejected and deleted content is never in the index at all.
- New `purge`: deletes a memory and all derived copies, scrubs freed pages (`secure_delete`),
  truncates the WAL and vacuums; reports what it cannot reach.
- Secret screening covers source, tags and event ids, full-width text, more token formats, Chinese
  key words, payment cards (Luhn); notes *about* passwords are no longer rejected.
- Fixes from an independent review (24 findings, docs/REVIEW.md), including redaction of import
  metadata, the viewer serving forgotten text by id, and a Windows UNC path in `memory_import`
  causing SMB access.
- Viewer review mode (`web --review`) protected by token, Origin, Host and content-type checks.

### Retrieval
- Bigram analyzer for Chinese/Japanese/Korean/Thai text, query-side stopwords, unigram backoff,
  prefix matching; tags indexed; filters by category, tags, kind, polarity, status.
- Optional embeddings: Qwen3 preset (query instruction, Matryoshka dimensions), batching, incremental
  indexing, float32 storage, immutable model fingerprints, canary-based drift detection.
- Fusion tuned on dev data: vector-first RRF with lexical backfill (weights 0.01/1.0).
- Optional Rust kernel for exact top-k search (85-125x faster than pure Python at 10k-100k vectors).
- `:user` scope for cross-project preferences; profile and cited start-of-task briefing.

### Memory lifecycle
- States: pending, approved, rejected, archived, superseded, deleted; explicit transition table.
- `supersedes` is enforced; contradictions are surfaced; exact/normalised duplicates become
  sightings with a support count; negative ("do not repeat") memories.

### Ingestion
- Markdown (heading-aware, cites heading path and lines), text, PDF (optional `pypdf`), browser
  bookmarks, JSONL highlights; per-document review; re-import versioning.
- Two-way Markdown: mirror edits and inbox notes become pending proposals (`sync`, `sync --watch`).
- Session archive with redaction, JSONL import format, Claude Code transcript adapter and hook.

### Models
- In-process backends: sentence-transformers and llama.cpp (optional extras).
- Judge: strict schema, constrained decoding when available, thinking-model handling, caching per
  content and model, calibration against the user's review decisions; prompt judge-v3 chosen on half
  the corpus (held-out category agreement 46% -> 71% with Qwen3-1.7B). Off by default; see docs/MODELS.md.

### Operations and packaging
- Schema migrations: refuse newer databases, verified pre-migration backup, one transaction, heal
  after downgrade by older code; tested against databases written by the real 0.1 code.
- `doctor`, `drill` (backup + restore round trip), `restore`, `maintain`, `report`, `rebuild` (now
  rebuilds the index too), `prune-vectors`.
- Typed errors with stable codes for MCP and CLI; CLI no longer crashes printing non-GBK text on
  Chinese Windows consoles.
- Platform data directory by default (0.1's in-checkout `data/` is still used if it exists).
- `pip install .`, `memory-merge-mcp` entry point, Dockerfile (non-root), CI for Linux/macOS/Windows
  x Python 3.11-3.13 (not yet run), issue/PR templates, CONTRIBUTING, SECURITY.
- Evaluation harness and labelled dataset; benchmarks for vectors, embeddings and the judge.

### Breaking changes
- `tags`/`locator` returned as JSON values; `memory_review_queue` returns an object; identical
  content in a project is stored once; `rebuild` also rebuilds the index; see docs/OPERATIONS.md
  "Upgrading from 0.1".

### Repository
- `.gitignore` added (data, databases, keys, env files); `.gitattributes` pins LF.
- LICENSE-STATUS.md corrected: the project is MIT-licensed.
- README restructured; credits moved to docs/REFERENCES.md with commits and licenses.

## 0.1.0a1 (published 2026-10-13)

Released as git tag `0.1.0`, GitHub Release `memory-merge-v0.1.0-alpha.1`, Python package version
`0.1.0a1`: the same code under three names. Source ZIP SHA-256
`aa3a601b09de675041473ba6b72279e449118e0300c78233df0a169fdf37d470` (44,358 bytes).

- SQLite store with outbox-based Markdown mirror, pending/approved review, six categories,
  project scopes, idempotent events, typed edges.
- MCP stdio server (official SDK), lexical retrieval with substring fallback, optional
  OpenAI-compatible embeddings and judge, RAG evidence packs, read-only mind-graph viewer.
- 15 tests.
