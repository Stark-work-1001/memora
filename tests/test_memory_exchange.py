import json
import unittest
from memory_merge.memory_exchange import import_graph
from memory_merge.store import Store
from memory_merge.errors import InvalidInput
from tests.helpers import tmpdir


class ExchangeTests(unittest.TestCase):
    def test_jsonl_graph_pending_and_relation_label_preserved(self):
        with tmpdir() as d:
            s=Store(d)
            records=[{'type':'entity','name':'Embedding','entityType':'concept','observations':['向量表示']},
                     {'type':'entity','name':'Memory','entityType':'concept','observations':['记忆管理']},
                     {'type':'relation','from':'Memory','to':'Embedding','relationType':'uses'}]
            out=import_graph(s,'p','\n'.join(json.dumps(r) for r in records))
            self.assertEqual(out['relations'],1)
            self.assertTrue(all(s.get('p',mid)['status']=='pending' for mid in out['memories']))
            self.assertIn('uses → Embedding',s.get('p',out['memories'][1])['content'])
            self.assertEqual(s.graph('p')['nodes'],[])
            for mid in out['memories']:s.review('p',mid,'approve')
            self.assertEqual(len(s.graph('p')['edges']),1)

    def test_bad_graph_fails_before_writing(self):
        with tmpdir() as d:
            s=Store(d)
            with self.assertRaises(InvalidInput):import_graph(s,'p','{"entities":[{"name":"x","observations":[1]}]}')
            self.assertEqual(s.health()['memories'],0)
