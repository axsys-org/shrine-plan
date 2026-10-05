"""Declared JSON providers. Values enter through the same native typed commits.

Providers own read-only fields. Writable fields are local native controls, never
an implied remote device command. Unknown/changed shapes stay disconnected.
"""
import json,uuid,urllib.request,urllib.parse,threading
import typed_collections

def read(url):
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme not in ('http','https') or parsed.username or parsed.password:raise ValueError('Use an HTTP(S) source URL without embedded credentials.')
    with urllib.request.urlopen(urllib.request.Request(url,headers={'Accept':'application/json'}),timeout=5) as response:
        raw=response.read(65537)
    if len(raw)>65536:raise ValueError('The source response exceeds 64 KiB.')
    value=json.loads(raw)
    schema=typed_collections.schema_input(value.get('name'),value.get('fields'),source_authority=True)
    values=typed_collections.values_checked(schema,value.get('values',{}))
    return {'schema':schema,'values':values}

def storage(server):
    file=server.world/'source-connections.json'
    return file,json.loads(file.read_text()) if file.exists() else {}

def run(server,request):
    action=request.get('action')
    if action=='preview':return read(request.get('url',''))
    file,connections=storage(server)
    if action=='connect':
        ident=request.get('event','')
        if len(ident)!=36:raise ValueError('A stable connection identity is required.')
        if ident in connections and connections[ident].get('status')=='ready':return {'connection':connections[ident]}
        url=request.get('url','');value=read(url);schema=value['schema']
        if schema!=request.get('schema'):raise ValueError('The source schema changed. Preview it again before connecting.')
        result=typed_collections.run(server,{'action':'create','name':schema['name'],'fields':schema['fields'],'source':{'kind':'http-json','url':url},'event':ident},_source_authority=True)
        held=connections.get(ident)
        if held:value['values']=held['initialValues']
        else:
            connections[ident]={'id':ident,'status':'connecting','url':url,'schema':schema,'initialValues':value['values']}
            file.write_text(json.dumps(connections,indent=2))
        collection=result['collection'];record_event=str(uuid.uuid5(uuid.UUID(ident),'source-record'))
        result=typed_collections.run(server,{'action':'record','collection':collection,'values':value['values'],'event':record_event},_source_authority=True)
        connection={'id':ident,'status':'ready','url':url,'collection':collection,'record':result['record'],'schema':schema}
        connections[ident]=connection;file.write_text(json.dumps(connections,indent=2))
        return {'connection':connection,'frame':result['frame']}
    if action=='list':return {'connections':[c for c in connections.values() if c.get('status')=='ready']}
    connection=connections.get(request.get('id'))
    if not connection:raise ValueError('Choose a connected provider.')
    if action=='sync':
        latest=read(connection['url'])
        if latest['schema']!=connection['schema']:raise ValueError('The provider schema changed. Existing data is retained; review a new connection.')
        code,frame=server.call('read')
        if code!=200:raise ValueError('The native owner is unavailable.')
        record=next((n for n in frame['nodes'] if n['id']==connection['record']),None)
        if not record:raise ValueError('The connected record is missing.')
        before={p['label']:p['value'] for p in record['properties']}
        fields=[f['name'] for f in latest['schema']['fields'] if not f['writable'] and latest['values'][f['name']]!=before.get(f['name'])]
        if not fields:return {'frame':frame,'changed':False}
        result=typed_collections.run(server,{'action':'update','collection':connection['collection'],'record':record['id'],'fields':fields,'values':{k:latest['values'][k] for k in fields},'before':{k:before[k] for k in fields},'event':str(uuid.uuid4())},_source_authority=True)
        return {'frame':result['frame'],'changed':True}
    raise ValueError('Unknown source action.')
