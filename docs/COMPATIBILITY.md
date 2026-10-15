# Memory Merge compatibility and document boundaries

Memora adds a workbench around Memory Merge. The original `memory_merge` Python import,
CLI aliases, memory database schema (v2), review lifecycle, retrieval service, Markdown
outbox and existing MCP tool signatures remain available. No model is needed for the
memory-only CLI, legacy Web viewer or ordinary MCP memory tools.

```powershell
python -m memory_merge --data ./my-data web --port 8765
python -m memory_merge --data ./my-data agent --port 8765
```

`web` opens the original viewer; `agent` adds chat, model assembly, document storage,
archive adapters and two read-only 3D projections. Existing `MM_EMBED_*` / `MM_JUDGE_*`
environment settings remain the fallback when a model role has no workbench binding.

## Two stores, explicit responsibilities

| Store | Responsibility | Markdown files |
| --- | --- | --- |
| `memory.sqlite3` | Original Memory Merge: reviewed memory, knowledge chunks, citations, relations, conversations, tool experience, embedding and judge metadata | Original `markdown/*.md` mirrors and outbox |
| `memora-documents.sqlite3` | New document workspace: identity, audience, immutable content revisions, hashes, sources, drafts and publication metadata | `documents/<uuid>/<human-or-agent-or-shared>/v000001.md` and subsequent versions |

The separate document database avoids changing the memory schema or migrations. The
workbench backup action backs up both databases. The legacy CLI backup intentionally keeps
its original scope, so it backs up the memory database only. Document files can be rebuilt
from the document database through the workbench. They are not a second authoritative
database and editing a mirror does not silently publish new instructions.

The same document slug may have independent `human`, `agent` and `shared` version streams.
Audience describes purpose; it is not access control. Saving appends a draft. Publication
is explicit, historical revisions remain readable, and restoring a version means loading
its text and saving another revision. `expected_version` rejects conflicting concurrent
edits. Secret screening runs before content reaches the new database or Markdown files.

Published documents can be sent to the original knowledge ingestion pipeline explicitly;
their chunks remain pending. Document publication alone does not approve a memory or put
document instructions in a model system prompt.

## Agent communication

Peers communicate through MCP rather than opening SQLite files or issuing SQL:

- Existing memory capture/recall/graph tools keep their signatures and review rules.
- `memory_session_append` archives peer conversations with retry-safe sequence numbers.
- `MM_ENABLE_DOCUMENTS=1` adds `memory_document_list`, `memory_document_get` and
  `memory_document_put`. Reads expose published versions; writes create draft proposals.
- `memory_document_publish` additionally requires `MM_ENABLE_REVIEW=1`, for a reviewer
  instance driven by the user.
- `MM_ENABLE_AGENT=1` independently opts into model delegation tools.

These variables must be configured on the MCP server process; the Web window does not
change another agent's plugin configuration. A new document draft cannot overwrite a
published revision, and a peer without review authority cannot publish it.

## Brain graph isolation

The dictionary graph reads approved memory and explicitly stored relations. Layout
distance is not semantic confidence. The outline graph reads categories, conversation
metadata and published document variant metadata. A graph cannot approve memory or change
the database through a pointer, label, layout or search action.

The graph copies are modified inside this project. The two supplied source directories
are not edited. Original copy hashes remain in `graph-copy-manifest.json`.

`tests/test_documents.py` checks complete SQLite dumps, schema version and original Markdown
bytes before and after document operations and graph projection. The original integration,
migration, retrieval, knowledge ingestion and lifecycle suites also run for the release.
