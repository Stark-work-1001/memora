"""Real MCP Streamable HTTP round trip on disposable data, with an ephemeral credential."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def verify(url,token):
    async with httpx.AsyncClient(trust_env=False,timeout=10) as unauthorized:
        for _ in range(100):
            try:
                response=await unauthorized.get(url)
                if response.status_code==401:break
            except httpx.ConnectError:pass
            await asyncio.sleep(.1)
        else:raise RuntimeError('bridge startup/authentication failed')
    async with httpx.AsyncClient(trust_env=False,headers={'Authorization':'Bearer '+token},timeout=20) as client:
        async with streamable_http_client(url,http_client=client) as (reader,writer,_):
            async with ClientSession(reader,writer) as session:
                await session.initialize()
                names={t.name for t in (await session.list_tools()).tools}
                assert 'memory_peer_heartbeat' in names
                r=await session.call_tool('memory_peer_heartbeat',{'project':'synthetic','peer':'synthetic-peer','name':'Synthetic mobile','location':'mobile'})
                assert not r.isError
                peers=await session.call_tool('memory_peer_list',{'project':'synthetic'})
                assert not peers.isError
                return {'unauthorized_denied':True,'mcp_initialize':True,'peer_heartbeat_roundtrip':True,'tools':len(names)}


def main():
    root=Path(__file__).resolve().parents[1]
    executable=root/'desktop/release/win-unpacked/resources/backend/memora-backend.exe'
    if not executable.exists():raise SystemExit('Build desktop first')
    with tempfile.TemporaryDirectory(prefix='memora-bridge-') as data:
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        env={k:v for k,v in os.environ.items() if not k.startswith('MM_')};token=secrets.token_urlsafe(40)
        env.update(MM_DATA=data,MM_ENABLE_COORDINATION='1',MM_BRIDGE_TOKEN=token)
        process=subprocess.Popen([str(executable),'bridge','--port',str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:report=asyncio.run(verify(f'http://127.0.0.1:{port}/mcp',token))
        finally:process.terminate();process.wait(timeout=15)
    (root/'dist/BRIDGE_VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n','utf-8');print(json.dumps(report))


if __name__=='__main__':main()
