import sqlite3
import unittest

from memory_merge import ops
from memory_merge.errors import Conflict, InvalidInput, InvalidTransition, LimitExceeded, NotFound, SensitiveContent
from memory_merge.store import TRANSITIONS, USER_SCOPE, Store
from tests.helpers import tmpdir


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tmpdir(); self.s = Store(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def fts_ids(self):
        with self.s.connect() as c: return {r[0] for r in c.execute('SELECT id FROM memory_fts')}

    def test_transition_table_is_enforced(self):
        states = {}
        for status in ('pending', 'approved', 'rejected', 'archived', 'superseded'):
            m = self.s.capture('p', f'state {status}', 'test')
            if status != 'pending':
                with self.s.connect() as c: c.execute('UPDATE memories SET status=? WHERE id=?', (status, m['id']))
            states[status] = m['id']
        for action, (allowed, to) in TRANSITIONS.items():
            for status in states:
                m = self.s.capture('p', f'{action} from {status}', 'test')
                if status != 'pending':
                    with self.s.connect() as c: c.execute('UPDATE memories SET status=? WHERE id=?', (status, m['id']))
                if status in allowed or status == to:
                    self.assertEqual(self.s.review('p', m['id'], action)['status'], to)
                else:
                    with self.assertRaises(InvalidTransition): self.s.review('p', m['id'], action)
        gone = self.s.capture('p', 'gone', 'test'); self.s.review('p', gone['id'], 'forget')
        with self.assertRaises(InvalidTransition): self.s.review('p', gone['id'], 'approve')

    def test_only_recallable_states_are_indexed_and_forget_removes_derived_copies(self):
        m = self.s.capture('p', 'pending text', 'test')
        self.assertNotIn(m['id'], self.fts_ids())
        self.s.review('p', m['id'], 'approve'); self.assertIn(m['id'], self.fts_ids())
        with self.s.connect() as c:
            c.execute("INSERT INTO embeddings VALUES(?, 'fp', 1, ?, x'0000803f', 'now')", (m['id'], m['digest']))
        self.s.review('p', m['id'], 'forget')
        self.assertNotIn(m['id'], self.fts_ids())
        with self.s.connect() as c: self.assertEqual(c.execute('SELECT count(*) FROM embeddings').fetchone()[0], 0)

    def test_supersedes_is_enforced_on_approval_and_restorable(self):
        old = self.s.capture('p', 'Node 18 is the runtime', 'test', mode='manual', confirmed=True)
        new = self.s.capture('p', 'Node 22 is the runtime', 'test', supersedes=old['id'])
        self.assertEqual(self.s.get('p', old['id'])['status'], 'approved')  # pending proposal changes nothing
        self.s.review('p', new['id'], 'approve')
        retired = self.s.get('p', old['id'])
        self.assertEqual(retired['status'], 'superseded'); self.assertIsNotNone(retired['valid_until'])
        self.assertEqual([r['id'] for r in self.s.recall('p', 'runtime')], [new['id']])
        self.assertEqual({r['id'] for r in self.s.recall('p', 'runtime', statuses=('approved', 'superseded'))}, {new['id'], old['id']})
        self.assertEqual(self.s.review('p', old['id'], 'restore')['status'], 'approved')
        a = self.s.capture('p', 'A', 'test', mode='manual', confirmed=True); b = self.s.capture('p', 'B', 'test', mode='manual', confirmed=True)
        self.s.link('p', a['id'], b['id'], 'supersedes')
        self.assertEqual(self.s.get('p', b['id'])['status'], 'superseded')

    def test_duplicates_become_sightings_with_support(self):
        a = self.s.capture('p', 'We deploy on Tuesdays', 'agent-a', event_id='1')
        b = self.s.capture('p', 'we deploy on tuesdays ', 'agent-b', event_id='2')
        self.assertEqual(a['id'], b['id']); self.assertTrue(b['deduplicated']); self.assertEqual(b['support'], 2)
        self.assertEqual(self.s.capture('p', 'We deploy on Tuesdays', 'agent-b', event_id='2')['id'], a['id'])  # retry
        with self.assertRaises(Conflict): self.s.capture('p', 'something else', 'agent-b', event_id='2')
        self.assertNotEqual(self.s.capture('q', 'We deploy on Tuesdays', 'agent-a')['id'], a['id'])  # other project
        self.s.review('p', a['id'], 'forget')
        self.assertNotEqual(self.s.capture('p', 'We deploy on Tuesdays', 'agent-c')['id'], a['id'])

    def test_user_scope_polarity_tags_and_filters(self):
        pref = self.s.capture(USER_SCOPE, 'I prefer tabs over spaces in Go code', 'user', mode='manual', confirmed=True)
        neg = self.s.capture('p', "Don't format Go code with spaces", 'user', mode='manual', confirmed=True, tags=['go', 'style'])
        self.assertEqual(neg['polarity'], 'negative'); self.assertEqual(neg['tags'], ['go', 'style'])
        found = {r['id']: r['scope'] for r in self.s.recall('p', 'Go code spaces')}
        self.assertEqual(found, {pref['id']: 'user', neg['id']: 'project'})
        self.assertEqual([r['id'] for r in self.s.recall('p', 'Go code', include_user=False)], [neg['id']])
        self.assertEqual([r['id'] for r in self.s.recall('p', 'Go', tags=['style'])], [neg['id']])
        self.assertEqual([r['id'] for r in self.s.recall('p', 'Go', polarity='negative')], [neg['id']])
        self.assertEqual([r['id'] for r in self.s.recall('p', 'style')], [neg['id']])  # tags are indexed
        with self.assertRaises(InvalidInput): self.s.capture('../p', 'x', 'test')

    def test_pagination_and_graph_truncation(self):
        ids = [self.s.capture('p', f'item {i}', 'test', mode='manual', confirmed=True)['id'] for i in range(25)]
        seen, cursor = [], None
        while True:
            page = self.s.page('p', limit=10, cursor=cursor)
            seen += [m['id'] for m in page['items']]; cursor = page['next_cursor']
            if not cursor: break
        self.assertEqual(sorted(seen), sorted(ids)); self.assertEqual(len(seen), len(set(seen)))
        g = self.s.graph('p', limit=5)
        self.assertTrue(g['truncated']); self.assertEqual(g['total'], 25); self.assertEqual(len(g['nodes']), 5)
        with self.assertRaises(InvalidInput): self.s.page('p', cursor='garbage')
        with self.assertRaises(LimitExceeded): self.s.page('p', limit=0)

    def test_screening_reports_kind_not_value(self):
        with self.assertRaises(SensitiveContent) as e: self.s.capture('p', 'token ghp_' + 'Z' * 36, 'test')
        self.assertEqual(e.exception.details['kinds'], ['github_token'])
        self.assertNotIn('ZZZZ', e.exception.to_json())
        with self.assertRaises(NotFound): self.s.capture('p', 'x', 'test', supersedes='missing')

    def test_purge_leaves_no_bytes_in_database_files(self):
        marker = 'PURGE-MARKER-' + 'q7' * 12
        m = self.s.capture('p', f'my locker code is {marker}', 'test', mode='manual', confirmed=True)
        keep = self.s.capture('p', 'unrelated note stays', 'test', mode='manual', confirmed=True)
        self.s.review('p', m['id'], 'forget')
        self.s.flush()
        res = ops.purge(self.s, 'p', m['id'])
        self.assertEqual(res['purged'], m['id']); self.assertNotIn('error', res['compaction'])
        for f in self.s.root.rglob('*'):
            if f.is_file(): self.assertNotIn(marker.encode(), f.read_bytes(), f.name)
        with self.s.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM audit WHERE id=? AND digest IS NOT NULL', (m['id'],)).fetchone()[0], 0)
        self.assertEqual(self.s.recall('p', 'unrelated')[0]['id'], keep['id'])
        with self.assertRaises(NotFound): self.s.get('p', m['id'])


if __name__ == '__main__':
    unittest.main()
