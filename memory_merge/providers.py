"""Model backends. Nothing here runs unless explicitly configured; lexical retrieval needs none.

Embedding backends share one contract: embed(text) and optionally embed_batch(texts) return
L2-normalised vectors, after Matryoshka truncation when `dimensions` is set; descriptor() describes
everything that determines the *document-side* vector space (model, revision, pooling, dimension,
normalisation, document template). The descriptor is hashed into the fingerprint that every stored
vector carries. The query template is recorded but not fingerprinted: changing it changes query
quality, not the compatibility of stored vectors.

Judge backends share: judge(text) -> validated dict, and descriptor().

Backends:
- Provider: OpenAI-compatible HTTP (llama.cpp server, Ollama, vLLM, LM Studio, TEI, remote APIs).
  Loopback by default; anything else needs HTTPS and MM_ALLOW_REMOTE=1. No redirects, no proxies,
  bounded response size and time.
- SentenceTransformersEmbedder, LlamaCppEmbedder, LlamaCppJudge: in-process, no server to run.
  Optional dependencies, imported only when selected.
"""
import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from . import judge as judge_mod, vectors
from .errors import DependencyMissing, ModelOutputInvalid, ProviderConfigError, ProviderError

LOOPBACK = {'127.0.0.1', '::1'}
# English task text, as the Qwen3-Embedding model card recommends even for non-English corpora.
DEFAULT_TASK = 'Given a question or keywords, retrieve stored notes and memories that answer it'
PRESETS = {
    # Verified against the Qwen/Qwen3-Embedding-0.6B model card and config_sentence_transformers.json
    # (revision 97b0c614, accessed 2026-10-13): last-token pooling, no document instruction, query
    # template without a space after "Query:", L2 normalisation, MRL dimensions 32..1024.
    'qwen3-embedding': {'query_template': 'Instruct: {task}\nQuery:{text}', 'pooling': 'last-token', 'min_dim': 32, 'max_dim': 1024},
    'none': {'query_template': '{text}', 'pooling': 'unknown'},
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): raise ProviderError('provider redirects are forbidden')


def _check_dim(dimensions, preset):
    if dimensions is None: return None
    if isinstance(dimensions, bool) or not isinstance(dimensions, int) or not 1 <= dimensions <= 8192:
        raise ProviderConfigError('dimensions must be a positive integer')
    p = PRESETS.get(preset, {})
    if 'min_dim' in p and not p['min_dim'] <= dimensions <= p['max_dim']:
        raise ProviderConfigError(f"{preset} supports MRL dimensions {p['min_dim']}..{p['max_dim']}")
    return dimensions


class _EmbedderBase:
    preset = 'none'

    def _setup(self, dimensions, preset, query_template, task):
        self.preset = preset if preset in PRESETS else 'none'
        self.dimensions = _check_dim(dimensions, self.preset)
        self.query_template = query_template or PRESETS[self.preset]['query_template']
        self.task = task or DEFAULT_TASK
        if '{text}' not in self.query_template: raise ProviderConfigError('query template must contain {text}')

    def query_text(self, query):
        return self.query_template.replace('{task}', self.task).replace('{text}', query)

    def _finish(self, raw):
        return vectors.normalize(raw, self.dimensions)


class Provider(_EmbedderBase):
    """OpenAI-compatible HTTP client for embeddings and chat completions."""

    def __init__(self, base, model, key='', allow_remote=False, timeout=30, dimensions=None, preset='none',
                 query_template=None, task=None, revision=None, batch_size=32, response_format='json_schema',
                 no_think=False, extra=None):
        if not isinstance(base, str): raise ProviderConfigError('provider URL required')
        p = urlsplit(base)
        if p.username or p.password or p.query or p.fragment or p.scheme not in {'http', 'https'}:
            raise ProviderConfigError('invalid provider URL')
        if p.hostname not in LOOPBACK and (not allow_remote or p.scheme != 'https'):
            raise ProviderConfigError('remote provider requires explicit consent and HTTPS',
                                      hint='set MM_ALLOW_REMOTE=1 and use https://, or use 127.0.0.1 for a local server (localhost is not trusted to resolve to loopback)')
        if not model: raise ProviderConfigError('model required')
        if response_format not in judge_mod.RESPONSE_FORMATS: raise ProviderConfigError('response_format must be json_schema, json_object or none')
        self.base, self.model, self.key = base.rstrip('/'), model, key
        self.identity = self.base + '|' + model  # 0.1 identity, kept for display
        self.timeout, self.revision, self.batch_size = timeout, revision, batch_size
        self.response_format, self.no_think, self.extra = response_format, no_think, extra or {}
        self._setup(dimensions, preset, query_template, task)

    def post(self, path, payload):
        headers = {'Content-Type': 'application/json'}
        if self.key: headers['Authorization'] = 'Bearer ' + self.key
        req = urllib.request.Request(self.base + path, data=json.dumps(payload).encode(), headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            with opener.open(req, timeout=self.timeout) as r:
                data = r.read(4_000_001)
        except urllib.error.HTTPError as e:
            raise ProviderError(f'provider returned HTTP {e.code}', status=e.code) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise ProviderError('provider unreachable: ' + type(e).__name__) from None
        if len(data) > 4_000_000: raise ProviderError('response too large')
        try:
            return json.loads(data)
        except ValueError:
            raise ModelOutputInvalid('provider returned invalid JSON') from None

    # -- embeddings
    def _vectors(self, obj, n):
        try:
            items = sorted(obj['data'], key=lambda d: d.get('index', 0))
            if len(items) != n: raise ValueError
            return [self._finish(d['embedding']) for d in items]
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            raise ModelOutputInvalid('invalid embedding response') from e

    def embed(self, text):
        return self._vectors(self.post('/embeddings', {'model': self.model, 'input': text}), 1)[0]

    def embed_batch(self, texts):
        out = []
        for i in range(0, len(texts), self.batch_size):
            chunk = texts[i:i + self.batch_size]
            out.extend(self._vectors(self.post('/embeddings', {'model': self.model, 'input': chunk}), len(chunk)))
        return out

    def descriptor(self):
        return {'backend': 'openai-http', 'endpoint': self.base, 'model': self.model, 'revision': self.revision,
                'dimensions': self.dimensions, 'pooling': 'server-defined', 'normalize': 'l2', 'document_template': '{text}'}

    # -- chat / judge
    def chat(self, messages, max_tokens=300, schema_format=None):
        payload = dict(self.extra, model=self.model, temperature=0, max_tokens=max_tokens, messages=messages)
        if schema_format: payload['response_format'] = schema_format
        obj = self.post('/chat/completions', payload)
        try:
            return obj['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError) as e:
            raise ModelOutputInvalid('invalid chat response') from e

    def judge(self, text):
        raw = self.chat(judge_mod.messages(text, self.no_think), schema_format=judge_mod.RESPONSE_FORMATS[self.response_format])
        return judge_mod.parse(raw)

    def judge_descriptor(self):
        return {'backend': 'openai-http', 'endpoint': self.base, 'model': self.model, 'revision': self.revision,
                'response_format': self.response_format, 'no_think': self.no_think}


def file_sha256(path, _cache={}):
    """Model files are content-addressed: the hash *is* the revision. Cached per (path, size, mtime)."""
    st = os.stat(path)
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key not in _cache:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
        _cache[key] = h.hexdigest()
    return _cache[key]


class SentenceTransformersEmbedder(_EmbedderBase):
    """In-process reference implementation (pip install 'memory-merge-local[local]')."""

    def __init__(self, model, revision=None, device=None, dimensions=None, preset='qwen3-embedding',
                 query_template=None, task=None, max_seq_length=8192, batch_size=16, allow_remote=False):
        local = Path(model).is_dir()
        weights = sorted(Path(model).glob('*.safetensors')) if local else []
        # Decide identity and network use before loading anything: a hub id needs a pinned revision
        # (otherwise the fingerprint could silently change) and an explicit consent to download.
        revision = revision or (file_sha256(weights[0]) if weights else None)
        if revision is None:
            raise ProviderConfigError('pin a model revision (MM_EMBED_REVISION) so the vector fingerprint is immutable')
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise DependencyMissing('sentence-transformers is not installed', hint="pip install 'memory-merge-local[local]'") from e
        self._setup(dimensions, preset, query_template, task)
        self.model_name, self.batch_size, self.revision = model, batch_size, revision
        self.m = SentenceTransformer(model, revision=None if local else revision, device=device,
                                     local_files_only=local or not allow_remote)
        self.m.max_seq_length = max_seq_length  # the repo pins none; 8192 matches the official evaluation

    def embed(self, text):
        return self.embed_batch([text])[0]

    def embed_batch(self, texts):
        raw = self.m.encode(texts, batch_size=self.batch_size, normalize_embeddings=False, convert_to_numpy=True)
        return [self._finish([float(x) for x in row]) for row in raw]

    def descriptor(self):
        return {'backend': 'sentence-transformers', 'model': self.model_name, 'revision': self.revision,
                'dimensions': self.dimensions, 'pooling': 'model-config', 'normalize': 'l2', 'document_template': '{text}',
                'max_seq_length': self.m.max_seq_length}


class LlamaCppEmbedder(_EmbedderBase):
    """In-process GGUF embeddings via llama-cpp-python (pip install 'memory-merge-local[gguf]')."""

    def __init__(self, path, dimensions=None, preset='qwen3-embedding', query_template=None, task=None,
                 n_ctx=8192, n_threads=None, n_gpu_layers=0):
        try:
            import llama_cpp
        except ImportError as e:
            raise DependencyMissing('llama-cpp-python is not installed', hint="pip install 'memory-merge-local[gguf]'") from e
        self._setup(dimensions, preset, query_template, task)
        self.path = str(Path(path).resolve())
        self.revision = file_sha256(self.path)
        pooling = llama_cpp.LLAMA_POOLING_TYPE_LAST if PRESETS[self.preset]['pooling'] == 'last-token' else llama_cpp.LLAMA_POOLING_TYPE_MEAN
        self.llm = llama_cpp.Llama(model_path=self.path, embedding=True, pooling_type=pooling, n_ctx=n_ctx,
                                   n_threads=n_threads, n_gpu_layers=n_gpu_layers, verbose=False)
        self.pooling = 'last-token' if pooling == llama_cpp.LLAMA_POOLING_TYPE_LAST else 'mean'

    def embed(self, text):
        v = self.llm.embed(text, normalize=False)
        return self._finish(v[0] if v and isinstance(v[0], list) else v)

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]

    def descriptor(self):
        return {'backend': 'llama-cpp', 'model': Path(self.path).name, 'revision': 'sha256:' + self.revision,
                'dimensions': self.dimensions, 'pooling': self.pooling, 'normalize': 'l2', 'document_template': '{text}'}


class LlamaCppJudge:
    """In-process GGUF judge with grammar-constrained JSON (llama.cpp compiles the schema to a grammar)."""

    def __init__(self, path, n_ctx=4096, n_threads=None, n_gpu_layers=0, no_think=False):
        try:
            import llama_cpp
        except ImportError as e:
            raise DependencyMissing('llama-cpp-python is not installed', hint="pip install 'memory-merge-local[gguf]'") from e
        self.path = str(Path(path).resolve())
        self.revision = file_sha256(self.path)
        self.no_think = no_think
        self.llm = llama_cpp.Llama(model_path=self.path, n_ctx=n_ctx, n_threads=n_threads, n_gpu_layers=n_gpu_layers, verbose=False)

    def judge(self, text):
        out = self.llm.create_chat_completion(messages=judge_mod.messages(text, self.no_think), temperature=0, max_tokens=300,
                                              response_format={'type': 'json_object', 'schema': judge_mod.SCHEMA})
        return judge_mod.parse(out['choices'][0]['message']['content'])

    def judge_descriptor(self):
        return {'backend': 'llama-cpp', 'model': Path(self.path).name, 'revision': 'sha256:' + self.revision,
                'response_format': 'grammar', 'no_think': self.no_think}


def embedding_fingerprint(provider, dim):
    """Immutable identity of a vector space. `dim` is the observed output dimension."""
    d = provider.descriptor() if hasattr(provider, 'descriptor') else {'legacy_identity': getattr(provider, 'identity', repr(provider))}
    payload = json.dumps(dict(d, observed_dim=dim), sort_keys=True, ensure_ascii=False)
    return 'emb-' + hashlib.sha256(payload.encode()).hexdigest()[:20]


def judge_fingerprint(provider):
    d = provider.judge_descriptor() if hasattr(provider, 'judge_descriptor') else {'legacy_identity': getattr(provider, 'identity', repr(provider))}
    return judge_mod.fingerprint(d)


def timed(fn, *args):
    t = time.perf_counter()
    out = fn(*args)
    return out, round((time.perf_counter() - t) * 1000)


def __getattr__(name):
    # 0.1 exported MemoryService from this module; keep that import path working.
    if name == 'MemoryService':
        from .service import MemoryService
        return MemoryService
    raise AttributeError(name)
