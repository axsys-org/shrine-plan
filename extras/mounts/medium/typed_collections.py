"""Prepared Grove collection definitions. The native compiler owns types and writes.

Python emits bounded source, never evaluates user formulas or models record state.
"""
import json,re,uuid
MARKER="' grove-collection/1 "
TYPES={'Text','Natural','Number','Boolean','Choice','Date','Reference','Image','File','List','Sequence','Object','Duration','Many','Enum','Ref'}
STRUCTURED={'Number','List','Sequence','Object','Duration','Many'}

def quoted(text):
    return '"'+text.replace('"','""').replace('\n',' ').replace('\r',' ')+'"'

def schema_input(name, fields, source_authority=False):
    if not isinstance(name,str) or not 0<len(name.strip())<=80:raise ValueError('Name the collection (up to 80 characters).')
    if not isinstance(fields,list) or not 1<=len(fields)<=16:raise ValueError('Add between 1 and 16 fields.')
    result=[];seen=set()
    for field in fields:
        label=field.get('name','').strip();kind={'Choice':'Enum','Reference':'Ref'}.get(field.get('type','Text'),field.get('type','Text'))
        if not label or len(label)>60 or label.casefold() in seen or label in ('id','__proto__','constructor','prototype'):raise ValueError('Use distinct, nonempty field names.')
        if kind not in TYPES:raise ValueError('Choose a supported native field type.')
        if 'writable' in field and not isinstance(field['writable'],bool):raise ValueError('Source writability must be a boolean.')
        choices=field.get('choices',[])
        if kind in {'Choice','Enum'} and (not isinstance(choices,list) or not 1<=len(choices)<=24 or any(not isinstance(v,str) or not v.strip() or len(v)>60 for v in choices) or len(set(choices))!=len(choices)):raise ValueError('Give Choice fields distinct options.')
        result.append({'name':label,'type':kind,'key':'f'+str(len(result)),'choices':choices if kind in {'Choice','Enum'} else [],'target':field.get('target','') if kind in {'Reference','Ref','Many'} else '', 'role':field.get('role',''), 'writable':field.get('writable',False) if source_authority else True, 'unit':field.get('unit','days' if kind=='Duration' else '')});seen.add(label.casefold())
    
    if any(f['type'] in {'Ref','Many'} and not f['target'] for f in result):raise ValueError('Choose the collection each reference points to.')
    singular='Person' if name.strip().lower()=='people' else name.strip()[:-1] if name.strip().endswith('s') else name.strip()
    return {'version':1,'name':name.strip(),'singular':singular,'fields':result}

def codec(field):
    key=field['key'];kind=field['type'];typ='bool' if kind=='Boolean' else 'nat' if kind=='Natural' else 'str'
    case='b' if kind=='Boolean' else 'n' if kind=='Natural' else 't'
    validate=''
    if kind in {'Choice','Enum'}:validate='    ? !(row/has[str] value.t ['+' '.join(quoted(v) for v in field['choices'])+']) .none\n'
    if kind=='Date':validate='    ? !(date_valid value.t) .none\n'
    native=f'''type_{key} =
  @type
  ! foil
  {typ}
  + read
    \\ value=pail
    ^ maybe[type_{key}]
    ?> value=pails/{case} value .none
{validate}    | ./some value.{case}
  + write
    \\ value=type_{key}
    ^ pail
    | pails/{case} value
  + contract
    ^ curb
    | curb/of_type (^ pails/{case})
'''
    # A text transport codec validates before the action constructs typed values.
    checks=validate
    if kind=='Natural':checks='    ?> (./some parsed) (nat/parse value.t) .none\n'
    elif kind=='Boolean':checks='    ? !((eq value.t "true") || (eq value.t "false")) .none\n'
    return native+f'''
input_{key} =
  @type
  ! foil
  str
  + read
    \\ value=pail
    ^ maybe[input_{key}]
    ?> value=pails/t value .none
    ? (eq value.t "") (./some value.t)
{checks}    | ./some value.t
  + write
    \\ value=input_{key}
    ^ pail
    | pails/t value
  + contract
    ^ curb
    | curb/of_type (^ pails/t)

{key} =
  @slot

arg_{key} =
  @slot
'''

def decoded(f):
    k=f['key']
    if f['type']=='Natural':return '(nat/parse '+k+')'
    if f['type']=='Boolean':return '(? (eq '+k+' "") .none (./some (eq '+k+' "true")))'
    return '(? (eq '+k+' "") .none (./some '+k+'))'

DATE_CHECK='''date_valid =
  ! foil
  \\ value=str
  ^ bool
  ? !(eq value.len 10) .false
  ? !(and (eq value.at(4) 45) (eq value.at(7) 45)) .false
  ?> (./some year) (nat/parse value.slice(0 4)) .false
  ?> (./some month) (nat/parse value.slice(5 2)) .false
  ?> (./some day) (nat/parse value.slice(8 2)) .false
  ? ((eq year 0) || (eq month 0) || (gt month 12) || (eq day 0)) .false
  = leap (and (eq (mod year 4) 0) (!(eq (mod year 100) 0) || (eq (mod year 400) 0)))
    days=row[nat] [31 (? leap 29 28) 31 30 31 30 31 31 30 31 30 31]
  | le day days.at(month.dec)
'''

def source(schema, root):
    parts=[MARKER+json.dumps(schema,ensure_ascii=True), '#import lede=sys/lede\n#import text=lib/grove/types/text\n']
    if any(f['type'] in STRUCTURED for f in schema['fields']):parts.append('#import values=gov/user/collection_values_v1')
    if any(f['type'] in {'Reference','Ref','Image','File'} for f in schema['fields']):parts.append('#import reference=lib/grove/types/path')
    for kind in sorted({f['type'] for f in schema['fields']} & {'Natural','Boolean','Date'}):
        parts.append('#import '+kind.lower()+'=gov/user/field_codecs_v1/'+kind.lower())
    for f in schema['fields']:
        if f['type'] in {'Choice','Enum'}:parts.append(codec(f))
        else:parts.append(f['key']+' =\n  @slot\n\narg_'+f['key']+' =\n  @slot')
    def type_ref(f,mode):
        if f['type']=='Text':return 'text'
        if f['type'] in STRUCTURED:return 'values/'+f['type'].lower()
        if f['type'] in {'Reference','Ref','Image','File'}:return 'reference'
        if f['type'] in {'Choice','Enum'}:return mode+'_'+f['key']
        return f['type'].lower()+'/'+mode+'_value'
    parts.append('record =\n  @role\n  #opt ;\n'+'\n'.join('    %/'+f['key']+': '+type_ref(f,'type') for f in schema['fields']))
    parts.append('''accepts =
  ! foil
  | grove_binding_contract
  \\ inputs=row[myth]
  ^ either[str unit]
  ? !(eq inputs.len 0) (./err "This collection owns its fields.")
  | ./ok []

realize =
  ! foil
  | grove_realization
  \\ inputs=row[myth] current=myth
  ^ myth
  | current.put(['sys 'lede] (pails/t '''+quoted(schema['name'])+'''))
''')
    # Same native Grove handler protocol, without expanding N argument structs.
    # Native codecs validate every field before one immutable record commits.
    path=lambda suffix:'['+' '.join('($x '+str(int(v,16))+')' if v.startswith('0x') else "'"+v for v in (root+'/'+suffix).strip('/').split('/'))+']'
    lines=['save_all =','  @slot','  #meta ;','    "/sys/grove/action_handler": (grove_action_handler save_all/apply)','  ! foil','  + apply','    \\ arguments=myth current=myth','    ^ maybe[myth]']
    if schema.get('source'):
        lines.extend(['    | save_all/checked .false arguments current','  + ingest','    \\ arguments=myth current=myth','    ^ maybe[myth]','    | save_all/checked .true arguments current','  + checked','    \\ ingest=bool arguments=myth current=myth','    ^ maybe[myth]'])
        parts.append('ingest_all =\n  @slot\n  #meta ;\n    "/sys/grove/action_handler": (grove_action_handler save_all/ingest)')
    helpers=[]
    for f in schema['fields']:
        key=f['key'];kind=f['type'];ref=type_ref(f,'type');slot=path(key)
        lines.extend(['    < '+key+' arguments.get('+path('arg_'+key)+')','    < '+key+' (text/read '+key+')'])
        if schema.get('source') and not f.get('writable',True):
            display=path(('display_' if kind in STRUCTURED else '')+key)
            lines.append('    ? (and !(ingest) (and current.has('+slot+') !(eq current.txt_at('+display+') '+key+'))) .none')
        # Complex values stay native typed structures. Their display slot is a
        # canonical projection produced by the same native action, not editable.
        lines.append('    < current (save_all/put_'+key+' current '+key+')')
        helper=['  + put_'+key,'    \\ current=myth '+key+'=str','    ^ maybe[myth]']
        helper.extend(['    ? (eq '+key+' "") (./some current.del('+slot+').del('+path('display_'+key)+'))'])
        if kind in STRUCTURED:
            helper.extend(['      < value ('+ref+'/parse '+key+')','      | ./some current.put('+slot+' ('+ref+'/write value)).put('+path('display_'+key)+' (pails/t ('+ref+'/format value)))'])
        elif kind in {'Reference','Ref','Image','File'}:
            helper.extend(['      < value (path_parse '+key+')','      ? (eq value.len 0) .none','      | ./some current.put('+slot+' (pails/p value))'])
        else:
            if kind!='Text':helper.append('      < '+key+' ('+type_ref(f,'input')+'/read (pails/t '+key+'))')
            value='(pails/n (nat/parse '+key+').fall(0))' if kind=='Natural' else '(pails/b (eq '+key+' "true"))' if kind=='Boolean' else '(pails/t '+key+')'
            helper.append('      | ./some current.put('+slot+' '+value+')')
        helpers.extend(line[2:] if line.startswith('      ') else line for line in helper)
    lines.append('    | ./some current');parts.append('\n'.join(lines+helpers))
    groups=[]
    for subset,action in [(schema['fields'],'save_all')]+([(schema['fields'],'ingest_all')] if schema.get('source') else []):
        groups.append('    group(on = card, action = %/'+action+', myth = {\n'+'\n'.join("      '"+root+'/arg_'+f['key']+' = .input("")' for f in subset)+'\n    }) {\n'+'\n'.join("      input('"+root+'/arg_'+f['key']+')' for f in subset)+'\n      action('+quoted(action)+')\n    }')
    parts.append('surface =\n  @view\n  #on ; %/record\n  #for ; /sys/slot/detail\n  card => {\n'+'\n'.join(groups)+'\n  }\n')
    return '\n\n'.join(parts)

def schema_from(node):
    first=(node.get('source') or '').split('\n',1)[0]
    if not first.startswith(MARKER):return None
    try:
        data=json.loads(first[len(MARKER):])
        if data.get('version')!=1:return None
        return data
    except (ValueError,TypeError):return None

def project(frame):
    """Transport projection of actual compiled native fields, by stable slot."""
    definitions={n['code_root']:schema_from(n) for n in frame.get('nodes',[]) if schema_from(n)}
    for node in frame.get('nodes',[]):
        schema=definitions.get(node.get('code_root'))
        if not schema:continue
        root=node['code_root'];declared={f['slot'] for f in (node.get('typing',{}).get('role') or {}).get('fields',[])}
        # A source annotation cannot assert fields the compiled role lacks.
        if any(root+'/'+f['key'] not in declared for f in schema['fields']):continue
        values={f['slot']:f.get('value') for f in node.get('fields',[])}
        node['collectionSchema']=schema
        node['properties']=[{'label':f['name'],'type':f['type'],'choices':f['choices'],'target':(node.get('parent') if node.get('parent') not in ('/',None,'') else node['id']) if f.get('target')=='self' else f.get('target',''),'role':f.get('role',''),'writable':f.get('writable',True),'unit':f.get('unit',''),'slot':root+'/'+f['key'],'argument':root+'/arg_'+f['key'],'value':values.get(root+'/'+('display_' if f['type'] in STRUCTURED else '')+f['key']) or ''} for f in schema['fields']]
    return frame

def values_checked(schema, values):
    from datetime import date
    allowed={f['name'] for f in schema['fields']}
    if not isinstance(values,dict) or set(values)-allowed:raise ValueError('An input has no declared field.')
    for f in schema['fields']:
        v=str(values.get(f['name'],''))
        if len(v)>4096:raise ValueError(f['name']+': value is too long.')
        if not v:continue
        kind=f['type']
        if kind in {'Natural','Duration'} and not re.fullmatch('[0-9]+',v):raise ValueError(f['name']+': enter a whole number, zero or greater.')
        if kind=='Number' and not re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?',v):raise ValueError(f['name']+': enter a finite decimal number.')
        if kind=='Boolean' and v not in ('true','false'):raise ValueError(f['name']+': choose yes or no.')
        if kind in {'Choice','Enum'} and v not in f['choices']:raise ValueError(f['name']+': choose one of its options.')
        if kind=='Date':
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v):raise ValueError()
                date.fromisoformat(v)
            except ValueError:raise ValueError(f['name']+': enter a valid date.')
        if kind in {'Many','Sequence','List','Object'}:
            def pairs(items):
                result={}
                for k,item in items:
                    if k in result:raise ValueError('Duplicate object key: '+k)
                    result[k]=item
                return result
            def reject_constant(value):raise ValueError('Use finite numbers.')
            try:value=json.loads(v,object_pairs_hook=pairs,parse_constant=reject_constant)
            except (ValueError,TypeError) as error:raise ValueError(f['name']+': '+str(error)) from None
            if kind=='Object' and not isinstance(value,dict):raise ValueError(f['name']+': enter a JSON object.')
            if kind!='Object' and not isinstance(value,list):raise ValueError(f['name']+': enter a list.')
            if kind=='Sequence' and any(isinstance(x,bool) or not isinstance(x,(float,int)) for x in value):raise ValueError(f['name']+': each sequence value must be a number.')
            if kind=='Many' and (any(not isinstance(x,str) or not x.startswith('/') for x in value) or len(set(value))!=len(value)):raise ValueError(f['name']+': select distinct native records.')
        if kind in {'Ref','Reference','Image','File'} and not v.startswith('/'):raise ValueError(f['name']+': select native material.')
    return {f['name']:str(values.get(f['name'],'')) for f in schema['fields']}

def run(server, request, _source_authority=False):
    from contextlib import nullcontext
    with getattr(server,'collection_lock',nullcontext()):return _run(server,request,_source_authority)

def _run(server, request, _source_authority=False):
    event=request.get('event','')
    if not re.fullmatch('[a-f0-9-]{16,40}',event):raise ValueError('A stable interaction identity is required.')
    def call(op,frame,body,suffix):
        code,result=server.call(op,frame.get('expected','0'),event+suffix,body)
        if code!=200:raise ValueError(result.get('error','Native check rejected this change.'))
        return result
    code,frame=server.call('read')
    if code!=200:raise ValueError(frame.get('error','Shrine is not ready.'))
    kind=request.get('action');target='/0x11/app/medium/c'+event.replace('-','')
    if kind=='create':
        schema=schema_input(request.get('name'),request.get('fields'),_source_authority)
        if _source_authority and request.get('source'):schema['source']=request['source']
        existing=next((n for n in frame['nodes'] if n['id']==target),None)
        if existing:
            if schema_from(existing)!=schema:raise ValueError('This interaction already created different material.')
        else:
            frame=call('author',frame,{'edits':[{'target':target,'source':source(schema,target.replace('/app/','/gov/')),'label':schema['name'],'intent':'User-declared collection fields and native codecs','reuse':'','scope':'occurrence','inputs':[]}]},'a')
        return {'frame':frame,'collection':target}
    collection=next((n for n in frame['nodes'] if n['id']==request.get('collection')),None)
    schema=schema_from(collection or {})
    if not schema:raise ValueError('Select a typed native collection.')
    values=values_checked(schema,request.get('values',{}))
    for f in schema['fields']:
        if f['type'] not in {'Ref','Reference','Many'}:continue
        value=values[f['name']]
        refs=json.loads(value or '[]') if f['type']=='Many' else [value] if value else []
        destination=collection['id'] if f.get('target')=='self' else f.get('target')
        if any(not any(n['id']==ref and n.get('parent')==destination for n in frame['nodes']) for ref in refs):raise ValueError(f['name']+': the selected record is no longer in the referenced collection.')
    if kind=='record':
        if schema.get('source') and not _source_authority:raise ValueError('This source supplies its own records.')
        # Creation, validation, values and containment are one native commit.
        # The identity is derived by Shrine from this stable user event.
        target='/0x11/app/medium/$'+event
        prior=next((n for n in frame['nodes'] if n['id']==target),None)
        if prior:
            receipt=next((e for e in frame.get('events',[]) if e['id']==event and e['kind']=='instantiate-filled'),None)
            if receipt:
                submitted=json.loads(receipt['body'])
                arguments={collection['code_root']+'/arg_'+f['key']:values[f['name']] for f in schema['fields']}
                same=submitted.get('pattern')==collection['id'] and submitted.get('inputs')==arguments
            else:
                def canonical(field,value):
                    if field['type'] in {'Many','List','Sequence','Object'}:
                        return json.loads(value or ('{}' if field['type']=='Object' else '[]'))
                    if field['type'] in {'Number','Natural','Duration'} and value!='':
                        from decimal import Decimal
                        return Decimal(value)
                    return value
                same=all(canonical(f,str(next((p['value'] for p in prior['properties'] if p['label']==f['name']),'')))==canonical(f,values[f['name']]) for f in schema['fields'])
            if prior.get('parent')!=collection['id'] or not same:raise ValueError('This submission already created a record. Its values have changed; no duplicate was added.')
            return {'frame':frame,'record':target,'collection':collection['id']}
        actions=[o for o in collection['view']['occurrences'] if o['kind']=='action' and o['invoke']]
        if len(actions)!=(2 if schema.get('source') else 1):raise ValueError('The collection record constructor changed.')
        if _source_authority and schema.get('source'):actions=actions[1:]
        args={collection['code_root']+'/arg_'+f['key']:values[f['name']] for f in schema['fields']}
        code,result=server.call('instantiate-filled',frame['expected'],event,{'pattern':collection['id'],'control':actions[0]['control'],'inputs':args})
        if code!=200:raise ValueError(result.get('error','Native form validation failed.'))
        return {'frame':result,'record':target,'collection':collection['id']}
    elif kind=='update':target=request.get('record')
    else:raise ValueError('Unknown collection action.')
    record=next((n for n in frame['nodes'] if n['id']==target),None)
    if not record or record['code_root']!=collection['code_root']:raise ValueError('This record has a different native type.')
    if kind=='update':
        if record.get('parent')!=collection['id']:raise ValueError('This record is not in the selected collection.')
        for label,before in request.get('before',{}).items():
            current=next((p['value'] for p in record['properties'] if p['label']==label),None)
            if current!=before:raise ValueError(label+' changed elsewhere; your draft is retained.')
    selected=(request.get('field') or request.get('fields')) if kind=='update' else None
    if selected:
        selected=[selected] if isinstance(selected,str) else selected
        if not isinstance(selected,list) or not selected or len(set(selected))!=len(selected) or any(name not in {f['name'] for f in schema['fields']} for name in selected):raise ValueError('The declared write fields no longer exist.')
        if set(request.get('values',{}))!=set(selected):raise ValueError('The supplied values must exactly match the declared write fields.')
    if selected:
        values=values_checked(schema,{p['label']:str(request.get('values',{}).get(p['label'],p['value'])) for p in record['properties']})
    fields=schema['fields']
    if not fields:raise ValueError('The field no longer exists.')
    if not _source_authority and any(not f.get('writable',True) and f['name'] in (selected or request.get('values',{})) for f in fields):raise ValueError('This field is read-only at its source. No values were written.')
    if request.get('component'):
        import behaviors
        behaviors.validate_change(server,request,frame,collection,record,values)
    args={record['code_root']+'/arg_'+f['key']:values[f['name']] for f in fields}
    actions=[o for o in record['view']['occurrences'] if o['kind']=='action' and o['invoke']]
    index=1 if _source_authority and schema.get('source') else 0
    frame=call('act',frame,{'target':target,'expected':record['expected'],'displayed':record['displayed'],'publication':frame['publication'],'control':actions[index]['control'],'inputs':args},'c')
    if kind=='record':frame=call('place',frame,{'target':target,'parent':collection['id']},'d')
    return {'frame':frame,'record':target,'collection':collection['id']}
