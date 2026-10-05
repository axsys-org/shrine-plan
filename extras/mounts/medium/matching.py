"""Structural presentation matching. Names of applications never enter scoring.

Fields come from the compiled native role projection. Roles disambiguate meaning;
type-only and adapter matches remain visible blanks for confirmation.
"""
import itertools

ALIASES={'Choice':'Enum','Reference':'Ref'}
PREPARED={
 'dial':[('value',('Number','Natural'),'quantity',True),('max',('Number','Natural'),'max',True),('limit',('Number','Natural'),'limit',True),('target',('Number','Natural'),'target',True)],
 'board':[('group',('Enum','Ref'),'group',True),('title',('Text',),'title',True)],
 'table':[('title',('Text',),'title',True)],
 'list':[('title',('Text',),'title',True)],
}

def enumerate_shape(fields,needs):
    """Return bounded, inspectable candidates, with no invented fields/values."""
    fields=[{**f,'type':ALIASES.get(f.get('type'),f.get('type','Text'))}for f in fields]
    domains=[]
    for need in needs:
        channel,types,role,required=need[:4]
        enum_values=need[4] if len(need)>4 else None
        options=[]
        for f in fields:
            if f['type'] not in types:continue
            if enum_values and f['type']=='Enum' and not set(f.get('choices',[]))<=set(enum_values):continue
            exact=bool(role and f.get('role')==role)
            options.append({'channel':channel,'field':f['label'],'slot':f['slot'],'fit':1 if exact else .5,'blank':not exact,'uses':[f['slot']],'reason':'exact role '+role if exact else 'type fits; choose its meaning'})
        if channel=='duration' and not any(o['fit']==1 for o in options):
            starts=[f for f in fields if f['type']=='Date' and f.get('role')=='start']
            ends=[f for f in fields if f['type']=='Date' and f.get('role')=='end']
            for start,end in itertools.product(starts,ends):
                options.append({'channel':channel,'adapter':'end-minus-start','from':start['label'],'to':end['label'],'fit':.8,'blank':True,'uses':[start['slot'],end['slot']],'reason':'duration = end − start; inverse moves both endpoints'})
        if not options:
            if required:return []
            continue
        best=max(o['fit'] for o in options)
        domains.append([o for o in options if o['fit']==best][:4])
    if not domains:return []
    role_slots={f['slot'] for f in fields if f.get('role')}
    result=[]
    for bindings in itertools.islice(itertools.product(*domains),32):
        used=set().union(*(set(b['uses']) for b in bindings))
        blanks=sum(b['blank'] for b in bindings)
        coverage=len(role_slots&used)/len(role_slots) if role_slots else 0
        score=sum(b['fit'] for b in bindings)/len(bindings)+.05*len(bindings)-.05*blanks+.5*coverage
        result.append({'bindings':list(bindings),'blanks':blanks,'coverage':coverage,'score':round(score+1e-9,2)})
    return sorted(result,key=lambda r:r['score'],reverse=True)

def enumerate_collection(node):
    result=[]
    for part,needs in PREPARED.items():
        for candidate in enumerate_shape(node.get('properties',[]),needs):
            fields={b['channel']:b.get('field') for b in candidate['bindings']}
            result.append({**candidate,'part':part,'collection':node['id'],'titleField':fields.get('title'),'groupField':fields.get('group')})
    return sorted(result,key=lambda r:r['score'],reverse=True)

def decision_mode(candidates,ai=True):
    if not candidates:return 'hole'
    margin=candidates[0]['score']-candidates[1]['score'] if len(candidates)>1 else float('inf')
    if not candidates[0]['blanks'] and margin>=.25:return 'local'
    if ai:return 'model'
    return 'unconfirmed' if margin>=.15 else 'hole'


def definition_needs(definition):
    needs={}
    for part in definition.get('parts',[]):
        for channel,field in part.get('mapping',{}).items():
            spec=part.get('properties',{}).get(channel,{})
            kind=ALIASES.get(spec.get('type'),spec.get('type'))
            if not field:continue
            if channel=='x' and kind=='Date':need=('start',('Date',),'start',True)
            elif channel=='width' and kind=='Duration':need=('duration',('Duration',),'duration',True)
            elif channel=='row':need=('row',('Ref','Enum'),'row',True)
            elif channel in ('text','label'):need=('title',('Text',),'title',False)
            elif channel=='colour':need=('fill',('Enum',),'group',False,spec.get('choices'))
            else:need=(field,(kind or 'Text',),spec.get('role',''),True)
            needs[need[0]]=need
    return list(needs.values())
