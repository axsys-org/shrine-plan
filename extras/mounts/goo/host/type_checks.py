"""Compile real Foil clients against the published IR; reject illegal phase use."""
import json, shutil, tempfile
from pathlib import Path
from runtime import run, responses, verify
from wire import string

def cases():
    result=[]
    def add(name,arguments,output,expression,error=None):
        source=f'- goo_app/types\n- goo_app/results\n- goo_app/codecs\n- goo_app/measurement\n- goo_app/ascii\n- goo_app/html\n+ probe\n  \\ {arguments}\n  ^ {output}\n  {expression}\n'
        result.append(dict(name=name,source=source,error=error))
    add('semantic-is-not-prepared','tree=goo/semantic','str','| goo_html/fragment tree','type mismatch')
    add('plan-is-not-prepared','plan=goo_measure/plan','str','| goo_html/fragment plan','type mismatch')
    add('prepared-painter-has-no-width-override','p=goo_html_internal/prepared','str','| goo_html/fragment p (goo_fp/integer 100)','function arity mismatch')
    for phase in ('source','core','normalized','visible','semantic'):
        add(phase+'-flow','a=goo/'+phase+'_attrs child=goo/'+phase,'goo/'+phase,
            f'| goo/{phase}/flow a (goo/direction/row) [child]')
        add(phase+'-text','a=goo/'+phase+'_attrs','goo/'+phase,f'| goo/{phase}/text a "payload"')
        if phase!='source':
            add(phase+'-group-forbidden','a=goo/'+phase+'_attrs','goo/'+phase,f'| goo/{phase}/group a []','unbound reference')
            add(phase+'-opt-forbidden','a=goo/'+phase+'_attrs','goo/'+phase,f'| goo/{phase}/opt a (goo/rank/full) []','unbound reference')
        if phase in ('source','core'):
            add(phase+'-id-forbidden','a=goo/'+phase+'_attrs','goo/node_id','a.node_id','member')
        if phase!='semantic':
            add(phase+'-edge-forbidden','a=goo/'+phase+'_attrs','maybe[goo/edge]','a.after','member')
    for phase in ('normalized','visible','semantic'):
        add(phase+'-id-readable','node=goo/'+phase,'goo/node_id','node.node_id')
    add('semantic-edge-readable','node=goo/semantic','maybe[goo/edge]','node.after')
    add('source-group','a=goo/source_attrs child=goo/source','goo/source','| goo/source/group a [child]')
    add('source-opt','a=goo/source_attrs child=goo/source','goo/source','| goo/source/opt a (goo/rank/full) [child]')
    for before,after in [('source','core'),('core','normalized'),('normalized','visible'),('visible','semantic')]:
        add(before+'-cannot-be-'+after,'value=goo/'+before,'goo/'+after,'value','type mismatch')
        add(after+'-rejects-'+before+'-child','a=goo/'+after+'_attrs child=goo/'+before,'goo/'+after,f'| goo/{after}/flow a (goo/direction/col) [child]','type mismatch')
        add(after+'-rejects-'+before+'-attrs','a=goo/'+before+'_attrs','goo/'+after,f'| goo/{after}/text a "payload"','type mismatch')
    add('nominal-id-not-slot','id=goo/node_id','goo/slot','id','type mismatch')
    add('nominal-slot-not-id','slot=goo/slot','goo/node_id','slot','type mismatch')
    add('native-path-not-goo-path','p=path','goo/path','p','type mismatch')
    add('config-number-not-text','c=goo/config text=str','goo/config','| goo/config c.grow (./some text) c.primary c.toggle c.label c.option_label c.value c.max','type mismatch')
    add('rank-not-natural','n=nat','goo/rank','n','type mismatch')
    add('normalized-requires-id','c=goo/common','goo/normalized_attrs','| goo/normalized_attrs c','arity mismatch')
    add('visible-requires-id','c=goo/common','goo/visible_attrs','| goo/visible_attrs c','arity mismatch')
    add('semantic-requires-id-and-edge-slot','c=goo/common id=goo/node_id','goo/semantic_attrs','| goo/semantic_attrs c id','arity mismatch')
    add('read-output-rejects-core','tree=goo/core','goo_result/output','| goo_result/output/read tree','type mismatch')
    add('semantic-output-rejects-visible','tree=goo/visible','goo_result/output','| goo_result/output/semantic (./some tree)','type mismatch')
    add('pass-rejects-wrong-partial-type','tree=goo/core','goo_result/pass[goo/source]','| goo_result/pass/rejected[goo/source] (./some tree) []','type mismatch')
    add('cancellation-is-not-compiled-result','p=goo_result/progress','goo_result/compiled','| goo_result/control/cancelled p','type mismatch')
    add('cancelled-is-not-pass-failure','u=unit','goo_result/pass[goo/source]','| goo_result/attempt/cancelled','type mismatch')
    add('empty-semantic-success','p=goo_result/progress','goo_result/compiled','| goo_result/compiled p (goo_result/completion/succeeded .none)')
    add('partial-source-failure','tree=goo/source','goo_result/pass[goo/source]','| goo_result/pass/rejected[goo/source] (./some tree) []')
    add('wire-not-semantic','wire=goo_wire/node','goo/semantic','wire','type mismatch')
    add('json-not-semantic','value=json','goo/semantic','value','type mismatch')
    add('semantic-not-wire','tree=goo/semantic','goo_wire/node','tree','type mismatch')
    add('normalized-codec-is-phase-specific','wire=goo_wire/node','maybe[goo/semantic]','| goo_codec/normalized wire','type mismatch')
    add('checked-semantic-decode','value=json','maybe[goo/semantic]','| goo_codec/decode_semantic value')
    add('raw-not-checked-measurement','raw=goo_measure/raw','goo_measure/result','raw','type mismatch')
    add('measurement-requires-validation','raw=goo_measure/raw','goo_measure/result','| goo_measure/make raw','type mismatch')
    add('checked-measurement-factory','raw=goo_measure/raw','maybe[goo_measure/result]','| goo_measure/make raw')
    add('json-not-measurement','value=json','goo_measure/result','value','type mismatch')
    add('size-not-config','size=goo_measure/size','goo/config','size','type mismatch')
    add('plan-id-not-slot','plan=goo_measure/plan','goo/slot','plan.id','type mismatch')
    add('trace-axis-not-string','trace=goo_measure/trace','str','trace.axis','type mismatch')
    add('font-face-not-slot','face=goo_fonts/face','goo/slot','face','type mismatch')
    add('text-style-not-size','style=goo_ascii/style','goo_measure/size','style','type mismatch')
    add('measurement-width-is-scalar','scale=goo/scalar tree=goo/semantic width=nat','goo/scalar','| goo_ascii/leaf_height scale tree width','type mismatch')
    add('source-cannot-be-measured','scale=goo/scalar tree=goo/source','goo_measure/size','| goo_ascii/leaf_size scale tree','type mismatch')
    add('semantic-leaf-measurement','scale=goo/scalar tree=goo/semantic','goo_measure/size','| goo_ascii/leaf_size scale tree')
    return result

PREFIX='''
(define (mentions needle value)
  (If (Equal needle value) 1
    (If (IsApp value)
      (Or (mentions needle (Hd value)) (any (mentions needle) value)) 0)))
(define (compile-client name text)
  (define prepared (source:prepare-publication-with
    (lambda (requested) (If (Equal name requested) (rex:ParseRexNormFile text)
      (error ["unexpected-test-source" requested])))
    (context:publication-key (publication:compilation-context system-plan))
    compiler local-root (Weld (_2 system-code) (_2 app-code)) (lambda (path) 0) [name]))
  (DeepSeq (publication:compile prepared (_1 app-code)) 0))
'''

def check_types(directory=None):
    directory,manifest=verify(directory)
    probes=cases();lines=[PREFIX]
    for i,case in enumerate(probes):
        name='goo_type_probe_'+str(i)
        # Force compilation under Try; checking only an unevaluated result would
        # allow invalid definitions to appear successful in the lazy runtime.
        lines.append(f'(define result (Try (lambda (z) (compile-client {string(name)} {string(case["source"])})) 0))')
        lines.append(f'(Seq (print ("GOO-TYPE-DETAIL" {i} result)) 0)')
        failed='(Eq 1 (Hd result))'
        if case['error']:
            # Match compiler diagnostics, not parse failures or runtime crashes.
            expected=case['error']
            if expected=='member':
                reason='(Or (mentions "unknown member" (_0 result)) (mentions "unbound reference" (_0 result)))'
            elif expected=='arity mismatch':
                reason='(mentions "argument arity mismatch" (_0 result))'
            else:reason=f'(mentions {string(expected)} (_0 result))'
            ok=f'(And {failed} (And (mentions "foil-new-elab" (_0 result)) {reason}))'
        else:ok=f'(Nil {failed})'
        yes=string('{"ok":true}');no=string('{"ok":false}')
        lines.append(f'(Seq (print ("GOO-TYPE" {i} (If {ok} {yes} {no}))) 0)')
    with tempfile.TemporaryDirectory(prefix='goo-types-') as temp:
        work=Path(temp);(work/'snap').mkdir()
        for name in ('data.mdb','pins.pack'):shutil.copy2(directory/'snapshot'/name,work/'snap'/name)
        out,err=run([manifest['wisp'],'--file-root',str(directory/'empty'),'snap','root','_'],work,'\n'.join(lines)+'\n')
    log=out+err
    (directory.parent/'last-type-checks.log').write_text(log)
    answers=responses(log,'GOO-TYPE',len(probes))
    report=[dict(name=c['name'],expected='reject' if c['error'] else 'compile',passed=r['ok']) for c,r in zip(probes,answers)]
    if not all(r['ok'] for r in answers):
        # Keep exact diagnostic trees available for failures, without changing
        # the immutable build or frozen oracle evidence.
        raise AssertionError('Type acceptance failed: '+json.dumps(report)+'\n'+log[-16000:])
    return report

if __name__=='__main__':
    report=check_types();print(json.dumps(report,indent=2))
