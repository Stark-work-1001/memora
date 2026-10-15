"""Generate bilingual project documentation with a shared, explicit upstream inventory."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
PROJECTS=[
 ('Memory Merge','https://github.com/Stark-work-1001/memory-merge','MIT','复用记忆内核 / reused memory core'),
 ('Obsidian 3D Mindmap','https://github.com/Stark-work-1001/obsidian-3d-mindmap','MIT','用户提供脑图源码的相关仓库 / related source repository'),
 ('Obsidian 3D Mindmap Refresh','https://github.com/Stark-work-1001/obsidian-3d-mindmap-refresh','MIT','用户提供双脑图源码的相关仓库 / related source repository'),
 ('Obsidian 3D Graph','https://github.com/Apoo711/obsidian-3d-graph','MIT (copied notice)','布局来源追溯 / inherited layout attribution; see THIRD_PARTY_NOTICES'),
 ('three.js','https://github.com/mrdoob/three.js','MIT','3D 渲染 / 3D rendering'),
 ('KaTeX','https://github.com/KaTeX/KaTeX','MIT','数学公式与字体 / math and fonts'),
 ('MCP Python SDK','https://github.com/modelcontextprotocol/python-sdk','MIT','内置 MCP stdio 服务 / built-in MCP server'),
 ('MCP Reference Servers / Memory','https://github.com/modelcontextprotocol/servers/tree/main/src/memory','upstream MIT + Apache-2.0 notices','知识图谱交换格式兼容 / graph interchange compatibility'),
 ('Mem0','https://github.com/mem0ai/mem0','Apache-2.0','架构研究：记忆提炼；没有复制其实现 / research only'),
 ('Graphiti','https://github.com/getzep/graphiti','Apache-2.0','架构研究：时间与来源关系；没有集成图数据库 / research only'),
 ('Ollama','https://github.com/ollama/ollama','MIT','本地模型 HTTP、发现、装卸 / local model protocol'),
 ('llama.cpp','https://github.com/ggml-org/llama.cpp','MIT','可选 C++ GGUF 推理 / optional C++ inference'),
 ('llama-cpp-python','https://github.com/abetlen/llama-cpp-python','MIT','可选 Python/C++ 桥接 / optional bindings'),
 ('LM Studio','https://lmstudio.ai/','proprietary application','可选兼容服务；未捆绑，非开源组件 / optional external app, not bundled'),
 ('Electron','https://github.com/electron/electron','MIT + bundled notices','桌面封装 / desktop shell'),
 ('electron-builder','https://github.com/electron-userland/electron-builder','MIT','桌面目录打包 / desktop packaging'),
 ('Tauri','https://github.com/tauri-apps/tauri','MIT OR Apache-2.0','方案对比；1.0.0 未提供 Tauri 壳 / evaluated, not shipped'),
 ('PyO3','https://github.com/PyO3/pyo3','MIT OR Apache-2.0','可选 Rust/Python 向量内核 / optional vector kernel'),
 ('maturin','https://github.com/PyO3/maturin','MIT OR Apache-2.0','可选 Rust 扩展构建 / native build'),
 ('wasm-bindgen','https://github.com/wasm-bindgen/wasm-bindgen','MIT OR Apache-2.0','复制脑图的 Rust/WASM 桥 / inherited WASM bridge'),
 ('glam','https://github.com/bitshifter/glam-rs','MIT OR Apache-2.0','脑图向量计算 / graph math'),
 ('serde','https://github.com/serde-rs/serde','MIT OR Apache-2.0','脑图 WASM 序列化 / serialization'),
 ('serde-wasm-bindgen','https://github.com/RReverser/serde-wasm-bindgen','MIT','WASM 数据转换 / WASM data conversion'),
 ('SQLite','https://sqlite.org/','public domain','本地事务存储和 FTS5 / storage and lexical index'),
 ('Python / CPython','https://github.com/python/cpython','PSF-2.0 + included notices','后端运行时 / backend runtime'),
 ('Rust','https://github.com/rust-lang/rust','MIT OR Apache-2.0','可选本机内核与脑图 WASM / native and WASM tooling'),
 ('Node.js','https://github.com/nodejs/node','MIT + included notices','前端构建与 Electron 运行时 / build runtime'),
 ('TypeScript','https://github.com/microsoft/TypeScript','Apache-2.0','复制的脑图源码 / typed graph source'),
 ('esbuild','https://github.com/evanw/esbuild','MIT','离线前端打包 / offline frontend bundles'),
 ('PyInstaller','https://github.com/pyinstaller/pyinstaller','GPL-2.0-or-later with bootloader exception','独立后端发布包 / frozen backend packaging'),
 ('Sentence Transformers','https://github.com/huggingface/sentence-transformers','Apache-2.0','可选进程内向量后端 / optional embedding backend'),
 ('pypdf','https://github.com/py-pdf/pypdf','BSD-3-Clause','可选 PDF 导入 / optional PDF ingestion'),
 ('Qwen3 Embedding','https://huggingface.co/Qwen/Qwen3-Embedding-0.6B','Apache-2.0 (model card)','原系统向量预设；不捆绑权重 / embedding preset, no weights bundled'),
 ('Dictionary of AI Coding','https://github.com/mattpocock/dictionary-of-ai-coding','see upstream content terms','复制代码中的词典来源追溯；不发布词典数据 / attribution only, dataset excluded'),
 ('AI Coding Dictionary','https://www.aicodingdictionary.com/','see upstream content terms','词义图原始设计参考；不捆绑站点内容 / design attribution, not bundled'),
 ('AI Hero','https://www.aihero.dev/','see site terms','上游词典内容署名 / upstream content attribution'),
]


def references():
    lines=['| 项目 / Project | 许可 / License | 用途 / Use |','| --- | --- | --- |']
    for name,url,license_,use in PROJECTS: lines.append(f'| [{name}]({url}) | {license_} | {use} |')
    return '\n'.join(lines)


def main():
    # Preserve every inherited research-project link, explicitly marking these as historical
    # references rather than current dependencies or freshly verified license assertions.
    known={re.sub(r'(https://github.com/[^/]+/[^/]+).*',r'\1',p[1]).lower() for p in PROJECTS}
    for line in (ROOT/'docs/REFERENCES.md').read_text('utf-8').splitlines():
        if not line.startswith('|'): continue
        match=re.search(r'https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',line)
        if match and match.group().lower() not in known:
            name=line.split('|')[1].strip()
            PROJECTS.append((name,match.group(),'历史许可见 docs/REFERENCES.md','继承的设计研究记录；非代码复用 / inherited research, no code copied'))
            known.add(match.group().lower())
    legacy=(ROOT/'docs/REFERENCES.md').read_text('utf-8')
    known_urls={p[1].lower() for p in PROJECTS}
    for url in re.findall(r'https://huggingface.co/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',legacy):
        if url.lower() not in known_urls:
            PROJECTS.append((url.split('/')[-1],url,'历史模型许可见 docs/REFERENCES.md','继承模型研究记录，不捆绑权重 / inherited model reference, no weights bundled'))
            known_urls.add(url.lower())
    table=references()
    zh='''# memora 1.0.0 · 记忆体

[English](README.md) · [中文](README.zh-CN.md) · [架构 SVG](docs/Memora-Architecture.svg) · [可离线打开的 SVG/HTML](docs/Memora-Architecture.svg.html)

**面向用户、多个智能体及零散知识的本地优先记忆实体。** 把长期记忆、知识库、模型装配、MCP 通信和双 3D 脑图放进一个工作台。

![Memora architecture](docs/Memora-Architecture.svg)

## 能力

- 中文对话窗口：多会话、流式回答、停止生成、系统提示词、Temperature 和输出长度控制。
- 多模型分工：Generator、Embedding、Judge、Router、Curator；可分别使用本地服务或经明确授权的云端兼容 API。
- 本地模型：Ollama 发现、状态、加载与卸载；LM Studio / llama-server 兼容接口；可选 llama-cpp-python 进程内 GGUF。
- 原记忆内核完整保留：SQLite、FTS5 中文二元分词、可选 Rust top-k、混合向量召回、模型指纹和漂移检查、带引用的证据包。
- Markdown 文档库：用户版 / 智能体版 / 共同参考版独立修订；保留历史、草稿发布、下载和文件重建；MCP 读已发布版本、提交草稿。文档层使用独立数据库，原记忆内核无需迁移。详见 [兼容边界](docs/COMPATIBILITY.md)。
- 知识管理：Markdown / TXT / PDF / 书签 / JSONL，去重、来源、修订、矛盾、生命周期、跨项目用户画像和工具操作经验。
- 多智能体积累：Codex、Claude Code、Gemini CLI 的常见 JSON/JSONL 对话格式；工具调用示例、Skills、Plugins、专家描述、Teams、Agents Swarm 和自定义来源目录。
- 两个已复制整合的脑图：词义关系图与层级思维导图，读取当前项目已审核的真实记忆和会话结构；原目录保持不变。
- 内置 MCP：保留原工具，新增对话追加和可选问答委派；其他智能体可通过既有 MCP 插件接入。
- Markdown 镜像与数据库维护：导出、修改同步、索引整理、压缩、诊断、校验备份及原 CLI 的恢复演练。

所有自动提炼和外部导入均先进入待审。Judge 是建议层，用户审核后才成为检索知识。图中的连线来自明确记录的关系，空间距离不是经过验证的语义结论。

## 快速开始

Python 3.11+；已提交前端构建产物，运行 Web 版无需 Node.js、Rust 或 C++ 编译器。

```bash
git clone https://github.com/Stark-work-1001/memora.git
cd memora
python -m venv .venv
# Windows
.venv\\Scripts\\python -m pip install -r requirements-lock.txt
.venv\\Scripts\\python -m pip install -e .
.venv\\Scripts\\python -m memory_merge --data ./agent-data agent --port 8765
# Linux / macOS: 将 .venv\\Scripts\\python 换成 .venv/bin/python
```

打开 `http://127.0.0.1:8765`。Windows 也可运行 `./start-memora.ps1`。已有 Memory Merge 数据可直接通过 `--data` 指向原数据目录；升级前建议创建校验备份。新建来源目录后，扫描、选择并导入文件；不会默认导入整机私人对话。

## 配置模型

在“模型装配”中填写模型 ID、服务地址和角色。

| 接入 | 地址示例 | 控制范围 |
| --- | --- | --- |
| Ollama | `http://127.0.0.1:11434` | 发现、加载、卸载、状态、生成 |
| LM Studio | `http://127.0.0.1:1234/v1` | 发现、生成 |
| llama-server | `http://127.0.0.1:8080/v1` | 发现、生成 |
| 云端兼容 API | 供应商的 HTTPS `/v1` 地址 | 生成；需勾选云端数据发送授权 |
| 本机 GGUF | 选择 `gguf` 并填写本机模型文件路径 | 进程内加载、卸载、生成 |

密钥只填写环境变量名称。先在启动终端设置该变量，再启动 Memora。模型配置保存于数据目录中的 `agent-models.json`，角色绑定保存于 `agent-assembly.json`。Embedding 角色需要使用真正的向量模型。沿用原系统时可继续使用 `MM_EMBED_*`、`MM_JUDGE_*`。更改向量模型后重新建立索引；独立 MCP 进程需重启以读取新装配。

```bash
python -m pip install ".[gguf]"  # 可选 C++ 后端，需要合适的 wheel 或构建工具链
python -m pip install ./native  # 可选 Rust top-k，需要 Rust 工具链
```

安装不含模型权重，不会自动下载或运行未知工具。模型支持范围是兼容 Chat Completions 协议的云端接口；没有宣称覆盖所有供应商的私有协议。

## 内置 MCP 与多智能体历史

```json
{
  "mcpServers": {
    "memora": {
      "command": "<本项目 Python 的绝对路径>",
      "args": ["-m", "memory_merge", "--data", "<记忆数据目录>", "mcp"],
      "env": {"MM_ENABLE_AGENT": "1", "MM_ENABLE_DOCUMENTS": "1"}
    }
  }
}
```

- 原 `memory_capture`、`memory_recall`、`memory_rag_context`、`memory_judge`、`memory_index` 等继续可用。
- `memory_session_append(project, agent, external_id, turns)`：以稳定会话 ID 和序号增量汇集其他智能体对话。
- `memory_agent_ask` / `memory_agent_result` / `memory_agent_cancel`：显式启用 `MM_ENABLE_AGENT=1` 后提供委派问答。
- 审核工具仍由独立的 `MM_ENABLE_REVIEW=1` 控制，默认客户端不能自行批准记忆。
- `MM_ENABLE_DOCUMENTS=1`：启用 Markdown 文档列表、已发布版本读取和草稿提交；文档发布还需审核权限。数据库保存版本、来源与通信状态，智能体通过 MCP 访问。
- 在“本机智能体资料”里导入 Skills、插件描述、专家、团队和 Swarm；它们只是待审数据，不执行其中的指令。
- 支持 MCP Reference Memory 的 entities / relations / observations JSON 或 JSONL 导出格式，原关系标签保存在记忆正文中。

本机所有智能体没有统一的历史格式。扫描器支持预设目录和自定义来源，按 200 文件分页，单批导入 50 文件、单文件最多 64 MiB；解析和跳过情况会报告。OpenCode 的原生数据库或其他未公开格式需先导出，不能声称自动读取所有软件数据库。

## 桌面版与构建

```bash
cd frontend
npm ci
npm run build
cd ../desktop
npm ci
npm start
```

Electron 开发模式复用根目录 `.venv`；发行版捆绑独立 Python 后端，不要求用户安装 Python。构建步骤见 [发布说明](docs/MEMORA_RELEASE.md)。Tauri 作为备选方案研究，1.0.0 实际提供 Web 与 Electron。

## 验证、数据与许可

```bash
python -m unittest discover -s tests -v
python tools/build_architecture.py
python tools/release_memora.py
```

测试包括真实本机 HTTP 假服务的 SSE / NDJSON 协议、待审隔离、跨进程会话互斥、MCP、导入幂等、迁移与原检索回归。真实云端账号与所有硬件上的 GGUF 推理不属于自动测试覆盖；实际构建机报告见 Release 附件。1.0.0 为首个完整框架发布，不代表所有模型和操作系统均已验证。

运行数据、私人对话、数据库、备份、环境变量、模型配置及密钥不进入仓库或 Release。发布脚本使用白名单、脱敏扫描和 SHA-256 校验；模式扫描不能识别所有形式的隐私。可选本地资料采集只在本机执行，远程模型只有明确配置后才被调用。

Memora 新增代码采用 [Apache-2.0](LICENSE)。原记忆内核和复制的 MIT 组件保留原有许可，见 [NOTICE](NOTICE)、[LICENSES](LICENSES/Memory-Merge-MIT.txt) 和 [第三方清单](THIRD_PARTY_NOTICES.md)。

## 所有引用项目、仓库与开源方案

下面区分代码复用、运行依赖、兼容服务、架构研究和内容署名。研究项目没有被冒称为已安装依赖；LM Studio 不是开源组件。用户提供的脑图目录通过文件哈希记录来源，未声称与某个远端提交完全一致。没有重新分发上游 AI 词典数据。

'''+table+'''

[Memory Merge compatibility / 兼容边界](docs/COMPATIBILITY.md) · [Graph repairs and design reference / 脑图修复记录](docs/GRAPH_REPAIRS.md)


完整 npm / Python 安装依赖及项目链接见 [DEPENDENCIES.md](docs/DEPENDENCIES.md)；继承的 Rust crate 许可见 [rust-crates.txt](frontend/vendor/original-dev/licenses/rust-crates.txt)。[方案比较与复用记录](docs/OPEN_SOURCE_REUSE.md) 包含参考日期、已实现的兼容适配和后续扩展边界。
'''
    en='''# memora 1.0.0

[English](README.md) · [中文](README.zh-CN.md) · [Architecture SVG](docs/Memora-Architecture.svg) · [Offline SVG/HTML preview](docs/Memora-Architecture.svg.html)

**A local-first memory entity for people, collaborating agents, and fragmented knowledge.** Memora combines long-term memory, a knowledge base, model assembly, MCP communication, and two 3D graph views in one workspace.

![Memora architecture](docs/Memora-Architecture.svg)

## Features

- Multi-session chat, streamed answers, cooperative cancellation, citations, system prompts, temperature and output limits.
- Independent Generator, Embedding, Judge, Router and Curator models. Cloud-compatible APIs, Ollama, LM Studio / llama-server, and optional in-process C++ GGUF inference.
- The existing Memory Merge core: SQLite, CJK-aware FTS5, optional Rust exact top-k, hybrid retrieval, model fingerprints, drift checks and cited evidence packs.
- Knowledge ingestion, provenance, deduplication, revisions, contradictions, lifecycle management, user preferences and tool-use knowledge.
- Local agent sources: common Codex, Claude Code and Gemini CLI JSON/JSONL histories; tool-call examples, Skills, Plugins, expert descriptions, Teams, Swarms and custom folders.
- Two copied and integrated 3D apps: dictionary relationships and hierarchical mind maps, backed by approved memory and archive structure. The original source directories remain untouched.
- Built-in MCP stdio tools for peer agents, incremental conversation ingestion and optional model delegation.
- Human-readable Markdown mirrors, edit synchronization, database maintenance, verified backups and the original CLI restore drills.
- Versioned Markdown workspace: independent human/agent/shared variants, immutable history, explicit draft publication, downloads and mirror repair. A separate document database preserves the original memory schema; MCP reads published revisions and proposes drafts. See [compatibility boundaries](docs/COMPATIBILITY.md).

Automatic extraction and imported knowledge remain pending until reviewed. The Judge advises; it never approves. Graph edges represent stored relationships; layout distance is not a verified semantic claim.

## Quick start

Python 3.11+. Prebuilt browser assets are included; Node.js, Rust and a C++ compiler are not required for the Web app.

```bash
git clone https://github.com/Stark-work-1001/memora.git
cd memora
python -m venv .venv
# Windows; use .venv/bin/python on Linux/macOS
.venv\\Scripts\\python -m pip install -r requirements-lock.txt
.venv\\Scripts\\python -m pip install -e .
.venv\\Scripts\\python -m memory_merge --data ./agent-data agent --port 8765
```

Open `http://127.0.0.1:8765`, or run `./start-memora.ps1` on Windows. Point `--data` at an existing Memory Merge data directory to reuse it; make a verified backup before upgrading. Local archives are discovered and imported only when selected by the operator.

## Model assembly

Configure model profiles and roles in the UI. Ollama uses `http://127.0.0.1:11434`; LM Studio commonly uses `http://127.0.0.1:1234/v1`; llama-server commonly uses `http://127.0.0.1:8080/v1`. Cloud endpoints must use HTTPS with explicit remote consent. API credentials are referenced by environment-variable name, never saved in model profiles.

Profiles live in `agent-models.json`; role bindings live in `agent-assembly.json`, under the data directory. An Embedding role must use an actual embedding model. Existing `MM_EMBED_*` and `MM_JUDGE_*` settings remain supported. Re-index after changing embedding models; restart separate MCP processes to reload role bindings.

```bash
python -m pip install ".[gguf]"  # optional llama.cpp bindings; wheel/toolchain availability varies
python -m pip install ./native  # optional Rust vector kernel; Rust toolchain required
```

Ollama and in-process GGUF support model loading/unloading. Compatible HTTP providers support discovery and generation where their APIs implement it. No model weights are included. Cloud integration targets Chat Completions-compatible protocols, not every provider-specific API.

## Built-in MCP and agent archives

```json
{
  "mcpServers": {
    "memora": {
      "command": "<absolute path to project Python>",
      "args": ["-m", "memory_merge", "--data", "<memory directory>", "mcp"],
      "env": {"MM_ENABLE_AGENT": "1", "MM_ENABLE_DOCUMENTS": "1"}
    }
  }
}
```

Original `memory_capture`, `memory_recall`, `memory_rag_context`, `memory_judge`, `memory_index` and other memory tools remain compatible. `memory_session_append(project, agent, external_id, turns)` incrementally archives peer conversations using stable sequence ids. `memory_agent_ask`, `memory_agent_result` and `memory_agent_cancel` are available with `MM_ENABLE_AGENT=1`. Review authority still requires a separate `MM_ENABLE_REVIEW=1` operator instance.

The local source panel accepts Skills, plugin manifests, expert/team/swarm descriptions, loose notes and MCP Reference Memory entities/relations/observations exports. These are data, never executable instructions. Tool-call examples are explicitly distinguished from full tool definitions.

Enable `MM_ENABLE_DOCUMENTS=1` on the MCP server for `memory_document_list`, `memory_document_get` and `memory_document_put`; publication additionally requires review authority. Document text remains data. Original knowledge ingestion and memory approval remain explicit actions.

There is no universal local-agent archive format. Discovery is paginated at 200 files; imports accept 50 files per batch and 64 MiB per file with parse/skip reports. Native OpenCode databases and other unsupported formats require a JSON/JSONL export. Memora does not claim to automatically read every agent database.

## Desktop and builds

```bash
cd frontend
npm ci
npm run build
cd ../desktop
npm ci
npm start
```

Electron development uses the root `.venv`; packaged builds include a frozen Python backend. See [release build instructions](docs/MEMORA_RELEASE.md). Version 1.0.0 ships Web and Electron; Tauri was evaluated but is not shipped.

## Validation, privacy and licensing

```bash
python -m unittest discover -s tests -v
python tools/build_architecture.py
python tools/release_memora.py
```

Tests cover local fake HTTP SSE/NDJSON providers, evidence/review boundaries, cross-process session leases, MCP, incremental imports, migrations and existing retrieval regressions. They do not prove live cloud credentials or GGUF inference on every device. Build-machine validation accompanies the Release. Version 1.0.0 is the first complete framework release, not a claim that every model and platform has been validated.

Runtime data, personal chats, databases, backups, environment files, model profiles and credentials are excluded from source and binary releases. Packaging uses an allowlist, privacy scans and SHA-256 manifests; pattern scanning cannot identify every possible private identifier. Local collection stays local unless a remote model was explicitly configured.

New Memora code is licensed under [Apache-2.0](LICENSE). Inherited MIT components retain their licenses and attribution; see [NOTICE](NOTICE), [LICENSES](LICENSES/Memory-Merge-MIT.txt) and [third-party notices](THIRD_PARTY_NOTICES.md).

## All referenced projects, repositories and open-source approaches

The inventory distinguishes copied code, runtime/build dependencies, compatible external services, research references and content attribution. Research projects are not misrepresented as installed dependencies; LM Studio is not open source. User-provided graph directories are recorded by file hashes without claiming an exact upstream commit. The upstream AI dictionary dataset is not redistributed.

'''+table+'''

[Memory Merge compatibility / 兼容边界](docs/COMPATIBILITY.md) · [Graph repairs and design reference / 脑图修复记录](docs/GRAPH_REPAIRS.md)


All installed npm/Python dependencies and project links are listed in [DEPENDENCIES.md](docs/DEPENDENCIES.md). Inherited Rust crate licenses are in [rust-crates.txt](frontend/vendor/original-dev/licenses/rust-crates.txt). See [open-source research and reuse](docs/OPEN_SOURCE_REUSE.md) for adoption decisions and extension boundaries.
'''
    (ROOT/'README.md').write_text(en,'utf-8');(ROOT/'README.zh-CN.md').write_text(zh,'utf-8')
    (ROOT/'docs/OPEN_SOURCE_REUSE.md').write_text('''# 开源方案、复用与来源 / Open-source reuse

评估日期 / Evaluated: 2026-10-15. 用户给定名称：memora，版本：1.0.0。

## 实际复用

Memory Merge 是记忆内核。用户提供的 dictionary-graph 与 original-dev 复制到 frontend/vendor，保留原 MIT 许可；原目录不变。副本的 Markdown 外部链接限制到 HTTP(S)/mailto；WASM 中三个编译目录标识被等长替换，不改变模块偏移；宿主读取同一 SQLite 的审核后投影。

MCP Reference Memory 的实体、观察和关系 JSONL 结构通过独立编写的 Python 适配器兼容：memory_merge/memory_exchange.py。未复制上游服务器代码。导入实体保持待审，原关系标签保存在正文中，图边使用非破坏性 related。

Mem0 用于比较提炼、持久化和召回的分层；Graphiti 用于比较带来源的情节记忆和关系时间语义。没有复制其代码、提示词或性能数据，也没有宣称 Memora 实现 Graphiti 的双时间图数据库。现阶段继续使用原系统的修订、valid_until 和来源机制。

## 扩展边界

chat_models.py 的 stream/models/control 是模型适配接口；agent.py 负责角色装配；local_sources.py 负责本机资料格式。Reranker、多模态、主动工具执行和通用 MCP 客户端编排是架构图标出的扩展位置，不是当前已实现功能。Tauri 仅比较方案，实际发布 Electron。

## 全部项目链接与方案清单

'''+table+'\n\n完整传递依赖链接与许可记录见 [DEPENDENCIES.md](DEPENDENCIES.md)。\n','utf-8')
    notices='''Memora 1.0.0
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
'''
    notices+='\nCopied UI changes: explicit body-line wiki links, refreshed graph counts, personal-scale visual defaults, and initialized scene background for readable labels.\n'
    (ROOT/'NOTICE').write_text(notices,'utf-8')
    (ROOT/'THIRD_PARTY_NOTICES.md').write_text('# Third-party notices / 第三方声明\n\n'+notices+'\n\n'+table+'\n\nInherited full license texts: [graph notices](frontend/vendor/original-dev/THIRD_PARTY_NOTICES.md), [MIT core](LICENSES/Memory-Merge-MIT.txt). Electron binaries also include LICENSE.electron.txt and LICENSES.chromium.html. Frozen Python dependencies include THIRD_PARTY_LICENSES.txt. See [dependency inventory](docs/DEPENDENCIES.md).\n','utf-8')
    (ROOT/'LICENSE-STATUS.md').write_text('# Licensing\n\nMemora 1.0.0 new code: Apache-2.0. Inherited Memory Merge, copied graph sources and third-party dependencies retain their original licenses. See [LICENSE](LICENSE), [NOTICE](NOTICE), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [dependency inventory](docs/DEPENDENCIES.md).\n','utf-8')
    notes='''# memora 1.0.0

首个记忆体框架版本 / First memory entity framework release.

- Web + Electron，双 3D 脑图 / dual 3D views.
- 多模型角色装配 / Generator, Embedding, Judge, Router, Curator.
- 本机智能体对话与能力资料采集 / agent histories and capability catalogs.
- 内置 MCP、知识库、Markdown 镜像、SQLite 运维 / built-in MCP and retained memory core.
- 多版本 Markdown：用户 / 智能体 / 共用版本，草稿发布与 MCP 交换 / audience-specific document history and draft exchange.
- 修复脑图标签、鼠标与键盘导航、视角、搜索、详情和连线 / repaired labels, navigation, camera, search and related-node details.
- Apache-2.0 新代码；继承组件保留原许可 / preserved upstream licensing.

源码包、Windows x64 桌面包、SHA256SUMS、脱敏与验证报告将作为附件发布。真实模型需要用户配置服务或 GGUF 文件；没有捆绑模型或私人记忆。

Source package, Windows x64 desktop package, checksums and validation/privacy reports accompany this release. Models require operator configuration; no personal memories or model weights are included.

## 所有引用项目、仓库、项目链接和方案 / All projects, repositories, links and approaches

'''+table+'\n\n完整传递依赖 / Complete transitive dependency inventory: [docs/DEPENDENCIES.md](https://github.com/Stark-work-1001/memora/blob/main/docs/DEPENDENCIES.md).\n'
    for path in ('RELEASE_NOTES.en.md','RELEASE_NOTES.zh-CN.md'):(ROOT/path).write_text(notes,'utf-8')
    changelog=ROOT/'CHANGELOG.md'
    s=changelog.read_text('utf-8')
    if '## 1.0.0' not in s:s='# Changelog\n\n## 1.0.0 — 2026-10-15\n\nMemora memory entity: model assembly, chat, dual 3D graph views, local agent sources, MCP delegation, preserved knowledge/Markdown/database core, Apache-2.0 distribution.\n\n'+s
    changelog.write_text(s,'utf-8')
    print('Wrote bilingual README, complete upstream links, notices and release notes.')


if __name__=='__main__':
    from write_iteration_docs import main as current_main
    current_main()
