# Integrations

`memory-merge setup <host>` prints the configuration for your interpreter and data directory; it
writes nothing. The snippets below assume the package is installed (`pip install .` from a
checkout), which provides the `memory-merge` and `memory-merge-mcp` commands.

## Agent instruction pack

[`integrations/AGENT_INSTRUCTIONS.md`](../integrations/AGENT_INSTRUCTIONS.md) tells an agent when to
call the briefing, when to recall, what to capture and what never to capture. Paste it into
CLAUDE.md, AGENTS.md, Cursor rules or a system prompt. The MCP server also sends a one-paragraph
version as its `instructions`.

## Claude Code

```bash
claude mcp add-json memory-merge '{"command":"memory-merge-mcp","env":{"MM_DATA":"/abs/path/memory-data"}}'
```

or a project `.mcp.json` ([example](../integrations/examples/claude-code.mcp.json)).

Archive every session automatically with a `SessionEnd` hook in `.claude/settings.json`
([example](../integrations/examples/claude-code.settings-hooks.json)). The hook reads the event JSON
from stdin, imports the transcript named by `transcript_path`, and always exits 0: a memory failure
never breaks the session. The project name comes from `MM_PROJECT`, else the working directory name.
Archived turns are searchable (`memory_session_search`) but never enter recall; curated memories
still go through capture and review.

## Claude Desktop, Cursor, other JSON-configured hosts

```json
{"mcpServers": {"memory-merge": {"command": "memory-merge-mcp", "env": {"MM_DATA": "/abs/path/memory-data"}}}}
```

Claude Desktop: `claude_desktop_config.json`; Cursor: `~/.cursor/mcp.json` or `.cursor/mcp.json`.
If the host cannot find `memory-merge-mcp` on its PATH, use the absolute interpreter path from
`memory-merge setup claude-desktop`.

## Codex CLI

Append to `~/.codex/config.toml` ([example](../integrations/examples/codex.config.toml)):

```toml
[mcp_servers.memory-merge]
command = "memory-merge-mcp"
env = { MM_DATA = "/abs/path/memory-data" }
```

## A reviewer instance

Capture agents should never hold review authority. To review from an agent session you drive
yourself, register a second server with `MM_ENABLE_REVIEW=1`
([example](../integrations/examples/reviewer.mcp.json)); it adds `memory_review_queue`,
`memory_review`, `memory_review_document`, `memory_link`, `memory_link_remove`,
`memory_judge_pending` and `memory_purge`. Alternatives without MCP: `memory-merge queue` and
`memory-merge review` on the command line, or `memory-merge web --review` in the browser.

## Local embeddings with Ollama

```bash
ollama pull qwen3-embedding:0.6b          # blob sha256 06507c7b...c3e439 = official Qwen Q8_0 GGUF
```

Environment for the MCP server and CLI ([example](../integrations/examples/ollama-embeddings.env)):

```bash
MM_EMBED_URL=http://127.0.0.1:11434/v1
MM_EMBED_MODEL=qwen3-embedding:0.6b
MM_EMBED_PRESET=qwen3-embedding
MM_EMBED_REVISION=sha256:06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439
```

then `memory-merge index`. Use `127.0.0.1`, not `localhost` (see docs/THREAT_MODEL.md, T3).
Verify the blob yourself: `ollama show --modelfile qwen3-embedding:0.6b` prints its path; hash it
with `sha256sum` or `Get-FileHash`.

For a judge model served by Ollama, set its context explicitly. Ollama loaded the official
Qwen3-1.7B GGUF with a 40,960-token context (7.2 GB) on an 8 GB GPU and spilled 14-54% of it to the
CPU, making each call 15-60 s; a derived model with `PARAMETER num_ctx 4096` used 2.4 GB, 100% GPU,
about 1.3 s per call (measured, docs/EVALUATION.md). `OLLAMA_CONTEXT_LENGTH` did not override the
value stored with that model.

## In-process models (no server)

- `pip install 'memory-merge-local[local]'` and `MM_EMBED_BACKEND=sentence-transformers`,
  `MM_EMBED_MODEL=/path/to/Qwen3-Embedding-0.6B` (a local snapshot; downloading from the hub needs
  `MM_EMBED_REVISION=<commit>` and `MM_ALLOW_REMOTE=1`). This is the model card's reference usage.
- `pip install 'memory-merge-local[gguf]'` and `MM_EMBED_BACKEND=llama-cpp`,
  `MM_EMBED_PATH=/path/to/Qwen3-Embedding-0.6B-Q8_0.gguf` (the file's SHA-256 becomes the revision).
  Same for the judge: `MM_JUDGE_BACKEND=llama-cpp`, `MM_JUDGE_PATH=...gguf`.

docs/MODELS.md states which of these paths were measured and which only compile against the API.

## Docker

```bash
docker build -t memory-merge-local .
docker run -i --rm -v memory-merge-data:/data memory-merge-local    # MCP over stdio
```

The image runs as an unprivileged user with `MM_DATA=/data`. From inside a container the host's
model server is not `127.0.0.1`; providers then need HTTPS and `MM_ALLOW_REMOTE=1`, or run the model
server in the same network namespace (`--network host` on Linux).

## Other hosts

Anything that speaks MCP over stdio works with `command: memory-merge-mcp`. Host-specific hook
adapters exist only for Claude Code; for other hosts, export transcripts to the session JSONL format
(docs/DATA_FORMATS.md) and run `memory-merge session import`.
