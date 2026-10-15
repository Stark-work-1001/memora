# memora 1.0.1 · 记忆体

[English](README.md) · [中文](README.zh-CN.md) · [Architecture SVG](docs/Memora-Architecture.svg) · [Offline SVG/HTML](docs/Memora-Architecture.svg.html)

**面向用户、多个智能体与零散知识的本地记忆实体（memory entity）。** 保留 Memory Merge 的记忆管理内核，增加对话工作台、模型工作流、Markdown 文档库、通讯资料与二维 / 三维脑图。项目名始终是 memora。

![架构](docs/Memora-Architecture.svg)

## 仓库总览

- 对话工作台：流式生成、模型选择、记忆引用与真实心跳状态。默认模型卡是连接模板，填写地址并检测后才知道服务是否可用。
- 模型装配：Embedding、Judge、Router、Curator、归纳、分类、文档重构、SQL 分析、关系提案、核验共十类职责；工作流可以编辑每一步的模型、任务和要求。
- 原记忆内核：SQLite、中文 FTS5、Rust top-k 与 RRF、向量模型指纹、增量索引、来源、去重、修订、审核和 Markdown outbox。未配置 Embedding 时明确使用词法检索。
- Markdown：human / agent / shared 三种用途；不可变版本、独立原始日期、项目大标题、来源、新草稿与显式发布。导入 Markdown/TXT/JSON 时同时保存可阅读原文；JSONL 用于结构化导入。
- 本机智能体资料：Chat、Env、Skill、MCP、Plugin、Ghost、Organization、Subagent、Tool 与处理记录分栏。扫描结果不等于已连接；工具调用样例不等于完整工具定义。
- 项目对话：一个逻辑条目聚合多模型 / 多智能体会话，显示时间、来源、已报告进度、等待用户事项及可用的原位置链接。未知状态不会被猜成完成。
- MCP：原工具兼容；可选心跳、资源目录、逻辑会话、任务领取 / 租约 / 汇报、用户批复，以及外部智能体模型确认调度计划。可选鉴权 Streamable HTTP 桥用于隧道接入。
- 脑图：词义关系与层级两种视图，二维 / 三维切换、多布局、点击聚焦与合适角度、距离雾化、父到子的流动。关系来自明确记录；二维未登记层级时仅显示类别分组。
- 运维：三份数据库的校验备份；原数据库维护、FTS / 向量索引重建、Markdown 镜像修复与恢复指南。

## 快速开发与自用

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-lock.txt
.venv/Scripts/python -m pip install -e .
# 需安装 Rust/MSVC 构建工具，构建本机扩展
.venv/Scripts/python -m pip install ./native
npm --prefix frontend ci
npm --prefix frontend run build
.venv/Scripts/python -m memory_merge --data ./my-private-data agent --port 8765
```

浏览器打开 `http://127.0.0.1:8765`。源码模式没有 Rust 时可使用明确标识的 Python 回退；Windows standalone 必须包含 Rust 内核。开发目录允许保存自己的资料、模型地址与能力配置；公开输出采用另一套数据为空的构建流程。

**只想使用发行包？** 读取 [中文发行说明](RELEASE_NOTES.zh-CN.md)，解压 Windows 包并运行 `Memora.exe`。发行包不需要安装 Python / Node / Rust；模型服务和权重需自行配置。这里的 README 介绍仓库，发行说明单独介绍安装、升级与限制。

## 模型、判定与协议

Embedding 负责把文档和查询编码为向量，Rust 负责对向量计算排名；Judge 给出类别、持久性、重要性、敏感性与指令风险建议；Router 负责选择目标模型。Judge 可以为路由提供信号，但不能直接等同于路由。队列仍由用户审核；工作流 Judge 还可根据检索证据给出来源与冲突建议。

用户规划“哪个模型处理哪一步”；可以将 dispatcher 设为已连接的 peer。对端智能体使用自己的模型领取调度任务并通过 `memory_workflow_plan` 确认依赖顺序。当前是有边界的顺序工作流和 MCP 任务协调，不宣称是任意软件的远程控制器或完整 A2A 服务。小模型通过清晰输入输出、固定职责、来源核验和失败记录协作，而非假设它们拥有相同上下文或能力。

工作流自动召回已审核证据，再执行选定的分类 / Judge / 重构 / 两层摘要 / 关系提案 / 只读统计 / 核验步骤。每步保存模型身份与输入输出摘要和实际输出；修改只成为新草稿。为小模型限定单次原文 30,000 字符，超出会要求分段而不静默截断。角色绑定说明能力用途，具体步骤使用工作流中明确选择的模型。

六种基础记忆类型保持兼容；学科、资源与学习层级使用独立标签或结构字段。先分区可提高特定范围的精度，但硬分区会漏掉跨学科知识，因此默认跨领域召回，按需筛选。层级是可有多个父节点的有向无环关系；语义网络允许循环。两者分开保存，暂不让未经验证的图传播改变检索排序。

## 技术栈与实测

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

本机 10,000 × 1,024 维、5 个合成查询的 top-10 中位延迟：Rust 22.35 ms；Python sumprod 157.00 ms；Python fsum 467.40 ms。所有对照排序一致。测量包含 Rust 输入快照，不包含模型嵌入、数据库加载或网络耗时；不能外推为端到端加速倍数或稳定性保证。见 [原始基准](docs/eval/vector-bench-1.0.1.json)、[原检索设计](docs/NATIVE.md)。

## 调研结论与执行计划

本次按“保留 1.0.0 基线 → 兼容侧库与 Rust 热点 → 工作流与资料界面 → 脑图修复 → 自动化和界面验证 → 分离脱敏交付”实施。需求对照和验收记录见 [迭代计划](docs/ITERATION_1.0.1.md)、[变更日志](CHANGELOG.md)、[操作与协议](docs/OPERATIONS_1.0.1.md)。

灵枢的条件化记忆卡、证据定位、明确写入确认值得借鉴；“灵枢”是项目名，不是标准化的语义协议；其“无幻觉 / 白箱 AGI”等表述不能直接视为工程保证。我们保留显式语义类型、证据、审核和可检验的失败路径。详见 [批判性评估与脑图研究](docs/RESEARCH_1.0.1.md)。

已逐项核对用户提供的参考集合，包括多个同名 Engram 和另一个同名 Memora。Basic Memory 为 AGPL；raya-ac/engram 的所供版本是自定义非销售许可；engram-mcp 的许可元数据矛盾，因此都没有复制代码。AI Coding Dictionary 站点存档只用于分析交互，没有将站点构建代码、词典内容或私有下载材料放进发行包。实际复制的两个脑图副本保留原 MIT 声明，参考目录不改动。

## 脱敏、许可与发布

新代码 Apache-2.0；继承代码和依赖遵循各自许可。见 [LICENSE](LICENSE)、[NOTICE](NOTICE)、[第三方声明](THIRD_PARTY_NOTICES.md)、[完整依赖清单](docs/DEPENDENCIES.md)。

`public` 与 `release` 必须排除自用数据、会话、配置、私有文档、身份标识、凭据、内部地址及编译机路径；需要示例时使用合成数据并保留来源结构。公开版权和必要许可署名保留。详细过程见 [脱敏交付说明](docs/DELIVERY_1.0.1.md)。扫描不是对所有隐私的绝对保证；上传 GitHub 前仍需用户验收公开目录与发行包。

## 全部参考项目、项目链接及开源方案

下表区分实际复用、协议兼容、设计研究和未集成方案。历史快照结论以 [原研究记录](docs/REFERENCES.md) 为准；新核对与差异说明见 [本次研究](docs/RESEARCH_1.0.1.md)。不把“参考”写成“依赖已集成”。

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
