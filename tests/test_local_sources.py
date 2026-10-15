import json
from pathlib import Path
import unittest

from memory_merge.local_sources import LocalSources, local_path, parse_history
from memory_merge.store import Store
from memory_merge.errors import InvalidInput
from tests.helpers import tmpdir


class LocalSourceTests(unittest.TestCase):
    def test_codex_claude_tools_and_team_provenance(self):
        records=[{'type':'session_meta','payload':{'id':'x','parent_thread_id':'parent','agent_role':'reviewer'}},
            {'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'你好'}]}},
            {'type':'response_item','payload':{'type':'function_call','name':'search','arguments':'{"query":"memory"}'}},
            {'type':'response_item','payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':'回答'}]}}]
        out,caps,info=parse_history('\n'.join(json.dumps(r) for r in records),'codex','s')
        self.assertEqual(len(out),4);self.assertEqual(out[2]['role'],'tool')
        self.assertEqual({c[0] for c in caps},{'tool','team'})
        raw=json.dumps({'type':'assistant','message':{'role':'assistant','content':[{'type':'text','text':'hello'},{'type':'tool_use','name':'Read','input':{'path':'note.md'}}]}})
        out,caps,_=parse_history(raw,'claude-code','c');self.assertEqual(caps[0][1],'Read')

    def test_discovery_import_redaction_idempotence_and_traversal(self):
        with tmpdir() as d:
            folder=Path(d)/'source';folder.mkdir()
            (folder/'SKILL.md').write_text('# Skill\nA useful tool\napi_key=supersecret123','utf-8')
            (folder/'auth.json').write_text('{"access_token":"private"}','utf-8')
            local=LocalSources(Store(Path(d)/'data'))
            local.save({'id':'skills','name':'skills','agent':'peer','root':str(folder),'kind':'skill'})
            found=local.discover('skills');self.assertEqual(len(found['items']),1)
            self.assertEqual(found['items'][0]['kind'],'skill')
            body={'source':'skills','project':'p','paths':['SKILL.md']}
            report=local.import_files(body);mid=report['files'][0]['memories'][0]
            m=local.store.get('p',mid);self.assertEqual(m['status'],'pending');self.assertNotIn('supersecret123',m['content'])
            again=local.import_files(body);self.assertEqual(again['files'][0]['memories'][0],mid)
            self.assertIn('error',local.import_files({'source':'skills','project':'p','paths':['../outside.md']})['files'][0])
            with self.assertRaises(InvalidInput): local_path('//server/share')

    def test_history_incremental_append_and_unsupported_report(self):
        with tmpdir() as d:
            folder=Path(d)/'source';folder.mkdir();target=folder/'conversation.jsonl'
            line={'type':'assistant','message':{'role':'assistant','content':'hello'}}
            target.write_text(json.dumps(line),'utf-8')
            local=LocalSources(Store(Path(d)/'data'));local.save({'id':'h','name':'History','agent':'peer','root':str(folder),'kind':'history'})
            body={'source':'h','project':'p','paths':['conversation.jsonl']}
            self.assertEqual(local.import_files(body)['files'][0]['archive']['turns'],1)
            self.assertEqual(local.import_files(body)['files'][0]['archive']['turns'],0)
            target.write_text(json.dumps(line)+'\n'+json.dumps({'type':'user','message':{'role':'user','content':'next'}}),'utf-8')
            self.assertEqual(local.import_files(body)['files'][0]['archive']['turns'],1)
