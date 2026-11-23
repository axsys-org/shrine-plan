#!/usr/bin/env python3
"""Disposable namespace workbench acceptance, using authoritative live receipts."""
import argparse, json, time, urllib.request, urllib.error


def check(server, mock=None):
    results=[]
    def request(**body):
        req=urllib.request.Request(server+'/shuin-test',json.dumps(body).encode(),{'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=180) as response:
            text=response.read().decode()
        try: return json.loads(text)
        except ValueError: return text
    def status(target='post_message'):
        return request(operation='workbench_status',target=target)
    def command(command,target='post_message'):
        request(operation='workbench_command',target=target,command=command)
        return status(target)
    def source(text,target='post_message'):
        request(operation='workbench_source',target=target,source=text)
    def slot(path,slot,value,target='post_message'):
        request(operation='workbench_slot',target=target,path=path,slot=slot,value=value)
    def expect(name, condition, detail=None):
        assert condition, (name,detail)
        results.append(name)
        print('PASS:', name, flush=True)
    post=status(); reflection=status('reflection')
    expect('both targets bootstrap through tested candidates',post['active']==1 and reflection['active']==1,[post,reflection])
    original=post['source']
    changed=original.replace('message body by created_at','message (str/cat_all ["[live] " body]) by created_at')
    channel='/0x11/app/shuin_chat/festival'
    def provider(route):
        req=urllib.request.Request(mock+route,b'{}',{'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=10) as response: return response.read()
    def queue(task):
        request(operation='queue',agent='workbench_poster',task=task,dependencies=channel,writes=channel)
    def idle():
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            current=request(operation='state',agent='workbench_poster')
            if not current['inbox'] and current['status']=='idle': return current
            time.sleep(.1)
        raise AssertionError(current)
    if mock:
        provider('/release')
        previous=request(operation='state',agent='workbench_poster')
        if previous['status']=='running': idle()
        prior=[r for r in request(operation='stencil_inspect',path=channel) if r['author']=='workbench_poster']
        prior_changed=sum(r['content'].startswith('[live] ') for r in prior)
        queue('Post a baseline message.')
        first_agent=idle()
        with urllib.request.urlopen(mock,timeout=10) as response: provider_before=len(json.load(response))
        provider('/hold')
        queue('Post after the publication race.')
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            with urllib.request.urlopen(mock,timeout=10) as response: held=json.load(response)
            if len(held)>=provider_before+2: break
            time.sleep(.1)
        else: raise AssertionError('Provider never reached held creation response')
    before=request(operation='stencil_inspect',path='/0x11/app/shuin_chat/festival')
    def discover():
        return request(operation='stencil_tool',grant=channel,care='z',call={'function':{'name':'grove_stencils','arguments':json.dumps({'path':channel})}})
    discovery_before=discover()
    fixture_before=request(operation='stencil_inspect',path='/0x11/app/workbench/post_message/fixture')
    expect('test receipts passed',post['passed'] and reflection['passed'])
    source(changed)
    built=command('build'); expect('build preserves every active output revision',built['versions']==post['versions'],built)
    expect('new candidate is isolated',built['candidate']!=post['candidate'] and built['active']==1,built)
    expect('unpublished candidate is absent from discovery',discover()['stencils']==discovery_before['stencils'])
    failed=command('test');expect('old expectations catch changed behavior',not failed['passed'] and failed['active']==1,failed)
    refused=command('publish');expect('failed test prevents activation',refused['active']==1 and refused['versions']==post['versions'],refused)
    for name,content,author in [('normal','Hello','Tester'),('unicode','שלום\nHello 🌱','テスト')]:
        expected={'/sys/content':{'type':'text','value':'[live] '+content},'/sys/author':{'type':'text','value':author}}
        slot('/0x11/app/workbench/post_message/tests/'+name,'/sys/workbench/outputs',json.dumps(expected,ensure_ascii=False))
    passed=command('test');expect('editable expectations rerun the same candidate',passed['passed'] and passed['candidate']==built['candidate'],passed)
    def fixture(path):
        case='/0x11/app/workbench/post_message/tests/normal'
        call={'function':{'name':'namespace_write','arguments':json.dumps({'path':case,'slot':'/sys/workbench/fixture','type':'path','value':path})}}
        request(operation='stencil_tool',grant=case,care='x',call=call)
    fixture('/0x11/gov/shuin_chat/post_message')
    refused=command('test');expect('fixture cannot replace the candidate being tested','Fixtures must be separate' in refused['status'],refused)
    refused=command('publish');expect('fixture overlay attempt cannot activate',refused['active']==1,refused)
    fixture('/0x11/app/workbench/post_message/fixture')
    command('test')
    published=command('publish');expect('exact candidate activated',published['active']==2 and published['candidate']==built['candidate'] and published['artifactMatches'],published)
    after=request(operation='stencil_inspect',path='/0x11/app/shuin_chat/festival')
    expect('build and tests create no live messages',before==after)
    expect('tests retain the captured fixture',fixture_before==request(operation='stencil_inspect',path='/0x11/app/workbench/post_message/fixture'))
    if mock:
        provider('/release')
        later=idle()
        messages=request(operation='stencil_inspect',path=channel)
        posts=[r for r in messages if r['author']=='workbench_poster']
        expect('held stale creation rediscovered without duplication',len(posts)==len(prior)+2 and sum(r['content'].startswith('[live] ') for r in posts)==prior_changed+1,posts)
        history=' '.join(str(e) for e in later['entries'])
        expect('stale creation receipt retained in same agent history','discover stencils again' in history and len(later['entries'])>len(first_agent['entries']),history)
        queue('Post again through the new stencil.')
        idle()
        posts=[r for r in request(operation='stencil_inspect',path=channel) if r['author']=='workbench_poster']
        expect('existing agent uses new publication on subsequent task',len(posts)==len(prior)+3 and sum(r['content'].startswith('[live] ') for r in posts)==prior_changed+2,posts)
    def denied(name,args):
        call={'id':'guard','function':{'name':name,'arguments':json.dumps(args)}}
        req=urllib.request.Request(server+'/shuin-test',json.dumps({'operation':'stencil_tool','grant':'/0x11','care':'z','call':call}).encode(),{'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=30) as response: raise AssertionError(response.read())
        except urllib.error.HTTPError as error:
            body=error.read().decode()
            expect('agent denial: '+args.get('path',''),error.code==409 and 'protected' in body,body)
    denied('namespace_write',{'path':'/0x11/app/workbench/post_message','slot':'/sys/workbench/command','type':'text','value':'publish'})
    denied('namespace_write',{'path':'/0x11/lib/shuin_post_message/post_message','slot':'/sys/content','type':'text','value':'forged'})
    denied('namespace_write',{'path':published['run'],'slot':'/sys/workbench/run','type':'text','value':'passed'})
    denied('namespace_write',{'path':'/0x11/weft/change_workbench/post_message','slot':'/sys/workbench/registration','type':'text','value':'forged'})
    denied('grove_invoke',{'path':'/0x11/app/workbench/post_message','action':'/0x11/gov/shuin_workbench/publish','recordVersion':'0','publication':'0','roleVersion':'0','arguments':{}})
    def draft_command(command):
        source_path='/0x11/app/workbench/post_message/source'
        call={'id':'draft','function':{'name':'namespace_write','arguments':json.dumps({'path':source_path,'slot':'/sys/workbench/command','type':'text','value':command})}}
        return request(operation='stencil_tool',grant=source_path,care='x',call=call)
    draft_command('build');draft_command('test')
    expect('authorized agent can build and test without activation',status()['passed'] and status()['active']==2,status())
    draft_command('publish')
    expect('source commands cannot publish',status()['active']==2 and 'human control' in status()['status'],status())
    # Source edit, concurrent fixture change, and invalid interfaces retain active output.
    source(original+'\n# invalid syntax (')
    rejected=command('build');expect('bad source retains publication',rejected['active']==2 and rejected['versions']==published['versions'],rejected)
    source(original.replace('#import author=', '#import help=sys/help\n#import author=').replace('  content: text', '  help: text'))
    rejected=command('build');expect('incompatible interface retains publication',rejected['active']==2 and 'interface' in rejected['status'],rejected)
    source(changed)
    command('build');tested=command('test')
    expect('passing candidate precedes concurrent edit',tested['passed'],tested)
    source(changed+'\n')
    source(changed)
    rejected=command('publish');expect('edit then revert invalidates source revision',rejected['active']==2 and 'Source or dependencies' in rejected['status'],rejected)
    source(changed)
    command('build');command('test')
    slot('/0x11/gov/shuin_chat/channel','/sys/help','A dependency changed after testing.')
    rejected=command('publish');expect('changed dependency prevents activation',rejected['active']==2 and 'dependencies' in rejected['status'],rejected)
    command('build');command('test')
    slot('/0x11/lib/shuin_post_message/post_message','/sys/help','A concurrent live predecessor edit.')
    concurrent=status()
    rejected=command('publish');expect('stale predecessor preserves entire output set',rejected['active']==2 and rejected['versions']==concurrent['versions'] and 'dependencies' in rejected['status'],rejected)
    command('build');command('test')
    slot('/0x11/app/workbench/post_message/tests/normal','/sys/workbench/outputs','{}')
    rejected=command('publish');expect('changed case invalidates its receipt',rejected['active']==2 and 'cases or fixtures' in rejected['status'],rejected)
    # Reflection uses the same lifecycle, with a multi-record publication.
    refl=reflection['source'].replace('    row {','    col {',1)
    source(refl,'reflection');built=command('build','reflection')
    expect('view candidate includes generated records',len(built['records'])>1,built)
    tested=command('test','reflection');expect('semantic reflection tests pass',tested['passed'],tested)
    slot('/0x11/app/shuin_reflection/note','/sys/content','Fixture changed','reflection')
    rejected=command('publish','reflection');expect('changed fixture invalidates receipt',rejected['active']==1,rejected)
    command('test','reflection');published=command('publish','reflection')
    expect('reflection uses common publication lifecycle',published['active']==2 and published['artifactMatches'],published)
    request(operation='workbench_clone',target='reflection')
    command('build','third');tested=command('test','third');published=command('publish','third')
    expect('additional registration reuses existing adapter',tested['passed'] and published['active']==1 and published['artifactMatches'],published)
    expect('multi-source target publishes both output boundaries',any(p.startswith('/0x11/gov/workbench_auxiliary') for p in published['records']) and any(p.startswith('/0x11/gov/workbench_third') for p in published['records']),published)
    expect('publishing another target preserves unrelated output records',status('reflection')['artifactMatches'])
    return {'checks':results,'post_message':status(),'reflection':status('reflection'),'third':status('third')}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--server',default='http://127.0.0.1:8376');p.add_argument('--output');p.add_argument('--mock');args=p.parse_args()
    result=check(args.server,args.mock);text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output: open(args.output,'w').write(text+'\n')
    print(text)
