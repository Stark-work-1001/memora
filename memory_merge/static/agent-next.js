/* Memora 1.0.1 controls. All imported descriptions stay inert text. */
'use strict';
(() => {
  const kinds={chat:'对话 Chat',env:'环境 Env',skill:'技能 Skill',mcp:'连接器 MCP',plugin:'插件 Plugin',ghost:'身份容器 Ghost',organization:'组织 Organization',subagent:'子智能体 Subagent',tool:'工具 Tool',knowledge:'零散知识',processing:'处理记录'};
  const explanations={
    chat:'按来源、智能体筛选原始会话。一个项目对话可以包含多次本地与云端模型调用，在“项目对话”中合并查看。',
    env:'记录运行时、模型能力、工作目录与工具限制的描述；不要把 API 密钥或凭据配置作为环境知识导入。',
    skill:'可复用的任务方法、输入输出与适用条件。导入只保存描述，不会自动执行技能。',
    mcp:'智能体调用 Memora 的工具接口。心跳代表近期实际通讯；历史目录存在不表示连接在线。',
    plugin:'插件的来源、版本、依赖和提供的能力。工具调用样例与完整定义会分别标记。',
    ghost:'身份与专家上下文的容器：专业描述、身份来源、适用任务、记忆归属和出现过程。它是可追溯的资料，不代表模型具有独立意识。',
    organization:'组织成员、目标、职责、依赖与协调规则。可以描述敏捷团队、蜂群、公司、军队或其他组织；用任务责任和并发上限避免把工作集中给一个成员。',
    subagent:'由主智能体委派、负责有限任务的执行单元。记录任务边界、可用工具、工作流、输入输出、所属组织与负责人；常见类型有检索、研究、实现、审查和核验。',
    tool:'工具接口、参数、返回格式和实际调用示例。仅能收集来源文件中确实存在的资料，无法凭历史恢复未记录的完整工具定义。',
    knowledge:'独立文章、词条、学习笔记和资料集合。导入候选与审核后的长期记忆分别管理。',
    processing:'实际发生的资料导入、工作流步骤和任务状态变更。'
  };
  const operations={summarize:'项目→条目两层归纳',organize_markdown:'Markdown 重构',classify:'领域 / 层级分类',extract_relations:'语义与层级关系提案',analyze_records:'只读 SQL 统计分析',verify:'来源核验',assess_memory:'Judge 记忆质量建议'};
  const states={queued:'排队',running:'执行中',waiting_user:'等待用户',done:'已完成',failed:'失败',cancelled:'已取消',unknown:'未报告'};
  function card(title,text){const c=node('article','card');c.append(node('h3','',title));if(text)c.append(node('p','muted',text));return c;}
  function label(title,input){const l=node('label','',title);l.append(input);return l;}
  function field(name,placeholder=''){const i=node('input');i.name=name;i.placeholder=placeholder;return i;}
  function select(values){const s=node('select');for(const [v,t] of Object.entries(values)){const o=node('option','',t);o.value=v;s.append(o);}return s;}
  function showJSON(c,title,value){c.append(button(title,()=>detail(title,value)));}

  // Additional role selectors are editable and save through the same assembly transaction.
  const extraRoles={summarizer:'项目归纳',classifier:'领域与层级分类',documenter:'Markdown 重构',sql_analyst:'只读数据库分析',relation:'关系提案',verifier:'来源核验'};
  for(const [role,title] of Object.entries(extraRoles)){const s=node('select');s.id='role-'+role;$('assembly-form').insertBefore(label(title,s),$('assembly-form').querySelector('button'));}
  const roleHelp=card('分工说明','Embedding 把文本编码为向量；Rust 计算检索排名。Judge 按持久性、来源、重要性、矛盾与敏感性给审核建议。Router 才是选择下一模型或目标的路由层。三者可以协作，但不等同。');
  $('assembly-form').before(roleHelp);
  const originalConfiguration=configuration;
  configuration=async function(){await originalConfiguration();roleHelp.querySelectorAll('details').forEach(x=>x.remove());for(const [key,r] of Object.entries(state.config.roles)){const d=node('details');d.append(node('summary','',r.title+' · '+key),node('p','',r.description));roleHelp.append(d);}await peerSummary();};

  // Local/cloud choice comes before protocol-specific connection fields.
  function connectionFields(reset=false){const cloud=$('model-location').value==='cloud';if(cloud&&$('model-kind').value==='gguf')$('model-kind').value='openai';
    const kind=$('model-kind').value,gguf=kind==='gguf';$('model-remote').checked=cloud;$('model-remote').disabled=true;
    for(const key of ['base','key_env'])$('model-'+key).closest('label').hidden=gguf||(!cloud&&key==='key_env');
    for(const key of ['path','n_ctx','gpu_layers'])$('model-'+key).closest('label').hidden=!gguf;
    $('model-base').placeholder=cloud?'https://provider.example/v1':kind==='ollama'?'http://127.0.0.1:11434':'http://127.0.0.1:1234/v1';
    if(reset)$('model-base').value=cloud?'':kind==='ollama'?'http://127.0.0.1:11434':gguf?'':'http://127.0.0.1:1234/v1';
    $('model-base').required=!gguf;$('model-path').required=gguf;
  }
  const originalEdit=editModel;editModel=function(p={}){originalEdit(p);$('model-location').value=p.remote?'cloud':'local';connectionFields();};
  $('model-location').onchange=()=>{if($('model-location').value==='cloud')$('model-kind').value='openai';connectionFields(true);};$('model-kind').onchange=()=>connectionFields(true);connectionFields();

  async function peerSummary(){const out=await api(scoped('/peers'));const host=$('peer-summary');host.replaceChildren(node('h3','','智能体通讯状态'));
    const live=out.items.filter(x=>x.connected);host.append(node('p','',live.length?`${live.length} 个智能体近期在线`:'尚无有效心跳；可在资料 → MCP 配置连接。'));
    for(const p of out.items)host.append(node('p',p.connected?'peer-live':'muted',`${p.connected?'●':'○'} ${p.name} · ${p.model||'模型未报告'} · ${p.location} · ${p.last_seen_age_seconds}s 前`));
    host.append(node('small','muted','身份由已授权客户端报告；连接状态根据心跳有效期计算。'));
  }
  const timer=setInterval(()=>{if(!document.hidden)safe(peerSummary)();},15000);window.addEventListener('pagehide',()=>clearInterval(timer));

  // Consolidate archives, source discovery and capability catalogs under one sidebar entry.
  const sourceView=$('view-sources'),sourceColumns=sourceView.querySelector('.two-column');
  const resourceTabs=node('div','tabs resource-tabs');const intro=node('p','resource-description');
  const resourceFilter=field('agent','筛选智能体名称…');resourceFilter.setAttribute('aria-label','资料所属智能体');
  const catalog=node('div','card-list');const archiveView=$('view-archives');archiveView.hidden=false;archiveView.classList.remove('view','content-view');archiveView.classList.add('archive-subview');
  sourceView.insertBefore(resourceTabs,sourceColumns);sourceView.insertBefore(intro,sourceColumns);sourceView.insertBefore(resourceFilter,sourceColumns);sourceView.insertBefore(catalog,sourceColumns);sourceView.insertBefore(archiveView,sourceColumns);
  const scanDetails=node('details','card');scanDetails.append(node('summary','','本机来源扫描与导入'));sourceColumns.before(scanDetails);scanDetails.append(sourceColumns);
  // Move the existing MCP example beside the live resource status.
  const mcpDetails=$('mcp-example').closest('details');const mcpIntro=mcpDetails.querySelector('p');mcpIntro.textContent='启用 MM_ENABLE_COORDINATION=1 后提供心跳、逻辑会话、资料目录和任务租约工具。外部智能体需主动调用；本界面不会把扫描结果伪装为在线连接。跨主机可使用带 Bearer 令牌的 Streamable HTTP 桥接，再通过 TLS 隧道接入。';
  sourceView.append(mcpDetails);
  const resourceForm=node('form','card');resourceForm.append(node('h3','','新增 / 更新资料描述'));
  const rf={kind:select(Object.fromEntries(Object.entries(kinds).filter(([k])=>!['chat','processing'].includes(k)))),id:field('id','可选：更新时填写资源 ID'),title:field('title','标题'),agent:field('agent','所属智能体'),description:node('textarea'),payload:node('textarea')};
  rf.description.rows=4;rf.payload.rows=6;rf.payload.value='{}';rf.title.required=true;rf.agent.value='generic';
  for(const [k,t] of Object.entries({kind:'类型',id:'资源 ID',title:'标题',agent:'智能体',description:'描述 / 职责 / 任务边界',payload:'结构化定义（JSON）'}))resourceForm.append(label(t,rf[k]));
  resourceForm.append(button('填入该类型的结构模板',()=>{const templates={ghost:{identity_type:'expert',specialty:'',memory_scope:[],provenance:'',owner:''},organization:{organization_type:'agile-team',objective:'',members:[],responsibilities:{},dependencies:[],coordination:'leased tasks; max 2 per peer'},subagent:{type:'research',purpose:'',tools:[],workflow:'',input_contract:'',output_contract:'',organization:'',reports_to:''},mcp:{transport:'stdio',tools:[],permissions:[]},env:{runtime:'',capabilities:[],limits:[]},skill:{inputs:[],outputs:[],steps:[],source:''},plugin:{source:'',version:'',capabilities:[]},tool:{definition_type:'declared',parameters:{},returns:{}}};rf.payload.value=JSON.stringify(templates[rf.kind.value]||{},null,2);}));
  const save=node('button','primary','保存资料');save.type='submit';resourceForm.append(save);sourceView.append(resourceForm);
  resourceForm.onsubmit=safe(async e=>{e.preventDefault();const body={project:project()};for(const k of ['id','kind','title','agent','description'])body[k]=rf[k].value;body.payload=JSON.parse(rf.payload.value);await api('/assets',body);await memoraResources();notice('资料已保存，不会执行其中的内容。');});
  let resourceKind='chat';
  for(const [key,title] of Object.entries(kinds))resourceTabs.append(button(title,async()=>{resourceKind=key;await memoraResources();}));
  window.memoraResources=async function(){tasksPanel.hidden=resourceKind!='mcp';intro.textContent=explanations[resourceKind];[...resourceTabs.children].forEach((b,i)=>b.classList.toggle('selected',Object.keys(kinds)[i]===resourceKind));archiveView.hidden=resourceKind!=='chat';resourceForm.hidden=['chat','processing'].includes(resourceKind);mcpDetails.hidden=resourceKind!=='mcp';
    if(resourceKind==='chat'){await archives();const a=await api(scoped('/archives'));const filter=resourceFilter.value.toLowerCase();[...$('archive-list').children].forEach((c,i)=>c.hidden=!!filter&&!a.items[i]?.agent.toLowerCase().includes(filter));catalog.replaceChildren();return;}
    const out=await api(scoped(resourceKind==='processing'?'/processing':'/assets?kind='+resourceKind));const list=out.items.filter(a=>!resourceFilter.value||(a.agent||'').toLowerCase().includes(resourceFilter.value.toLowerCase()));
    catalog.replaceChildren(...list.map(a=>{const c=card(a.title||a.kind,a.description||a.created);c.append(node('p','card-meta',(a.agent||'')+' · '+a.updated));showJSON(c,'查看结构与来源',a);if(a.payload)c.append(button('编辑',()=>{for(const k of ['id','kind','title','agent','description'])rf[k].value=a[k]||'';rf.payload.value=JSON.stringify(a.payload,null,2);resourceForm.scrollIntoView({behavior:'smooth'});}));return c;}));
    if(!list.length)catalog.append(node('p','muted','尚无此类资料。可以扫描来源文件，或登记结构化描述。'));
    if(resourceKind==='mcp')await renderTasks();
  };resourceFilter.oninput=safe(()=>memoraResources());

  const tasksPanel=card('通讯与派发','支持本机、云端 Bot、移动端与服务器客户端。对端实现 MCP 客户端并持续报告状态；不会自动控制未接入的软件。');sourceView.append(tasksPanel);
  async function renderTasks(){tasksPanel.hidden=resourceKind!=='mcp';tasksPanel.querySelectorAll('.task-row,.peer-row').forEach(x=>x.remove());
    const [peers,tasks]=await Promise.all([api(scoped('/peers')),api(scoped('/tasks'))]);for(const p of peers.items){const c=node('div','peer-row');c.append(node('p','',`${p.connected?'● 在线':'○ 心跳过期'} ${p.name} / ${p.model||'未报告模型'} / ${p.location}`));showJSON(c,'能力与连接详情',p);tasksPanel.append(c);}
    for(const t of tasks.items){const c=node('div','task-row');c.append(node('h4','',t.title+' · '+(t.lease_expired?'租约已过期，可重新领取':states[t.status])),node('p','muted',`${t.owner||t.assigned||'待领取'} · ${t.progress??'未知'}%`));showJSON(c,'任务输入与结果',t);if(t.needs_user){const response=field('response',t.question);c.append(node('p','',t.question),response,button('提交用户答复',async()=>{await api('/task-response',{project:project(),id:t.id,response:response.value});await renderTasks();}));}tasksPanel.append(c);}
  }
  tasksPanel.append(button('刷新连接与任务',renderTasks));const taskTitle=field('title','派发任务标题'),taskPeer=field('peer','目标 peer ID，留空可由成员领取'),taskThread=field('thread','关联逻辑条目 ID / 会话 ID，可选'),taskPayload=node('textarea');taskPayload.value='{}';tasksPanel.append(taskTitle,taskPeer,taskThread,taskPayload,button('创建待领取任务',async()=>{await api('/tasks',{project:project(),title:taskTitle.value,assigned:taskPeer.value,thread:taskThread.value,payload:JSON.parse(taskPayload.value)});await renderTasks();}));tasksPanel.hidden=true;

  // Logical conversations, rather than one entry per model invocation.
  titles.threads='项目对话';const threadView=node('section','view content-view');threadView.id='view-threads';threadView.hidden=true;document.querySelector('main').append(threadView);
  threadView.append(node('h2','','按项目大标题组织的完整对话'),node('p','muted','一个条目可以关联多个智能体、多个模型和多个会话；时间与执行状态来自真实档案或客户端报告，未报告的进度显示为未知。'));
  const threadSearch=field('query','搜索项目或对话标题'),threadAgent=field('agent','筛选智能体'),threadState=select({'':'所有状态',...states}),threadList=node('div','card-list');threadView.append(threadSearch,threadAgent,threadState,button('刷新',()=>memoraThreads()),threadList);
  window.memoraThreads=async function(){const out=await api(scoped('/threads'));threadList.replaceChildren();const groups=new Map();for(const t of out.items){if(threadSearch.value&&!(t.title+' '+t.group_title).toLowerCase().includes(threadSearch.value.toLowerCase()))continue;if(threadAgent.value&&!t.agents.some(a=>a.includes(threadAgent.value)))continue;if(threadState.value&&t.status!==threadState.value)continue;if(!groups.has(t.group_title))groups.set(t.group_title,[]);groups.get(t.group_title).push(t);}
    for(const [title,items] of groups){const group=node('section','thread-group');group.append(node('h3','',title));for(const t of items){const c=card(t.title);c.append(node('p','card-meta',`${t.started||t.updated} · ${t.agents.join(', ')||'智能体未报告'} · ${states[t.status]} · 进度 ${t.progress==null?'未知':t.progress+'%'}`));if(t.needs_user)c.append(node('p','needs-user','需要用户干预：'+(t.question||'请到原智能体查看待办')));for(const sid of t.sessions)c.append(button('查看会话 '+sid.slice(0,8),async()=>{state.archive=sid;await view('sources');resourceKind='chat';await memoraResources();const a=await api(scoped('/archive?id='+encodeURIComponent(sid)));$('archive-title').textContent=a.title||sid;$('archive-turns').replaceChildren(...a.turns.map(v=>card(v.role,v.content)));}));if(t.origin){const a=node('a','origin-link','打开原智能体位置 ↗');a.href=t.origin;a.target='_blank';a.rel='noopener noreferrer';c.append(a);}for(const task of t.tasks||[]){if(task.status==='waiting_user'){const answer=field('response',task.question);c.append(answer,button('答复：'+task.title,async()=>{await api('/task-response',{project:project(),id:task.id,response:answer.value});await memoraThreads();}));}}showJSON(c,'状态与成员详情',t);group.append(c);}threadList.append(group);}
    if(!groups.size)threadList.append(node('p','muted','没有匹配的项目对话。导入会话或由 MCP 客户端登记。'));
  };
  for(const input of [threadSearch,threadAgent,threadState])input.onchange=safe(()=>memoraThreads());
  const merge=card('登记 / 合并逻辑对话','填写稳定的逻辑 ID 与成员会话 ID。切换模型不会生成新的逻辑条目。客户端也可以调用 memory_thread_update。');const mf={logical_id:field('logical_id','逻辑 ID'),title:field('title','对话标题'),group_title:field('group_title','项目大标题'),sessions:field('sessions','成员会话完整 ID，逗号分隔'),status:select(states),origin:field('origin','可选 HTTPS 或 codex://threads/…'),question:field('question','待用户处理的问题')};for(const [k,i] of Object.entries(mf))merge.append(label(k,i));merge.append(button('保存逻辑条目',async()=>{const b={project:project()};for(const [k,i] of Object.entries(mf))b[k]=i.value;b.sessions=b.sessions.split(',').map(x=>x.trim()).filter(Boolean);await api('/threads',b);await memoraThreads();}));threadView.append(merge);

  // Model assembly is a concrete editable sequence, optionally dispatched by a connected peer's model.
  const workflowPanel=card('可编辑模型工作流','每一步指定任务和模型。选择外部调度智能体时，其模型需通过 MCP 领取并确认计划；本机按已配置依赖执行，逐步保留结果与模型身份。');$('view-models').append(workflowPanel);
  const wfTitle=field('title','工作流标题'),wfId=field('id','可选：更新已有工作流 ID'),wfDispatcher=field('dispatcher','调度 peer ID；留空为用户直接执行'),stages=node('div','workflow-stages'),workflowList=node('div','card-list');workflowPanel.append(wfTitle,wfId,wfDispatcher,stages);
  function addStage(value={}){const row=node('div','workflow-stage');const op=select(operations),model=node('select'),instruction=field('instruction','此步骤的具体要求');options(model,state.config?.models||[]);op.value=value.operation||'organize_markdown';model.value=value.model||model.value;instruction.value=value.instruction||'';row.append(label('处理任务',op),label('执行模型',model),label('要求',instruction),button('移除',()=>row.remove()));row.read=()=>({operation:op.value,model:model.value,instruction:instruction.value});stages.append(row);}
  workflowPanel.append(button('＋ 添加步骤',()=>addStage()),button('保存工作流',async()=>{const out=await api('/workflows',{project:project(),id:wfId.value,title:wfTitle.value,dispatcher:wfDispatcher.value,steps:[...stages.children].map(x=>x.read())});wfId.value=out.id;await memoraWorkflows();notice('工作流已保存。到 Markdown 文档库选择原文并执行。');}));workflowPanel.append(workflowList);
  window.memoraWorkflows=async function(){const out=await api(scoped('/workflows'));workflowList.replaceChildren(...out.items.map(w=>{const c=card(w.title,w.steps.map(s=>`${operations[s.operation]} → ${s.model}`).join('；'));c.append(node('p','muted','调度：'+(w.dispatcher||'用户直接执行')),button('编辑',()=>{wfTitle.value=w.title;wfId.value=w.id;wfDispatcher.value=w.dispatcher;stages.replaceChildren();w.steps.forEach(addStage);}));return c;}));if(!stages.children.length&&state.config?.models.length)addStage();};
  const docFlows=card('按日期重构与归纳','原始日期独立于修改时间保存。工作流读取一个固定版本；结果是新草稿，用户发布后才提供给其他智能体。向量索引在知识与记忆页构建；分类、重构与核验模型可组合。');const flowSelect=node('select'),runs=node('div','card-list');docFlows.append(flowSelect,button('对当前文档运行工作流',async()=>{if(!workspaceRevision)throw new Error('请先保存或打开一份文档。');detail('工作流已提交',await api('/workflow-start',{project:project(),workflow:flowSelect.value,slug:workspaceRevision.slug,audience:workspaceRevision.audience,version:workspaceRevision.version}));await memoraDocumentFlows();}),button('刷新执行记录',()=>memoraDocumentFlows()),runs);$('view-markdown').append(docFlows);
  window.memoraDocumentFlows=async function(){const [w,r]=await Promise.all([api(scoped('/workflows')),api(scoped('/workflow-runs'))]);options(flowSelect,w.items.map(x=>({id:x.id,name:x.title})));runs.replaceChildren(...r.items.map(x=>{const c=card((x.input.slug||'文档')+' · '+(states[x.status]||x.status),x.updated);c.append(node('p','muted',`源 v${x.input.version} · 记录日期 ${x.input.recorded_date||'未知'} · 调度 ${x.input.dispatcher}`));showJSON(c,'逐步模型、输出与版本记录',x);if(x.status==='running')c.append(button('停止',async()=>{await api('/workflow-cancel',{project:project(),id:x.id});await memoraDocumentFlows();}));if(x.output.draft)c.append(button('打开新草稿',()=>loadWorkspaceDocument(x.output.draft.slug,x.output.draft.audience,x.output.draft.version)));return c;}));};
  $('brain-dimension').onchange=brain;
  safe(configuration)();

  const provenance=card('这些记忆来自哪里？','来源包括用户手工记录、导入文档及对话、工具调用和 Curator 提炼候选。偏好必须有用户表达或明确证据；不会因模型猜测自动成为用户习惯。六种基础类型继续兼容原系统；学科、资源类型和知识层级作为独立标签，例如 domain:physics、resource:skill、level:concept。');$('view-knowledge').querySelector('.tabs').before(provenance);
  provenance.append(node('p','muted','Judge 建议依据：是否长期有效、是否重要、来源能否定位、是否含敏感内容、是否与已有记忆矛盾、是否夹带指令。阈值与模型判断会出错，批准与拒绝保留在原审核流程。领域先筛选可缩小检索范围，但可能漏掉跨领域知识；默认跨领域检索，按需加标签筛选。'));
  const hierarchy=card('建立有证据的层级关系','父 → 子表示组成、前置知识或顺序，不等同于语义相似。各类关系拒绝循环；两端必须是已审核记忆。');const hf={parent:field('parent','父 / 前置记忆完整 ID'),child:field('child','子 / 后续记忆完整 ID'),kind:select({part_of:'组成：整体 → 部分',prerequisite:'前置：基础 → 进阶',sequence:'顺序：先 → 后'}),evidence:field('evidence','关系的证据或出处')};for(const i of Object.values(hf))hierarchy.append(i);hierarchy.append(button('保存层级关系',async()=>{const b={project:project()};for(const [k,i] of Object.entries(hf))b[k]=i.value;await api('/hierarchy',b);notice('层级关系已保存，可在脑图中观察。');}));$('view-knowledge').append(hierarchy);
  $('view-maintenance').append(card('需要维护的内容','三份 SQLite 分别保存 Memory Merge 真源、Markdown 版本和通讯 / 工作流元数据；备份操作覆盖三份库。向量、FTS 与 Markdown 镜像可重建。模型连接、分工、来源目录配置和自用模型权重需单独备份。原始记录日期、来源、任务租约和处理日志也属于资料资产。完整恢复顺序见 docs/OPERATIONS_1.0.1.md。'));
})();
