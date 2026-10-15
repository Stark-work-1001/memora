import json
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from memory_merge.agent import Agent
from memory_merge.chat_models import HTTPChat, profile
from memory_merge.errors import Conflict, InvalidInput, NotFound, ProviderError
from memory_merge.store import Store
from memory_merge.web import make_server
from tests.helpers import tmpdir
from tests.test_ops_web_cli import http


class ModelHandler(BaseHTTPRequestHandler):
    requests = []
    def do_GET(self):
        out = {'models': [{'name': 'tiny'}]} if self.path == '/api/tags' else {'data': [{'id': 'tiny'}]}
        self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(out).encode())

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.payloads.append((self.path, body))
        self.send_response(200); self.end_headers()
        if not body.get('stream'):
            self.wfile.write(b'{"done":true}'); return
        if self.path == '/api/chat':
            for piece in ['Ollama ', 'answer']:
                self.wfile.write((json.dumps({'message': {'content': piece}, 'done': False})+'\n').encode())
            self.wfile.write(b'{"message":{"content":""},"done":true}\n')
        else:
            for piece in ['Cited ', 'answer']:
                self.wfile.write(('data: '+json.dumps({'choices': [{'delta': {'content': piece}}]})+'\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n')

    def log_message(self,*args): pass


class FakeModel:
    def __init__(self, answer='记忆回答', delay=0): self.answer,self.delay,self.messages=answer,delay,[]
    def stream(self,messages,settings,cancel):
        self.messages=messages
        for piece in self.answer:
            if cancel.is_set(): break
            if self.delay: time.sleep(self.delay)
            yield piece


def done(agent, job):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        out=agent.snapshot(job['id'])
        if out['status']!='running': return out
        time.sleep(.01)
    raise AssertionError('generation did not finish')


class ChatAdapterTests(unittest.TestCase):
    def setUp(self):
        self.server=ThreadingHTTPServer(('127.0.0.1',0),ModelHandler);self.server.payloads=[]
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.base=f'http://127.0.0.1:{self.server.server_port}'

    def test_openai_and_ollama_real_http_streams(self):
        for kind,base,expected in [('openai',self.base+'/v1','Cited answer'),('ollama',self.base,'Ollama answer')]:
            model=HTTPChat({'id':'test','name':'test','kind':kind,'base':base,'model':'tiny'})
            self.assertEqual(model.models(),['tiny'])
            self.assertEqual(''.join(model.stream([{'role':'user','content':'hello'}],{'temperature':.4,'max_tokens':123},threading.Event())),expected)
        self.assertEqual(self.server.payloads[0][1]['temperature'],.4)
        self.assertEqual(self.server.payloads[1][1]['options']['num_predict'],123)
        model.control('unload')
        self.assertEqual(self.server.payloads[-1][1]['keep_alive'],0)

    def test_remote_url_requires_consent_https_and_no_embedded_secret(self):
        for p in [dict(base='http://example.com/v1',remote=True),dict(base='https://example.com/v1'),dict(base='https://user:secret@example.com/v1',remote=True)]:
            with self.assertRaises(ProviderError): profile(dict(id='x',name='x',model='x',kind='openai',**p))


class AgentTests(unittest.TestCase):
    def make(self,d,answer='记忆回答',delay=0):
        agent=Agent(Store(d));fake=FakeModel(answer,delay);agent.adapters['ollama']=fake
        return agent,fake

    def test_evidence_persistence_and_capture_pending(self):
        with tmpdir() as d:
            agent,model=self.make(d)
            good=agent.store.capture('p','用户喜欢中文回答','test',mode='manual',confirmed=True)
            pending=agent.store.capture('p','用户喜欢隐藏的候选信息','test')
            out=done(agent,agent.start({'project':'p','content':'用户喜欢什么','model':'ollama'}))
            self.assertEqual(out['status'],'done');self.assertIn(good['id'],out['references']);self.assertNotIn(pending['id'],out['references'])
            prompt=json.dumps(model.messages,ensure_ascii=False)
            self.assertIn('用户喜欢中文回答',prompt);self.assertNotIn('隐藏的候选',prompt)
            conv=agent.conversation(out['session'],'p');self.assertEqual([t['role'] for t in conv['turns']],['user','assistant'])
            capture=agent.post('/capture',{'session':conv['id'],'project':'p','seq':2})
            self.assertEqual(capture['status'],'pending')
            self.assertTrue((Path(d)/'markdown'/(capture['id']+'.md')).exists())
            self.assertEqual(Agent(Store(d)).conversation(conv['id'],'p')['turns'][1]['content'],'记忆回答')
            with self.assertRaises(NotFound): agent.conversation(conv['id'],'other')

    def test_cancel_serialization_and_history(self):
        with tmpdir() as d:
            agent,_=self.make(d,'abcdefghij',.05)
            first=agent.start({'project':'p','content':'hello','model':'ollama'})
            with self.assertRaises(Conflict): agent.start({'project':'p','content':'other','model':'ollama'})
            time.sleep(.08);agent.cancel(first['id']);out=done(agent,first)
            self.assertEqual(out['status'],'cancelled')
            self.assertLess(len(out['content']),10)
            agent.adapters['ollama']=FakeModel('second')
            second=done(agent,agent.start({'project':'p','session':first['session'],'content':'next','model':'ollama'}))
            self.assertEqual(second['status'],'done')
            self.assertEqual(agent.conversation(first['session'],'p')['turns'][-1]['seq'],4)

    def test_two_mcp_process_runtimes_cannot_write_same_session(self):
        with tmpdir() as d:
            first,_=self.make(d,'slow answer',.04)
            conv=first.create('p')
            job=first.start({'project':'p','session':conv['id'],'content':'hello','model':'ollama'})
            second,_=self.make(d)
            with self.assertRaises(Conflict): second.start({'project':'p','session':conv['id'],'content':'race','model':'ollama'})
            done(first,job)
            self.assertEqual(done(second,second.start({'project':'p','session':conv['id'],'content':'after','model':'ollama'}))['status'],'done')

    def test_router_and_curator_are_bounded_and_pending(self):
        with tmpdir() as d:
            agent,_=self.make(d)
            agent.assembly.update(router='lmstudio',route_models=['ollama'],curator='lmstudio')
            agent.adapters['lmstudio']=FakeModel('{"model":"ollama"}')
            out=done(agent,agent.start({'project':'p','content':'test','model':'ollama'}));self.assertEqual(out['model'],'ollama')
            agent.adapters['lmstudio']=FakeModel('{"memories":[{"content":"偏好中文回复","category":"preference","tags":["habit"]}]}')
            extracted=agent.distill({'project':'p','session':out['session']})
            self.assertEqual(extracted['memories'][0]['status'],'pending')
            agent.adapters['lmstudio']=FakeModel('{"model":"unpermitted"}')
            out=done(agent,agent.start({'project':'p','content':'test','model':'ollama'}));self.assertEqual(out['status'],'error')

    def test_brain_uses_explicit_approved_edges(self):
        with tmpdir() as d:
            agent,_=self.make(d)
            a=agent.store.capture('p','知识甲 [[伪造连线]]','test',mode='manual',confirmed=True)
            b=agent.store.capture('p','知识乙','test',mode='manual',confirmed=True)
            agent.store.capture('p','不应显示的待审知识','test')
            agent.store.link('p',a['id'],b['id'],'related')
            brain=agent.brain('p')
            self.assertEqual(brain['nodes'],2);self.assertNotIn('[[伪造连线]]',brain['dictionary'])
            self.assertIn('related → [[',brain['dictionary']);self.assertNotIn('不应显示',brain['outline'])

    def test_workbench_http_auth_and_brain_assets(self):
        with tmpdir() as d:
            agent,_=self.make(d)
            server=make_server(agent.store,0,review=True,agent=agent)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
            base=f'http://127.0.0.1:{server.server_port}'
            token=http(base+'/api/session')[1]['token']
            body=json.dumps({'project':'p','content':'hello','model':'ollama'}).encode()
            headers={'Content-Type':'application/json','Origin':base,'X-MM-Token':token}
            self.assertEqual(http(base+'/api/agent/generate',body,{**headers,'Origin':'http://evil.test'})[0],403)
            status,job=http(base+'/api/agent/generate',body,headers)
            self.assertEqual(status,200);self.assertEqual(done(agent,job)['status'],'done')
            for route in ['/','/architecture','/architecture.svg','/brain/dictionary/','/brain/outline/']:
                with urllib.request.urlopen(base+route) as r: self.assertEqual(r.status,200)
            with urllib.request.urlopen(base+'/api/agent/events?id='+job['id']) as r:
                event=r.readline().decode();self.assertTrue(event.startswith('data: '));self.assertIn('done',event)
