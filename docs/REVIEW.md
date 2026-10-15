# Independent review of the 0.2 upgrade

After the upgrade passed its own 79 tests, a separate reviewer (an agent given only the repository,
no design notes, and an instruction to confirm findings by reproduction) audited it. It reported 24
defects, reproducing 23 of them. All were fixed; each fix has a regression test in
`tests/test_review_findings.py` (numbered as below) unless noted. The reviewer's "found sound" list
is at the end.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | high | Import redaction covered chunk bodies only: secrets in document titles, heading paths, bookmark URLs and JSONL locators were stored raw and shown in recall and the mirror | `text.redact_value` redacts every string in titles and locators; test scans all files for the secret |
| 2 | medium | Capture screened `content` only; `source`, `tags`, `event_id` passed through | All four fields are screened (NFKC-folded too) |
| 3 | medium | Viewer `/api/memory` served pending, rejected and forgotten text by id | Only recallable states (plus pending in review mode); 404 otherwise |
| 4 | medium | On Windows, a UNC path given to `memory_import` was resolved (opening an SMB connection) before the root-confinement check | `ingest.safe_relative` validates agent paths lexically (drive, root, UNC, `..`) before any filesystem call |
| 5 | medium | A file reverted to an earlier version re-imported as "unchanged", leaving the newer version live | "Unchanged" only matches a current (approved/pending) document; the uniqueness constraint became an index |
| 6 | medium | Inbox notes were archived in `inbox/.imported/`, a plaintext copy that purge could not reach | Inbox files are removed after import |
| 7 | medium | Purge deleted the mirror file outside any retry; a locked file (open in an editor) survived for good | Purge leaves an outbox tombstone; the exporter retries; `sync` removes files of purged ids |
| 8 | medium | `memory_judge` sent rejected/deleted memories to the model and echoed paraphrases; advice survived forget | Judge refuses rejected and deleted memories; forget deletes cached advice (rejected keeps it: it is calibration data) |
| 9 | medium | Secret heuristic treated any value containing `env` or starting with `$ < % ( {` as a placeholder (`$uperS3cret!`, `Envoy#2024xyz` passed); full-width text bypassed screening | Exact placeholder shapes; screening also runs on NFKC-folded text |
| 10 | medium | `offset` up to 500 accepted but the candidate pool was 200: silent empty pages | `offset` capped at 150 and rejected beyond |
| 11 | medium | Healing a database reopened by 0.1 dropped legacy tables but not the effects of 0.1's reviews (stale index, vectors of forgotten rows) | Heal rebuilds the FTS index and deletes vectors of non-recallable rows |
| 12 | medium | Mirror sync proposed case/whitespace/CRLF-only edits, which then deduplicated against the original (self-sighting, dropped `supersedes`) | Normalisation-equal bodies count as unchanged; a revision that duplicates an existing memory is a conflict |
| 13 | medium | One malformed front-matter value (e.g. a list as `category`) aborted `sync` and `sync --watch` permanently | Types are validated; every file is isolated in its own error handler |
| 14 | medium | Recall's access statistics took the write lock with a 15 s timeout, so reads failed while another process wrote | Best effort: 0.2 s timeout, failures ignored |
| 15 | low-med | Purge ignored a blocked WAL checkpoint and reported success while text remained in the WAL | Blocked checkpoint is an error; purge returns `complete: false` |
| 16 | low-med | sentence-transformers backend downloaded from the hub without `MM_ALLOW_REMOTE` and before checking for a pinned revision; `doctor` loaded models | Revision required first; local files only unless `MM_ALLOW_REMOTE=1`; `doctor` loads in-process models only with `--probe` |
| 17 | low | Vector-stage rows fetched without a status/project filter (cross-process race) | Filter added (code-reviewed; no deterministic test) |
| 18 | low | A confirmed capture of content already pending returned the pending row unchanged | Trusted confirmation approves the queued duplicate |
| 19 | low | Import read the whole file before the size check | `stat()` first (code-reviewed) |
| 20 | low | Two processes healing at once both dropped the same table | Heal re-checks state under the write lock; 3-thread test |
| 21 | low | Session titles and metadata not redacted; a malformed field aborted the whole import; `session search` accepted `limit=-1` | Redacted, type-checked per record, limit validated |
| 22 | low | A forgotten document could be re-approved and supersede the live version | Document-level transitions enforced |
| 23 | low | Overlapping secret matches left a fragment of the secret | Overlapping spans are merged before redaction |
| 24 | low | `journal_mode=WAL` was set before refusing a too-new database; 0.1 vectors of rejected rows were migrated | Version is read before any write; only recallable rows' vectors migrate |

Documentation findings (README still described 0.1, docs referenced files that did not exist yet,
LICENSE-STATUS.md contradicted LICENSE, `tools/release.py` would have shipped an archive missing the
new modules) were addressed in the same change set.

## What the reviewer checked and found sound

Approval gating over MCP; judge parsing and fail-closed behaviour; provider network policy; every
f-string in SQL (constants and placeholders only); FTS5 query construction; status transitions and
index maintenance; transaction boundaries; vector-cache invalidation across processes; Matryoshka
truncation order; fingerprints and canary drift detection; keyset pagination; RRF; evidence-pack
boundaries; viewer Host/Origin/token checks and `textContent` rendering; import confinement apart
from #4; session turn idempotency; native kernel buffer handling and tie-breaking; migration locking
and verified backups.

## Process note

The reviewer worked from the code, not from this project's own claims, and was asked to reproduce
each finding before reporting it. Several defects (#1, #3, #4, #8) sit exactly on safety properties
the upgrade advertised, which is why a review separate from the author was worth its cost.
