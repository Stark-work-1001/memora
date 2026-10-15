# Public research summary / 公开研究整理

Research snapshot: 2026-10-13. Repositories, commits, licenses and what was taken from each are in [REFERENCES.md](REFERENCES.md); design decisions in [DECISIONS.md](DECISIONS.md). This document is a curated synthesis, not a benchmark ranking or certification of every upstream service. Raw source snapshots and private research context are intentionally not distributed.

调研时点：2026-10-13。参考仓库、提交、许可与借鉴内容见[REFERENCES.md](REFERENCES.md)，设计决策见[DECISIONS.md](DECISIONS.md)。本文件整理选型结论，不构成性能排名或对所有上游服务的认证；不分发原始快照及私人研究上下文。

## Storage, stacks and model roles / 存储、技术栈与模型角色

| Project / 项目 | Storage / 存储 | Stack / 技术栈 | Retrieval and judgment / 检索与判定 |
|---|---|---|---|
| Basic Memory | Markdown primary + SQLite index / Markdown主存与SQLite索引 | Python | Structured observations/relations, optional semantic search / 结构化观察关系与可选语义检索 |
| MCP Memory Service | SQLite-vec, optional other deployment modes / 可选其他部署模式 | Python, MCP, FastAPI | Local embeddings and memory management / 本地向量与记忆管理 |
| dsh-memory | Markdown cognitive graph and indexes / Markdown认知图及索引 | TypeScript/Node, supporting components / 配套组件 | Capture/review/provenance concepts / 采集、审核与溯源 |
| SynaBun | SQLite, vector/full-text/relations / 向量全文与关系 | JS/TS, Node, ONNX | Local retrieval and graphical exploration / 本地检索与图形浏览 |
| Gentleman Engram | SQLite/FTS, version-specific backend options / 版本相关后端 | Go | Lightweight structured engineering memory / 轻量结构化工程记忆 |
| DeepSeek Engram | Model-internal N-gram embedding tables / 模型内部N-gram表 | Python/PyTorch | Conditional model memory, not a user-memory MCP database / 条件记忆而非用户MCP数据库 |
| Shodh | RocksDB and local models / 本地模型 | Rust, ONNX, MCP | Entity/graph retrieval and lifecycle rules / 实体图检索与生命周期规则 |
| edg-l Engram MCP | SQLite, ONNX, FTS5 | Rust | Branch-scoped handoffs, cosine and hybrid retrieval / 分支交接与混合检索 |
| raya-ac Engram | SQLite or PostgreSQL, optional ANN / 可选ANN | Python | Dense/full-text/entity retrieval, optional LLM maintenance / 稠密全文实体检索及LLM维护 |
| Mem0 | Configurable vector storage, history, optional graph / 可配向量历史及图 | Python, SDKs | Provider-based extraction and updates / 模型接口化提取更新 |
| Letta / Letta Code | Current MemFS/Git context; historical server differs / 当前与旧服务不同 | Current Node harness / 当前Node框架 | Agent-managed memory blocks / 智能体管理记忆块 |
| Graphiti | Temporal graph databases / 时态图数据库 | Python | Hybrid retrieval and temporal fact processing / 混合检索与时态事实 |
| Zep | Current repository: Cloud examples / 当前仓库为云示例 | Integration examples / 集成示例 | Do not equate current examples with old server / 不等同旧服务 |
| Cognee | Graph + vector + relational adapters / 图向量关系适配器 | Python | Local extraction, retrieval and optional generation / 本地提取检索与可选生成 |
| MemOS | Memory Cube abstractions and configured backends / 抽象与配置后端 | Python | Scheduling, feedback and governance / 调度反馈治理 |
| Memobase | PostgreSQL + Redis | Python/FastAPI, SDKs | User profiles, event timelines, batch extraction / 画像时间线批处理 |
| A-MEM | ChromaDB, structured notes / 结构化笔记 | Python | Linking and LLM-assisted memory evolution / 关联及LLM演化 |
| LightRAG | File-persisted defaults; database adapters / 文件默认及DB适配器 | Python | Document graph RAG / 文档图RAG |
| MCP reference Memory | JSONL knowledge graph / JSONL知识图 | TypeScript/Node | Explicit entities/relations/observations / 显式实体关系观察 |
| Claude-Mem | SQLite/FTS5 + Chroma | TypeScript/Bun | Host hooks, summaries, MCP search / 宿主hooks摘要与MCP检索 |
| LangMem | Storage-independent; persistent stores optional / 存储无关 | Python/LangGraph | Background extraction and consolidation / 后台提取巩固 |
| Hindsight | Banks and service-specific persistence / bank及服务持久层 | Python, SDKs | Retain/recall/reflect / 存储召回反思 |
| OpenViking | Virtual filesystem and hierarchical context / 虚拟文件系统与分层上下文 | Service/CLI/Web Studio | Scoped semantic search, progressive loading / 范围语义检索与渐进加载 |

RAG is a retrieval-and-generation workflow, not a storage format. A graph edge is not proof of causality. An LLM call is not automatically an independent Judge. MCP exposes read/write operations but does not, by itself, collect every host conversation.

RAG是检索生成流程而非存储格式；图边不证明因果；LLM调用不自动等于独立Judge；MCP可暴露读写，但不会自行采集所有宿主对话。

## Selection / 融合取舍

1. SQLite is authoritative; Markdown is a recoverable view. Adopt readability and provenance without two competing primary stores. SQLite为真源，Markdown可恢复；保留可读性与溯源，不维护双主库。
2. Use lexical retrieval as a transparent baseline, then optional embeddings. Model identity, dimension and content hash must agree. 先采用透明词法基线，再接向量；模型标识、维度与内容哈希须一致。
3. Separate automatic capture from human approval. A Judge is advisory. 自动采集与人工批准分离，Judge只提建议。
4. Use explicit typed edges and a small viewer instead of claiming a complete temporal reasoning engine. 显式关系与轻量图谱不冒称完整时态推理。
5. Use the official MCP SDK, not a custom imitation. Host-specific hooks remain separate integrations. 使用官方SDK，宿主hooks作为独立集成。
6. Study upstream mechanisms without bundling source or assuming compatible licenses. 研究机制不等于直接合并源码或默认许可相容。

Update for 0.2: Qwen3-Embedding-0.6B has since been verified (file hashes) and evaluated on this project's dataset; see [MODELS.md](MODELS.md) and [EVALUATION.md](EVALUATION.md). Weights are still not bundled.

0.2 更新：Qwen3-Embedding-0.6B 已核对文件哈希并在本项目数据集上评测，见 [MODELS.md](MODELS.md) 与 [EVALUATION.md](EVALUATION.md)；仍不捆绑模型权重。
