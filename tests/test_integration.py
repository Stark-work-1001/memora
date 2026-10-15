import asyncio,json,os,sys,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from memory_merge.store import Store
from memory_merge.web import make_server

class IntegrationTests(unittest.TestCase):
    def test_http_readonly_host_guard_and_graph(self):
        with tempfile.TemporaryDirectory(prefix='mm-http-test-') as d:
            store=Store(d); store.capture('p','<script>alert(1)</script>',source='test',mode='manual',confirmed=True)
            server=make_server(store,0); thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{server.server_port}'
            try:
                with urllib.request.urlopen(base+'/api/graph?project=p') as r:
                    self.assertIn("script-src 'self'",r.headers['Content-Security-Policy'])
                    self.assertEqual(len(json.load(r)['nodes']),1)
                req=urllib.request.Request(base+'/api/graph',headers={'Host':'evil.example'})
                with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
                self.assertEqual(e.exception.code,403)
                with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(urllib.request.Request(base+'/',data=b'{}'))
                self.assertEqual(e.exception.code,501)
                with urllib.request.urlopen(base+'/app.js') as r: self.assertNotIn('innerHTML',r.read().decode())
            finally: server.shutdown(); server.server_close();thread.join()
    def test_real_mcp_handshake_tools_and_roundtrip(self):
        async def check(d):
            env={**os.environ,'MM_DATA':d,'MM_ENABLE_REVIEW':'1'}
            for key in list(env):
                if key.startswith(('MM_EMBED','MM_JUDGE')): del env[key]
            params=StdioServerParameters(command=sys.executable,args=['-m','memory_merge.server'],env=env,cwd=str(Path(__file__).resolve().parents[1]))
            async with stdio_client(params) as (read,write):
                async with ClientSession(read,write) as session:
                    hello=await session.initialize(); self.assertEqual(hello.serverInfo.name,'Memora')
                    names={t.name for t in (await session.list_tools()).tools}; self.assertIn('memory_capture',names)
                    def decode(r):
                        self.assertFalse(r.isError);return json.loads(r.content[0].text)
                    cap=decode(await session.call_tool('memory_capture',{'project':'p','content':'SQLite decision','source':'test','event_id':'e'}))
                    mid=cap['memory']['id']
                    empty=decode(await session.call_tool('memory_recall',{'project':'p','query':'SQLite'}));self.assertEqual(empty['results'],[])
                    decode(await session.call_tool('memory_review',{'project':'p','id':mid,'action':'approve'}))
                    rag=decode(await session.call_tool('memory_rag_context',{'project':'p','query':'SQLite'}));self.assertIn(mid,rag['references'])
                    graph=decode(await session.call_tool('memory_graph',{'project':'p'}));self.assertEqual(len(graph['nodes']),1)
            self.assertEqual(len(Store(d).recall('p','SQLite')),1)
        with tempfile.TemporaryDirectory(prefix='mm-mcp-test-') as d: asyncio.run(check(d))
