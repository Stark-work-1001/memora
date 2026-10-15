import contextlib
import io
import json
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from memory_merge import __main__ as cli, ops
from memory_merge.errors import InvalidInput
from memory_merge.store import Store
from memory_merge.web import make_server
from tests.helpers import tmpdir


class OpsTests(unittest.TestCase):
    def test_backup_restore_drill(self):
        with tmpdir() as d:
            s = Store(Path(d) / 'live')
            for i in range(5): s.capture('p', f'note {i}', 'test', mode='manual', confirmed=True)
            b = s.backup()
            self.assertEqual((b['integrity'], b['memories']), ('ok', 5))
            r = ops.restore(b['backup'], Path(d) / 'restored')
            self.assertEqual((r['integrity'], r['memories']), ('ok', 5))
            self.assertEqual(len(Store(Path(d) / 'restored').recall('p', 'note')), 5)
            with self.assertRaises(InvalidInput): ops.restore(b['backup'], Path(d) / 'restored')  # never over existing data
            self.assertEqual(ops.drill(s)['drill'], 'pass')

    def test_doctor_and_report_offline(self):
        with tmpdir() as d:
            s = Store(d)
            a = s.capture('p', 'duplicate-ish', 'test', mode='manual', confirmed=True)
            b = s.capture('p', 'conflicting claim', 'test', mode='manual', confirmed=True)
            s.link('p', a['id'], b['id'], 'contradicts')
            doc = ops.doctor(s, env={})
            names = {c['check']: c['status'] for c in doc['checks']}
            self.assertEqual(names['database'], 'ok'); self.assertEqual(names['fts5_json'], 'ok')
            self.assertEqual(names['embedding_config'], 'ok'); self.assertEqual(names['backups'], 'warn')
            bad = ops.doctor(s, env={'MM_EMBED_URL': 'http://example.com/v1', 'MM_EMBED_MODEL': 'm'})
            self.assertEqual({c['check']: c['status'] for c in bad['checks']}['embedding_config'], 'fail')
            self.assertEqual(len(ops.report(s, 'p')['unresolved_conflicts']), 1)
            self.assertIn('vacuum', ops.compact(s))


def http(url, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read() or b'null')
    except urllib.error.HTTPError as e:
        return e.code, None


class WebTests(unittest.TestCase):
    def serve(self, store, review):
        server = make_server(store, 0, review=review)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        return f'http://127.0.0.1:{server.server_port}', server.server_port

    def test_read_routes(self):
        with tmpdir() as d:
            s = Store(d); m = s.capture('p', 'viewer search target', 'test', mode='manual', confirmed=True)
            base, _ = self.serve(s, review=False)
            self.assertEqual(http(base + '/api/search?project=p&q=viewer')[1]['results'][0]['id'], m['id'])
            self.assertEqual(http(base + '/api/timeline?project=p')[1]['items'][0]['id'], m['id'])
            self.assertEqual(http(base + f"/api/memory?project=p&id={m['id']}")[1]['support'], 1)
            self.assertEqual(http(base + '/api/session')[1], {'review': False, 'token': None})
            self.assertEqual(http(base + '/api/queue?project=p')[0], 404)
            self.assertEqual(http(base + '/api/graph?project=../x')[0], 400)
            self.assertEqual(http(base + '/api/review', b'{}', {'Content-Type': 'application/json'})[0], 501)

    def test_review_mode_requires_token_origin_and_json(self):
        with tmpdir() as d:
            s = Store(d); m = s.capture('p', 'awaiting review', 'agent')
            base, port = self.serve(s, review=True)
            token = http(base + '/api/session')[1]['token']
            body = json.dumps({'project': 'p', 'id': m['id'], 'action': 'approve'}).encode()
            good = {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{port}', 'X-MM-Token': token}
            for broken in ({'X-MM-Token': 'wrong'}, {'Origin': 'http://evil.example'}, {'Content-Type': 'text/plain'}, {'Host': 'evil.example'}):
                self.assertEqual(http(base + '/api/review', body, dict(good, **broken))[0], 403, broken)
            self.assertEqual(s.get('p', m['id'])['status'], 'pending')
            self.assertEqual(http(base + '/api/queue?project=p')[1]['items'][0]['id'], m['id'])
            status, out = http(base + '/api/review', body, good)
            self.assertEqual((status, out['memory']['status']), (200, 'approved'))
            bad = json.dumps({'project': 'p', 'id': m['id'], 'action': 'purge'}).encode()
            self.assertEqual(http(base + '/api/review', bad, good)[0], 400)


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try: cli.main(list(argv))
            except SystemExit as e: code = e.code
        return code, out.getvalue(), err.getvalue()

    def test_roundtrip_and_error_contract(self):
        with tmpdir() as d:
            code, out, _ = self.run_cli('--data', d, 'capture', '--project', 'p', '--source', 'cli', '--event-id', 'e1', 'Thai ภาษา emoji ✅ note')
            mid = json.loads(out)['id']; self.assertEqual(code, 0)
            self.assertEqual(json.loads(self.run_cli('--data', d, 'list', '--project', 'p', '--status', 'pending')[1])['items'][0]['id'], mid)
            self.run_cli('--data', d, 'review', '--project', 'p', mid, 'approve')
            res = json.loads(self.run_cli('--data', d, 'recall', '--project', 'p', 'ภาษา')[1])
            self.assertEqual(res['results'][0]['id'], mid)
            self.assertTrue((Path(d) / 'markdown' / f'{mid}.md').exists())  # mirror flushed after writes
            code, _, err = self.run_cli('--data', d, 'capture', '--project', 'p', '--source', 'cli', 'api_key=supersecret123')
            self.assertEqual((code, json.loads(err)['error']['code']), (2, 'sensitive_content'))
            code, _, err = self.run_cli('--data', d, 'review', '--project', 'p', 'missing-id', 'approve')
            self.assertEqual((code, json.loads(err)['error']['code']), (3, 'not_found'))
            self.assertIn('mcpServers', self.run_cli('--data', d, 'setup', 'claude-desktop')[1])


if __name__ == '__main__':
    unittest.main()
