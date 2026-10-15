# Third-party notices / 第三方声明

Memora 1.0.0
Copyright 2026 Stark-work-1001 and contributors.
New Memora contributions: Apache License, Version 2.0.

This distribution includes Memory Merge (MIT), Copyright 2026 Stark-work-1001.
The original MIT license is retained at LICENSES/Memory-Merge-MIT.txt.

Copied user-supplied Dictionary Graph and 3D Mind Map components retain their MIT licenses
under frontend/vendor/. Their original source directories were not modified.
The inherited physics layout credits Obsidian 3D Graph, Copyright 2025 Aryan Gupta.
three.js, KaTeX, Rust/WASM crates and other dependencies retain their licenses.

Modified copies: external Markdown link scheme allowlist; compiler-home path removal
from embedded WASM; Memora host adapters and memory data projections.
The upstream AI Coding Dictionary dataset and website content are not redistributed.

Complete project/repository links and use classifications are in both READMEs,
docs/OPEN_SOURCE_REUSE.md, docs/DEPENDENCIES.md and THIRD_PARTY_NOTICES.md.

Copied UI changes: explicit body-line wiki links, refreshed graph counts, personal-scale visual defaults, and initialized scene background for readable labels.


| 项目 / Project | 许可 / License | 用途 / Use |
| --- | --- | --- |
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
| [PyO3](https://github.com/PyO3/pyo3) | MIT OR Apache-2.0 | 可选 Rust/Python 向量内核 / optional vector kernel |
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
| [Basic Memory](https://github.com/basicmachines-co/basic-memory) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [MCP Memory Service](https://github.com/doobidoo/mcp-memory-service) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [dsh-memory](https://github.com/FuRongJun-1999/dsh-memory) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [SynaBun](https://github.com/danilokhury/Synabun) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [Engram (Go)](https://github.com/Gentleman-Programming/engram) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [Engram (deepseek-ai)](https://github.com/deepseek-ai/Engram) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [shodh-memory](https://github.com/varun29ankuS/shodh-memory) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [engram-mcp](https://github.com/edg-l/engram-mcp) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [Engram (Python)](https://github.com/raya-ac/engram) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [Letta](https://github.com/letta-ai/letta) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [Zep](https://github.com/getzep/zep) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [Cognee](https://github.com/topoteretes/cognee) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [MemOS](https://github.com/MemTensor/MemOS) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [Memobase](https://github.com/memodb-io/memobase) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [A-MEM](https://github.com/agiresearch/A-mem) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [LightRAG](https://github.com/HKUDS/LightRAG) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [Claude-Mem](https://github.com/thedotmack/claude-mem) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [LangMem](https://github.com/langchain-ai/langmem) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [Hindsight](https://github.com/vectorize-io/hindsight) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [OpenViking](https://github.com/volcengine/OpenViking) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [Qwen3-Embedding evaluation code](https://github.com/QwenLM/Qwen3-Embedding) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [sqlite-vec](https://github.com/asg017/sqlite-vec) | 历史许可见 docs/REFERENCES.md | 继承的设计研究记录；非代码复用 / inherited research, no code copied |
| [Qwen3-Embedding-0.6B-GGUF](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF) | 历史模型许可见 docs/REFERENCES.md | 继承模型研究记录，不捆绑权重 / inherited model reference, no weights bundled |
| [Qwen3-1.7B-GGUF](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF) | 历史模型许可见 docs/REFERENCES.md | 继承模型研究记录，不捆绑权重 / inherited model reference, no weights bundled |
| [Qwen3.8-2B-Distill](https://huggingface.co/empero-ai/Qwen3.8-2B-Distill) | 历史模型许可见 docs/REFERENCES.md | 继承模型研究记录，不捆绑权重 / inherited model reference, no weights bundled |

Inherited full license texts: [graph notices](frontend/vendor/original-dev/THIRD_PARTY_NOTICES.md), [MIT core](LICENSES/Memory-Merge-MIT.txt). Electron binaries also include LICENSE.electron.txt and LICENSES.chromium.html. Frozen Python dependencies include THIRD_PARTY_LICENSES.txt. See [dependency inventory](docs/DEPENDENCIES.md).

## 1.0.1 research additions

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
