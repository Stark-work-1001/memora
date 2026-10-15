# References

All accessed 2026-10-13 (GitHub REST API and Hugging Face API; commit = head of the default branch
at that time). **No source code from any of these projects was copied into Memory Merge.** "Taken"
describes ideas or published facts that informed a decision. Memory Merge's own MIT license covers
only its original work; no upstream license transfers to it.

## Memory systems (design references)

| Project | Repository | Commit | License (as published) | Taken |
|---|---|---|---|---|
| Basic Memory | https://github.com/basicmachines-co/basic-memory | d1275262b202 | AGPL-3.0 | Markdown as a human-readable view of structured memory. Copyleft: no code reuse. |
| MCP Memory Service | https://github.com/doobidoo/mcp-memory-service | d72c9cb5117c | Apache-2.0 | Local embeddings behind MCP; considered sqlite-vec (not adopted, see docs/NATIVE.md) |
| dsh-memory | https://github.com/FuRongJun-1999/dsh-memory | b90c071561db | MIT | Provenance, review queue, RRF fusion as a baseline |
| SynaBun | https://github.com/danilokhury/Synabun | 9393942ba801 | Apache-2.0 | One SQLite file holding full-text, vector and relational data |
| Engram (Go) | https://github.com/Gentleman-Programming/engram | fc438498198c | MIT | FTS-first engineering memory with no model in the hot path (our lexical default) |
| Engram (deepseek-ai) | https://github.com/deepseek-ai/Engram | fb7f84a21f91 | Apache-2.0 | Background only: model-internal memory research, not an agent memory store |
| shodh-memory | https://github.com/varun29ankuS/shodh-memory | 902daf8394e7 | Apache-2.0 | Access/decay heuristics; we record access but deliberately do not rank by it |
| engram-mcp | https://github.com/edg-l/engram-mcp | 71d945d85c21 | Conflicting: Cargo.toml says MIT, the only LICENSE file is Apache-2.0, README says "MIT OR Apache-2.0" | FTS5 + cosine hybrid in one SQLite file. Resolve the license with the author before any reuse. |
| Engram (Python) | https://github.com/raya-ac/engram | ab52ad4e56a8 | Custom "Engram Public Use License 1.0" since 2026-09-19 (MIT up to fe31b9218663) | Layered dense/full-text/graph retrieval. Not reusable in an MIT project after the relicence. |
| Mem0 | https://github.com/mem0ai/mem0 | d26ba5e4518c | Apache-2.0 | Separating embedder, store and history behind interfaces |
| Letta | https://github.com/letta-ai/letta | 5bcdd177d70f | Apache-2.0 | Memory blocks: a compact always-loaded context (our briefing) versus searchable archive |
| Graphiti | https://github.com/getzep/graphiti | 2f0fb35b749f | Apache-2.0 | Validity intervals (our `valid_until` on superseded/archived memories); needs a graph database, so not adopted |
| Zep | https://github.com/getzep/zep | cfa2ab2bbc3c | Apache-2.0 | Background only (examples for a hosted service) |
| Cognee | https://github.com/topoteretes/cognee | 0ec7a9fa61c9 | Apache-2.0 | Clear line between retrieval and generation (our `generation: client_required`) |
| MemOS | https://github.com/MemTensor/MemOS | a7367d07e55d | Apache-2.0 | Governance as a first-class layer (review, audit) |
| Memobase | https://github.com/memodb-io/memobase | 358c16bbc6d6 | Apache-2.0 | User profile separate from the event timeline (our profile vs session archive) |
| A-MEM | https://github.com/agiresearch/A-mem | ceffb860f071 | MIT | Note evolution; adopted only as reviewed revisions (`supersedes`), never automatic |
| LightRAG | https://github.com/HKUDS/LightRAG | 4d0afc1bc36e | MIT | Document chunking with structural context (our heading-path prefix) |
| MCP reference servers | https://github.com/modelcontextprotocol/servers | bbb701e7ac1e | NOASSERTION on GitHub (transition MIT -> Apache-2.0, docs CC-BY-4.0) | Minimal entity/relation tool shape |
| MCP Python SDK | https://github.com/modelcontextprotocol/python-sdk | 754254c08fe1 | MIT | Runtime dependency (`mcp==1.30.0`, used as a library) |
| Claude-Mem | https://github.com/thedotmack/claude-mem | a2150b2c09c6 | Apache-2.0 | Host hooks as the real capture mechanism (our SessionEnd adapter) |
| LangMem | https://github.com/langchain-ai/langmem | 48e3c11f5bb5 | MIT | Background consolidation; adopted only as suggestions (`report`), never automatic |
| Hindsight | https://github.com/vectorize-io/hindsight | f843f173bb41 | MIT | Retain / recall / reflect split |
| OpenViking | https://github.com/volcengine/OpenViking | 938ef31f61fb | AGPL-3.0 | Progressive loading (briefing first, recall on demand). Copyleft: no code reuse. |

## Models

| Model | Source | Revision / file | License | Use here |
|---|---|---|---|---|
| Qwen3-Embedding-0.6B | https://huggingface.co/Qwen/Qwen3-Embedding-0.6B | commit 97b0c614be4d; `model.safetensors` sha256 0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd (1,191,586,416 bytes) | Apache-2.0 | Reference embeddings (sentence-transformers, fp32 CPU) |
| Qwen3-Embedding-0.6B GGUF | https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF | commit 370f27d7550e; `Qwen3-Embedding-0.6B-Q8_0.gguf` sha256 06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439 (639,150,592 bytes); identical to Ollama `qwen3-embedding:0.6b` | Apache-2.0 | Measured embedding path (via Ollama) |
| Qwen3-1.7B GGUF | https://huggingface.co/Qwen/Qwen3-1.7B-GGUF | commit 90862c4b9d27; `Qwen3-1.7B-Q8_0.gguf` sha256 061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a (1,834,426,016 bytes) | Apache-2.0 | Measured judge |
| Qwen3.8-2B-Distill (named in the brief) | https://huggingface.co/empero-ai/Qwen3.8-2B-Distill | commit e37a2dc4acc6 | apache-2.0 claimed; teacher model license (qwen3.8-max) unaddressed | Not used: community fine-tune, single commit, training data and claims unverifiable, name resembles an official release |
| Qwen3-Embedding evaluation code | https://github.com/QwenLM/Qwen3-Embedding | 44548aa5f0a0 | no license file (all rights reserved by default) | Read only, for the query template and truncation order; nothing copied |

## Techniques and papers

- Reciprocal Rank Fusion: Cormack, Clarke, Buettcher. "Reciprocal Rank Fusion outperforms Condorcet
  and individual Rank Learning Methods", SIGIR 2009, pp. 758-759, doi:10.1145/1571941.1572114. k = 60.
- CJK bigram analysis: Lucene `CJKBigramFilter`
  (https://lucene.apache.org/core/10_3_1/analysis/common/org/apache/lucene/analysis/cjk/CJKBigramFilter.html)
  and the Elasticsearch `cjk_bigram` filter. Scheme only; implemented independently in Python.
- SQLite: FTS5 (https://www.sqlite.org/fts5.html; trigram tokenizer limits considered and rejected
  because two-character Chinese words cannot match it), `PRAGMA secure_delete`
  (https://www.sqlite.org/pragma.html#pragma_secure_delete), WAL checkpoints
  (https://www.sqlite.org/wal.html).
- Matryoshka representation learning: truncate, then L2-normalise, as in the Qwen3-Embedding
  evaluation code.

## Tooling

| Tool | Repository | Commit | License | Use |
|---|---|---|---|---|
| PyO3 | https://github.com/PyO3/pyo3 | 071edecda46b | MIT OR Apache-2.0 | Native extension bindings (crate 0.22) |
| maturin | https://github.com/PyO3/maturin | 6fe12cbc0cf6 | MIT OR Apache-2.0 | Build backend for `native/` |
| sqlite-vec | https://github.com/asg017/sqlite-vec | 04d28bd21773 | MIT OR Apache-2.0 | Considered, not adopted: loadable extensions are disabled in several Python builds |

## Evaluation dataset

`datasets/memory-eval-v1` was written for this project by a separate agent that was not told how
retrieval works. It contains no real personal data. See docs/EVALUATION.md for its limits.
