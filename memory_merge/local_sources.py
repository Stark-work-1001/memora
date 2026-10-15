"""Local agent archives and capability catalog, always parsed as data, never executed.

The UI operator selects/imports local files. MCP peers cannot alter filesystem sources.
Discovery never traverses arbitrary drives or reads auth/config/env files. Imported tool
definitions, skills, personas and team descriptions become pending knowledge candidates.
"""
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re

from . import sessions, text
from .errors import InvalidInput, MemoryMergeError
from .store import scope

SKIP = {'node_modules', 'target', '.git', '.venv', 'venv', 'release', '__pycache__', 'dist', 'build'}
KINDS = {'history', 'skill', 'plugin', 'expert', 'team', 'swarm', 'tool', 'instructions', 'knowledge', 'mcp-graph', 'env', 'mcp', 'ghost', 'organization', 'subagent'}
MAX_FILE = 64 * 1024 * 1024


def local_path(value):
    if not isinstance(value, str) or not value or '\x00' in value: raise InvalidInput('local directory required')
    if value.startswith(('\\\\', '//')) or PureWindowsPath(value).drive.startswith('\\\\'):
        raise InvalidInput('network and device paths are not supported')
    return Path(value).expanduser().resolve()


def defaults():
    home = Path.home()
    candidates = [
        ('codex-history', 'Codex 对话', home / '.codex/sessions', 'history', 'codex'),
        ('codex-history-archive', 'Codex 已归档对话', home / '.codex/archived_sessions', 'history', 'codex'),
        ('claude-history', 'Claude Code 对话', home / '.claude/projects', 'history', 'claude-code'),
        ('gemini-history', 'Gemini CLI 对话', home / '.gemini/tmp', 'history', 'gemini'),
        ('opencode-history', 'OpenCode 导出', home / '.local/share/opencode/storage', 'history', 'opencode'),
        ('codex-skills', 'Codex Skills', home / '.codex/skills', 'skill', 'codex'),
        ('codex-plugins', 'Codex Plugins', home / '.codex/plugins/cache', 'plugin', 'codex'),
        ('claude-skills', 'Claude Skills', home / '.claude/skills', 'skill', 'claude-code'),
        ('claude-plugins', 'Claude Plugins', home / '.claude/plugins/cache', 'plugin', 'claude-code'),
        ('claude-agents', 'Claude 专家定义', home / '.claude/agents', 'expert', 'claude-code'),
        ('codex-agents', 'Codex 专家定义', home / '.codex/agents', 'expert', 'codex'),
        ('claude-teams', 'Claude 团队', home / '.claude/teams', 'team', 'claude-code'),
    ]
    return [dict(id=i, name=n, root=str(r), kind=k, agent=a) for i,n,r,k,a in candidates]


def _plain(value):
    if isinstance(value, str): return value
    if isinstance(value, list): return '\n'.join(filter(None, (_plain(v) for v in value)))
    if isinstance(value, dict):
        if value.get('type') == 'tool_result': return '[tool_result] ' + _plain(value.get('content', ''))
        if value.get('type') in {'tool_use', 'function_call'}:
            return '[tool] ' + str(value.get('name', 'unknown')) + '\n' + json.dumps(value.get('input', value.get('arguments', {})), ensure_ascii=False)
        return value.get('text', '') if isinstance(value.get('text', ''), str) else ''
    return ''


def parse_history(raw, agent, external_id):
    """Common Codex/Claude/Gemini and exported JSONL schemas. Unsupported records are counted."""
    try:
        if raw.lstrip().startswith('['): items = json.loads(raw)
        elif raw.lstrip().startswith('{'):
            try:
                obj = json.loads(raw)
                if 'messages' in obj or 'turns' in obj: items = obj.get('messages', obj.get('turns'))
                else: items = [obj]
            except ValueError: items = [json.loads(line) for line in raw.splitlines() if line.strip()]
        else: raise ValueError
        if not isinstance(items, list): raise ValueError
    except (ValueError, TypeError): raise InvalidInput('history is not valid JSON / JSONL') from None
    # Native Memory Merge session exports preserve tool-role turns and retry-safe sequence ids.
    if items and isinstance(items[0], dict) and items[0].get('type') == 'session':
        return items, [], {'unsupported': 0, 'format': 'memory-merge-jsonl'}
    records = [{'type': 'session', 'id': external_id, 'agent': agent, 'title': f'{agent} · {external_id[:60]}'}]
    capabilities, unsupported, seq = [], 0, 0
    for item in items:
        if not isinstance(item, dict): unsupported += 1; continue
        kind = item.get('type')
        payload = item.get('payload', item)
        if not isinstance(payload, dict): unsupported += 1; continue
        for field, catalog_kind in [('tools','tool'),('skills','skill'),('plugins','plugin'),('agents','expert'),('team','team'),('swarm','swarm'),('mcp','mcp'),('environment','env'),('ghosts','ghost'),('organizations','organization'),('subagents','subagent')]:
            definitions=payload.get(field)
            if isinstance(definitions,(dict,list)):
                capabilities.append((catalog_kind,field,json.dumps(definitions,ensure_ascii=False)))
        if kind == 'session_meta':
            # Provenance can include parent / team / swarm metadata. It remains quoted catalog data.
            meta = {k:payload[k] for k in ('id','source','agent_role','agent_nickname','forked_from_id','parent_thread_id') if k in payload}
            records[0]['meta'] = meta
            if isinstance(payload.get('id'),str):
                records[0]['id']=external_id=payload['id'][:200]
            if any(k in meta for k in ('agent_role','forked_from_id','parent_thread_id')):
                capabilities.append(('team', '会话协作信息', json.dumps(meta, ensure_ascii=False)))
            continue
        if kind in {'turn_context', 'token_count', 'progress', 'file-history-snapshot', 'queue-operation'}: continue
        message = item.get('message', payload)
        if not isinstance(message, dict): message = payload
        subtype = payload.get('type')
        role = message.get('role')
        content = _plain(message.get('content', ''))
        if kind == 'event_msg' and subtype in {'user_message', 'agent_message'}:
            # Codex response_item contains the canonical turn; avoid double archive of event echoes.
            continue
        if kind == 'response_item' and subtype in {'function_call', 'custom_tool_call'}:
            role = 'tool'
            name = str(payload.get('name', 'unknown'))[:150]
            args = payload.get('arguments', payload.get('input', ''))
            content = '[tool_call] ' + name + '\n' + (args if isinstance(args, str) else json.dumps(args, ensure_ascii=False))
            capabilities.append(('tool', name, '工具调用示例（不是完整工具定义）：\n' + content))
        elif kind == 'response_item' and subtype in {'function_call_output', 'custom_tool_call_output'}:
            role = 'tool'; content = '[tool_result] ' + _plain(payload.get('output', ''))
        elif kind == 'tool_result': role = 'tool'; content = _plain(item.get('content', ''))
        elif role is None and item.get('type') in {'user', 'assistant', 'model'}:
            role = 'assistant' if item['type'] == 'model' else item['type']
            content = _plain(item.get('content', item.get('text', '')))
        if role == 'model': role = 'assistant'
        if isinstance(message.get('content'), list):
            for part in message['content']:
                if isinstance(part, dict) and part.get('type') == 'tool_use':
                    name = str(part.get('name', 'unknown'))[:150]
                    capabilities.append(('tool', name, '工具调用示例：\n' + _plain(part)))
        if role not in sessions.ROLES or not content.strip(): unsupported += 1; continue
        seq += 1
        records.append({'type': 'turn', 'session': external_id, 'seq': seq, 'role': role,
                        'content': content, 'created': item.get('timestamp') if isinstance(item.get('timestamp'), str) else None})
    return records, capabilities, {'unsupported': unsupported, 'format': agent, 'turns': seq}


class LocalSources:
    def __init__(self, store):
        self.store = store
        self.path = store.root / 'agent-sources.json'
        self.sources = json.loads(self.path.read_text('utf-8')) if self.path.exists() else defaults()

    def list(self):
        return [dict(s, exists=local_path(s['root']).is_dir()) for s in self.sources]

    def save(self, body):
        sid, kind = body.get('id'), body.get('kind')
        if not isinstance(sid, str) or not re.fullmatch(r'[\w-]{1,80}', sid): raise InvalidInput('source id: 1..80 letters/digits/underscore/hyphen')
        if kind not in KINDS: raise InvalidInput('unsupported source kind')
        root = local_path(body.get('root'))
        if not root.is_dir(): raise InvalidInput('source directory does not exist')
        name, agent = body.get('name', sid), body.get('agent', 'generic')
        if not isinstance(name, str) or not 1 <= len(name) <= 120: raise InvalidInput('source name required')
        if not isinstance(agent, str) or not 1 <= len(agent) <= 80 or agent == 'memory-agent': raise InvalidInput('invalid agent name')
        source = dict(id=sid, name=name, root=str(root), kind=kind, agent=agent)
        updated = [s for s in self.sources if s['id'] != sid] + [source]
        if len(updated)>64: raise InvalidInput('at most 64 local sources')
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(updated, ensure_ascii=False, indent=2),'utf-8');os.replace(tmp,self.path)
        self.sources=updated
        return source

    def source(self, sid):
        if not isinstance(sid,str): raise InvalidInput('source id required')
        out=next((s for s in self.sources if s['id']==sid), None)
        if out is None: raise InvalidInput('source not found')
        return out

    @staticmethod
    def classify(path, source):
        name = path.name.lower()
        if name in {'auth.json','credentials.json','token.json','tokens.json','settings.json'} or name.startswith('.env'):
            return None
        if name in {'skill.md', 'agents.md', 'claude.md', 'gemini.md'}:
            return 'skill' if name=='skill.md' else 'instructions'
        if name in {'plugin.json', 'manifest.json'} and source['kind']=='plugin': return 'plugin'
        if source['kind']=='history' and path.suffix.lower() in {'.json','.jsonl'}: return 'history'
        if source['kind'] in {'expert','team','swarm','tool'} and path.suffix.lower() in {'.md','.json','.toml','.yaml','.yml'}: return source['kind']
        if source['kind']=='knowledge' and path.suffix.lower() in {'.md','.txt'}: return 'knowledge'
        if source['kind']=='mcp-graph' and path.suffix.lower() in {'.json','.jsonl'}: return 'mcp-graph'
        return None

    def discover(self, sid, offset=0):
        source=self.source(sid);root=local_path(source['root'])
        if not root.is_dir(): return {'items': [], 'total': 0, 'next_offset': None, 'missing': True}
        found=[]
        for directory, dirs, filenames in os.walk(root, followlinks=False):
            dirs[:]=sorted(d for d in dirs if d not in SKIP and not (Path(directory)/d).is_symlink())
            for name in sorted(filenames):
                path=Path(directory)/name
                if path.is_symlink(): continue
                kind=self.classify(path,source)
                if kind:
                    try: size=path.stat().st_size
                    except OSError: continue
                    found.append({'path':str(path.relative_to(root)), 'kind':kind, 'size':size,'importable':size<=MAX_FILE})
        if not isinstance(offset,int) or offset<0: raise InvalidInput('invalid discovery offset')
        return {'items':found[offset:offset+200], 'total':len(found), 'next_offset':offset+200 if len(found)>offset+200 else None,
                'note':'只列出受支持的文件；分页不会自动导入。工具调用示例不等于完整工具定义。'}

    def import_files(self, body):
        source=self.source(body.get('source'));root=local_path(source['root']);project=scope(body.get('project','default'))
        paths=body.get('paths')
        if not isinstance(paths,list) or not 1<=len(paths)<=50: raise InvalidInput('select 1..50 files per import')
        reports=[]
        for relative in paths:
            try:
                from .ingest import safe_relative
                safe_relative(relative)
                full=(root/relative).resolve()
                if not full.is_relative_to(root) or not full.is_file(): raise InvalidInput('file is outside source or missing')
                kind=self.classify(full,source)
                if not kind: raise InvalidInput('unsupported source file')
                if full.stat().st_size>MAX_FILE: raise InvalidInput('file exceeds 64 MiB; export a smaller archive')
                raw=full.read_bytes()
                if len(raw)>MAX_FILE: raise InvalidInput('file exceeds size limit')
                raw=raw.decode('utf-8-sig')
                uri='local:'+str(full)
                digest=hashlib.sha256(raw.encode()).hexdigest()
                capabilities=[]
                if kind=='mcp-graph':
                    from .memory_exchange import import_graph
                    reports.append({'path':relative, 'graph':import_graph(self.store,project,raw,uri[:300])})
                    continue
                if kind=='history':
                    external=hashlib.sha256(str(full).encode()).hexdigest()[:24]
                    records,capabilities,info=parse_history(raw,source['agent'],external)
                    records=[dict(r, project=project) if r.get('type')=='session' else r for r in records]
                    if len(records)<=1: raise InvalidInput('no supported dialogue turns found')
                    report=sessions.import_records(self.store,records,project,agent=source['agent'],actor='local-source')
                    reports.append({'path':relative,'archive':report,'parser':info})
                else:
                    capabilities=[(kind, full.stem, raw)]
                    if full.suffix.lower() in {'.md','.markdown','.txt'} and len(raw)<=80000:
                        from .documents import Documents
                        from .errors import NotFound
                        documents=Documents(self.store);slug='source-'+hashlib.sha256((project+'\0'+str(full)).encode()).hexdigest()[:32]
                        try:
                            previous=documents.read(project,slug,'shared',drafts=True)
                            version=previous['version']
                        except NotFound:previous=None;version=0
                        clean_document=text.redact(raw)[0]
                        if previous is None or previous['content']!=clean_document:
                            documents.put(project,slug,'shared',full.stem[:160],clean_document,version,
                                source=uri[:300],recorded_date=documents.infer_date(raw,full.name),origin_uri=uri[:1500],group_title=source['name'])
                captured=[]
                seen=set()
                from .control import Control, ASSET_KINDS
                catalog=Control(self.store)
                for ckind,name,content in capabilities:
                    # Keep bounded examples per tool per file; full calls remain in the turn archive.
                    key=(ckind,name)
                    if key in seen: continue
                    seen.add(key)
                    heading=f'资源类型：{ckind}\n所属智能体：{source["agent"]}\n名称：{name}\n来源：{full}\n'
                    clean,_=text.redact(heading+content)
                    resource_kind={'expert':'ghost','team':'organization','swarm':'organization','instructions':'knowledge'}.get(ckind,ckind)
                    if resource_kind in ASSET_KINDS:
                        catalog.save_asset({'id':hashlib.sha256((project+'\0'+uri+'\0'+ckind+'\0'+name).encode()).hexdigest(),
                            'project':project,'kind':resource_kind,'title':str(name)[:160] or full.stem[:160],
                            'agent':source['agent'],'description':clean[:16000],
                            'payload':{'source':uri,'sha256':digest,'source_kind':ckind,'truncated':len(clean)>16000,
                                'definition_type':'invocation example' if '调用示例' in content else 'declared description'}})
                    # Long Skills/personas are split, with no silent content truncation.
                    for start in range(0,len(clean),14000):
                        chunk=clean[start:start+14000]
                        m=self.store.capture(project,chunk,uri[:300],event_id=f'{digest}:{ckind}:{name[:80]}:{start}',
                            category='knowledge',tags=[ckind,'agent:'+source['agent'][:50]],actor='local-source')
                        captured.append(m['id'])
                if kind!='history': reports.append({'path':relative,'kind':kind,'memories':captured,'status':'pending'})
                elif captured: reports[-1]['capabilities']=captured
                catalog.event(project,'source_import',source['id'],{'path':relative,'kind':kind,'capabilities':len(seen)})
            except (MemoryMergeError, OSError, UnicodeError) as e:
                reports.append({'path':relative,'error':str(e)[:200]})
        self.store.flush()
        return {'files':reports,'approval':'human_required','executed':False}
