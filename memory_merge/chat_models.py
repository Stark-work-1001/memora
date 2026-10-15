"""Chat adapters: bounded HTTP streams and optional C++/GGUF inference.

Profiles contain environment variable names, never credentials. HTTP transport inherits
the memory provider's no-proxy/no-redirect policy and explicit remote HTTPS consent.
"""
import json
import math
import os
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path

from .errors import DependencyMissing, InvalidInput, ModelOutputInvalid, ProviderError
from .providers import NoRedirect, Provider

MAX_RESPONSE = 4_000_000


def number(value, name, lo, hi, integer=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not lo <= value <= hi
            or (integer and not isinstance(value, int))):
        raise InvalidInput(f'{name}: {lo}..{hi}' + (' (integer)' if integer else ''))
    return value


def profile(value):
    if not isinstance(value, dict): raise InvalidInput('model profile must be an object')
    kind = value.get('kind', 'openai')
    if kind not in {'openai', 'ollama', 'gguf'}: raise InvalidInput('kind: openai, ollama or gguf')
    out = {'kind': kind}
    for field, default, size in [('id', '', 80), ('name', '', 120), ('model', '', 200),
                                 ('base', '', 1000), ('key_env', '', 100), ('path', '', 2000)]:
        v = value.get(field, default)
        if not isinstance(v, str) or len(v) > size or any(c in v for c in '\r\n\x00'):
            raise InvalidInput(f'invalid {field}')
        out[field] = v.strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', out['id']): raise InvalidInput('invalid profile id')
    if not out['name'] or not out['model']: raise InvalidInput('name and model required')
    if out['key_env'] and not re.fullmatch(r'[A-Z_][A-Z0-9_]*', out['key_env']):
        raise InvalidInput('key_env must be an environment variable name')
    if type(value.get('remote', False)) is not bool: raise InvalidInput('remote must be boolean')
    out['remote'] = value.get('remote', False)
    if kind != 'gguf':
        Provider(out['base'], out['model'], allow_remote=out['remote'])
    else:
        if not out['path'] or Path(out['path']).suffix.lower() != '.gguf':
            raise InvalidInput('a local .gguf path is required')
        out['n_ctx'] = number(value.get('n_ctx', 8192), 'n_ctx', 512, 131072, True)
        out['gpu_layers'] = number(value.get('gpu_layers', 0), 'gpu_layers', -1, 256, True)
    return out


class HTTPChat:
    def __init__(self, config):
        self.config = profile(config)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, path, payload=None):
        p = self.config
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        key = os.environ.get(p['key_env'], '') if p['key_env'] else ''
        if p['key_env'] and not key: raise ProviderError(f"set environment variable {p['key_env']} before starting")
        if key: headers['Authorization'] = 'Bearer ' + key
        req = urllib.request.Request(p['base'].rstrip('/') + path,
                                     data=None if payload is None else json.dumps(payload).encode(), headers=headers)
        try:
            return self.opener.open(req, timeout=45)
        except urllib.error.HTTPError as e:
            raise ProviderError(f'model endpoint returned HTTP {e.code}') from None
        except (OSError, urllib.error.URLError) as e:
            raise ProviderError(f'model endpoint unavailable ({type(e).__name__})') from None

    def json(self, path, payload=None):
        try:
            with self.request(path, payload) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE: raise ProviderError('model response too large')
            out = json.loads(raw)
            if not isinstance(out, dict): raise ValueError
            if out.get('error'): raise ProviderError('model endpoint reported an error')
            return out
        except (ValueError, UnicodeError):
            raise ModelOutputInvalid('invalid model JSON response') from None

    def models(self):
        ollama = self.config['kind'] == 'ollama'
        out = self.json('/api/tags' if ollama else '/models')
        items = out.get('models' if ollama else 'data', [])
        if not isinstance(items, list): raise ModelOutputInvalid('invalid models list')
        return [m.get('name' if ollama else 'id') for m in items if isinstance(m, dict)]

    def control(self, action):
        if self.config['kind'] != 'ollama':
            raise InvalidInput('load/unload are available for Ollama and in-process GGUF only')
        if action == 'status': return self.json('/api/ps')
        return self.json('/api/chat', {'model': self.config['model'], 'messages': [], 'stream': False,
                                       'keep_alive': 0 if action == 'unload' else '10m'})

    def stream(self, messages, settings, cancel):
        ollama = self.config['kind'] == 'ollama'
        payload = {'model': self.config['model'], 'messages': messages, 'stream': True}
        if ollama:
            payload['options'] = {'temperature': settings['temperature'], 'num_predict': settings['max_tokens']}
            payload['keep_alive'] = '10m'
        else:
            payload.update(temperature=settings['temperature'], max_tokens=settings['max_tokens'])
        try:
            with self.request('/api/chat' if ollama else '/chat/completions', payload) as response:
                total, completed = 0, False
                while not cancel.is_set():
                    line = response.readline(262145)
                    if not line: break
                    total += len(line)
                    if len(line) > 262144 or total > MAX_RESPONSE: raise ProviderError('model stream too large')
                    line = line.decode('utf-8').strip()
                    if not line or line.startswith(':'): continue
                    if not ollama:
                        if not line.startswith('data:'): continue
                        line = line[5:].strip()
                        if line == '[DONE]': completed = True; break
                    obj = json.loads(line)
                    if obj.get('error'): raise ProviderError('model stream reported an error')
                    if ollama:
                        chunk = obj.get('message', {}).get('content', '')
                        completed = obj.get('done', False)
                    else:
                        choices = obj.get('choices') or []
                        chunk = choices[0].get('delta', {}).get('content') or '' if choices else ''
                        if choices and choices[0].get('finish_reason') is not None: completed = True
                    if not isinstance(chunk, str): raise ValueError
                    if chunk: yield chunk
                    if ollama and completed: break
                if not completed and not cancel.is_set(): raise ProviderError('model stream ended before completion')
        except (ValueError, KeyError, TypeError, AttributeError, UnicodeError):
            raise ModelOutputInvalid('invalid model stream') from None
        except (OSError, urllib.error.URLError) as e:
            raise ProviderError(f'model stream interrupted ({type(e).__name__})') from None


class GGUFChat:
    """Lazy llama-cpp-python adapter. The C++ model stays loaded until explicit unload."""
    def __init__(self, config):
        self.config, self.llm, self.lock = profile(config), None, threading.Lock()

    def _load(self):
        if self.llm is None:
            if not Path(self.config['path']).is_file(): raise InvalidInput('GGUF file does not exist')
            try: from llama_cpp import Llama
            except ImportError: raise DependencyMissing('install the gguf extra: pip install ".[gguf]"') from None
            self.llm = Llama(model_path=self.config['path'], n_ctx=self.config['n_ctx'],
                             n_gpu_layers=self.config['gpu_layers'], verbose=False)

    def models(self): return [self.config['model']]

    def control(self, action):
        if not self.lock.acquire(blocking=False): raise InvalidInput('GGUF model is generating; stop it first')
        try:
            if action == 'load': self._load()
            elif action == 'unload' and self.llm is not None:
                self.llm.close(); self.llm = None
            return {'loaded': self.llm is not None, 'model': self.config['model']}
        finally: self.lock.release()

    def stream(self, messages, settings, cancel):
        with self.lock:
            self._load()
            stream = self.llm.create_chat_completion(messages=messages, stream=True,
                temperature=settings['temperature'], max_tokens=settings['max_tokens'])
            try:
                for part in stream:
                    if cancel.is_set(): break
                    chunk = part['choices'][0].get('delta', {}).get('content', '')
                    if chunk: yield chunk
            finally:
                close = getattr(stream, 'close', None)
                if close: close()


def adapter(config):
    return GGUFChat(config) if config['kind'] == 'gguf' else HTTPChat(config)
