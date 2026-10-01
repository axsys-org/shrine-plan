const {test} = require('node:test');
const assert = require('node:assert/strict');
const {GooWorkspace} = require('../goo-workspace.js');
const {GooSession} = require('../goo-session.js');
const source='/0x11/gov/example';
const unit=(requested,completed,ready=true)=>({source,requested,completed,ready});
function host(units) {
  const calls=[]; let reloads=0;
  const adapter=new GooWorkspace([{key:'/reload',kind:'mount-rescan',source}],{
    fetch:async(url,options)=>{calls.push([url,options]);return {ok:true,json:async()=>({units:[units.shift()]})};},
    reload:()=>reloads++, sleep:async()=>{}
  });
  return {adapter,calls,reloads:()=>reloads};
}
test('host rescan pins expected scan, polls publication, and reloads on success', async()=>{
  const h=host([unit('1','1'),unit('2','1'),unit('2','1'),unit('2','2')]);
  await h.adapter.run('/reload');
  assert.equal(h.calls[1][1].method,'POST');
  assert.equal(h.calls[1][1].body.get('scan'),'1');
  assert.equal(h.calls[1][1].body.get('source'),source);
  assert.equal(h.adapter.state('/reload').phase,'success');assert.equal(h.reloads(),1);
});
test('publication failure keeps page and exposes diagnostic',async()=>{
  const h=host([unit('1','1'),unit('2','1'),{...unit('2','2',false),diagnostic:'line 12: syntax error'}]);
  await h.adapter.run('/reload');assert.equal(h.reloads(),0);
  assert.equal(h.adapter.state('/reload').message,'line 12: syntax error');
});
test('superseded scan does not reload',async()=>{
  const h=host([unit('1','1'),unit('2','1'),unit('3','3')]);
  await h.adapter.run('/reload');assert.equal(h.adapter.state('/reload').phase,'error');assert.equal(h.reloads(),0);
});
test('unknown capability cannot cause a request',async()=>{
  const h=host([]);await assert.rejects(h.adapter.run('/other'),/Unavailable/);assert.equal(h.calls.length,0);
});
test('duplicate operation is ignored while pending',async()=>{
  let release, calls=0;
  const waiting=new Promise(r=>release=r);
  const h=new GooWorkspace([{key:'/reload',kind:'mount-rescan',source}],{fetch:async()=>{calls++;await waiting;throw Error('offline');},reload:()=>{}});
  const first=h.run('/reload'); await h.run('/reload');assert.equal(calls,1);release();await first;
  assert.equal(h.state('/reload').phase,'error');
});
test('host controls require a pane and have scoped identities',async()=>{
  const session=new GooSession();
  assert.throws(()=>session.plan([{kind:'navigate',key:'go'}]),/requires-pane/);
  await session.reconcile(['a','b'].map(key=>({kind:'pane',key,children:[{kind:'operation',key:'reload',operation:'/reload'}]})));
  assert.equal([...session.owners.values()].filter(s=>s.kind==='operation').length,2);
});
