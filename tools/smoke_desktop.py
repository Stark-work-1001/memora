"""Verify the frozen backend, MCP stdio and hidden packaged Electron startup on disposable data."""
import asyncio
import json
import marshal
import os
from pathlib import Path
import queue
import re
import subprocess
import tempfile
import threading
import types
import zipfile
import urllib.request

from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from PyInstaller.archive.readers import CArchiveReader

ROOT=Path(__file__).resolve().parents[1]


def binary_code_scan(executable):
    archive=CArchiveReader(str(executable))
    pyz=archive.open_embedded_archive('PYZ.pyz')
    count=0
    def check(code):
        nonlocal count
        if not isinstance(code,types.CodeType):return
        count+=1
        filename=code.co_filename
        if Path.home().name.lower() in filename.lower() or str(ROOT).lower() in filename.lower():
            raise RuntimeError('private compiler path in frozen bytecode')
        for constant in code.co_consts:
            if isinstance(constant,types.CodeType):check(constant)
    for name in pyz.toc:
        check(pyz.extract(name))
    for name,entry in archive.toc.items():
        if entry[-1]=='s':check(marshal.loads(archive.extract(name)))
    standard=Path(executable).parent/'_internal/base_library.zip'
    if standard.exists():
        with zipfile.ZipFile(standard) as z:
            for name in z.namelist():
                if name.endswith('.pyc'):check(marshal.loads(z.read(name)[16:]))
    return {'checked_code_objects':count,'private_code_filenames':0}


async def mcp_smoke(executable,data,env):
    params=StdioServerParameters(command=str(executable),args=['--data',str(data),'mcp'],env=env)
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            names={t.name for t in (await session.list_tools()).tools}
            assert {'memory_recall','memory_session_append','memory_agent_ask','memory_document_put','memory_document_get','memory_peer_heartbeat','memory_task_claim','memory_workflow_plan'}<=names
            peer=await session.call_tool('memory_peer_heartbeat',{'project':'smoke','peer':'synthetic-peer','name':'Synthetic peer','model':'synthetic-model'})
            assert not peer.isError
            queued=await session.call_tool('memory_task_create',{'project':'smoke','title':'Synthetic coordination task','assigned':'synthetic-peer'})
            assert not queued.isError
            task=json.loads(queued.content[0].text)
            claimed=await session.call_tool('memory_task_claim',{'project':'smoke','peer':'synthetic-peer','id':task['id']})
            assert not claimed.isError
            result=await session.call_tool('memory_session_append',{'project':'smoke','agent':'test-peer','external_id':'smoke-session',
                'turns':[{'seq':1,'role':'user','content':'Synthetic release validation turn'}]})
            assert not result.isError
            draft=await session.call_tool('memory_document_put',{'project':'smoke','slug':'release-guide','audience':'agent',
                'title':'Synthetic release guide','content':'# Synthetic document\nTest data only.', 'expected_version':0,'source':'release-smoke'})
            assert not draft.isError
            published=await session.call_tool('memory_document_list',{'project':'smoke'})
            assert not published.isError
            assert not published.content or json.loads(published.content[0].text)==[]
            return {'tools':len(names),'peer_archive_append':True,'document_draft_exchange':True,
                'review_tools_exposed':bool({'memory_review','memory_document_publish'} & names)}


def main():
    executable=ROOT/'desktop/release/win-unpacked/resources/backend/memora-backend.exe'
    shell=ROOT/'desktop/release/win-unpacked/Memora.exe'
    report={'version':subprocess.check_output([str(executable),'--version'],text=True).strip()}
    assert report['version']=='1.0.1'
    env={k:v for k,v in os.environ.items() if not k.startswith(('MM_','ELECTRON_RUN_AS_NODE'))}
    system_root=Path(os.environ.get('SystemRoot','C:/Windows'))
    env['PATH']=os.pathsep.join([str(system_root),str(system_root/'System32')])
    env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
    report['external_runtimes_removed_from_path']=True
    with tempfile.TemporaryDirectory(prefix='memora-smoke-') as tmp:
        data=Path(tmp)/'data';env.update(MM_DATA=str(data),MM_ENABLE_AGENT='1',MM_ENABLE_DOCUMENTS='1',MM_ENABLE_COORDINATION='1')
        backend=subprocess.Popen([str(executable),'--data',str(data),'agent','--port','0'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',env=env)
        lines=queue.Queue()
        threading.Thread(target=lambda:lines.put(backend.stdout.readline()),daemon=True).start()
        try:
            line=lines.get(timeout=30)
            match=re.search(r'http://127\.0\.0\.1:\d+',line)
            if not match:raise RuntimeError('frozen backend did not announce its URL')
            base=match.group()
            paths=['/','/agent-next.js','/architecture.svg','/brain/dictionary/','/brain/outline/','/brain/plane/','/api/agent/config','/api/agent/sources','/api/agent/workspace-documents','/api/agent/brain','/api/agent/threads','/api/agent/peers','/api/agent/tasks','/api/agent/workflows','/api/agent/map']
            for path in paths:
                with urllib.request.urlopen(base+path,timeout=10) as response:assert response.status==200
            with urllib.request.urlopen(base+'/api/agent/config') as response:assert json.load(response)['kernel']=='native'
            report['frozen_http_routes']=len(paths);report['rust_kernel_required']=True
        finally:
            backend.terminate();backend.wait(timeout=10)
        report['mcp']=asyncio.run(mcp_smoke(executable,data,env))
        process=subprocess.run([str(shell),'--smoke-test'],env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
        if process.returncode or 'MEMORA_DESKTOP_READY' not in process.stdout:
            raise RuntimeError('Electron smoke failed: '+process.stderr[-1000:])
        report['electron_window_loaded']=True
    report['frozen_bytecode']=binary_code_scan(executable)
    (ROOT/'dist/SMOKE_VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
