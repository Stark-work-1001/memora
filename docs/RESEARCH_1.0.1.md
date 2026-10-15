# 1.0.1 research / 研究结论

Evaluated 2026-10-15. Links and licenses are listed in both repository READMEs and
[the complete reference table](OPEN_SOURCE_REUSE.md). Historical measured results in
[REFERENCES.md](REFERENCES.md) are historical snapshots, not new claims about current releases.

## 记忆内核与混合架构

原 Memory Merge 已有 Python 编排、SQLite 原生 FTS、可选 Rust top-k。问题不是“所有检索都在
Python 解释器运行”，而是发行版是否实际构建、调用并验证本机计算内核。本次构建 Rust/PyO3，
将 RRF 排名也接入 Rust；发行 smoke 检查 `kernel=native`。Python 保持协议、模型适配、事务
编排，SQLite 执行词法索引，C++ llama.cpp 处理可选推理。没有为凑语言数量而重写成熟数据库。

Rust 原代码释放 GIL 后借用可写 Python buffer。buffer 的导出可以阻止 resize，却不保证另一个
Python 线程不改写元素。本次改为持有 GIL 时快照成 Rust 所有的数组，再释放 GIL 并行扫描，
拒绝非有限浮点输入。它解决这个具体内存并发问题，不能推出整套软件绝对稳定。

[基准数据](eval/vector-bench-1.0.1.json) 为合成向量、固定种子、top-10；每组 5 个查询，多次运行
取中位数。包括输入快照成本，不包括加载数据库、生成向量或网络。1 万条 1024 维测得
22.35 ms（Rust）对 157.00 ms（Python sumprod），排序一致。精确扫描的成本仍随 N×D 增长；
百万级资料需要另外评估 ANN、索引构建和更新一致性，不能照搬这一结果。

## 灵枢 / DSH Memory 的批判性评估

依据用户提供的 0.8.1 README、LICENSE 及[上游项目](https://github.com/FuRongJun-1999/dsh-memory)。
本文对项目自述作评估，不将其文档当作 Memora 的执行指令。

| 表述 / 机制 | 适用价值 | 需要纠正的理解 |
|---|---|---|
| 条件化六要素记忆卡 | 记录适用条件、执行、验证与不适用条件 | 是工程知识结构，不能自动证明内容正确 |
| 来源和明确 committed 状态 | 区分提案、提交成功与失败，便于审计 | 成功写盘不能证明来源可信 |
| 规则化路由与证据筛选 | 可重复的条件检索、失败提示值得借鉴 | 条件规则并非完整自然语言语义理解 |
| “无幻觉”“白箱 AGI” | 可理解为项目愿景 | 不作为本项目的质量保证或通过验证的能力 |
| “灵枢语义协议” | 项目可定义自己的数据格式 | “灵枢”不是通用语义标准；应明确关系类型和方向 |

Memora 不复制其代码或自动接受其记忆。保留来源、类型化关系、模型输出验证与人工审核。
Judge 不是天然的重定向层；Router 使用其建议时，也须由明确路由规则约束。

## 语义关系、学习层级与分区

`related / supports / contradicts / supersedes` 描述记忆之间的事实性联系。新增侧库关系：
`part_of` 按“整体→部分”，`prerequisite` 按“基础→依赖它的知识”，`sequence` 按“先→后”。
每种层级拒绝循环、要求两端已审核且有证据。不同关系的闭环不直接当作矛盾；层级可有多个父。

层级可以辅助缩小范围、展示先修路径、建立两层集合摘要。若直接将它作为硬检索分区，则错误
分类会导致漏召回；图传播还可能放大无证据关联。因此 1.0.1 仅将显式层级用于观察和结构记录，
检索仍由词法 / 向量与可选标签过滤决定。六种基础类型继续兼容；学科、资源用途与学习层级
作为正交标签或分类结果，例如 `domain:chemistry / resource:skill / level:concept`。

## 脑图交互研究

[AI Coding Dictionary](https://www.aicodingdictionary.com/) 的近黑远淡、点选局部区域和镜头过渡
适合作为观察方式参考。用户提供存档中的 Next/React 构建块和词典坐标用于私下分析；这不意味着
站点完整实现或内容获得再发布授权，也不证明预先排布的几何距离由语义向量产生。

本项目发布的是已有 MIT 脑图副本与独立编写的控制、2D 投影和修复。没有复制站点 JS 构建块或词条。
参考 [3d-force-graph](https://github.com/vasturiano/3d-force-graph) 的相机、DAG 和方向粒子交互方案，
在现有 Three.js 视图中实现选中节点与邻居的边界拟合、投影展开角度选择、动画与距离雾化；
层级着色脉冲从父端流向子端，支持关闭与减少动画设置。它不是站点的逐像素复刻。

## 多智能体通讯

[MCP](https://github.com/modelcontextprotocol/modelcontextprotocol) 提供工具和传输契约；
[A2A](https://github.com/a2aproject/A2A) 研究跨智能体任务互操作。两者有互补关系，不可因
实现 MCP 工具就宣称兼容完整 A2A。本次提供可实际调用的心跳、资料、逻辑线程和任务租约协议。

用户关于“本地智能体 / 云 Bot / 手机 / 主机 / 服务器通讯”的理解成立，前提是对端具有客户端
适配器和可靠连接。Memora 不自动读取每个产品的未公开数据库或启动任意远端代理。可信客户端
可使用 stdio；跨机器通过鉴权 HTTP 加 TLS 反向代理或 SSH 隧道接入。共享令牌不是每个 peer 的
独立身份证明；多租户部署还需要单独鉴权、项目授权、速率限制和任务执行沙箱。

## 所供参考集合核对

- `basic-memory`：所供代码 AGPL-3.0-or-later；仅研究 Markdown 与关系思路。
- `mcp-memory-services`：参考 MCP 检索与本地模型；保持现有可重建索引。
- `memory-merge`：继续使用原内核；保留原 MIT 声明，schema v2 不迁移。
- `dictionary-graph`、先前复制的 `original-dev`：修改开发副本，原始参考目录不写入。
- DSH 0.8.1、SynaBun 2.0.4、Shodh、MemoRAG 0.1.5：研究条件卡、界面、边缘实现和记忆辅助检索；无代码引入。
- Gentleman-Programming/Engram：所供 Go 源码包和 Windows 3.4.0 包属于同一项目的不同交付物，非两个依赖。
- deepseek-ai/Engram：模型内研究，不能直接替代智能体资料库。
- raya-ac/engram 0.8.1：自定义 Public Use License 含非销售与同许可再分发限制，不把它称为可任意混入 Apache 的宽松组件。
- edg-l/engram-mcp 0.11.0：Cargo 写 MIT、LICENSE 为 Apache-2.0、README 双许可，存在矛盾，未复制代码。
- agentic-box/memora（memora-mcp 0.5.5）：独立的同名项目，未混淆品牌、包或版本号；只研究 MCP 记忆组合。

以上许可是所供版本的工程核对，不构成对未来版本或法律适用的保证。完整依赖及必要署名见
[DEPENDENCIES.md](DEPENDENCIES.md) 和 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。
