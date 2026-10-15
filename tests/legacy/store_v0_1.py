"""SQLite is authoritative; Markdown is a retryable materialized view."""
import contextlib
import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

CATEGORIES = {'fact', 'decision', 'preference', 'procedure', 'lesson', 'knowledge'}
RELATIONS = {'supports', 'contradicts', 'supersedes', 'related'}

def now(): return datetime.now(timezone.utc).isoformat()
def scope(project):
    if not isinstance(project, str) or not re.fullmatch(r'[\w-]{1,80}', project):
        raise ValueError('project must be 1-80 letters, digits, underscore or hyphen')
    return project

def classify(text):
    if any(x in text.lower() for x in ['选择', '决定', '决策', 'chose', 'decision']): return 'decision'
    if any(x in text.lower() for x in ['偏好', '喜欢', 'prefer']): return 'preference'
    if any(x in text.lower() for x in ['步骤', 'procedure']): return 'procedure'
    if any(x in text.lower() for x in ['教训', '踩坑', 'lesson']): return 'lesson'
    return 'fact'

def validate_content(text):
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 16000:
        raise ValueError('content must contain 1-16000 characters')
    if re.search(r'(?i)(api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*\S{6,}|-----BEGIN .*PRIVATE KEY-----|\bsk-[A-Za-z0-9]{16,}', text):
        raise ValueError('possible credential: redact before capture')
    return text.strip()

class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'memory.sqlite3'
        with self.connect() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS memories(
              id TEXT PRIMARY KEY, project TEXT NOT NULL, content TEXT NOT NULL,
              source TEXT NOT NULL, event_id TEXT, digest TEXT NOT NULL,
              mode TEXT NOT NULL, status TEXT NOT NULL, category TEXT NOT NULL,
              tags TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL,
              version INTEGER NOT NULL DEFAULT 1,
              UNIQUE(project,source,event_id));
            CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, version INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY, id TEXT, action TEXT,
              digest TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS edges(project TEXT, a TEXT, b TEXT, relation TEXT,
              PRIMARY KEY(project,a,b,relation), FOREIGN KEY(a) REFERENCES memories(id),
              FOREIGN KEY(b) REFERENCES memories(id));
            CREATE TABLE IF NOT EXISTS vectors(id TEXT PRIMARY KEY, model TEXT, dim INTEGER,
              digest TEXT, vector TEXT, FOREIGN KEY(id) REFERENCES memories(id));
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(id UNINDEXED, content);
            CREATE INDEX IF NOT EXISTS memories_scope ON memories(project,status);
            PRAGMA user_version=1;
            ''')

    @contextlib.contextmanager
    def connect(self):
        c=sqlite3.connect(self.db, timeout=15)
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            with c: yield c
        finally: c.close()

    def _audit(self,c,id,action,digest):
        c.execute('INSERT INTO audit(id,action,digest,created) VALUES(?,?,?,?)',(id,action,digest,now()))
    def _outbox(self,c,id,version):
        c.execute('INSERT OR REPLACE INTO outbox VALUES(?,?)',(id,version))
    def _get(self,c,project,id):
        row=c.execute('SELECT * FROM memories WHERE project=? AND id=?',(scope(project),id)).fetchone()
        if row is None: raise KeyError('memory not found in project')
        return dict(row)
    def get(self,project,id):
        with self.connect() as c: return self._get(c,project,id)

    def capture(self,project,content,source,mode='auto',confirmed=False,event_id=None,category=None,tags=None):
        scope(project); content=validate_content(content)
        if mode not in {'auto','manual'} or (confirmed and mode!='manual'):
            raise ValueError('only explicit manual capture may be confirmed')
        if not isinstance(source,str) or not 1<=len(source)<=300: raise ValueError('source required, max 300 characters')
        if event_id is not None and (not isinstance(event_id,str) or not 1<=len(event_id)<=200): raise ValueError('bad event_id')
        category=category or classify(content)
        if category not in CATEGORIES: raise ValueError('unknown category')
        tags=tags or []
        if not isinstance(tags,list) or len(tags)>20 or any(not isinstance(t,str) or not 1<=len(t)<=60 for t in tags): raise ValueError('invalid tags')
        digest=hashlib.sha256(content.encode()).hexdigest()
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if event_id:
                old=c.execute('SELECT * FROM memories WHERE project=? AND source=? AND event_id=?',(project,source,event_id)).fetchone()
                if old:
                    if old['digest']!=digest: raise ValueError('event_id reused with different content')
                    return dict(old)
            id=str(uuid.uuid4()); t=now()
            c.execute('INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (id,project,content,source,event_id,digest,mode,'approved' if confirmed else 'pending',category,json.dumps(tags,ensure_ascii=False),t,t,1))
            c.execute('INSERT INTO memories_fts VALUES(?,?)',(id,content))
            self._outbox(c,id,1); self._audit(c,id,'capture',digest)
            return self._get(c,project,id)

    def review(self,project,id,action):
        states={'approve':'approved','reject':'rejected','forget':'deleted'}
        if action not in states: raise ValueError('approve, reject or forget required')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE'); r=self._get(c,project,id)
            if r['status']=='deleted' and action!='forget': raise ValueError('deleted memory cannot be silently restored')
            v=r['version']+1
            c.execute('UPDATE memories SET status=?,updated=?,version=? WHERE id=?',(states[action],now(),v,id))
            self._outbox(c,id,v); self._audit(c,id,action,r['digest'])
            return self._get(c,project,id)

    def list_memories(self,project,status=None,limit=200):
        scope(project)
        if not 1<=limit<=1000: raise ValueError('limit 1..1000')
        sql='SELECT * FROM memories WHERE project=?'; args=[project]
        if status:
            if status not in {'pending','approved','rejected','deleted'}: raise ValueError('unknown status')
            sql+=' AND status=?'; args.append(status)
        sql+=' ORDER BY created DESC LIMIT ?'; args.append(limit)
        with self.connect() as c: return [dict(r) for r in c.execute(sql,args)]

    def recall(self,project,query,limit=10):
        scope(project)
        if not isinstance(query,str) or not 1<=len(query.strip())<=1000 or not 1<=limit<=50: raise ValueError('invalid query or limit')
        tokens=re.findall(r'[\w]+',query.lower())[:30]
        terms=' OR '.join('"'+t+'"' for t in tokens)
        scores={}
        with self.connect() as c:
            if terms:
                rows=c.execute('''SELECT m.*,bm25(memories_fts) AS rank FROM memories_fts
                    JOIN memories m ON m.id=memories_fts.id
                    WHERE memories_fts MATCH ? AND m.project=? AND m.status='approved'
                    ORDER BY rank LIMIT 100''',(terms,project)).fetchall()
                for i,r in enumerate(rows): scores[r['id']]=(1/(60+i+1),dict(r))
            # FTS unicode61 does not segment Chinese: bounded literal fallback, not semantic embeddings.
            for r in c.execute("SELECT * FROM memories WHERE project=? AND status='approved' ORDER BY created DESC LIMIT 5000",(project,)):
                hits=sum(t in r['content'].lower() for t in tokens)
                if hits:
                    base=scores.get(r['id'],(0,None))[0]
                    scores[r['id']]=(base+hits/100,dict(r))
        return [dict(r,score=round(s,6),retrieval='lexical') for s,r in sorted(scores.values(),key=lambda v:v[0],reverse=True)[:limit]]

    def link(self,project,a,b,relation):
        if relation not in RELATIONS or a==b: raise ValueError('invalid relation')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            self._get(c,project,a); self._get(c,project,b)
            c.execute('INSERT OR IGNORE INTO edges VALUES(?,?,?,?)',(project,a,b,relation))
            self._audit(c,a,'link:'+relation,b)
        return {'a':a,'b':b,'relation':relation}

    def graph(self,project):
        nodes=self.list_memories(project,'approved',1000); ids={r['id'] for r in nodes}
        with self.connect() as c:
            edges=[dict(r) for r in c.execute('SELECT * FROM edges WHERE project=?',(project,)) if r['a'] in ids and r['b'] in ids]
        return {'nodes':nodes,'edges':edges,'limit':1000,'semantics':'explicit typed links, not automatically proven causality'}

    def flush(self):
        result={'written':0,'failed':0}
        with self.connect() as c: items=list(c.execute('SELECT id FROM outbox'))
        for item in items:
            try:
                # Serialize mirror writers with mutation, so older processes cannot overwrite newer versions.
                with self.connect() as c:
                    c.execute('BEGIN IMMEDIATE')
                    r=c.execute('SELECT * FROM memories WHERE id=?',(item['id'],)).fetchone()
                    folder=self.root/'markdown'; folder.mkdir(exist_ok=True)
                    path=folder/(r['id']+'.md')
                    if r['status']=='deleted': path.unlink(missing_ok=True)
                    else:
                        fields={k:r[k] for k in ['id','project','source','status','category','created','updated','version']}
                        header='---\n'+''.join(f'{k}: {json.dumps(v,ensure_ascii=False)}\n' for k,v in fields.items())+'---\n\n'
                        text=header+r['content']+'\n'
                        temp=path.with_suffix('.tmp'); temp.write_text(text,encoding='utf-8'); temp.replace(path)
                    c.execute('DELETE FROM outbox WHERE id=?',(r['id'],)); result['written']+=1
            except OSError: result['failed']+=1
        return result

    def rebuild(self):
        with self.connect() as c:
            c.execute('INSERT OR REPLACE INTO outbox SELECT id,version FROM memories')
        return self.flush()

    def backup(self,target):
        target=Path(target).resolve()
        # Exclusive creation prevents accidental replacement of an existing database.
        with target.open('xb'): pass
        dest=sqlite3.connect(target)
        try:
            with self.connect() as source: source.backup(dest)
        finally: dest.close()
        return {'backup':str(target)}

    def health(self):
        with self.connect() as c:
            return {'schema':1,'integrity':c.execute('PRAGMA quick_check').fetchone()[0],
                    'pending_exports':c.execute('SELECT count(*) FROM outbox').fetchone()[0],
                    'memories':c.execute('SELECT count(*) FROM memories').fetchone()[0],
                    'default_retrieval':'lexical','network':'disabled unless provider explicitly configured'}
