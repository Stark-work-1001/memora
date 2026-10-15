"""Configuration comes from environment variables only: MCP hosts pass env per server, and nothing
is read from files a capture client could edit. `summary()` shows the effective configuration
without secrets (used by `doctor`)."""
import json
import os
import sys
from pathlib import Path

from .errors import ProviderConfigError


def default_data_dir(env=None):
    env = os.environ if env is None else env
    if env.get('MM_DATA'): return Path(env['MM_DATA'])
    # 0.1 defaulted to <checkout>/data. Keep using it if it holds a database, or upgrading would
    # silently present an empty store.
    legacy = Path(__file__).resolve().parents[1] / 'data'
    if (legacy / 'memory.sqlite3').exists(): return legacy
    if sys.platform == 'win32':
        base = Path(env.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(env.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    return base / 'memory-merge'


def _int(env, key, default=None):
    v = env.get(key)
    if v in (None, ''): return default
    try:
        return int(v)
    except ValueError:
        raise ProviderConfigError(f'{key} must be an integer') from None


def _flag(env, key):
    return env.get(key) == '1'


def _need(env, key, why):
    if not env.get(key): raise ProviderConfigError(f'{key} is required {why}')
    return env[key]


def embedding_from_env(env=None):
    from . import providers
    env = os.environ if env is None else env
    backend = env.get('MM_EMBED_BACKEND') or ('openai' if env.get('MM_EMBED_URL') else None)
    if not backend: return None
    common = dict(dimensions=_int(env, 'MM_EMBED_DIM'), query_template=env.get('MM_EMBED_QUERY_TEMPLATE'), task=env.get('MM_EMBED_TASK'))
    if backend == 'openai':
        return providers.Provider(_need(env, 'MM_EMBED_URL', 'for the openai backend'), env.get('MM_EMBED_MODEL', ''),
                                  env.get('MM_EMBED_KEY', ''), _flag(env, 'MM_ALLOW_REMOTE'), timeout=_int(env, 'MM_EMBED_TIMEOUT', 30),
                                  preset=env.get('MM_EMBED_PRESET', 'none'), revision=env.get('MM_EMBED_REVISION'),
                                  batch_size=_int(env, 'MM_EMBED_BATCH', 32), **common)
    if backend == 'sentence-transformers':
        return providers.SentenceTransformersEmbedder(_need(env, 'MM_EMBED_MODEL', 'for sentence-transformers (hub id or path)'),
                                                      revision=env.get('MM_EMBED_REVISION'), device=env.get('MM_EMBED_DEVICE'),
                                                      preset=env.get('MM_EMBED_PRESET', 'qwen3-embedding'),
                                                      allow_remote=_flag(env, 'MM_ALLOW_REMOTE'), **common)
    if backend == 'llama-cpp':
        return providers.LlamaCppEmbedder(_need(env, 'MM_EMBED_PATH', 'for llama-cpp (path to a .gguf file)'),
                                          preset=env.get('MM_EMBED_PRESET', 'qwen3-embedding'),
                                          n_gpu_layers=_int(env, 'MM_EMBED_GPU_LAYERS', 0), **common)
    raise ProviderConfigError('MM_EMBED_BACKEND must be openai, sentence-transformers or llama-cpp')


def judge_from_env(env=None):
    from . import providers
    env = os.environ if env is None else env
    backend = env.get('MM_JUDGE_BACKEND') or ('openai' if env.get('MM_JUDGE_URL') else None)
    if not backend: return None
    if backend == 'openai':
        try:
            extra = json.loads(env.get('MM_JUDGE_EXTRA') or '{}')
        except ValueError:
            raise ProviderConfigError('MM_JUDGE_EXTRA must be a JSON object') from None
        if not isinstance(extra, dict): raise ProviderConfigError('MM_JUDGE_EXTRA must be a JSON object')
        return providers.Provider(_need(env, 'MM_JUDGE_URL', 'for the openai backend'), env.get('MM_JUDGE_MODEL', ''),
                                  env.get('MM_JUDGE_KEY', ''), _flag(env, 'MM_ALLOW_REMOTE'), timeout=_int(env, 'MM_JUDGE_TIMEOUT', 60),
                                  revision=env.get('MM_JUDGE_REVISION'), response_format=env.get('MM_JUDGE_RESPONSE_FORMAT', 'json_schema'),
                                  no_think=_flag(env, 'MM_JUDGE_NO_THINK'), extra=extra)
    if backend == 'llama-cpp':
        return providers.LlamaCppJudge(_need(env, 'MM_JUDGE_PATH', 'for llama-cpp (path to a .gguf file)'),
                                       n_gpu_layers=_int(env, 'MM_JUDGE_GPU_LAYERS', 0), no_think=_flag(env, 'MM_JUDGE_NO_THINK'))
    raise ProviderConfigError('MM_JUDGE_BACKEND must be openai or llama-cpp')


SECRET_KEYS = ('MM_EMBED_KEY', 'MM_JUDGE_KEY')


def summary(env=None):
    env = os.environ if env is None else env
    shown = {k: ('<set>' if k in SECRET_KEYS else v) for k, v in sorted(env.items()) if k.startswith('MM_')}
    return {'data_dir': str(default_data_dir(env)), 'environment': shown,
            'review_tools': _flag(env, 'MM_ENABLE_REVIEW'), 'agent_confirm_allowed': _flag(env, 'MM_TRUST_AGENT_CONFIRM'),
            'remote_providers_allowed': _flag(env, 'MM_ALLOW_REMOTE')}
