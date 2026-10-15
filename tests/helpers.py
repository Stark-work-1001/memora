"""Shared test helpers. No network, no model downloads."""
import hashlib
import math
import tempfile

from memory_merge import text


class FakeEmbedder:
    """Deterministic hashed bag-of-terms embedder.

    `salt` changes the vector space while `descriptor()` stays the same, which simulates a different
    model being served behind an unchanged name -- the case canary checks exist for.
    """

    def __init__(self, dim=64, salt='', revision='r1', dimensions=None, query_template='{text}'):
        self.dim, self.salt, self.revision, self.dimensions, self.query_template = dim, salt, revision, dimensions, query_template
        self.calls = 0
        self.task = 'test task'

    def query_text(self, q):
        return self.query_template.replace('{task}', self.task).replace('{text}', q)

    def embed(self, s):
        self.calls += 1
        v = [0.0] * self.dim
        terms, chars = text.analyze(s)
        for term in (terms + ' ' + chars).split():
            h = int(hashlib.sha1((self.salt + term).encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0 if (h >> 8) % 2 else -1.0
        if not any(v): v[0] = 1.0
        if self.dimensions: v = v[:self.dimensions]
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_batch(self, texts):
        return [self.embed(s) for s in texts]

    def descriptor(self):
        return {'backend': 'fake', 'model': 'fake-embedder', 'revision': self.revision, 'dimensions': self.dimensions,
                'pooling': 'hash', 'normalize': 'l2', 'document_template': '{text}'}


class FakeJudge:
    def __init__(self, reply=None, exc=None):
        self.reply, self.exc, self.calls = reply, exc, 0

    def judge(self, s):
        from memory_merge import judge
        self.calls += 1
        if self.exc: raise self.exc
        return judge.parse(self.reply)

    def judge_descriptor(self):
        return {'backend': 'fake', 'model': 'fake-judge'}


def tmpdir():
    return tempfile.TemporaryDirectory(prefix='mm-test-', ignore_cleanup_errors=True)
