/* Hidden Electron validation of our own app with disposable synthetic data. */
const {app,BrowserWindow}=require('electron');
const {spawn}=require('node:child_process');const fs=require('node:fs');const path=require('node:path');
const root=path.resolve(__dirname,'..'),out=path.join(root,'artifacts/ui-1.0.1');fs.mkdirSync(out,{recursive:true});
app.setPath('userData',path.join(out,'electron-profile-'+process.pid));
let backend;const errors=[],checks=[];const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function main(){
  await app.whenReady();
  const python=path.join(root,'.venv/Scripts/python.exe'),data=path.join(out,'synthetic-data-'+Date.now());
  const seed=spawn(python,['-c',`from memory_merge.store import Store
from memory_merge.agent import Agent
import sys
a=Agent(Store(sys.argv[1]))
items=[a.store.capture('demo',t,'synthetic:user',mode='manual',confirmed=True,event_id=str(i),category='knowledge') for i,t in enumerate(['记忆体架构与模型装配','向量检索：文本编码与相似度','Judge：来源与持久性判定','Rust：精确 top-k 内核','Markdown：保留原始日期','MCP：智能体通讯接口','层级脑图：基础到进阶','用户偏好：需要有来源','组织：责任分工与任务租约','来源核验与审核'])]
for i in range(1,len(items)):a.store.link('demo',items[0]['id'],items[i]['id'],'related')
for i in range(1,5):a.control.hierarchy_link('demo',items[0]['id'],items[i]['id'],'part_of','synthetic example')
a.control.save_asset({'project':'demo','kind':'ghost','title':'研究专家（合成）','description':'核验来源、报告不确定性','payload':{'specialty':'research'},'agent':'demo-agent'})
a.documents.put('demo','learning-log','human','按日期的学习笔记','# 学习笔记\\n仅用于界面验证的合成资料。',0,recorded_date='2025-01-02',group_title='记忆体开发')
a.control.heartbeat('demo','demo-peer','合成通讯客户端','示例模型','local',{},300)
a.store.flush()
`,data],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
  let seedError='';seed.stderr.on('data',b=>seedError+=b);await new Promise((resolve,reject)=>seed.on('exit',c=>c?reject(new Error(seedError)):resolve()));
  backend=spawn(python,['-m','memory_merge','--data',data,'agent','--port','0'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
  const base=await new Promise((resolve,reject)=>{let text='';backend.stdout.on('data',b=>{text+=b;const m=text.match(/http:\/\/127\.0\.0\.1:\d+/);if(m)resolve(m[0]);});setTimeout(()=>reject(new Error('backend timeout')),15000);});
  const win=new BrowserWindow({show:false,width:1500,height:1000,webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,offscreen:true,backgroundThrottling:false}});
  win.webContents.on('console-message',(...args)=>{const d=args[1];if(d&&typeof d==='object'&&d.level==='error')errors.push(d.message);});
  win.webContents.on('render-process-gone',()=>errors.push('render process gone'));
  await win.loadURL(base);await delay(700);
  const js=s=>win.webContents.executeJavaScript(s);
  await js(`$('project').value='demo';$('project').dispatchEvent(new Event('change'));`);await delay(300);
  for(const view of ['models','sources','threads','knowledge','markdown','maintenance','chat']){
    await js(`view(${JSON.stringify(view)})`);await delay(180);
    const status=await js(`({view:state.view,title:$('view-title').textContent,notice:$('notice').hidden?'':$('notice').textContent})`);
    if(status.notice&&status.notice.includes('失败'))throw new Error(status.notice);
    checks.push(status);
  }
  await js(`view('models')`);await delay(150);await js(`$('model-location').value='cloud';$('model-location').dispatchEvent(new Event('change'));`);
  checks.push(await js(`({cloudProtocol:$('model-kind').value,cloudRemote:$('model-remote').checked,emptyCloudEndpoint:$('model-base').value==='',roles:Object.keys(state.config.roles).length,kernel:state.config.kernel})`));
  await win.webContents.capturePage().then(i=>fs.writeFileSync(path.join(out,'models.png'),i.toPNG()));
  await js(`view('sources')`);await delay(150);await js(`[...document.querySelectorAll('.resource-tabs button')].find(b=>b.textContent.includes('Ghost')).click()`);await delay(150);
  checks.push(await js(`({ghost:document.querySelector('.resource-description').textContent,rows:document.querySelector('.resource-description').nextElementSibling.nextElementSibling.textContent})`));
  await js(`view('brain');state.brain='dictionary';brain()`);await delay(1500);
  let frame=win.webContents.mainFrame.frames.find(f=>f.url.includes('/brain/dictionary/'));
  checks.push(await frame.executeJavaScript(`(()=>{dictionaryGraph.select(0,true);return {dictionaryNodes:dictionaryGraph.searchEntries.length,layouts:dictionaryGraph.layoutChoices.length}})()`));await delay(2100);
  await win.webContents.capturePage().then(i=>fs.writeFileSync(path.join(out,'dictionary-3d.png'),i.toPNG()));
  await js(`state.brain='outline';brain()`);await delay(1600);frame=win.webContents.mainFrame.frames.find(f=>f.url.includes('/brain/outline/'));
  checks.push(await frame.executeJavaScript(`(()=>{const id=mindMap.nodeIds[2];mindMap.selectById(id,true);return {outlineNodes:mindMap.nodeCount,layouts:mindMap.layoutChoices.length}})()`));await delay(1900);
  await win.webContents.capturePage().then(i=>fs.writeFileSync(path.join(out,'hierarchy-3d.png'),i.toPNG()));
  await js(`$('brain-dimension').value='2d';brain()`);await delay(1900);
  checks.push({planeLoaded:win.webContents.mainFrame.frames.some(f=>f.url.includes('/brain/plane/'))});
  await win.webContents.capturePage().then(i=>fs.writeFileSync(path.join(out,'hierarchy-2d.png'),i.toPNG()));
  const report={checks,console_errors:errors};fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));
  if(errors.length)throw new Error(JSON.stringify(errors));console.log(JSON.stringify(report));
  win.destroy();backend.kill();app.quit();
}
main().catch(e=>{console.error(e.stack);if(backend)backend.kill();app.exit(1);});
