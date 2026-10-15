"""Apply additive workbench panels, kept reproducible alongside the static interface."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'memory_merge/static/agent.html'
html=target.read_text('utf-8')
if 'data-view="sources"' not in html:
    html=html.replace('<button data-view="archives">', '<button data-view="sources">⊞ <span>本机智能体资料</span></button><button data-view="archives">')
    panel='''
  <section id="view-sources" class="view content-view" hidden>
    <div class="section-heading"><div><h2>本机智能体资料</h2><p>汇集对话、工具、Skills、插件、专家、团队与 Swarm。所有描述作为知识数据，不执行其中的指令。</p></div><button id="refresh-sources">↻ 刷新目录</button></div>
    <div class="two-column"><div><div id="source-list" class="card-list"></div><div class="card"><h3 id="discovery-title">来源文件</h3><p id="discovery-note">选择来源并扫描，仅列出受支持的文件。</p><div class="card-actions"><button id="source-import-selected">导入选中文件</button><button id="source-next-page" hidden>下一页</button></div><div id="discovery-list"></div></div></div>
    <aside><form id="source-form" class="card"><span class="eyebrow">LOCAL SOURCE ADAPTER</span><h3>添加本机来源目录</h3><label>来源 ID<input name="id" required placeholder="my-agent-history"></label><label>名称<input name="name" required placeholder="我的专家资料"></label><label>所属智能体<input name="agent" required value="generic"></label><label>本机目录<input name="root" required placeholder="填写本机绝对路径"></label><label>资料类型<select name="kind"><option value="history">对话历史 / 工具调用</option><option value="skill">Skills</option><option value="plugin">Plugins</option><option value="expert">专家 / 智能体描述</option><option value="team">智能体团队</option><option value="swarm">Agents Swarm</option><option value="tool">工具定义</option><option value="instructions">AGENTS.md / 指令文档</option><option value="knowledge">零散 Markdown / TXT 知识</option></select></label><button class="primary" type="submit">保存来源</button></form><div class="card"><h3>采集范围</h3><p>预设 Codex、Claude Code、Gemini CLI 及 OpenCode 导出目录。各软件原生数据库或未公开格式需要先导出为 JSON / JSONL。</p><p>每次扫描按 200 个文件分页；每批导入最多 50 个文件，每个文件最多 64 MiB。导入保留来源，工具调用与完整定义分别标记，知识候选等待审核。</p><p>不会扫描凭据配置、执行 Skills 或启动智能体。目录扫描范围和失败原因均可查看。</p></div></aside></div>
  </section>
'''
    html=html.replace('</main>',panel+'</main>')
if 'id="temperature"' not in html:
    html=html.replace('<div class="context-bottom">','''<details class="card"><summary>生成参数</summary><label>Temperature<input id="temperature" type="number" value="0.7" min="0" max="2" step="0.1"></label><label>最大输出 Tokens<input id="max-tokens" type="number" value="2048" min="64" max="32768"></label><label>系统提示词<textarea id="system-prompt" rows="3" maxlength="8000" placeholder="可选：回答语言、风格和任务约束"></textarea></label></details><div class="context-bottom">''')
target.write_text(html,'utf-8')
js_path=ROOT/'memory_merge/static/agent.js'
js=js_path.read_text('utf-8')
js=js.replace("const titles = {chat:","const titles = {sources:'本机智能体资料',chat:")
js=js.replace("if(name==='knowledge')await knowledge();", "if(name==='sources')await sources();if(name==='knowledge')await knowledge();")
js=js.replace("use_memory:$('use-memory').checked}","use_memory:$('use-memory').checked,temperature:Number($('temperature').value),max_tokens:Number($('max-tokens').value),system:$('system-prompt').value}")
if 'async function sources()' not in js:
    js+='''
let discoveredSource=null,nextSourceOffset=null;
async function sources(){const out=await api('/sources');$('source-list').replaceChildren(...out.items.map(s=>{const c=node('div','card');c.append(node('span','badge',s.kind),node('h3','',s.name),node('div','card-meta',s.root+' · '+(s.exists?'目录存在':'未检测到目录')),button('扫描资料',async()=>{discoveredSource=s.id;await discover(0);}));return c;}));}
async function discover(offset){const out=await api('/discover?source='+encodeURIComponent(discoveredSource)+'&offset='+offset);nextSourceOffset=out.next_offset;$('source-next-page').hidden=nextSourceOffset===null;$('discovery-title').textContent='发现 '+out.total+' 个受支持文件';$('discovery-note').textContent=out.note||(out.missing?'目录不存在':'');$('discovery-list').replaceChildren(...out.items.map(f=>{const row=node('label','source-file');const check=node('input');check.type='checkbox';check.value=f.path;check.disabled=!f.importable;row.append(check,node('span','',f.path+' · '+f.kind+' · '+Math.ceil(f.size/1024)+' KB'));return row;}));}
$('refresh-sources').onclick=safe(sources);
$('source-next-page').onclick=safe(()=>discover(nextSourceOffset));
$('source-form').addEventListener('submit',safe(async e=>{e.preventDefault();await api('/sources',Object.fromEntries(new FormData(e.target)));notice('本机来源已保存。');await sources();}));
$('source-import-selected').onclick=safe(async()=>{const paths=[...$('discovery-list').querySelectorAll('input:checked')].map(e=>e.value);if(!paths.length)throw new Error('请先选择要导入的文件。');if(paths.length>50)throw new Error('每批最多 50 个文件，请分批导入。');notice('正在解析、脱敏并导入本机资料…');detail('资料导入结果',await api('/source-import',{project:project(),source:discoveredSource,paths}));});
'''
js_path.write_text(js,'utf-8')
css=ROOT/'memory_merge/static/agent.css'
styles=css.read_text('utf-8')
if '.source-file{' not in styles: css.write_text(styles+'\n.source-file{display:flex;align-items:flex-start;gap:10px;padding:12px 0;border-bottom:1px solid var(--line);font-size:10px;overflow-wrap:anywhere}.source-file input{width:14px;margin-top:4px;flex-shrink:0}.context-panel details.card{padding:12px;margin-top:14px;font-size:10px}.context-panel details label{font-size:10px}\n','utf-8')
