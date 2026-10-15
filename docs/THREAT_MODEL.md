# Threat model

Scope: one user, one machine, Memory Merge 0.2.0a1. Everything here was checked against the code;
items marked **test** have an automated test, **measured** were reproduced with the stated command,
and **not defended** are deliberate gaps.

## Assets

1. The user's memories, documents and session archive (often private: preferences, decisions,
   project details, conversation transcripts).
2. The integrity of what agents retrieve: a poisoned memory becomes a persistent instruction channel
   into every future session.
3. Credentials that might be pasted into conversations or notes.

## Trust boundaries

| Actor | Trusted for | Not trusted for |
|---|---|---|
| The user at the CLI or the `--review` viewer | approving, linking, importing with `--approve`, purging | -- |
| A capture agent over MCP (default instance) | proposing memories, reading approved memory | approving anything; reading pending, rejected or deleted content |
| A reviewer MCP instance (`MM_ENABLE_REVIEW=1`) | review actions, purge (typed confirmation) | -- (enable it only for an agent session the user drives) |
| Stored memory and imported documents | nothing: always quoted evidence | instructions of any kind |
| Embedding / judge model servers | computing vectors and advice | approving; receiving content unless configured |
| Other processes of the same OS user | -- | out of scope: they can read the database file directly |

## Threats and mitigations

### T1. Prompt injection persisted through memory (memory poisoning)

An agent reads a hostile web page or issue and is told to "remember" an instruction, which then
replays into every future session.

- Automatic capture is always `pending`; only approved memories are recalled (**test**
  `test_store`, `test_lifecycle`).
- An agent cannot approve its own capture: `memory_remember(confirmed=True)` stays pending unless the
  operator sets `MM_TRUST_AGENT_CONFIRM=1` (**test** `test_mcp_v2`). In 0.1 any agent could do this.
- Review tools exist only on an instance started with `MM_ENABLE_REVIEW=1` (**test** `test_mcp_v2`).
- Markdown mirror edits and inbox files (writable by any process, including agents with file tools)
  become pending proposals, never direct edits (**test** `test_ingest_sync_sessions`).
- The review queue flags `instruction_like` content and lists similar approved memories, so a
  near-duplicate with a changed instruction is visible (**test** `test_service`).
- Evidence packs fence each memory between `<<<evidence NONCE>>>` and `<<<end NONCE>>>` lines with a
  random per-response nonce and sanitised headers, so stored text cannot close its own block or
  forge a citation; 0.1 concatenated raw text (**test** `test_service`).
- **Not defended:** a user who approves a malicious memory. The instruction-like flag is a heuristic
  (regular expressions, English and Chinese) and misses paraphrased injections. The judge did not
  close that gap in measurement (docs/EVALUATION.md).

### T2. Hostile document import

- Size limit (20 MB, checked before reading), chunk limit (5,000), PDF page limit (2,000), UTF-8 only
  for text formats, binary detection (**test**).
- Path confinement: imports resolve inside a root; symbolic links are skipped (**test**; skipped on
  Windows without symlink privilege). Agent-supplied paths for `memory_import` (registered only when
  `MM_IMPORT_ROOT` is set) are validated *lexically* before any filesystem call, because on Windows
  merely resolving `//host/share` opens an SMB connection that can leak NTLM credentials (**test**
  `test_review_findings::test_04`; found by the independent review, docs/REVIEW.md).
- Secrets in chunk text, titles, headings, URLs and locator fields are redacted (**test**).
- Imported documents are pending and reviewed per document; their chunks are quoted evidence like
  any other memory.
- PDF parsing is delegated to `pypdf` (optional). **Not defended:** vulnerabilities in `pypdf`.

### T3. Provider data leakage

- No network unless configured. Providers accept loopback IP literals (`127.0.0.1`, `::1`) or HTTPS
  with `MM_ALLOW_REMOTE=1`; `localhost` is not trusted to resolve to loopback. Redirects are refused,
  proxies ignored, responses capped at 4 MB, timeouts bounded (**test**).
- The sentence-transformers backend loads only local files unless `MM_ALLOW_REMOTE=1`, and requires
  a pinned revision before it loads anything (**test**).
- What is sent when configured: indexing sends memory text, recall sends the query, the judge
  receives one memory. Rejected and deleted memories are never sent to the judge (**test**).
- `doctor` contacts providers only with `--probe`.
- **Not defended:** what a remote provider does with the text it receives. Copies sent to a remote
  provider are beyond the reach of `purge`.

### T4. Secrets entering the store

- Single memories with credential-like content are rejected (content, source, tags and event id,
  including full-width variants after NFKC folding); the error names the kind, never the value
  (**test**, an 18-case table in `test_text_vectors` plus review regressions).
- Bulk imports (documents, sessions) redact instead of rejecting.
- The rules avoid false positives on notes *about* secrets ("passwords live in the team password
  manager"). The first version of these rules wrongly refused 3 of 240 dataset memories until fixed
  (**measured**, docs/EVALUATION.md).
- **Not defended:** secrets that match no pattern (high-entropy strings without a key name,
  credentials described in prose). This is pattern matching, not data-loss prevention.

### T5. Cross-site requests to the local viewer

- Binds 127.0.0.1 only; rejects any `Host` other than `127.0.0.1:port` or `localhost:port` (DNS
  rebinding); read-only by default, POST returns 501 (**test**).
- `--review` mode has one write route, which requires `Content-Type: application/json`, a
  same-origin `Origin` and a per-process random token that a cross-origin page cannot read (**test**:
  wrong token, origin, content type or host each return 403).
- Memory text is rendered with `textContent` only, under a strict CSP without inline script (**test**
  checks the bundle for `innerHTML`).
- Only approved, archived and superseded memories are served by id (pending too in review mode);
  deleted and rejected text is never served (**test**; found by the independent review).

### T6. Deletion that leaves copies

- `forget` is a soft delete: the row keeps its text (so the decision is auditable) but leaves the
  full-text index, the vector table and the judge cache.
- `purge` deletes the row and every derived copy in the database (index, vectors, judgements,
  sightings, edges), nulls content digests in the audit log (a hash of a short secret can be brute
  forced), rebuilds the FTS index so old segments go, removes the mirror file (retrying via the
  outbox if the file is locked), checkpoints the WAL and runs VACUUM. Every connection uses
  `PRAGMA secure_delete=ON`.
- **Measured** with a marker string: after `purge`, no file in the data directory contains it
  (**test** `test_lifecycle::test_purge_leaves_no_bytes_in_database_files`). With `secure_delete=OFF`
  the text survives in `memory.sqlite3` after the same purge, so the pragma is load-bearing.
- **Not defended:** existing backups (purge reports how many exist), filesystem snapshots, cloud-sync
  copies, SSD wear levelling, the OS page cache. If another connection holds a read snapshot the
  WAL checkpoint is blocked; purge then reports `complete: false` rather than claiming success.
- **Not provided:** encryption at rest. Use full-disk encryption (BitLocker, FileVault, LUKS); see
  docs/DECISIONS.md for why SQLCipher was not added.

### T7. Supply chain and model provenance

- Runtime dependencies are pinned in `requirements-lock.txt`. Hashes are not pinned
  (`--require-hashes` is not used): **not defended** against an index serving a different file under
  the same version.
- The native kernel is optional, depends only on PyO3, and its only `unsafe` block is the documented
  buffer view.
- Model files: docs/MODELS.md records the official SHA-256 of every model file used in measurements,
  and the files used were verified against them. The judge named in the original brief
  ("Qwen3.8-2B-distill") is a community fine-tune with unverifiable training claims; it is not
  recommended.
- Vector fingerprints include model revision, pooling, dimension and document template, and canary
  vectors detect a different model served under an unchanged name (**test**), so a model swap cannot
  silently mix vector spaces.

### T8. Resource exhaustion

Bounded inputs: content 16,000 characters, query 1,000, recall limit 50, offset 150, page size 1,000,
graph 5,000 nodes, plus the import limits above. **Not defended:** a reviewer approving millions of
memories; the vector matrix is held in memory (about 4 KB per 1024-dimension vector).

## Out of scope

Multi-user access control (projects are namespaces, not permissions), a hostile process running as
the same OS user, hosted deployment.
