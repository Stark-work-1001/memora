const {app,BrowserWindow,dialog,shell}=require('electron');
const {spawn}=require('node:child_process');
const path=require('node:path');
const fs=require('node:fs');
let backend,window,base,quitting=false;
const smoke=process.argv.includes('--smoke-test');
const root=path.resolve(__dirname,'..');
async function launch(){
  const data=process.env.MM_DATA||path.join(app.getPath('userData'),'memory');
  let executable,args;
  if(app.isPackaged){executable=path.join(process.resourcesPath,'backend',process.platform==='win32'?'memora-backend.exe':'memora-backend');args=[];}
  else {const local=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');executable=process.env.MEMORA_PYTHON||(fs.existsSync(local)?local:'python');args=['-m','memory_merge'];}
  backend=spawn(executable,[...args,'--data',data,'agent','--port','0'],{cwd:app.isPackaged?app.getPath('userData'):root,env:{...process.env,PYTHONUNBUFFERED:'1'},windowsHide:true,stdio:['ignore','pipe','pipe']});
  base=await new Promise((resolve,reject)=>{let buffer='';const timeout=setTimeout(()=>reject(new Error('Backend startup timed out')),20000);backend.once('error',e=>{clearTimeout(timeout);reject(e);});backend.once('exit',code=>{clearTimeout(timeout);reject(new Error('Backend exited: '+code));});backend.stdout.on('data',chunk=>{buffer=(buffer+chunk.toString()).slice(-10000);const match=buffer.match(/Memora: (http:\/\/127\.0\.0\.1:\d+)/);if(match){clearTimeout(timeout);resolve(match[1]);}});});
  backend.stderr.on('data',chunk=>process.stderr.write(chunk));
  window=new BrowserWindow({title:'Memora · 记忆体',show:!smoke,width:1460,height:950,minWidth:860,minHeight:650,backgroundColor:'#f6f7f3',webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true}});
  window.setMenuBarVisibility(false);
  const allowed=url=>{try{return new URL(url).origin===base;}catch{return false;}};
  const external=url=>{try{const u=new URL(url);return (!u.username&&!u.password&&!u.search&&!u.hash&&u.protocol==='https:')||/^codex:\/\/threads\/[0-9a-f-]{36}$/i.test(url);}catch{return false;}};
  window.webContents.setWindowOpenHandler(({url})=>{if(allowed(url)){const child=new BrowserWindow({parent:window,width:1250,height:900,webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true}});child.setMenuBarVisibility(false);child.webContents.setWindowOpenHandler(()=>({action:'deny'}));child.webContents.on('will-navigate',(e,target)=>{if(!allowed(target))e.preventDefault();});void child.loadURL(url);}else if(external(url))void shell.openExternal(url);return {action:'deny'};});
  window.webContents.on('will-navigate',(event,url)=>{if(!allowed(url)){event.preventDefault();if(external(url))void shell.openExternal(url);}});
  window.webContents.session.setPermissionRequestHandler((_webContents,_permission,callback)=>callback(false));
  window.on('closed',()=>{window=null;app.quit();});
  backend.once('exit',()=>{if(!quitting&&window){dialog.showErrorBox('Memora','本地后端已停止，请重新打开应用。');app.quit();}});
  await window.loadURL(base);
  if(smoke){console.log('MEMORA_DESKTOP_READY '+window.webContents.getTitle());app.quit();}
}
if(!app.requestSingleInstanceLock())app.quit();
else{app.on('second-instance',()=>{if(window){window.restore();window.focus();}});app.whenReady().then(launch).catch(error=>{if(smoke){console.error(error.message);app.exit(1);}else{dialog.showErrorBox('Memora 无法启动',error.message);app.quit();}});}
app.on('before-quit',()=>{quitting=true;if(backend)backend.kill();});
app.on('window-all-closed',()=>app.quit());
