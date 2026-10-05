"""OpenRouter selects native continuations and authors source under native checks."""
import hashlib, json, os, threading, time, urllib.request, urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parent
STR={'type':'string'}
SELECTION={'type':'object','additionalProperties':False,'properties':{'subject':STR,'slots':{'type':'array','items':STR},'occurrence':STR},'required':['subject','slots','occurrence']}
EDIT={'type':'object','additionalProperties':False,'properties':{'target':STR,'label':STR,'source':STR,'intent':STR,'reuse':STR,'scope':{'type':'string','enum':['occurrence','definition']},'inputs':{'type':'array','items':SELECTION}},'required':['target','label','source','intent','reuse','scope','inputs']}
EDIT['properties']['source']={**STR,'description':'Full native Grove source. When providing source, reuse MUST be the empty string, including shared definition edits.'}
EDIT['properties']['reuse']={**STR,'description':'Leave empty when authoring or editing source. Otherwise an existing /app/ subject whose compiled definition will be reused without recompilation. Never a /gov/ code root. Source must be empty for reuse.'}
EDIT['properties']['scope']={**EDIT['properties']['scope'],'description':'definition replaces the existing shared code root of the selected occurrence; source must be supplied and reuse must be empty. occurrence edits only this occurrence.'}
SCHEMA={'type':'object','additionalProperties':False,'properties':{'intent':STR,'edits':{'type':'array','items':EDIT}},'required':['intent','edits']}

def scoped_frame(frame, gesture):
    """Deliver exact selected subjects, ancestors and affected consumers.

    Unrelated objects remain discoverable by identity, but their source and old
    synthetic gestures are not examples for this edit. Native assessment still
    checks the complete installed workspace; this is only context selection.
    """
    nodes={n['id']:n for n in frame['nodes']}
    selected=set()
    def anchors(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in ('subject','owner') and isinstance(item,str) and item in nodes:
                    selected.add(item)
                else: anchors(item)
        elif isinstance(value,list):
            for item in value: anchors(item)
    anchors(gesture)
    affected=set(selected)
    while True:
        patterns={nodes[ident].get('pattern') for ident in affected if nodes[ident].get('pattern')}
        more={n['id'] for n in nodes.values()
              if n.get('pattern') in patterns or any(i['subject'] in affected for i in n.get('inputs',[]))}
        if more <= affected: break
        affected |= more
    relevant=set(affected)
    while True:
        more={i['subject'] for ident in relevant for i in nodes[ident].get('inputs',[])
              if i['subject'] in nodes}
        patterns={nodes[ident].get('pattern') for ident in relevant if nodes[ident].get('pattern')}
        more|={n['id'] for n in nodes.values() if n.get('source') and n.get('pattern') in patterns}
        if more <= relevant: break
        relevant |= more
    provenance=[]
    for index,event in enumerate(frame.get('events',[])):
        try:body=json.loads(event.get('body','{}'))
        except (TypeError,ValueError):continue
        # Exact reference membership only. No name or topology similarity.
        def references(value):
            if isinstance(value,str):return {value} if value in relevant else set()
            if isinstance(value,list):return set().union(*(references(v) for v in value))
            if isinstance(value,dict):return set().union(*(references(v) for v in value.values()))
            return set()
        refs=references(body)
        if refs:
            provenance.append({'event':event.get('id'),'basis':event.get('basis'),
                'window_index':index,'operation':event.get('kind'),'references':sorted(refs),'request':body,
                'meaning':'Committed operation history; not proof that its former bindings still hold.'})
    return {key:value for key,value in frame.items() if key not in ('nodes','events')} | {
        'nodes':[n for n in nodes.values() if n['id'] in relevant],
        'selected':sorted(selected),'affected_consumers':sorted(affected-selected),
        'catalog':[{'id':n['id'],'label':n['label'],'pattern':n.get('pattern'),
                    'ready':n.get('ready'),'inputs':n.get('inputs',[])}
                   for n in nodes.values() if n['id'] not in relevant],
        'provenance':provenance,
        'provenance_coverage':'Relevant events within the returned native window (at most 24 of 128 retained); not complete construction history.',
        'context_scope':'Selected boundary, occurrences sharing its definition, dependencies and transitive consumers; unrelated source and event history omitted.'}


def exact_connection(frame, gesture):
    """Reuse one established exact boundary; no name/shape semantic matcher."""
    target=gesture.get('selected',{}).get('subject')
    node=next((n for n in frame['nodes'] if n['id']==target),None)
    if not node or not node.get('relation') or node.get('authored'):
        return None
    if gesture.get('text','').strip() or node.get('description','').strip():
        return None
    matches=[n for n in frame['nodes'] if n.get('authored') and n.get('ready')
             and n.get('relation') and n.get('inputs')==node.get('inputs')]
    if not matches or len({n['pattern'] for n in matches})!=1:
        return None
    origin=matches[0]
    return {'intent':'Reused the established connection; current inputs were checked again.',
        'edits':[{'target':target,'label':origin['label'],'source':'','reuse':origin['id'],
            'scope':'occurrence','inputs':node['inputs'], 'intent':origin.get('intent','')}]}


def author_context(context):
    """A declared context projection, never a mutation of the native frame.

    The current executable source stays complete. Historical source payloads and
    generated image bytes do not need to be repeated to edit that source. Exact
    identities, scalar values, dependencies, action routes and history remain.
    Explicitly selected image slots retain their full value for inspection.
    """
    result=json.loads(json.dumps(context))
    selected=result.get('gesture',{}).get('selected',{})
    media=[]
    def summary(value):
        raw=value.encode('utf-8')
        return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
    for node in result['frame']['nodes']:
        if isinstance(node.get('view'),dict):node['view'].pop('html',None)
        for field in node.get('fields',[]):
            value=field.get('value')
            if (isinstance(value,str) and len(value)>1024 and value.startswith('data:image/')
                    and not (node['id']==selected.get('subject') and field['slot'] in selected.get('slots',[]))):
                media.append({'subject':node['id'],'slot':field['slot'],**summary(value)})
                del field['value']
                field['value_summary']={**summary(value),'media_type':value[5:].split(';',1)[0].split(',',1)[0],
                    'prefix':value[:160], 'coverage':'Generated image bytes omitted from this authoring context; native value is intact. Its generating source is supplied.'}
    def history(value):
        if isinstance(value,dict):
            return {k:({'omitted_historical_source':summary(v)} if k=='source' and isinstance(v,str) and v else history(v)) for k,v in value.items()}
        if isinstance(value,list):return [history(v) for v in value]
        return value
    if 'provenance' in result['frame']:
        result['frame']['provenance']=history(result['frame']['provenance'])
    result['context_projection']={
        'current_source':'Complete current Grove/Foil source, including arbitrary executable checks.',
        'historical_source':'Historical source bodies are replaced by byte counts and hashes; these are not executable source. Operation identities, arguments, decisions and routes remain.',
        'rendering':'Derived HTML omitted. Native occurrence/action references remain. Unselected large generated images have explicit value_summary instead of a value.',
        'omitted_media':media}
    return result


def operational_context(frame):
    """Lossless projection of supplied native facts, not a second type checker.

    Source is included because arbitrary executable Foil constraints cannot be
    reduced honestly to a list of labels. A pinned old world may not export its
    compiled role schema yet; that missing coverage remains explicit.
    """
    subjects=[]
    for n in frame['nodes']:
        subjects.append({k:n[k] for k in ('id','authored','pattern','code_root','expected','displayed',
            'typing','source','inputs','open','ready','fields','intent') if k in n} | {
            'declared_context':n.get('typing') or {'coverage':'This pinned world supplies source and explicit input references, but no compiled role export.'}})
    return {'subjects':subjects,'provenance':frame.get('provenance',[]),
        'provenance_coverage':frame.get('provenance_coverage','No history supplied'),
        'distinctions':[
            'Exact reference identity differs from current realization and from presentation occurrence.',
            'Open input selections are prior anchors, NOT currently supplied values; their requirements survive detachment.',
            'Preserve established interiors; reassess changed boundaries and actual dependent projections.',
            'A prior successful binding is a reuse candidate, not proof it is still valid.',
            'Move preserves subject identity; copying a pattern creates a fresh occurrence and unresolved contextual inputs.',
            'Native declarations and observations are established evidence; proposed role/constraint changes are hypotheses until native assessment.'
        ]}

# The HTTP adapter owns only transport/routing. Every mutation is still a
# native operation with case checking. The model receives no host credential.
KEY_FILE=Path.home()/'.config/shrine/openrouter.key'
CONFIG_FILE=Path.home()/'.config/shrine/models.json'
HTTP_SLOTS=threading.Semaphore(1)


def configuration():
    settings={'decision':{'model':'typesafe/jev-1.13','threshold':.85,'timeout':8},
              'fast':{'model':'openrouter/auto','cost_tier':'low',
                      'fallback':'google/gemini-3.8-flash',
                      'max_tokens':2500,'max_price':{'prompt':1,'completion':5}},
              'author':{'model':'openrouter/auto','cost_tier':'high',
                        'fallback':'anthropic/claude-sonnet-5.5',
                        'max_tokens':10000,'max_price':{'prompt':10,'completion':50}},
              'repair':{'model':'openrouter/auto','cost_tier':'xhigh',
                        'fallback':'openai/gpt-6.1-sol',
                        'max_tokens':12000,'max_price':{'prompt':10,'completion':50}}}
    settings['interpret']={**settings['author'],'max_tokens':3500}
    if CONFIG_FILE.exists():
        overrides=json.loads(CONFIG_FILE.read_text())
        for lane in settings: settings[lane].update(overrides.get(lane,{}))
    return settings


class RoutingFailure(RuntimeError):
    def __init__(self,code,message):super().__init__(message);self.code=code


class IncompleteGeneration(RuntimeError):
    def __init__(self, receipt):
        super().__init__('OpenRouter exhausted this generation budget; native state is unchanged')
        self.receipt=receipt


def credential():
    # Shrine's configured connection must not be silently shadowed by a coding
    # tool's inherited provider credential. Environment is bootstrap fallback.
    try:
        configured = KEY_FILE.read_text().strip()
    except FileNotFoundError:
        configured = ''
    except OSError:
        raise RuntimeError('The configured OpenRouter connection cannot be read') from None
    key = configured or os.environ.get('OPENROUTER_API_KEY')
    if not key:
        raise RuntimeError('OpenRouter is not connected on this machine')
    return key


def completion(messages,lane,cancel,**options):
    settings=configuration()[lane]
    try:return _completion(messages,lane,settings,cancel,options)
    except IncompleteGeneration as error:
        if cancel.is_set():raise RuntimeError('Superseded by your next interaction') from None
        if not settings.get('fallback'):raise
        # One bounded recovery. Never submit a partial tool call or Grove unit.
        budget=min(16000,max(6000,options.get('max_tokens',settings['max_tokens'])*2))
        fallback={**settings,'model':settings['fallback'],'max_tokens':budget}
        recovery_options={**options,'max_tokens':budget}
        try:
            message,receipt=_completion(messages,lane,fallback,cancel,recovery_options)
        except IncompleteGeneration as exhausted:
            exhausted.receipt={**exhausted.receipt,'prior_attempt':error.receipt,
                'recovery':'The one bounded recovery also exhausted its budget; no partial output was executed.'}
            raise
        receipt['recovery']='A prior generation exhausted its budget; no partial output was executed.'
        receipt['prior_attempt']=error.receipt
        return message,receipt
    except RoutingFailure as error:
        if error.code not in (404,429,502,503) or not settings.get('fallback'):raise
        fallback={**settings,'model':settings['fallback']}
        message,receipt=_completion(messages,lane,fallback,cancel,options)
        receipt['fallback_from']=settings['model'];receipt['fallback_status']=error.code
        return message,receipt


def _completion(messages,lane,settings,cancel,options):
    options=dict(options);on_attempt=options.pop('_on_attempt',None)
    if cancel.is_set(): raise RuntimeError('Superseded by your next interaction')
    key=credential()
    payload={'model':settings['model'],'messages':messages,'stream':True,
             'stream_options':{'include_usage':True},'max_tokens':settings['max_tokens'],
             'provider':{'require_parameters':True,'sort':'latency','max_price':settings['max_price']},**options}
    if settings.get('reasoning_effort') and not options.get('reasoning'):
        payload['reasoning']={**payload.get('reasoning',{}),'effort':settings['reasoning_effort']}
    if lane=='fast':payload['reasoning']={'effort':'minimal'}
    if settings['model']=='openrouter/auto':
        payload['plugins']=[{'id':'auto-router','cost_tier':settings['cost_tier']}]
    req=urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',
        json.dumps(payload).encode(),{'Authorization':'Bearer '+key,'Content-Type':'application/json',
        'X-Title':'Grove Native Medium','X-OpenRouter-Metadata':'enabled'})
    while not HTTP_SLOTS.acquire(timeout=.1):
        if cancel.is_set(): raise RuntimeError('Superseded by your next interaction')
    started=time.monotonic();content=[];calls={};usage={};actual=None;generation=None;finish=None
    try:
        if cancel.is_set(): raise RuntimeError('Superseded by your next interaction')
        if on_attempt:on_attempt()
        with urllib.request.urlopen(req,timeout=45) as response:
            for line in response:
                if cancel.is_set(): raise RuntimeError('Superseded by your next interaction')
                if time.monotonic()-started>180: raise RuntimeError('OpenRouter generation timed out; native state is unchanged')
                if not line.startswith(b'data:'): continue
                data=line[5:].strip()
                if data==b'[DONE]': break
                part=json.loads(data)
                if part.get('error'): raise RuntimeError('OpenRouter generation failed; native state is unchanged')
                actual=part.get('model',actual);generation=part.get('id',generation)
                if part.get('usage'): usage=part['usage']
                for choice in part.get('choices',[]):
                    if choice.get('finish_reason'): finish=choice['finish_reason']
                    delta=choice.get('delta',{})
                    if delta.get('content'): content.append(delta['content'])
                    for call in delta.get('tool_calls',[]):
                        dest=calls.setdefault(call['index'],{'id':'','type':'function','function':{'name':'','arguments':''}})
                        if call.get('id'):dest['id']=call['id']
                        for field in ('name','arguments'):
                            if call.get('function',{}).get(field):dest['function'][field]+=call['function'][field]
    except urllib.error.HTTPError as error:
        # Provider bodies may echo request material. Keep errors factual and bounded.
        explanation={401:'OpenRouter rejected the credential',402:'OpenRouter account credit is unavailable',
                     404:'No OpenRouter provider matches this routing policy',429:'OpenRouter is rate limiting this request'}.get(error.code,'OpenRouter request failed')
        raise RoutingFailure(error.code,f'{explanation} (HTTP {error.code}); native state is unchanged') from None
    except (OSError,ValueError):
        raise RuntimeError('OpenRouter connection interrupted; native state is unchanged') from None
    finally: HTTP_SLOTS.release()
    receipt={'provider':'OpenRouter','lane':lane,'requested_model':settings['model'],
        'model':actual,'generation':generation,'seconds':round(time.monotonic()-started,2),
        'usage':usage,'finish_reason':finish}
    if cancel.is_set():raise RuntimeError('Superseded by your next interaction')
    if finish=='length':raise IncompleteGeneration(receipt)
    if finish not in ('stop','tool_calls'):
        raise RuntimeError('OpenRouter did not complete the requested response; native state is unchanged')
    message={'role':'assistant','content':''.join(content),'tool_calls':list(calls.values())}
    return message,receipt


def run(context,diagnostics,cancel,world):
    prompt=(ROOT/'proof/authoring.txt').read_text()
    authored_context=author_context(context) if context.get('proof') else context
    messages=[{'role':'system','content':prompt},
              {'role':'user','content':'NATIVE WORLD + LOCAL INTENT:\n'+json.dumps(authored_context,ensure_ascii=False)}]
    if diagnostics:messages.append({'role':'user','content':'RECONSIDER THIS FEEDBACK: native_error records actual native failures. inference_review is a fallible interpretation of the proposed types and reference continuity, not a compiler finding.\n'+json.dumps(diagnostics[-2:],ensure_ascii=False)})
    schema=SCHEMA
    options={}
    if context.get('proof'):
        # The small grammar refines exactly one selected subject. Addresses are
        # facts supplied by the owner, not another model inference task.
        target=context['gesture']['selected']['subject']
        construction='native-definition-actions' in context['frame'].get('features',[])
        targets=[target,*context.get('new_subjects',[])] if construction else [target]
        schema={**SCHEMA,'properties':{**SCHEMA['properties'],'edits':{
            'type':'array','maxItems':len(targets),'items':{**EDIT,'properties':{
                **EDIT['properties'],'target':{'type':'string','enum':targets}}}}}}
        options['reasoning']={'effort':'medium' if construction else 'minimal'}
    message,receipt=completion(messages,'repair' if diagnostics else 'author',cancel,
        response_format={'type':'json_schema','json_schema':{'name':'native_candidate','strict':True,'schema':schema}},**options)
    receipt['context_bytes']=len(json.dumps(authored_context,ensure_ascii=False).encode())
    receipt['supplied_context_bytes']=len(json.dumps(context,ensure_ascii=False).encode())
    try:candidate=json.loads(message['content'])
    except ValueError:raise RuntimeError('The source author returned invalid structured output; no change was installed') from None
    if context.get('proof') and any(e.get('target') not in targets for e in candidate.get('edits',[])):
        raise RuntimeError('The author proposed a target outside this construction boundary')
    if not isinstance(candidate.get('edits'),list):raise RuntimeError('The source author omitted native edits')
    if 'definition-scope' not in context['frame'].get('features',[]):
        if any(e.get('scope')=='definition' for e in candidate['edits']):
            raise RuntimeError('This pinned world cannot yet publish a shared definition edit; its existing objects are unchanged')
        for edit in candidate['edits']:edit.pop('scope',None)
    return candidate,receipt
