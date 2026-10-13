"""Package acceptance tests; no server and no compilation during requests."""
import copy, gzip, json, subprocess, sys, tempfile
from pathlib import Path
from runtime import PACKAGE, GOO, verify, invoke
from adapter import batch
from type_checks import check_types
from codec_checks import check_codecs
from gate_checks import check_gate
from measurement_checks import check_measurements
from ascii_checks import check_ascii
from layout_checks import check_layout, match
from html_checks import check_html, match_envelope
from cancellation_checks import check_cancellation
from formatter import format_sources, candidate, has_error
sys.path.insert(0,str(GOO/'scripts/porting'))
from oracle_compare import first, canonical

def require(condition,message):
    if not condition:raise AssertionError(message)
def same(expected,actual,context):
    mismatch=first(expected,actual)
    require(not mismatch,context+': '+json.dumps(mismatch))
def main():
    directory,manifest=verify()
    unit=invoke([('tests',None)])[0]
    require(unit['ok'],'Foil unit checks failed: '+json.dumps(unit))
    print('Foil unit checks:',len(unit['checks']),flush=True)
    types=check_types(directory)
    print('Foil type compilation checks:',len(types),flush=True)
    cancellation=check_cancellation()
    (directory.parent/'last-cancellation-checks.json').write_text(json.dumps(cancellation,indent=2)+'\n')
    print('Cancellation checks:',len(cancellation),flush=True)
    check_codecs()
    records=json.load(gzip.open(GOO/'porting/oracle-reference.json.gz','rt'))
    for start in range(0,len(records),40):
        chunk=records[start:start+40]
        actual=batch([r['case']['request'] for r in chunk])
        for record,answer in zip(chunk,actual):
            require(answer.get('ok') is True,record['case']['name']+': '+str(answer))
            match_envelope(record['response'],answer,record['case']['name'])
    print('Frozen oracle full responses:',len(records),flush=True)
    require(batch([dict(version=1,action='source',source='x',width=None,hiddenPaths=None)])[0]['ok'],'null option defaults rejected')
    leaf=dict(tag='leaf',span=[3,2,8,4],shape='word',text='test')
    trees=[leaf]
    for tag in ['nest','expr','pref','tyte','bloc','open','juxt','heir']:
        tree=dict(tag=tag,span=[1,2,3,4])
        if tag in ['nest','expr','bloc']:tree['color']='paren'
        if tag in ['nest','pref','tyte','bloc','open']:tree['rune']='+'
        if tag=='bloc':tree['head']=copy.deepcopy(leaf)
        if tag=='pref':tree['kid']=copy.deepcopy(leaf)
        else:tree['kids']=[copy.deepcopy(leaf)]
        trees.append(tree)
    for shape in ['quip','cord','tape','page','span','slug']:
        trees.append(dict(leaf,shape=shape))
    for reason in ['invalid-char','unclosed-trad','unclosed-ugly','mismatched-bracket','invalid-page','invalid-span']:
        trees.append(dict(leaf,shape={'bad':reason}))
    same(trees,batch([dict(version=1,action='echo',trees=trees)])[0]['trees'],'all Rex constructors')
    invalid=[None,{},dict(version=True,action='parse',source='x'),dict(version=2,action='source',source='x'),dict(version=1,action='parse',source='\0'),dict(version=1,action='echo',trees=[dict(leaf,span=[True,0,0,0])]),dict(version=1,action='source',source='x',width=-1),dict(version=1,action='source',source='x',surprise=1),dict(version=1,action='source',source='x',hiddenPaths=['bad']),dict(version=1,action='source',source='x',viewPath='/a/../b')]
    require(all(r['ok'] is False and r['stage']=='protocol' for r in batch(invalid)),'invalid requests accepted')
    require(batch([dict(version=1,action='fixture')])[0]['stage']=='protocol','missing fixture tree must fail protocol')
    parsed=batch([dict(version=1,action='parse',source='foo(bar)')])[0]
    printed=batch([dict(version=1,action=a,trees=parsed['trees']) for a in ['print','goo-print']])
    require(printed[0]['ok'] and isinstance(printed[0]['texts'],list) and printed[1]['ok'] and isinstance(printed[1]['text'],str),'printers failed')
    with tempfile.TemporaryDirectory(prefix='goo-foil-check-') as temp:
        for raw in ['{"version":1,"action":"capabilities"}','[{"version":1,"action":"capabilities"}]','{','{"version":NaN}']:
            proc=subprocess.run([str(PACKAGE/'bin/goo-foil'),'adapter'],input=raw,text=True,capture_output=True,cwd=temp,timeout=120)
            require(proc.returncode==0 and not proc.stderr,'standalone adapter stderr/exit: '+proc.stderr)
            response=json.loads(proc.stdout)
            require(isinstance(response,list)==raw.startswith('['),'response framing changed')
        good='+ example\n  ^ nat  \n  1\n\n'
        formatted=format_sources([good])[0]
        same(candidate(good),formatted,'formatter whitespace')
        same(formatted,format_sources([formatted])[0],'formatter idempotence')
        crlf=good.replace('\n','\r\n')
        try:format_sources([crlf])
        except ValueError:pass
        else:raise AssertionError('formatter must reject native CRLF error leaves')
        # Multiline string trailing whitespace is payload, not formatting.
        unsafe='+ message\n  ^ str\n  "payload  \n   next"\n'
        require(not has_error(invoke([('syntax',unsafe)])[0]),'payload regression must have valid syntax')
        try:format_sources([unsafe])
        except ValueError:pass
        else:raise AssertionError('formatter changed multiline-string payload')
        target=Path(temp)/'changed';target.mkdir()
        (target/'snapshot').symlink_to(directory/'snapshot',target_is_directory=True)
        (target/'retained-rex').symlink_to(directory/'retained-rex')
        changed=copy.deepcopy(manifest);changed['inputs']={}
        (target/'manifest.json').write_text(json.dumps(changed))
        try:verify(target)
        except RuntimeError as error:require('stale' in str(error),'wrong stale-build diagnosis')
        else:raise AssertionError('stale build accepted')
        changed=copy.deepcopy(manifest);changed['artifacts']['retained-rex']='0'*64
        (target/'manifest.json').write_text(json.dumps(changed))
        try:verify(target)
        except RuntimeError as error:require('artifact changed' in str(error),'wrong artifact diagnosis')
        else:raise AssertionError('corrupt build accepted')
    verify()
    print('Transport, printers, invalid requests, standalone framing, formatter and immutable artifacts: passed')
    check_gate(frozen_verified=len(records))
    check_measurements()
    check_ascii()
    check_layout()
    check_html(frozen_verified=len(records))
    print('Package acceptance passed (items 03–28, Gates S, M, L and H)')
