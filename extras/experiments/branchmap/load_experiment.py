"""Populate and verify the Branchmap experiment through Shrine MCP only."""
import json,hashlib,time
from pathlib import Path
from shrine_client import tool,rpc,RUN
from controller import *
ROOT=Path(__file__).resolve().parent
BASE='/0x11/user/branchmap'; AGENT='/0x11/agent/astra_branchmap'
def rec(path,**slots): return {'path':path,'slots':slots}
def write(records,**kwargs):
    result=tool('write',records=records,who='astra_branchmap',**kwargs)
    if result.get('refused'): raise RuntimeError(result)
    return result
def ref(path,care='y'):
    return {'type':'reference','value':f'/h/{care}/0/{len(path.strip("/").split("/"))}{path}'}
def text(value): return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def save(name,data):
    RUN.mkdir(exist_ok=True)
    (RUN/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
def main():
    rpc('initialize')
    schemas=rpc('tools/list');save('tools.json',schemas)
    write([rec(AGENT+'/plan',question='Build canonical conditional market namespaces from public Manifold observations',steps='Import provenance; derive verses; simulate assets; compose native cells; verify live updates and history',status='running',model='GPT-6 Astra',boundary='External Python controller; native Shrine records, cells and history')])
    sample=json.loads((ROOT/'data/sample.json').read_text())
    groups=['fomc_october_2026','fed_remainder_2026','bitcoin_2026','bitcoin_2026','bitcoin_2026','central_bank_parlay_2026','shanghai_masters_2026']
    records=[rec(BASE,title='Branchmap namespace experiment',kind='experiment',scope='Observed public data and simulated conditional assets',identity_scheme='SHA-256 demo IDs; not EVM namehash or Keccak',joint_probability='unknown unless directly sourced',facts_policy='Content-hash commitments; no kernel immutability',grouping_policy='Event grouping is local curation'),rec(BASE+'/markets',kind='market-index'),rec(BASE+'/branch',kind='event-root'),rec(BASE+'/sources',kind='provenance-root'),rec(BASE+'/verses',kind='canonical-verse-index'),rec(BASE+'/views',kind='native-cell-folder'),rec(BASE+'/assets',kind='simulated-assets'),rec(BASE+'/aliases',kind='traversal-aliases')]
    for group in sorted(set(groups)):
        records.append(rec(BASE+'/branch/'+group,kind='event-context',title=group,event_id=digest('event',group),grouping='local curation',ownership='observed; unclaimed'))
    markets=[]
    for i,(source,group) in enumerate(zip(sample,groups)):
        m=source['market']; mid=m['id']; path=BASE+'/branch/'+group+'/m_'+mid
        spec={k:m.get(k) for k in ['id','question','description','textDescription','closeTime','outcomeType','resolution','resolutionTime','shouldAnswersSumToOne','addAnswersMode']}
        spec_hash=digest('semantic-spec',spec)
        outcomes=[('yes','YES',m['probability']),('no','NO',1-m['probability'])] if m['outcomeType']=='BINARY' else [(a['id'],a['text'],a.get('probability',0)) for a in m['answers']]
        warning='October title has September exception wording; preserve venue specification' if i==0 else ('BTC threshold markets use different spot/candle rules; no implication asserted' if i in (2,3) else '')
        records.extend([rec(BASE+'/sources/m_'+mid,kind='source',predicate_id=mid,source=source['source'],url=source['source_api'],fetched_at=source['fetched_at'],raw_sha256=source['raw_sha256'],specification=text(spec),specification_hash=spec_hash),rec(path,kind='predicate',predicate_id=mid,event_id=digest('event',group),venue='Manifold',title=m['question'],source_url=m['url'],source_record=BASE+'/sources/m_'+mid,specification_hash=spec_hash,outcome_count=len(outcomes),ownership='observed; unclaimed',semantic_warning=warning,is_resolved=m.get('isResolved',False)),rec(BASE+'/markets/m_'+mid,kind='market',predicate_id=mid,title=m['question'],group=group,venue='Manifold',market_path=path,source_url=m['url'],outcome_count=len(outcomes),probability_ppm=round(m.get('probability',0)*1000000),has_binary_probability=m['outcomeType']=='BINARY',semantic_warning=warning,volume_milli=round(m.get('volume',0)*1000))])
        for index,(key,title,probability) in enumerate(outcomes):
            records.append(rec(path+'/o_'+key,kind='outcome',predicate_id=mid,outcome_id=digest('outcome',[group,mid,key]),outcome_value=key,index=index,title=title,probability_ppm=round(probability*1000000),probability_units='parts per million; observed marginal',source_url=m['url']))
        markets.append({'id':mid,'path':path,'outcomes':[x[0] for x in outcomes]})
    result=write(records);save('import-result.json',result)
    a,b=markets[0]['id'],markets[2]['id']; ab=[(a,'yes'),(b,'yes')]
    sets=[[],[(a,'yes')],[(a,'no')],[(b,'yes')],ab,[(a,'yes'),(b,'no')],[(a,'no'),(b,'yes')],[(a,'no'),(b,'no')]]
    records=[]
    for items in sets:
        vid=verse(items)
        records.append(rec(BASE+'/verses/v_'+vid,kind='verse',verse_id=vid,assignments=text(canonical(items)),assignment_count=len(canonical(items)),probability_status='unpriced conjunction' if len(items)>1 else ('unconditional' if not items else 'marginal available from source'),joint_probability='unknown' if len(items)>1 else 'not applicable',identity_scheme='SHA-256 domain-separated canonical assignments; demo'))
        records.append(rec(BASE+'/assets/a_'+asset('DEMO-USDC',items),kind='conditional-asset',root_asset='DEMO-USDC',verse_id=vid,asset_id=asset('DEMO-USDC',items),simulation=True,custody='none'))
    records.extend([rec(BASE+'/aliases/fed_yes/bitcoin_yes',kind='traversal-alias',canonical_verse=verse(ab),order=a+' then '+b),rec(BASE+'/aliases/bitcoin_yes/fed_yes',kind='traversal-alias',canonical_verse=verse(list(reversed(ab))),order=b+' then '+a)])
    tests=checks(a,b)
    for name,passed in tests.items(): records.append(rec(AGENT+'/checks/'+name,passed=passed,kind='controller-invariant'))
    records.extend([rec(AGENT+'/decisions',identity='SHA-256 prototype scheme, not contract-compatible',execution='Controller enforces operations before MCP write; native kernel does not enforce asset invariants',probabilities='No multiplication of marginal prices; conjunction probability remains unknown',metadata='Public observations; no ownership or resolution authority claimed'),rec(BASE+'/simulation',kind='simulation',quantity_units='demo units',warning='Exclusive child quantities are not additive unconditional wealth')])
    family=split('DEMO-USDC',[],a,['yes','no'],100)
    for index,c in enumerate(family): records.append(rec(BASE+'/simulation/split/'+str(index),operation='split',root=c['root'],verse_id=verse(c['assignments']),quantity=c['quantity'],simulation=True))
    merged=merge(family,[],a,['yes','no'])
    records.append(rec(BASE+'/simulation/merge',operation='complete-sibling-merge',root=merged['root'],verse_id=verse(merged['assignments']),quantity=merged['quantity'],simulation=True))
    for name,resolved in [('partial',{a:'yes'}),('contradicted',{a:'no'}),('complete',{a:'yes',b:'yes'})]:
        n=normalize(ab,resolved);records.append(rec(BASE+'/simulation/resolution/'+name,status=n['status'],verse_id=n['verse'] or 'invalid',remaining=text(n['assignments']),resolved=text(resolved),simulation=True))
    write(records)
    save('controller-checks.json',tests)
    # Ask the world a question before keeping the formulas as cells.
    save('formula-trial.json',tool('read',path=BASE+'/markets',formula='where',settings={'key':'/has_binary_probability','value':'true'}))
    names=['count','where','avg','sum','lookup','select','by']
    wefts={n:tool('read',path='/0x11/weft/stdlib/'+n,care='x')['reference'] for n in names}
    def cell(name,formula,input,**settings):
        return {'path':BASE+'/views/'+name,'slots':{'sys/weft':{'type':'reference','value':wefts[formula]},'sys/tack':ref(input),**settings}}
    write([cell('market_count','count',BASE+'/markets',into='/markets'),cell('binary_markets','where',BASE+'/markets',key='/has_binary_probability',value='true'),cell('mean_binary_probability','avg','/x'+BASE+'/views/binary_markets',slot='/probability_ppm',into='/mean_probability_ppm',purpose='Arithmetic diagnostic across different questions; not a joint probability or investment signal'),cell('outcome_count','sum',BASE+'/markets',slot='/outcome_count',into='/outcomes'),cell('by_event','by',BASE+'/markets',key='/group',op='count',into='/markets'),cell('market_titles','select',BASE+'/markets',slots='/title /source_url /probability_ppm'),cell('source_provenance','lookup',BASE+'/markets',key='/predicate_id',match='/predicate_id',take='/raw_sha256',into='/source_hash',table=ref(BASE+'/sources'))])
    views=['market_count','binary_markets','mean_binary_probability','outcome_count','by_event','market_titles','source_provenance']
    native=tool('read',reads=[{'path':prefix+BASE+'/views/'+n} for n in views for prefix in ['/x','/c/x']])
    save('native-views.json',native)
    for answer in native['answers']:
        assert 'error' not in answer,answer
        assert '/sys/view/fault' not in answer.get('properties',{}),answer
    assert native['answers'][0]['properties']['/markets']=='7',native['answers'][0]
    assert native['answers'][6]['properties']['/outcomes']=='16',native['answers'][6]
    target=BASE+'/markets/m_'+a
    before=tool('read',path=target,care='x')
    avg_before=tool('read',path='/x'+BASE+'/views/mean_binary_probability',care='x')
    old=int(before['properties']['/probability_ppm'])
    changed=write([{'path':target,'action':'poke','slots':{'probability_ppm':old+60000,'update_reason':'temporary propagation test'}}])
    avg_after=tool('read',path='/x'+BASE+'/views/mean_binary_probability',care='x')
    restored=write([{'path':target,'from':before['reference']}])
    avg_restored=tool('read',path='/x'+BASE+'/views/mean_binary_probability',care='x')
    values=[int(x['properties']['/mean_probability_ppm']) for x in [avg_before,avg_after,avg_restored]]
    assert values[1]-values[0]==10000 and values[2]==values[0],values
    save('live-update-check.json',{'before':avg_before,'after':avg_after,'restored':avg_restored,'update':changed,'restore':restored,'passed':True})
    completion=write([rec(AGENT+'/checks/native_composed_live_update',passed=True,before=values[0],after=values[1],restored=values[2]),rec(AGENT+'/progress',status='complete',markets=len(markets),controller_checks=len(tests),native_cells=len(views),live_update_passed=True)])
    history=tool('history',after=0,who='astra_branchmap',with_='x') if False else tool('history',after=0,who='astra_branchmap',**{'with':'x'})
    save('history.json',history)
    write([rec(AGENT+'/seen',epoch=completion['epoch'])])
    save('manifest.json',{'base':BASE,'agent':AGENT,'endpoint':'http://127.0.0.1:8148/mcp','views':views,'markets':markets,'controller_checks':tests,'native_update_values':values,'top_verse':TOP,'joint_verse':verse(ab),'identity_scheme':'SHA-256 demo; not EVM compatible'})
    print(json.dumps({'status':'complete','markets':len(markets),'checks':tests,'live_update_values':values}))
if __name__=='__main__': main()
