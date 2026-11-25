"""Notion follow-through fields. Schema setup is explicit, never performed by reads."""
from datetime import datetime
FIELDS = {
 'external_deadline': ('External Deadline','date'),
 'outcome': ('Intended Outcome','rich_text'), 'next_action': ('Next Action','rich_text'),
 'owner': ('Next Owner','select'), 'next_review': ('Next Review','date'),
 'blocker': ('Blocker','rich_text'), 'deadline_basis': ('Deadline Basis','select'),
 'last_progress': ('Last Progress','date'), 'closed_at': ('Closed At','date'),
 'closure_reason': ('Closure Reason','select'),
}
OPTIONS={'owner':['Assistant','User','External'], 'deadline_basis':['External','Personal target','Unknown'],
 'closure_reason':['Completed','Cancelled','Superseded','Migrated']}


def extract_fields(props):
    result={}
    for key,(name,kind) in FIELDS.items():
        p=props.get(name,{})
        if kind=='rich_text':value=''.join(x.get('plain_text',x.get('text',{}).get('content','')) for x in p.get(kind,[]))
        elif kind=='select':value=(p.get(kind) or {}).get('name','')
        else:value=(p.get(kind) or {}).get('start','')
        result[key]=value
    return result


def build_properties(updates):
    result={}
    for key,value in updates.items():
        if key not in FIELDS:raise ValueError(f'Unknown follow-through field: {key}')
        name,kind=FIELDS[key]
        if kind=='rich_text':result[name]={kind:[{'text':{'content':value[i:i+1800]}} for i in range(0,len(value),1800)]}
        elif kind=='select':
            if value and value not in OPTIONS[key]:raise ValueError(f'Invalid {key}: {value}')
            result[name]={kind:{'name':value} if value else None}
        else:
            if value:datetime.fromisoformat(value.replace('Z','+00:00'))
            result[name]={kind:{'start':value} if value else None}
    return result


def ensure_schema(client, database_id):
    existing=client._request('GET',f'/databases/{database_id}')['properties']
    additions={}
    for key,(name,kind) in FIELDS.items():
        if name in existing:
            if existing[name]['type']!=kind:raise ValueError(f'Incompatible Notion field: {name}')
            continue
        additions[name]={kind:{'options':[{'name':v} for v in OPTIONS[key]]} if kind=='select' else {}}
    if additions:client._request('PATCH',f'/databases/{database_id}',json={'properties':additions})
    return list(additions)
