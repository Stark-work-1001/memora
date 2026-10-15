import asyncio
import json
import os
import sys
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from memory_merge.store import Store
from tests.helpers import tmpdir

ROOT = Path(__file__).resolve().parents[1]


async def with_session(d, extra_env, fn):
    env = {k: v for k, v in os.environ.items() if not k.startswith('MM_')}
    env.update(MM_DATA=d, **extra_env)
    params = StdioServerParameters(command=sys.executable, args=['-m', 'memory_merge.server'], env=env, cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


def payload(r):
    return json.loads(r.content[0].text)


class McpTests(unittest.TestCase):
    def test_peer_archive_append_and_agent_tools_opt_in(self):
        async def go(session):
            names = {t.name for t in (await session.list_tools()).tools}
            args = {'project':'p','agent':'peer-agent','external_id':'stable-session',
                    'turns':[{'seq':1,'role':'user','content':'知识与工具调用记录'}]}
            first = payload(await session.call_tool('memory_session_append', args))
            again = payload(await session.call_tool('memory_session_append', args))
            return names,first,again
        with tmpdir() as d:
            names,first,again=asyncio.run(with_session(d, {'MM_ENABLE_AGENT':'1'}, go))
            self.assertTrue({'memory_agent_ask','memory_agent_result','memory_agent_cancel'} <= names)
            self.assertNotIn('memory_review',names)
            self.assertEqual(first['turns'],1);self.assertEqual(again['turns'],0)

    def test_agent_cannot_self_approve_by_default(self):
        async def go(session):
            names = {t.name for t in (await session.list_tools()).tools}
            r = await session.call_tool('memory_remember', {'project': 'p', 'content': 'User wants concise replies', 'source': 'chat', 'confirmed': True})
            return names, payload(r)
        with tmpdir() as d:
            names, out = asyncio.run(with_session(d, {}, go))
            self.assertEqual(out['memory']['status'], 'pending'); self.assertIn('not trusted', out['note'])
            self.assertTrue({'memory_briefing', 'memory_profile', 'memory_session_search'} <= names)
            self.assertFalse({'memory_review', 'memory_purge', 'memory_link', 'memory_import'} & names)

    def test_operator_can_opt_in_to_agent_confirmation(self):
        async def go(session):
            return payload(await session.call_tool('memory_remember', {'project': 'p', 'content': 'Trusted path', 'source': 'chat', 'confirmed': True}))
        with tmpdir() as d:
            self.assertEqual(asyncio.run(with_session(d, {'MM_TRUST_AGENT_CONFIRM': '1'}, go))['memory']['status'], 'approved')

    def test_structured_errors(self):
        async def go(session):
            bad = await session.call_tool('memory_capture', {'project': '../x', 'content': 'c', 'source': 's', 'event_id': 'e'})
            secret = await session.call_tool('memory_capture', {'project': 'p', 'content': 'api_key=supersecret123', 'source': 's', 'event_id': 'e2'})
            return bad, secret
        with tmpdir() as d:
            bad, secret = asyncio.run(with_session(d, {}, go))
            for r, code in ((bad, 'invalid_input'), (secret, 'sensitive_content')):
                self.assertTrue(r.isError)
                text = r.content[0].text
                err = json.loads(text[text.index('{'):])['error']
                self.assertEqual(err['code'], code); self.assertFalse(err['retryable'])
            self.assertNotIn('supersecret123', secret.content[0].text)

    def test_reviewer_instance_full_cycle(self):
        async def go(session):
            names = {t.name for t in (await session.list_tools()).tools}
            a = payload(await session.call_tool('memory_capture', {'project': 'p', 'content': 'Old: Node 18', 'source': 'agent', 'event_id': '1'}))['memory']
            b = payload(await session.call_tool('memory_capture', {'project': 'p', 'content': 'New: Node 22', 'source': 'agent', 'event_id': '2', 'supersedes': a['id']}))['memory']
            queue = payload(await session.call_tool('memory_review_queue', {'project': 'p'}))
            await session.call_tool('memory_review', {'project': 'p', 'id': a['id'], 'action': 'approve'})
            await session.call_tool('memory_review', {'project': 'p', 'id': b['id'], 'action': 'approve'})
            recall = payload(await session.call_tool('memory_recall', {'project': 'p', 'query': 'Node'}))
            refused = await session.call_tool('memory_purge', {'project': 'p', 'id': a['id'], 'confirm': 'yes'})
            purged = payload(await session.call_tool('memory_purge', {'project': 'p', 'id': a['id'], 'confirm': a['id']}))
            brief = payload(await session.call_tool('memory_briefing', {'project': 'p'}))
            return names, queue, recall, refused, purged, brief, a, b
        with tmpdir() as d:
            names, queue, recall, refused, purged, brief, a, b = asyncio.run(with_session(d, {'MM_ENABLE_REVIEW': '1'}, go))
            self.assertTrue({'memory_review', 'memory_link_remove', 'memory_purge', 'memory_review_document'} <= names)
            self.assertEqual(len(queue['items']), 2)
            self.assertEqual([r['id'] for r in recall['results']], [b['id']])
            self.assertTrue(refused.isError); self.assertEqual(purged['purged'], a['id'])
            self.assertIsInstance(brief['briefing'], str)
            self.assertEqual(Store(d).get('p', b['id'])['access_count'], 1)  # recall via MCP records access


if __name__ == '__main__':
    unittest.main()
