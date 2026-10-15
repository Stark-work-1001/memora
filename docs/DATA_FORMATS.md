# Data formats

## Markdown mirror (`markdown/<id>.md`)

Derived from the database; regenerate with `memory-merge rebuild --mirror-only`.

```markdown
---
id: "5c8ecc6b-1929-4874-abe8-5c556157c896"
project: "demo"
source: "demo:synthetic"
status: "approved"
category: "decision"
polarity: "positive"
kind: "memory"
tags: ["storage"]
created: "2026-10-13T11:54:03.395365+00:00"
updated: "2026-10-13T11:54:03.395365+00:00"
version: 1
digest: "sha256 of the content"
locator: {"path": "notes/runbook.md", "heading": ["Atlas", "Deploy"], "lines": [12, 18]}
# Edit the body below and run `memory-merge sync`: changes become a pending revision for review.
---

The memory text.
```

Values are JSON (also valid YAML). `locator` appears only for imported chunks.

**Editing.** `memory-merge sync` (or `sync --watch`) compares each file with the database:

- body unchanged after normalising case, width, whitespace and line endings: nothing happens;
- body changed and `version` matches the database: a *pending* revision is created with
  `supersedes=<id>`; approving it retires the original (status `superseded`);
- body changed but the database has moved on (`version` differs): reported as `stale`, not proposed,
  because it would revert newer content;
- unparsable or ill-typed front matter: reported in `errors`; the scan continues.

`category` and `tags` edits travel with the proposal. Deleting a mirror file does nothing (`rebuild`
restores it).

**Inbox.** Files in `markdown/inbox/*.md|*.txt` become pending manual memories on `sync`; optional
front matter may set `project`, `category`, `tags`. The file is removed after a successful import so
that no copy survives a later purge.

## Session archive JSONL (`memory-merge session import FILE`)

One JSON object per line. Sessions must precede their turns. Import is idempotent: sessions are keyed
by (project, agent, id), turns by (session, seq). Turn text, titles and metadata are redacted for
secrets. Malformed records are reported in `errors` and skipped.

```json
{"type": "session", "id": "2026-10-01-a", "project": "atlas", "agent": "codex", "title": "Fix import on Windows", "started": "2026-10-01T09:00:00Z", "meta": {"branch": "fix/paths"}}
{"type": "turn", "session": "2026-10-01-a", "seq": 1, "role": "user", "content": "Imports fail for long paths", "created": "2026-10-01T09:00:05Z"}
{"type": "turn", "session": "2026-10-01-a", "seq": 2, "role": "assistant", "content": "Use the \\\\?\\ prefix ..."}
{"type": "memory", "session": "2026-10-01-a", "content": "Windows imports need long-path support", "category": "lesson", "tags": ["windows"]}
```

- `role`: `user`, `assistant`, `system` or `tool`.
- `memory` records go through normal capture: screened, deduplicated, **pending**, linked to the
  session (`memories.session_id`).
- Turns are an archive: searchable with `session search` and `memory_session_search`, replayable with
  `session show`, never part of recall or evidence packs.

**Claude Code transcripts** (`session import FILE --format claude-code`, or the `SessionEnd` hook,
see docs/INTEGRATIONS.md): user and assistant text is archived; tool calls become
`[tool_use: Name]`; tool results and images are not archived (size and sensitivity). Re-importing a
longer transcript appends the new turns.

## Record import (`*.jsonl` documents)

Highlights, clippings, exported notes: one object per line.

```json
{"text": "The highlighted passage.", "title": "Book or page title", "url": "https://example.org/a", "locator": {"page": 12}, "tags": ["reading"]}
```

`text` is required; the rest is optional and kept in the locator. Each line becomes one chunk of one
document (`memory-merge import notes.jsonl --project P`).

## Other import formats

| Extension | Chunking | Locator |
|---|---|---|
| `.md`, `.markdown` | by heading, then paragraph (fenced code kept whole), about 350 estimated tokens per chunk; front matter title used | `heading` path, `lines` |
| `.txt` | by paragraph | `lines` |
| `.pdf` (needs `pypdf`) | by page, then paragraph | `page` |
| `.html`, `.htm` | Netscape bookmark export (all major browsers); only http(s) links | `url`, `folder` path |
| `.jsonl` | one record per line (above) | `record` number plus given fields |

Chunk text of Markdown starts with its heading path (`Atlas > Deploy`), which helps lexical
retrieval of section-specific content.

## Evaluation dataset (`datasets/<name>/`)

`corpus.jsonl`: `{"id", "project", "content", "category"?, "polarity"?, "tags"?, "lang"?}`; project
`"@user"` maps to the cross-project user scope.

`queries.jsonl`: `{"id", "project", "query", "relevant": {"m001": 2, "m007": 1}, "type"?, "lang"?, "split"?}`
with graded relevance (2 answers the question, 1 is useful context). BEIR-format directories
(`corpus.jsonl` with `_id`/`text`, `queries.jsonl`, `qrels/<split>.tsv`) are also accepted.

## Error contract

CLI errors are printed to stderr as JSON with a per-class exit code; MCP tool errors are MCP error
results whose text ends with the same JSON:

```json
{"error": {"code": "sensitive_content", "message": "possible credential in content: redact before capture",
           "retryable": false, "hint": "replace the secret with a placeholder such as <API_KEY>",
           "details": {"kinds": ["github_token"], "field": "content"}}}
```

| code | exit | meaning |
|---|---|---|
| `invalid_input`, `limit_exceeded`, `sensitive_content` | 2 | the request was malformed or refused |
| `not_found` | 3 | no such memory, document, session or relation in that project |
| `conflict`, `invalid_transition` | 4 | idempotency key reused with other content; lifecycle rule |
| `permission_denied` | 5 | reserved |
| `provider_error` (retryable), `provider_config`, `model_output_invalid`, `model_drift` | 6 | model server problems |
| `dependency_missing` | 7 | optional package not installed |
| `schema_error`, `schema_too_new` | 8 | database version problems |
| `storage_busy` (retryable) | 9 | another process held the write lock for 15 s |
| `internal` | 1 | unexpected; details only in the server log |
