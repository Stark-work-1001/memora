"""Generate the standalone SVG/HTML architecture preview from one source."""
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1480" height="1220" viewBox="0 0 1480 1220" role="img" aria-labelledby="title desc">',
        '<title id="title">Memora 记忆体架构</title><desc id="desc">多智能体通过内置 MCP 与 Memora 协作；多模型编排连接记忆内核、知识库、Markdown、SQLite 和双三维脑图。</desc>',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="#90a691"/></marker></defs>',
        '<rect width="1480" height="1220" rx="20" fill="#f7f9f3"/>']
    def text(x,y,value,size=14,color='#526b56',weight='400'):
        parts.append(f'<text x="{x}" y="{y}" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="{size}" fill="{color}" font-weight="{weight}">{escape(value)}</text>')
    def box(x,y,w,h,title,lines,tint='#ffffff',dashed=False):
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{tint}" stroke="#cad8c6" stroke-width="1.2"'+(' stroke-dasharray="5 5"' if dashed else '')+'/>')
        text(x+18,y+30,title,17,'#254d3c','600')
        for i,line in enumerate(lines): text(x+18,y+55+i*23,line,12)
    def arrow(x1,y1,x2,y2): parts.append(f'<path d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="#90a691" stroke-width="1.5" marker-end="url(#arrow)"/>')
    text(46,53,'MEMORA  /  记忆体',31,'#234c3a','600')
    text(46,82,'一个统一的记忆实体：记忆管理 × 多模型协作 × 多智能体通信 × 三维可视化',15)
    text(1140,48,'ARCHITECTURE · v1.0.1',11)
    text(1140,72,'实线：已实现  /  虚线：扩展位置',11)
    box(46,111,440,104,'用户窗口 · Web / Electron',['对话工作台 · 知识与记忆 · 模型装配','会话档案 · 用户画像 · 数据维护'])
    box(510,111,440,104,'脑图 · 二维 / 三维与多布局',['Dictionary：搜索 / 局部最佳视角 / 距离雾化','Mind Map：方向流动 / Rust WASM / 2D 投影'])
    box(974,111,460,104,'其他智能体 · 已有 MCP 插件',['Codex / Claude / 其他 MCP 客户端','归档对话 · 提交记忆 · 召回知识 · 委派问答'])
    arrow(266,215,266,246);arrow(730,215,730,246);arrow(1204,215,1204,246)
    box(46,249,1388,107,'内置入口层 · HTTP + SSE / MCP stdio + 鉴权 HTTP 桥',['HTTP：本地窗口与流式任务 / 会话管理 / 知识文档 / 镜像与数据库运维',
        'MCP：原 memory_* 工具兼容；可选心跳 / 任务租约 / 逻辑会话 / 外部模型调度确认'], '#e8f0e1')
    arrow(740,356,740,391)
    text(47,386,'01  可装配的模型编排层 · Python',12,'#47674c','600')
    box(46,401,262,132,'Router · 路由模型',['读任务 → 选择许可目标模型','严格校验 JSON / 目标白名单','未启用时由用户手动指定'])
    box(328,401,262,132,'Generator · 对话模型',['流式生成 / 停止 / 参数控制','上下文预算 / 引用记忆证据','多会话归档 / 本地与云端'])
    box(610,401,262,132,'Embedding · 向量模型',['文档与查询嵌入 / 增量索引','模型指纹 / 漂移检查','本地服务 / 本地模型 / 云端'])
    box(892,401,262,132,'Judge · 判定模型',['重要性 / 类别 / 冲突建议','结构化输出 / 校准缓存','建议保持待审，不自动批准'])
    box(1174,401,260,132,'Curator / 专家模型',['从多个智能体会话提炼','知识 / 习惯 / 工具 / 教训','分类 / 文档 / SQL 分析 / 核验工作流'])
    arrow(177,533,177,573);arrow(459,533,459,573);arrow(741,533,741,573);arrow(1023,533,1023,573);arrow(1304,533,1304,573)
    text(47,568,'02  记忆内核 · 保留并扩展原 memory_merge',12,'#47674c','600')
    box(46,583,440,174,'知识与多来源采集',['文档：Markdown / TXT / PDF / 书签 / JSONL','对话 / Skills / Plugins / 专家 / Teams / Swarm','习惯：跨项目 :user 偏好 / 禁忌 / 画像','工具：步骤 / 使用经验 / 标签 / 来源','审核：pending → 用户 approve / reject'])
    box(510,583,440,174,'词法、语义与关系',['FTS5：CJK 二元分词 / BM25 / 多语言','向量：Rust 精确 top-k + RRF；Python 兼容回退','混合召回：RRF / 覆盖率 / 降级提示','关系：supports / contradicts / supersedes / related','证据：随机隔离边界 / [memory:id] 引用'])
    box(974,583,460,174,'生命周期与数据库整理',['去重 / 独立来源 / 修订 / 归档 / 遗忘','Markdown outbox：原子导出 / 修改同步','数据库：索引重建 / 整理 / 压缩 / 诊断','校验备份 / 恢复演练 / 迁移前备份','自动捕获和模型提炼保持人工审核'])
    arrow(266,757,266,796);arrow(730,757,730,796);arrow(1204,757,1204,796)
    box(46,806,440,115,'SQLite · 唯一事务真源',['memories / documents / sessions / turns','edges / embeddings / models / judgements','audit / sightings / outbox / meta'], '#e8f0e1')
    box(510,806,440,115,'Markdown 文档库 · 独立版本数据库',['memora-documents.sqlite3 / documents/<id>/…','human / agent / shared：草稿 → 发布 / 历史版本','原 markdown/*.md 镜像与审核流程保留'], '#e8f0e1')
    box(974,806,460,115,'模型与装配配置 · 本地文件',['agent-models.json / agent-assembly.json + sidecar','控制库：peers / tasks / assets / workflows','密钥用环境变量；云端发送需显式配置'], '#e8f0e1')
    text(47,958,'03  混合运行时与可扩展方向',12,'#47674c','600')
    box(46,973,320,110,'Python · 编排与记忆',['memory_merge / CLI / MCP / HTTP','适配器接口 stream / models / control'])
    box(386,973,320,110,'Rust · 检索与脑图物理',['PyO3 原生 top-k / RRF（发行包必需）','复制的 Rust → WASM 脑图布局'])
    box(726,973,320,110,'C++ · llama.cpp 推理',['GGUF → llama-cpp-python','或 llama-server 兼容 HTTP 接口'])
    box(1066,973,368,110,'扩展插槽 · 后续可增加',['Reranker / 多模态 / 工具执行器','MCP 客户端编排 / 自动整理策略'], '#f3f5ee', True)
    text(46,1128,'一次完整循环',13,'#234c3a','600')
    text(46,1155,'其他智能体 / 用户 → 采集与归档 → Curator 候选 → Judge 建议 → 人工审核 → 知识与向量索引 → 混合召回 → 引用回答 / 双 3D 脑图',13)
    text(46,1193,'原始两个脑图目录保持不变；复制副本位于 frontend/vendor/。连线代表明确记录的关系，空间距离不是已验证的语义结论。',11,'#889780')
    parts.append('</svg>')
    svg='\n'.join(parts)
    static=ROOT/'memory_merge/static'
    (static/'architecture.svg').write_text(svg,'utf-8')
    html='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Memora 记忆体 · 架构预览</title><style>body{margin:0;padding:24px;background:#eef3e8;color:#234c3a;font-family:Segoe UI,Microsoft YaHei,sans-serif}main{max-width:1480px;margin:auto}svg{width:100%;height:auto}p{font-size:13px;line-height:1.8}a{color:#286e58}</style></head><body><main>'+svg+'<p>源码位置：memory_merge/agent.py · chat_models.py · server.py · frontend/vendor/。虚线模块是扩展位置；模型推理需要接入实际服务或模型文件。</p></main></body></html>'
    (ROOT/'docs'/'Memora-Architecture.svg.html').write_text(html,'utf-8')
    (ROOT/'docs'/'Memora-Architecture.svg').write_text(svg,'utf-8')
    (static/'architecture.html').write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Memora · 架构预览</title><link rel="stylesheet" href="/agent.css"></head><body class="architecture-page"><span class="eyebrow">MEMORA / SYSTEM DESIGN</span><h1>记忆体 · 架构预览</h1><div class="architecture-links"><a href="/">← 返回工作台</a><a href="/architecture.svg" download="Memora-Architecture.svg">下载 SVG ↗</a></div><img src="/architecture.svg" alt="记忆体的模型装配、记忆内核、MCP 通信和双三维脑图架构"></body></html>','utf-8')
    print('Generated SVG and standalone SVG/HTML architecture preview.')


if __name__=='__main__': build()
