# memora 1.0.1

[English](README.md) · [中文](README.zh-CN.md) · [Architecture SVG](docs/Memora-Architecture.svg) · [Offline SVG/HTML](docs/Memora-Architecture.svg.html)

**A local-first memory entity for people, collaborating agents and fragmented knowledge.** Memora preserves the Memory Merge core and adds a chat workspace, configurable model workflows, versioned Markdown, agent coordination and 2D/3D knowledge views.

![Architecture](docs/Memora-Architecture.svg)

## Repository overview

- Streaming chat with citations, model selection, cancellation and actual peer heartbeat status. Default model cards are configuration templates, not verified live connections.
- Ten model responsibilities: embedding, judging, routing, extraction, summarization, classification, document organization, read-only SQL analysis, relation proposals and verification. Workflow stages explicitly select models and requirements.
- Compatible Memory Merge v2 schema, original CLI/MCP APIs, native SQLite FTS5, Rust exact vector top-k and RRF, model fingerprints, provenance, review lifecycle and Markdown outbox.
- Human/agent/shared Markdown variants with immutable history, original record dates, source references, project titles, draft publication and mirror repair. Markdown/TXT/JSON imports also preserve readable source documents.
- Resource tabs for Chat, Env, Skill, MCP, Plugin, Ghost, Organization, Subagent, Tool and processing history. Invocation examples never masquerade as complete tool definitions; scanned archives never imply live connections.
- Logical project conversations aggregate model calls/sessions and report dates, agents, known progress, user intervention and validated origin links. Unknown progress remains unknown.
- Opt-in MCP peer heartbeat, resources, threads, leased task coordination and external-agent dispatch confirmation. Optional authenticated Streamable HTTP gateway supports trusted clients through a TLS tunnel.
- Semantic and hierarchical brain views in 2D/3D, multiple layouts, local focus with orientation selection, distance fog and downward flow. Geometry is a view, not a semantic truth claim.
- Verified backups of all three databases, index maintenance, mirror repair and documented restoration boundaries.

## Develop and run

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-lock.txt
.venv/Scripts/python -m pip install -e .
# Rust + MSVC build tools are required for the native module
.venv/Scripts/python -m pip install ./native
npm --prefix frontend ci
npm --prefix frontend run build
.venv/Scripts/python -m memory_merge --data ./my-private-data agent --port 8765
```

Open `http://127.0.0.1:8765`. Source deployments can explicitly fall back to Python without the native extension; Windows standalone requires Rust. Development/private data is separate from the sanitized distribution build.

For an unpack-and-run desktop, read the [English release guide](RELEASE_NOTES.en.md), unzip the Windows package and launch `Memora.exe`. Python, Node and Rust installations are not needed by the release user. Model services/weights require configuration. This README introduces the repository; release guides cover installation and upgrades separately.

## Models and coordination

Embedding encodes text; Rust ranks vectors. Judge gives advisory category, durability, importance and risk assessments. Router selects destinations; a judge may inform routing but is not inherently a redirect model. User review remains explicit. Workflow assessments can additionally compare source/conflict signals against retrieved evidence.

Users assign models to bounded workflow stages. Set a connected peer as dispatcher to let that agent's own model claim and confirm the configured dependency order through `memory_workflow_plan`. This is MCP-based task coordination, not universal remote application control or an A2A compliance claim. Models cooperate through contracts, provenance, verification and recorded failures.

Workflows retrieve approved evidence and run classification, assessment, Markdown organization, two-level summaries, relation proposals, predefined SQL statistics and verification. Every executed stage records model identity, hashes and output. Changes become new drafts. A 30,000-character source limit fails explicitly rather than silently truncating a document; split larger notes into dated parts. Role bindings explain responsibilities; actual workflow execution uses the models selected in each stage.

The original six memory categories remain stable. Domains, resource kinds and learning levels are independent facets. Domain filtering is optional because rigid partitions lose cross-domain recall. Explicit hierarchical links are directed/acyclic per type; semantic networks can contain cycles. Unverified hierarchy propagation does not affect ranking.

## Technology and measurements

| Layer / 技术 | Implemented responsibility / 实际职责 | Tradeoff / 取舍 |
|---|---|---|
| Rust + PyO3 | Compiled exact vector top-k and deterministic RRF; required in Windows standalone / 向量与融合检索 | Owned buffer snapshots avoid concurrent mutation; includes copy overhead / 计入拷贝成本 |
| SQLite / FTS5 (native C) | Transactional memory, CJK lexical search, provenance and audit / 事务与全文检索 | SQLite already runs native code; rewriting the SQL coordinator does not speed model calls / 不重复改写成熟底层 |
| Python 3.11+ | Existing Memory Merge API, ingestion, model adapters, orchestration, MCP and versioned docs / 兼容与编排 | Hot vector loops moved to Rust; Python is still suitable for I/O orchestration / 热点下沉 |
| C++ / llama.cpp | Optional GGUF inference via external server or optional Python binding / 可选模型推理 | No weights or GPU runtime bundled; capability depends on local installation / 不捆绑权重 |
| TypeScript + Three.js + Rust/WASM | Two copied 3D views, best-view focus, layouts and directional flow / 脑图交互与布局 | Explicit stored edges; layout distance is not a semantic score / 几何距离不冒充语义 |
| Canvas 2D | Semantic/hierarchy projections, pan/zoom, node focus, arrows and flow / 二维观察 | No WebGL required; shares the approved memory projection / 无 WebGL 也可查看 |
| Web + Electron | Loopback browser workspace and unpack-and-run Windows desktop / 网页与桌面 | Electron bundles a consistent Chromium runtime; bigger package / 包体较大 |
| Tauri | Evaluated alternative, not shipped / 备选方案，未交付 | Smaller shell needs WebView/runtime compatibility work / 需另做平台验证 |

On this Windows build machine, 10,000 × 1,024-dimensional synthetic vectors: median top-10 query latency was 22.35 ms in Rust, 157.00 ms in Python sumprod and 467.40 ms in Python fsum, with identical tested rankings. Rust timings include the owned input snapshot; model inference, database loading and network latency are excluded. These are kernel measurements, not end-to-end or stability guarantees. See [raw benchmark](docs/eval/vector-bench-1.0.1.json).

## Research and execution plan

The iteration follows: preserve 1.0.0 → compatible sidecars and Rust hot paths → workflows/resources → graph repair → behavioral/UI validation → isolated sanitized delivery. See [iteration acceptance plan](docs/ITERATION_1.0.1.md), [changelog](CHANGELOG.md), [operations/protocol](docs/OPERATIONS_1.0.1.md) and [research findings](docs/RESEARCH_1.0.1.md).

DSH/LINGSHU's conditional cards, source evidence and explicit commit confirmation are useful design ideas. Its name is not a standardized semantic protocol; broad claims of hallucination-free or white-box AGI behavior do not establish guarantees for arbitrary model outputs. We keep inspectable relation types, evidence and user review.

Provided archives were checked separately, including distinct Engram projects and an unrelated same-name Memora. Basic Memory uses AGPL; the provided Python Engram uses custom non-sale terms; engram-mcp has conflicting license metadata. None of their source was incorporated. The AI Coding Dictionary archive informed interaction analysis; its site bundles and dictionary data are excluded. The two copied graph implementations retain MIT notices and their original reference directories are untouched.

## Privacy, licensing and publication

New code: Apache-2.0. Inherited components keep their licenses: [LICENSE](LICENSE), [NOTICE](NOTICE), [third-party notices](THIRD_PARTY_NOTICES.md), [dependency inventory](docs/DEPENDENCIES.md).

Public source and release outputs exclude private chats, configuration, documents, identity markers, credentials, internal endpoints and compiler machine paths. Examples are synthetic; required public copyright attribution remains. See [delivery/redaction process](docs/DELIVERY_1.0.1.md). Pattern scans do not prove every possible identifier is absent. GitHub upload remains pending the user's acceptance of both outputs.

## All reference repositories, project links and open-source approaches

The table distinguishes reuse, protocol compatibility, research and unshipped alternatives. Historical snapshots remain in [REFERENCES.md](docs/REFERENCES.md); new findings and caveats are in [RESEARCH_1.0.1.md](docs/RESEARCH_1.0.1.md). A reference does not imply an integrated dependency.

| Project / 项目 | License / 许可 | Role / 用途 |
|---|---|---|
| [Memory Merge](https://github.com/Stark-work-1001/memory-merge) | MIT | 复用记忆内核 / reused memory core |
| [Obsidian 3D Mindmap](https://github.com/Stark-work-1001/obsidian-3d-mindmap) | MIT | 用户提供脑图源码的相关仓库 / related source repository |
| [Obsidian 3D Mindmap Refresh](https://github.com/Stark-work-1001/obsidian-3d-mindmap-refresh) | MIT | 用户提供双脑图源码的相关仓库 / related source repository |
| [Obsidian 3D Graph](https://github.com/Apoo711/obsidian-3d-graph) | MIT (copied notice) | 布局来源追溯 / inherited layout attribution; see THIRD_PARTY_NOTICES |
| [three.js](https://github.com/mrdoob/three.js) | MIT | 3D 渲染 / 3D rendering |
| [KaTeX](https://github.com/KaTeX/KaTeX) | MIT | 数学公式与字体 / math and fonts |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | MIT | 内置 MCP stdio 服务 / built-in MCP server |
| [MCP Reference Servers / Memory](https://github.com/modelcontextprotocol/servers/tree/main/src/memory) | upstream MIT + Apache-2.0 notices | 知识图谱交换格式兼容 / graph interchange compatibility |
| [Mem0](https://github.com/mem0ai/mem0) | Apache-2.0 | 架构研究：记忆提炼；没有复制其实现 / research only |
| [Graphiti](https://github.com/getzep/graphiti) | Apache-2.0 | 架构研究：时间与来源关系；没有集成图数据库 / research only |
| [Ollama](https://github.com/ollama/ollama) | MIT | 本地模型 HTTP、发现、装卸 / local model protocol |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | MIT | 可选 C++ GGUF 推理 / optional C++ inference |
| [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) | MIT | 可选 Python/C++ 桥接 / optional bindings |
| [LM Studio](https://lmstudio.ai/) | proprietary application | 可选兼容服务；未捆绑，非开源组件 / optional external app, not bundled |
| [Electron](https://github.com/electron/electron) | MIT + bundled notices | 桌面封装 / desktop shell |
| [electron-builder](https://github.com/electron-userland/electron-builder) | MIT | 桌面目录打包 / desktop packaging |
| [Tauri](https://github.com/tauri-apps/tauri) | MIT OR Apache-2.0 | 方案对比；1.0.0 未提供 Tauri 壳 / evaluated, not shipped |
| [PyO3](https://github.com/PyO3/pyo3) | MIT OR Apache-2.0 | 可选 Rust/Python 向量内核 / native vector kernel in standalone |
| [maturin](https://github.com/PyO3/maturin) | MIT OR Apache-2.0 | 可选 Rust 扩展构建 / native build |
| [wasm-bindgen](https://github.com/wasm-bindgen/wasm-bindgen) | MIT OR Apache-2.0 | 复制脑图的 Rust/WASM 桥 / inherited WASM bridge |
| [glam](https://github.com/bitshifter/glam-rs) | MIT OR Apache-2.0 | 脑图向量计算 / graph math |
| [serde](https://github.com/serde-rs/serde) | MIT OR Apache-2.0 | 脑图 WASM 序列化 / serialization |
| [serde-wasm-bindgen](https://github.com/RReverser/serde-wasm-bindgen) | MIT | WASM 数据转换 / WASM data conversion |
| [SQLite](https://sqlite.org/) | public domain | 本地事务存储和 FTS5 / storage and lexical index |
| [Python / CPython](https://github.com/python/cpython) | PSF-2.0 + included notices | 后端运行时 / backend runtime |
| [Rust](https://github.com/rust-lang/rust) | MIT OR Apache-2.0 | 可选本机内核与脑图 WASM / native and WASM tooling |
| [Node.js](https://github.com/nodejs/node) | MIT + included notices | 前端构建与 Electron 运行时 / build runtime |
| [TypeScript](https://github.com/microsoft/TypeScript) | Apache-2.0 | 复制的脑图源码 / typed graph source |
| [esbuild](https://github.com/evanw/esbuild) | MIT | 离线前端打包 / offline frontend bundles |
| [PyInstaller](https://github.com/pyinstaller/pyinstaller) | GPL-2.0-or-later with bootloader exception | 独立后端发布包 / frozen backend packaging |
| [Sentence Transformers](https://github.com/huggingface/sentence-transformers) | Apache-2.0 | 可选进程内向量后端 / optional embedding backend |
| [pypdf](https://github.com/py-pdf/pypdf) | BSD-3-Clause | 可选 PDF 导入 / optional PDF ingestion |
| [Qwen3 Embedding](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | Apache-2.0 (model card) | 原系统向量预设；不捆绑权重 / embedding preset, no weights bundled |
| [Dictionary of AI Coding](https://github.com/mattpocock/dictionary-of-ai-coding) | see upstream content terms | 复制代码中的词典来源追溯；不发布词典数据 / attribution only, dataset excluded |
| [AI Coding Dictionary](https://www.aicodingdictionary.com/) | see upstream content terms | 词义图原始设计参考；不捆绑站点内容 / design attribution, not bundled |
| [AI Hero](https://www.aihero.dev/) | see site terms | 上游词典内容署名 / upstream content attribution |
| [Basic Memory](https://github.com/basicmachines-co/basic-memory) | AGPL-3.0-or-later (provided checkout) | Markdown knowledge links; design study only / 仅研究，未复制代码 |
| [MCP Memory Service](https://github.com/doobidoo/mcp-memory-service) | Apache-2.0 (historical inventory) | MCP + local retrieval comparison / 检索方案对比 |
| [灵枢 LINGSHU / DSH Memory](https://github.com/FuRongJun-1999/dsh-memory) | MIT (provided 0.8.1) | Source conditions, evidence and confirmed writes; no code copied / 来源与条件路由研究 |
| [Engram (Go)](https://github.com/Gentleman-Programming/engram) | MIT (reference inventory) | Provided source and Windows 3.4.0 archives; FTS-first continuity / 工程记忆方案 |
| [Engram (Python)](https://github.com/raya-ac/engram) | Engram Public Use License 1.0 (provided 0.8.1) | Custom non-sale terms; no code incorporated / 自定义限制许可，仅研究 |
| [Engram (deepseek-ai)](https://github.com/deepseek-ai/Engram) | Apache-2.0 (reference inventory) | Model-internal memory research, different from an agent store / 模型内记忆研究 |
| [engram-mcp](https://github.com/edg-l/engram-mcp) | Conflicting MIT / Apache-2.0 metadata in provided 0.11.0 | Rust + SQLite comparison; no code copied / Rust 方案研究，许可待上游澄清 |
| [Memora (agentic-box; separate project)](https://github.com/agentic-box/memora) | MIT (provided memora-mcp 0.5.5) | Same-name independent project; collective MCP memory research / 同名独立项目，未移植 |
| [MemoRAG](https://github.com/qhjqhj00/MemoRAG) | MIT (provided 0.1.5 notice) | Memory model → retrieval → generation; not shipped / 长上下文研究，未集成权重 |
| [Shodh Memory](https://github.com/varun29ankuS/shodh-memory) | Apache-2.0 (provided notice) | Rust/edge memory and non-LLM retrieval comparison / 边缘记忆研究 |
| [SynaBun](https://github.com/danilokhury/Synabun) | Apache-2.0 (provided 2.0.4 notice) | Local memory/3D interface/agent workspace comparison / 本地协作界面对比 |
| [3d-force-graph](https://github.com/vasturiano/3d-force-graph) | MIT | Camera focus, DAG and directional particles studied; own implementation / 交互研究，独立实现 |
| [MCP specification](https://github.com/modelcontextprotocol/modelcontextprotocol) | See upstream specification terms | Tool transport and coordination boundaries / MCP 协议参考 |
| [A2A protocol](https://github.com/a2aproject/A2A) | Apache-2.0 | Task interoperability reference; no A2A compliance claimed / 任务协议对比，未宣称兼容实现 |
| [Letta](https://github.com/letta-ai/letta) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [Zep](https://github.com/getzep/zep) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [Cognee](https://github.com/topoteretes/cognee) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [MemOS](https://github.com/MemTensor/MemOS) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [Memobase](https://github.com/memodb-io/memobase) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [A-MEM](https://github.com/agiresearch/A-mem) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [LightRAG](https://github.com/HKUDS/LightRAG) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [MCP reference servers](https://github.com/modelcontextprotocol/servers) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [Claude-Mem](https://github.com/thedotmack/claude-mem) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [LangMem](https://github.com/langchain-ai/langmem) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [Hindsight](https://github.com/vectorize-io/hindsight) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [OpenViking](https://github.com/volcengine/OpenViking) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [Qwen3-Embedding evaluation code](https://github.com/QwenLM/Qwen3-Embedding) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [sqlite-vec](https://github.com/asg017/sqlite-vec) | Historical snapshot: see REFERENCES.md | Inherited design study; not a runtime dependency / 继承研究，非运行依赖 |
| [Qwen3-Embedding-0.6B-GGUF](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF) | See historical model card inventory | Model research only; no weights bundled / 模型参考，不含权重 |
| [Qwen3-1.7B-GGUF](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF) | See historical model card inventory | Model research only; no weights bundled / 模型参考，不含权重 |
| [Qwen3.8-2B-Distill](https://huggingface.co/empero-ai/Qwen3.8-2B-Distill) | See historical model card inventory | Model research only; no weights bundled / 模型参考，不含权重 |
