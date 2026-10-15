"""Independent compatibility adapter for MCP reference memory entities/relations/observations.

Schema: https://github.com/modelcontextprotocol/servers/tree/main/src/memory
No upstream implementation is copied here.
"""
import json
from .errors import InvalidInput
from . import text
from .store import scope


def import_graph(store, project, raw, source='mcp-memory-export'):
    scope(project)
    try:
        try: obj=json.loads(raw)
        except ValueError: obj=[json.loads(line) for line in raw.splitlines() if line.strip()]
        if isinstance(obj,dict): entities,relations=obj.get('entities',[]),obj.get('relations',[])
        elif isinstance(obj,list):
            entities=[v for v in obj if isinstance(v,dict) and v.get('type')=='entity']
            relations=[v for v in obj if isinstance(v,dict) and v.get('type')=='relation']
        else: raise ValueError
        if not isinstance(entities,list) or not isinstance(relations,list) or len(entities)+len(relations)>10000: raise ValueError
        for entity in entities:
            if (not isinstance(entity,dict) or not isinstance(entity.get('name'),str) or not entity['name'].strip()
                or not isinstance(entity.get('observations',[]),list)
                or any(not isinstance(o,str) for o in entity.get('observations',[]))): raise ValueError
        if any(not isinstance(r,dict) or not all(isinstance(r.get(k),str) for k in ('from','to','relationType')) for r in relations): raise ValueError
    except (ValueError,TypeError): raise InvalidInput('invalid MCP memory graph JSON / JSONL') from None
    mapping={};memories=[]
    for entity in entities:
        content='实体：'+entity['name']+'\n类型：'+str(entity.get('entityType','concept'))+'\n'+'\n'.join(entity.get('observations',[]))
        associations=[r for r in relations if r['from']==entity['name']]
        content+='\n'+'\n'.join('关系：'+r['relationType']+' → '+r['to'] for r in associations)
        content,_=text.redact(content)
        for index,start in enumerate(range(0,len(content),14000)):
            m=store.capture(project,content[start:start+14000],source,category='knowledge',tags=['mcp-graph'],actor='graph-import')
            memories.append(m['id'])
            if index==0: mapping[entity['name']]=m['id']
    linked,missing=0,[]
    for relation in relations:
        a,b=mapping.get(relation['from']),mapping.get(relation['to'])
        if not a or not b: missing.append(relation);continue
        if a==b: continue
        # Preserve the relationship label in text; imported edges cannot retire old memories.
        store.link(project,a,b,'related',actor='graph-import');linked+=1
    store.flush()
    return {'memories':memories,'relations':linked,'missing_endpoints':missing,'approval':'human_required'}
