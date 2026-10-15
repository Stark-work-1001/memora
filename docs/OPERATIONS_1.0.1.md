# 1.0.1 operations and protocol / 操作与协议

## 数据与兼容

| 内容 | 保存位置（相对于自用数据目录） | 恢复与维护 |
|---|---|---|
| 原记忆、审核、向量、会话 | memory.sqlite3 | 原 CLI backup / restore；FTS 与镜像可重建 |
| Markdown 不可变原文与版本元信息 | memora-documents.sqlite3 | 版本数据库备份；documents/ 镜像可 repair |
| 智能体资料、层级、任务、工作流记录 | memora-control.sqlite3 | 控制侧库在线校验备份 |
| 模型、分工、来源配置 | agent-models.json / agent-assembly.json / agent-sources.json | 私下备份，不公开；密钥仍来自进程环境变量 |
| 人类可读文件 | markdown/ 与 documents/ | 属于派生镜像；不要直接以它们替换数据库 |
| 模型权重、插件实际安装 | 用户自己选择的目录 | 独立维护，不包含在项目发行包 |

工作空间是项目作用域，不是复制一份环境或建立安全租户。`:user` 是原系统跨项目用户偏好作用域。
组织 / Ghost / Subagent 记录是资料和责任描述；不会因为录入一个名字而创建实际执行进程。

完整备份：先停止对话与工作流、暂停对端提交，然后在“存储与维护”创建校验备份，保存三份
结果和配置文件。每个库的 SQLite backup 独立一致；跨库不是一个全局原子快照，故应在静止时备份。

恢复到**新目录**：使用原 CLI `restore <memory-backup> <new-data-dir>` 恢复 memory.sqlite3，
在所有 Memora 进程停止后，将同一静止备份批次的文档库与控制库分别复制到新目录中的标准库名。
不要复制旧 WAL/SHM；运行 `PRAGMA integrity_check`，恢复自己的配置，再启动并执行文档镜像 repair。
原 CLI restore 不会自动恢复新增侧库；仅恢复一份库可能丢失跨库引用，需按此完整流程操作。

1.0.0 原存储可直接打开；新侧库和文档 revision_metadata 表采用增加式创建。回退旧程序时保留
新侧库以待以后升级，避免让旧版覆盖发布目录或删除不认识的文件。

## Markdown 与模型工作流

日期字段为 `recorded_date`，与版本创建时间 `created` 分开。新导入从日期式文件名 / front matter
推断，推断不出留空；每个新版本继承原日期，可由用户明确更正。来源和项目大标题也属于版本元信息。
草稿不会被 MCP 文档读取工具返回，用户发布后才可读取。用途 audience 是呈现用途，不是访问权限。

建议步骤：分类 → Judge 质量建议 → Markdown 重构或两层项目摘要 → 核验。Embedding 先提供相关
已审核证据；没有向量模型时明确退回词法。每一步绑定具体生成模型。关系提案保存为建议，不自动
写入正式图；用户将有证据的端点 ID 填入关系表单。SQL 分析仅接收固定参数化的分类 / 状态计数，
不会执行模型生成的 SQL。单文档原文 30,000 字符上限；长文先分日期 / 章节拆分，原始版本仍完整保存。

模型分工配置是职责绑定；工作流自己明确选择的模型才是每步执行者。Embedding 端点需支持
`/v1/embeddings`；Ollama 自动补 `/v1`。Chat/Judge/Router 使用各自模型协议，不应给生成任务选择
只有向量接口的模型。切换 embedding 模型后重新索引，旧指纹向量不会被混用。

当前外部调度确认保持用户已声明的线性依赖顺序，不能擅自加入步骤、模型或命令。此约束方便小
模型可靠协作；复杂 DAG 和任意工具执行器仍是扩展项。工作流每个进程最多两个同时运行。停止是
协作式，远程模型完成当前请求或超时后生效。中断进程的运行记录应保留用于诊断并从原文重试，
不能把持久记录中的 running 当作仍有活跃线程。只能由启动运行的进程取消其内存任务。

## MCP 对接

启动普通 stdio MCP：

```powershell
$env:MM_DATA='./my-private-data'
$env:MM_ENABLE_DOCUMENTS='1'
$env:MM_ENABLE_COORDINATION='1'
$env:MM_ENABLE_AGENT='1'
.venv/Scripts/python -m memory_merge mcp
```

Windows standalone 可以把上述命令换成 `resources/backend/memora-backend.exe --data <data-dir> mcp`。
MCP 进程与桌面必须指向同一个自用数据目录，界面才能看到同一份心跳、任务与档案。
默认不启用 review 权限；不要给普通采集客户端配置 `MM_ENABLE_REVIEW=1`。

客户端使用顺序：

1. `memory_peer_heartbeat(project, peer, name, model, location, capabilities, ttl)`，ttl 为 30–300 秒，
   建议每 30 秒刷新。location 为 local / cloud / mobile / server。peer 身份是信任连接里的自报告。
2. `memory_session_append` 保存真实轮次；`memory_thread_update` 使用稳定逻辑 ID 关联多个会话，
   用大标题归纳为同一项目。工具调用本身不拆成独立逻辑对话。
3. `memory_resource_put` 登记资源描述。Ghost 建议字段 specialty/memory_scope/provenance；
   Organization 用 members/responsibilities/dependencies；Subagent 用 purpose/tools/workflow/reports_to。
4. `memory_task_list` → `memory_task_claim` → `memory_task_report`。租约 180 秒，running 汇报续租，
   单 peer 最多两个活跃任务；过期可重新领取。领取是数据库原子操作，重复执行仍需对端幂等。
5. 需要用户核查时报告 waiting_user 和具体 question。智能体不能自己将此状态改成完成；用户在
   工作台提交答复后任务重新排队，由客户端领取答复并继续执行。
6. 外部调度任务由该 peer 的模型确认，通过 `memory_workflow_plan` 提交每个配置 stage ID。

远程模式：设置高熵 `MM_BRIDGE_TOKEN`（至少 32 字符），启动 `bridge --port 8766`。仅监听
127.0.0.1；客户端访问 `/mcp`，HTTP 头带 `Authorization: Bearer <token>`。跨主机采用 TLS
隧道 / 反向代理并保留后端允许的 Host；不把令牌写在 URL、README、下载包或聊天归档。浏览器
Origin 请求被拒绝。令牌由用户在本机生成保管，项目不会创建 GitHub / Codex OAuth 授权。

当前是可信个人部署的共享工具权限，并非多租户 ACL。对端的机器人、移动端和服务器仍需实现
MCP 客户端；并不支持无适配器自动读取任意软件。深链接只保存已知 HTTPS 无参数地址或 Codex
线程地址；其他产品可由用户提供可验证的来源地址，不猜测其内部窗口标识。
