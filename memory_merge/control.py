"""Agent coordination metadata. Never changes the Memory Merge v2 schema.

Heartbeat identity is self-reported by an already-authorized MCP client, not a
cryptographic identity. Imported archives never imply a live connection. JSON
descriptions, workflows and model results are data, never executable commands.
"""
import contextlib
import hashlib
import json
import re
import sqlite3
import time
import uuid
from urllib.parse import urlsplit

from . import sessions, text
from .errors import Conflict, InvalidInput, NotFound
from .schema import now
from .store import scope

ASSET_KINDS = ('chat', 'env', 'skill', 'mcp', 'plugin', 'ghost', 'organization', 'subagent', 'tool', 'knowledge')
STATES = ('queued', 'running', 'waiting_user', 'done', 'failed', 'cancelled', 'unknown')
ROLE_SPECS = {
    'embedding': ('向量嵌入', '将文本转换为向量；不生成回复，也不裁决记忆。'),
    'judge': ('质量判定', '按持久性、重要性、来源、敏感性、矛盾和指令风险给出审核建议。'),
    'router': ('路由选择', '在用户允许的模型或工作流中选择目标；与 Judge 分开。'),
    'curator': ('记忆提炼', '从会话提取有来源的长期记忆候选。'),
    'summarizer': ('项目归纳', '按大标题生成项目→条目的两层摘要，保留日期与引用。'),
    'classifier': ('领域与层级分类', '建议学科、资源类型、知识层级，不把分类当作真实语义关系。'),
    'documenter': ('Markdown 重构', '重组文档，保存新草稿，保留原版本和原始日期。'),
    'sql_analyst': ('结构化数据分析', '解释参数化查询得到的只读数据；不执行模型生成的 SQL。'),
    'relation': ('关系提案', '提出支持、矛盾、组成、前置等关系；需保留证据和审核。'),
    'verifier': ('结果核验', '检查输出与来源的一致性，报告缺证和冲突。'),
}
OPERATIONS = ('summarize', 'organize_markdown', 'classify', 'extract_relations', 'analyze_records', 'verify', 'assess_memory')


def short(value, name, maximum=200, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()) or len(value) > maximum or '\x00' in value:
        raise InvalidInput(f'{name}: text required, max {maximum}')
    return text.redact(value.strip())[0]


def data(value, maximum=100000):
    if not isinstance(value, dict): raise InvalidInput('metadata must be an object')
    try: raw = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError,ValueError): raise InvalidInput('metadata must be finite JSON data') from None
    if len(raw) > maximum: raise InvalidInput('metadata too large')
    return text.redact_value(value)[0]


def origin_link(value):
    if not value: return ''
    value = short(value, 'origin link', 1500)
    parsed = urlsplit(value)
    if parsed.username or parsed.password: raise InvalidInput('credentials are not allowed in origin links')
    if parsed.scheme == 'https' and parsed.hostname and not parsed.fragment and not parsed.query:
        return value
    if parsed.scheme == 'codex' and parsed.netloc == 'threads' and re.fullmatch(r'/[0-9a-fA-F-]{36}', parsed.path) and not parsed.query:
        return value
    raise InvalidInput('origin link: HTTPS without query credentials, or codex://threads/<uuid>')


class Control:
    def __init__(self, store):
        self.store = store
        self.db = store.root / 'memora-control.sqlite3'
        with self.connect() as c:
            c.executescript('''
              CREATE TABLE IF NOT EXISTS peers(id TEXT PRIMARY KEY, project TEXT NOT NULL, name TEXT NOT NULL,
                location TEXT NOT NULL, model TEXT NOT NULL, capabilities TEXT NOT NULL, seen REAL NOT NULL, ttl INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY, project TEXT NOT NULL, kind TEXT NOT NULL,
                title TEXT NOT NULL, agent TEXT NOT NULL, description TEXT NOT NULL, payload TEXT NOT NULL, updated TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS threads(id TEXT PRIMARY KEY, project TEXT NOT NULL, title TEXT NOT NULL,
                group_title TEXT NOT NULL, status TEXT NOT NULL, progress INTEGER, needs_user INTEGER NOT NULL,
                origin TEXT NOT NULL, question TEXT NOT NULL, updated TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS thread_sessions(thread TEXT NOT NULL REFERENCES threads(id), session TEXT NOT NULL,
                PRIMARY KEY(thread,session), UNIQUE(session));
              CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, project TEXT NOT NULL, thread TEXT NOT NULL,
                title TEXT NOT NULL, assigned TEXT NOT NULL, owner TEXT NOT NULL, status TEXT NOT NULL,
                progress INTEGER, question TEXT NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL,
                lease REAL NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS hierarchy(project TEXT NOT NULL, parent TEXT NOT NULL, child TEXT NOT NULL,
                kind TEXT NOT NULL, evidence TEXT NOT NULL, PRIMARY KEY(project,parent,child,kind));
              CREATE TABLE IF NOT EXISTS workflows(id TEXT PRIMARY KEY, project TEXT NOT NULL, title TEXT NOT NULL,
                dispatcher TEXT NOT NULL, steps TEXT NOT NULL, updated TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, project TEXT NOT NULL, workflow TEXT NOT NULL,
                status TEXT NOT NULL, input TEXT NOT NULL, output TEXT NOT NULL, updated TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL,
                kind TEXT NOT NULL, subject TEXT NOT NULL, detail TEXT NOT NULL, created TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS control_peers_project ON peers(project,name);
              CREATE INDEX IF NOT EXISTS control_assets_project ON assets(project,kind,updated);
              CREATE INDEX IF NOT EXISTS control_threads_project ON threads(project,updated);
              CREATE INDEX IF NOT EXISTS control_tasks_project ON tasks(project,created);
              CREATE INDEX IF NOT EXISTS control_tasks_leases ON tasks(owner,status,lease);
              CREATE INDEX IF NOT EXISTS control_runs_project ON runs(project,updated);
              CREATE INDEX IF NOT EXISTS control_events_project ON events(project,id);
            ''')

    @contextlib.contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=15); c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            with c: yield c
        finally: c.close()

    def event(self, project, kind, subject, detail):
        clean = data(detail)
        with self.connect() as c:
            c.execute('INSERT INTO events(project,kind,subject,detail,created) VALUES(?,?,?,?,?)',
                (scope(project), kind, subject, json.dumps(clean, ensure_ascii=False), now()))

    def events(self, project, kind=''):
        with self.connect() as c:
            rows = c.execute('SELECT * FROM events WHERE project=? AND (?="" OR kind=?) ORDER BY id DESC LIMIT 200',
                (scope(project), kind, kind)).fetchall()
        return [dict(r, detail=json.loads(r['detail'])) for r in rows]

    def heartbeat(self, project, peer, name, model='', location='local', capabilities=None, ttl=90):
        project, peer = scope(project), short(peer, 'peer id', 100)
        if location not in ('local','cloud','mobile','server'): raise InvalidInput('invalid peer location')
        if type(ttl) is not int or not 30 <= ttl <= 300: raise InvalidInput('heartbeat ttl: 30..300 seconds')
        value = data(capabilities or {}, 20000)
        with self.connect() as c:
            old = c.execute('SELECT project FROM peers WHERE id=?', (peer,)).fetchone()
            if old and old['project'] != project: raise Conflict('peer id belongs to another project')
            c.execute('INSERT OR REPLACE INTO peers VALUES(?,?,?,?,?,?,?,?)', (peer, project,
                short(name,'peer name',120), location, short(model,'model',200,True),
                json.dumps(value,ensure_ascii=False), time.time(), ttl))
        return next(p for p in self.peers(project) if p['id'] == peer)

    def peers(self, project):
        with self.connect() as c: rows = c.execute('SELECT * FROM peers WHERE project=? ORDER BY name', (scope(project),)).fetchall()
        return [dict(r, capabilities=json.loads(r['capabilities']), connected=time.time()-r['seen'] <= r['ttl'],
            identity='self-reported MCP peer', last_seen_age_seconds=max(0,int(time.time()-r['seen']))) for r in rows]

    def save_asset(self, body):
        project = scope(body.get('project','default')); kind = body.get('kind')
        if kind not in ASSET_KINDS: raise InvalidInput('invalid resource type')
        ident = short(body.get('id') or str(uuid.uuid4()), 'resource id',100)
        title = short(body.get('title'), 'resource title',160)
        description = short(body.get('description',''), 'description',16000,True)
        payload = data(body.get('payload',{}),60000)
        with self.connect() as c:
            old = c.execute('SELECT project FROM assets WHERE id=?',(ident,)).fetchone()
            if old and old['project'] != project: raise Conflict('resource belongs to another project')
            c.execute('INSERT OR REPLACE INTO assets VALUES(?,?,?,?,?,?,?,?)',(ident,project,kind,title,
                short(body.get('agent','generic'),'agent',100),description,json.dumps(payload,ensure_ascii=False),now()))
        self.event(project,'resource',ident,{'kind':kind,'title':title})
        return {'id':ident,'kind':kind,'executed':False}

    def assets(self, project, kind=''):
        kind=kind or ''
        if kind and kind not in ASSET_KINDS: raise InvalidInput('invalid resource type')
        with self.connect() as c:
            rows = c.execute('SELECT * FROM assets WHERE project=? AND (?="" OR kind=?) ORDER BY updated DESC LIMIT 500',
                (scope(project),kind,kind)).fetchall()
        return [dict(r,payload=json.loads(r['payload'])) for r in rows]

    def thread(self, body):
        project = scope(body.get('project','default'))
        external = short(body.get('logical_id'), 'logical conversation id',200)
        ident = hashlib.sha256((project+'\0'+external).encode()).hexdigest()[:32]
        status = body.get('status','unknown')
        if status not in STATES: raise InvalidInput('invalid conversation status')
        if status=='waiting_user' and not body.get('question'):raise InvalidInput('waiting_user requires a question')
        progress = body.get('progress')
        if progress is not None and (type(progress) is not int or not 0 <= progress <= 100): raise InvalidInput('progress: 0..100 or null')
        session_ids = body.get('sessions',[])
        if not isinstance(session_ids,list) or len(session_ids)>200: raise InvalidInput('up to 200 session references')
        for sid in session_ids:
            archived = sessions.show(self.store,sid)
            if archived['project'] != project: raise NotFound('session not found in project')
        with self.connect() as c:
            c.execute('''INSERT INTO threads VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,group_title=excluded.group_title,status=excluded.status,progress=excluded.progress,
                needs_user=excluded.needs_user,origin=excluded.origin,question=excluded.question,updated=excluded.updated''',(ident,project,
                short(body.get('title'),'conversation title',200),short(body.get('group_title') or body['title'],'project title',200),
                status,progress,int(status=='waiting_user'),origin_link(body.get('origin','')),
                short(body.get('question',''),'user question',4000,True),now()))
            for sid in session_ids: c.execute('INSERT OR REPLACE INTO thread_sessions VALUES(?,?)',(ident,sid))
        return {'id':ident,'logical_id':external,'status':status}

    def threads(self, project, agent='', status='', query=''):
        project=scope(project)
        archived=sessions.list_sessions(self.store,project,limit=500)
        by_id={r['id']:r for r in archived}
        with self.connect() as c:
            rows=c.execute('SELECT * FROM threads WHERE project=? ORDER BY updated DESC',(project,)).fetchall()
            mappings=c.execute('SELECT ts.* FROM thread_sessions ts JOIN threads t ON t.id=ts.thread WHERE t.project=?',(project,)).fetchall()
        attached={r['session'] for r in mappings};out=[]
        for row in rows:
            links=[by_id[m['session']] for m in mappings if m['thread']==row['id'] and m['session'] in by_id]
            out.append(dict(row,sessions=[r['id'] for r in links],agents=sorted({r['agent'] for r in links}),
                turns=sum(r['turns'] for r in links),started=min((r.get('started') or r['created'] for r in links),default=row['updated'])))
        for r in archived:
            if r['id'] in attached:continue
            meta=r.get('meta',{})
            if isinstance(meta,str):
                try:meta=json.loads(meta)
                except ValueError:meta={}
            inferred=meta.get('task_status','unknown')
            out.append({'id':r['id'],'project':project,'title':r['title'] or r['external_id'] or r['id'],
                'group_title':meta.get('project_title') or r['title'] or '未分类项目','status':inferred if inferred in STATES else 'unknown',
                'progress':None,'needs_user':inferred=='waiting_user','question':meta.get('question',''),
                'origin':self._archive_origin(r,meta),'updated':r.get('ended') or r['created'],
                'started':r.get('started') or r['created'],'agents':[r['agent']],'sessions':[r['id']],'turns':r['turns']})
        tasks=self.tasks(project)
        for row in out:
            linked=[t for t in tasks if t['thread']==row['id'] or t['thread'] in row['sessions']]
            row['tasks']=[{'id':t['id'],'title':t['title'],'status':t['status'],'progress':t['progress'],'question':t['question']} for t in linked]
            waiting=[t for t in linked if t['needs_user']]
            if waiting:
                row['needs_user']=True;row['status']='waiting_user';row['question']='\n'.join(t['title']+'：'+t['question'] for t in waiting)
        return [r for r in out if (not agent or agent in r['agents']) and (not status or r['status']==status)
            and (not query or query.casefold() in (r['title']+' '+r['group_title']).casefold())]

    @staticmethod
    def _archive_origin(row,meta):
        candidate=meta.get('origin_uri','')
        if not candidate and row['agent']=='codex' and re.fullmatch(r'[0-9a-fA-F-]{36}',row['external_id'] or ''):
            candidate='codex://threads/'+row['external_id']
        try:return origin_link(candidate)
        except InvalidInput:return ''

    def create_task(self, body):
        project=scope(body.get('project','default'));ident=str(uuid.uuid4())
        payload=data(body.get('payload',{}),80000)
        assigned=short(body.get('assigned',''),'assigned peer',100,True)
        thread=short(body.get('thread',''),'thread',200,True)
        if thread:
            with self.connect() as c:known=c.execute('SELECT 1 FROM threads WHERE id=? AND project=?',(thread,project)).fetchone()
            if not known and sessions.show(self.store,thread)['project']!=project:raise NotFound('task conversation not found in project')
        if assigned and not any(p['id']==assigned for p in self.peers(project)):raise NotFound('register assigned peer first')
        with self.connect() as c:
            c.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(ident,project,
                thread,short(body.get('title'),'task title',200),assigned,'','queued',None,'',
                json.dumps(payload,ensure_ascii=False),'{}',0,now(),now()))
        self.event(project,'task',ident,{'state':'queued','assigned':assigned})
        return self.task(project,ident)

    def task(self,project,ident):
        with self.connect() as c:row=c.execute('SELECT * FROM tasks WHERE project=? AND id=?',(scope(project),ident)).fetchone()
        if row is None:raise NotFound('task not found')
        return self._task_row(row)

    @staticmethod
    def _task_row(row):
        return dict(row,payload=json.loads(row['payload']),result=json.loads(row['result']),needs_user=row['status']=='waiting_user',
            lease_expired=row['status']=='running' and row['lease']<time.time())

    def tasks(self,project):
        with self.connect() as c:rows=c.execute('SELECT * FROM tasks WHERE project=? ORDER BY created DESC LIMIT 200',(scope(project),)).fetchall()
        return [self._task_row(r) for r in rows]

    def claim(self,project,peer,ident):
        project=scope(project)
        if not any(p['id']==peer and p['connected'] for p in self.peers(project)):raise Conflict('fresh peer heartbeat required')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM tasks WHERE id=? AND project=?',(ident,project)).fetchone()
            if row is None:raise NotFound('task not found')
            if row['assigned'] and row['assigned']!=peer:raise Conflict('task assigned to another peer')
            expired=row['status']=='running' and row['lease']<time.time()
            if row['status']!='queued' and not expired:raise Conflict('task is not available')
            active=c.execute('SELECT count(*) FROM tasks WHERE owner=? AND status="running" AND lease>?',(peer,time.time())).fetchone()[0]
            if active>=2:raise Conflict('peer concurrency limit reached; distribute work or finish an existing task')
            c.execute('UPDATE tasks SET owner=?,status="running",lease=?,updated=? WHERE id=?',(peer,time.time()+180,now(),ident))
        self.event(project,'task',ident,{'state':'running','peer':peer})
        return self.task(project,ident)

    def report_task(self,project,peer,ident,status,progress=None,result=None,question=''):
        if status not in ('running','waiting_user','done','failed'):raise InvalidInput('invalid task report state')
        if progress is not None and (type(progress) is not int or not 0<=progress<=100):raise InvalidInput('progress: 0..100')
        clean=data(result or {},80000);question=short(question,'question',4000,True)
        if status=='waiting_user' and not question:raise InvalidInput('waiting_user requires a question')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM tasks WHERE project=? AND id=?',(scope(project),ident)).fetchone()
            if row is None:raise NotFound('task not found')
            if row['owner']!=peer or row['status']!='running' or row['lease']<time.time():raise Conflict('task lease is not owned or no longer active')
            c.execute('UPDATE tasks SET status=?,progress=?,result=?,question=?,lease=?,updated=? WHERE id=?',
                (status,progress,json.dumps(clean,ensure_ascii=False),question,time.time()+180,now(),ident))
        self.event(project,'task',ident,{'state':status,'peer':peer,'progress':progress})
        return self.task(project,ident)

    def respond(self,project,ident,response):
        response=short(response,'user response',8000)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM tasks WHERE project=? AND id=?',(scope(project),ident)).fetchone()
            if row is None:raise NotFound('task not found')
            if row['status']!='waiting_user':raise Conflict('task is not waiting for user input')
            payload=json.loads(row['payload']);payload['user_response']=response
            c.execute('UPDATE tasks SET payload=?,status="queued",question="",lease=0,updated=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),now(),ident))
        self.event(project,'user_response',ident,{'recorded':True})
        return self.task(project,ident)

    def hierarchy_link(self,project,parent,child,kind,evidence):
        project=scope(project);parent=short(parent,'parent',200);child=short(child,'child',200)
        if kind not in ('part_of','prerequisite','sequence'):raise InvalidInput('hierarchy kind: part_of, prerequisite, sequence')
        if parent==child:raise InvalidInput('self hierarchy is not allowed')
        evidence=short(evidence,'relationship evidence',2000)
        # Nodes are references to existing approved memories, not new invented concepts.
        for ident in [parent,child]:
            memory=self.store.get(project,ident)
            if memory['status']!='approved':raise InvalidInput('hierarchy endpoints must be approved memories')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            cycle=c.execute('''WITH RECURSIVE descendants(id) AS (
                SELECT child FROM hierarchy WHERE project=? AND parent=? AND kind=? UNION
                SELECT h.child FROM hierarchy h JOIN descendants d ON h.parent=d.id WHERE h.project=? AND h.kind=?)
                SELECT 1 FROM descendants WHERE id=? LIMIT 1''',(project,child,kind,project,kind,parent)).fetchone()
            if cycle:raise Conflict('hierarchy must remain acyclic')
            c.execute('INSERT OR REPLACE INTO hierarchy VALUES(?,?,?,?,?)',(project,parent,child,kind,evidence))
        return {'parent':parent,'child':child,'kind':kind,'evidence':evidence}

    def hierarchy(self,project):
        with self.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM hierarchy WHERE project=?',(scope(project),))]

    def save_workflow(self,body,models):
        project=scope(body.get('project','default'));ident=short(body.get('id') or str(uuid.uuid4()),'workflow id',100)
        steps=body.get('steps');dispatcher=short(body.get('dispatcher',''),'dispatcher',100,True)
        if not isinstance(steps,list) or not 1<=len(steps)<=12:raise InvalidInput('workflow: 1..12 stages')
        clean=[]
        for i,step in enumerate(steps):
            if not isinstance(step,dict) or step.get('operation') not in OPERATIONS or step.get('model') not in models:
                raise InvalidInput('stage needs a supported operation and configured model')
            clean.append({'id':str(i+1),'operation':step['operation'],'model':step['model'],
                'instruction':short(step.get('instruction',''),'stage instruction',2000,True)})
        with self.connect() as c:
            prior=c.execute('SELECT project FROM workflows WHERE id=?',(ident,)).fetchone()
            if prior and prior['project']!=project:raise Conflict('workflow belongs to another project')
            c.execute('INSERT OR REPLACE INTO workflows VALUES(?,?,?,?,?,?)',(ident,project,
                short(body.get('title'),'workflow title',160),dispatcher,json.dumps(clean,ensure_ascii=False),now()))
        return {'id':ident,'steps':clean,'dispatcher':dispatcher}

    def workflows(self,project):
        with self.connect() as c:rows=c.execute('SELECT * FROM workflows WHERE project=? ORDER BY updated DESC',(scope(project),)).fetchall()
        return [dict(r,steps=json.loads(r['steps'])) for r in rows]

    def backup(self):
        folder=self.store.root/'backups';folder.mkdir(exist_ok=True);destination=folder/('control-'+uuid.uuid4().hex+'.sqlite3')
        with self.connect() as source:
            target=sqlite3.connect(destination)
            try:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise OSError('control backup failed integrity check')
            finally:target.close()
        return {'path':'backups/'+destination.name,'integrity':'ok'}
