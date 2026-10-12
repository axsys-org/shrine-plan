const {test}=require('node:test');
const assert=require('node:assert/strict');
const inspection=require('../goo-inspection.js');
const packet=()=>({view:'/gov/summary',role:'/gov/record',slot:'/sys/slot/label',kind:'view',
  snapshot:{subject:'/projection/a',target:'/objects/a',life:'7',displayed:'11',expected:'9',publication:'3',projectionSeq:'200'},
  context:{width:240,textScale:1,direction:'ltr'},profile:{id:'mash-goo',version:1,revision:'hash'},
  origin:{line:20,column:3},layout:'sm',display:{height:80,nodes:[{},{}]},controls:[{invoke:true,token:'secret'}]});
test('inspection records the installed packet, without aliasing subsequent mutations',()=>{
  const element={isConnected:true},data=packet();inspection.record(element,data);
  data.snapshot.displayed='12';data.origin.line=99;data.context.width=480;
  const captured=inspection.capture(element);
  assert.equal(captured.displayed,'11');assert.equal(captured.line,'20');assert.equal(captured.renderWidth,'240');
  assert.equal(captured.subject,'/projection/a');assert.equal(captured.target,'/objects/a');
  assert.equal(captured.renderHeight,'80');assert.equal(captured.layout,'sm');assert.equal(captured.nodes,'2');assert(Object.isFrozen(captured));
});
test('local observations expose counters and identity but never draft values or handles',()=>{
  const element={isConnected:true};inspection.record(element,packet());
  inspection.bind(element,()=>({revision:4,owner:'pane',encounter:'e1',dirty:2,composing:1,
    selection:'/projection/a',live:true,handle:{token:'secret'},inputs:[{value:'private draft'}]}));
  const captured=inspection.capture(element),text=JSON.stringify(captured);
  assert.equal(captured.revision,'4');assert.equal(captured.dirty,'2');assert.equal(captured.composing,'1');
  assert(!text.includes('secret'));assert(!text.includes('private draft'));assert(!text.includes('controls'));
});
test('capture stays frozen while recapture reports the new installation',()=>{
  const element={isConnected:true};inspection.record(element,packet());const first=inspection.capture(element);
  const replacement=packet();replacement.snapshot.life='8';inspection.record(element,replacement);
  const second=inspection.capture(element);assert.notEqual(first.capture,second.capture);
  assert.equal(first.life,'7');assert.equal(second.life,'8');
});
test('removed and retired owners cannot produce new observations',()=>{
  const element={isConnected:true};inspection.record(element,packet(),()=>({live:false}));
  assert.throws(()=>inspection.capture(element),/retired/);
  inspection.bind(element,()=>({live:true}));element.isConnected=false;
  assert.throws(()=>inspection.capture(element),/no longer installed/);
});
test('picking chooses the innermost installed presentation',()=>{
  const pane={isConnected:true},row={isConnected:true,parentElement:pane},leaf={parentElement:row};
  inspection.record(pane,packet());inspection.record(row,packet());assert.equal(inspection.find(leaf),row);
});
test('the generated inspection can itself be captured without recursive expansion',()=>{
  const element={isConnected:true};const data={...packet(),kind:'inspection',capture:'parent-capture'};
  delete data.snapshot;inspection.record(element,data,()=>({subject:'/objects/a',owner:'inspection',live:true}));
  const captured=inspection.capture(element);assert.equal(captured.parent,'parent-capture');assert.equal(captured.kind,'inspection');
  assert.equal(captured.subject,'/objects/a');assert.equal(captured.displayed,'');
});
