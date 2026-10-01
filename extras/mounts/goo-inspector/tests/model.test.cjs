const test=require('node:test');
const assert=require('node:assert/strict');
const M=require('../model.js');
test('namespace address validation and URL roundtrip',()=>{
  assert.equal(M.path('/0x11/app/'),'/0x11/app');
  for(const p of ['http://host/','/a//b','/a/../b','/a?x','/a#x','/a\\b','/a\n']) assert.throws(()=>M.path(p));
  const p='/0x11/hello world/%abc';
  assert.equal(new URL(M.link(p),'http://local').searchParams.get('path'),p);
  assert.equal(M.urlPath(p),'/0x11/hello%20world/%25abc');
  assert.equal(M.parent('/0x11/app'),'/0x11');
});
test('composition owns panes and uses existing typed list/follow without actions',()=>{
  const nodes=[]; const walk=ns=>ns.forEach(n=>{nodes.push(n);walk(n.children||[])});
  walk(M.composition('/0x11/app',true));
  const selection=nodes.find(n=>n.kind==='selection');
  assert.equal(selection.source,'/0x11/app');
  assert.equal(nodes.find(n=>n.kind==='list').selection,selection.key);
  assert.equal(nodes.find(n=>n.kind==='follow').selection,selection.key);
  assert.equal(nodes.find(n=>n.kind==='follow').slot,M.SYNTHETIC);
  assert.equal(nodes.filter(n=>n.kind==='selection').length,1);
  assert.ok(!nodes.some(n=>n.kind==='action'));
  assert.ok(!JSON.stringify(M.composition('/0x11/app',false)).includes('"follow"'));
});
test('debug descriptor rejects foreign children and invalid evidence',()=>{
  const d={version:1,path:'/a',hasRecord:true,children:[{path:'/a/b'}],collection:{epoch:'3',childCount:'1',slotCount:'1',nextChildren:null,nextSlots:null}};
  assert.equal(M.descriptor(d,'/a'),d);
  assert.throws(()=>M.descriptor({...d,path:'/b'},'/a'));
  assert.throws(()=>M.descriptor({...d,children:[{path:'/secret'}]},'/a'));
  assert.throws(()=>M.descriptor({...d,children:[{path:'/a/b/c'}]},'/a'));
  assert.throws(()=>M.descriptor({...d,children:[{path:'/a/b'},{path:'/a/b'}]},'/a'));
  assert.throws(()=>M.descriptor({...d,collection:{...d.collection,epoch:null,nextChildren:'cursor'}},'/a'));
});
