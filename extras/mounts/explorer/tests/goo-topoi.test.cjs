const {test}=require('node:test');
const assert=require('node:assert/strict');
const {topology,focusMember}=require('../goo-topoi.js');
const tree=[{key:'root',parent:null},{key:'branch',parent:'root'},{key:'leaf',parent:'branch'}];
test('all topoi use the same keyed memberships',()=> {
 for(const renderer of ['list','diagram_tree','list_tree']) assert.deepEqual([...topology(tree,renderer).keys()],['root','branch','leaf']);
});
test('tree topology rejects ambiguity, orphans and cycles',()=> {
 assert.throws(()=>topology([...tree,{key:'root'}],'list'),/Duplicate/);
 assert.throws(()=>topology([{key:'a'},{key:'b'}],'diagram_tree'),/one root/);
 assert.throws(()=>topology([{key:'root'}, {key:'child',parent:'missing'}],'list_tree'),/Missing/);
 assert.throws(()=>topology([{key:'root'},{key:'a',parent:'b'},{key:'b',parent:'a'}],'diagram_tree'),/Cyclic/);
 assert.throws(()=>topology(tree,'unknown'),/Unknown/);
});

test('tab position requires an available member with the same life and source',()=> {
 const a={key:'a',life:'1',source:'/cards',sourceLife:'2',status:'available'};
 const b={...a,key:'b'}, unavailable={...a,key:'closed',status:'unavailable'};
 assert.equal(focusMember([a,b],b),b);
 assert.equal(focusMember([unavailable,a,b],{...b,life:'old'}),a);
 assert.equal(focusMember([a,b],{...b,sourceLife:'old'}),a);
 assert.equal(focusMember([a,b],{...b,axis:'y'}),a);
 assert.equal(focusMember([a,unavailable],unavailable),a);
 assert.equal(focusMember([unavailable],a),null);
});

const {TreeSource}=require('../goo-topoi.js');
const m=(key,parent,hasChildren=false,life='1')=>({key,parent,hasChildren,life,status:'available'});
const page=(parent,members,next=null,epoch='1')=>({id:'/root',life:'1',axis:'z',topology:'tree',incremental:true,bounded:true,epoch,parent,members,next});
test('opaque cursors advance through pages of omitted raw keys without losing the root',async()=>{
 const calls=[];
 const loader=new TreeSource('/root','z',async q=>{
  calls.push(q);
  return q.after?{...page('/root',[m('/root/named','/root')]),omitted:1}
   :{...page('/root',[m('/root',null,true)],'v1/ts:00'),omitted:64};
 });
 const first=await loader.read();assert.equal(first.omitted,64);assert(first.members[0].moreChildren);
 loader.request(first.members[0],true);
 const next=await loader.read();assert.equal(calls.at(-1).after,'v1/ts:00');
 assert.equal(next.omitted,65);assert.equal(next.members.length,2);assert(!next.members[0].moreChildren);
});
test('incremental trees fetch only expanded child pages, retain identity, and drop removed branches',async()=>{
 const calls=[];let branchLife='1',remove=false;
 const loader=new TreeSource('/root','z',async query=>{
  calls.push(query);
  if(!query.parent)return page('/root',[m('/root',null,true),...(!remove?[m('/root/a','/root',true,branchLife)]:[])],'/root/a');
  if(query.parent==='/root' && query.after)return page('/root',[m('/root/b','/root')]);
  if(query.parent==='/root/a')return page('/root/a',[m('/root/a/leaf','/root/a')]);
  throw Error('Unexpected traversal');
 });
 let result=await loader.read();assert.equal(calls.length,1);assert.equal(result.members.length,2);
 assert.equal(result.members[1].childrenLoaded,false);assert.equal(result.members[0].moreChildren,true);
 loader.request(result.members[1]);result=await loader.read();
 assert.equal(result.members.length,3);assert.equal(calls.at(-1).epoch,'1');
 loader.request(result.members[0],true);result=await loader.read();
 assert.equal(result.members.length,4);assert.equal(result.members[0].moreChildren,false);
 assert.equal(result.members[1].childrenLoaded,true);
 branchLife='2';result=await loader.read();assert.equal(result.members.some(m=>m.key.endsWith('/leaf')),false);
 remove=true;result=await loader.read();assert.equal(result.members.some(m=>m.key==='/root/a'),false);
});
test('tree paging rejects mixed revisions and duplicate children without accepting a partial tree',async()=>{
 let bad='epoch';
 const loader=new TreeSource('/root','z',async q=>q.after
  ?page('/root',[m('/root/a','/root')],null,bad==='epoch'?'2':'1')
  :page('/root',[m('/root',null,true),m('/root/a','/root')],'/root/a'));
 const initial=await loader.read();loader.request(initial.members[0],true);
 await assert.rejects(loader.read(),/changed/);
 bad='duplicate';await assert.rejects(loader.read(),/Duplicate/);
 assert.equal(initial.members.length,2);
});
test('structural branches can receive keyboard focus without becoming selected records',()=>{
 const structural={...m('/root',null,true),status:'unavailable'};
 assert.equal(focusMember([structural],null),structural);
});
test('incremental loading is owned by an outline on the same lexical selection',()=>{
 const {hasOutline}=require('../goo-topoi.js');
 const outline={kind:'topos',renderer:'list_tree',selection:'current'};
 assert.equal(hasOutline([{kind:'pane',children:[outline]}],'current'),true);
 assert.equal(hasOutline([{...outline,renderer:'diagram_tree'}],'current'),false);
 assert.equal(hasOutline([outline],'other'),false);
 assert.equal(hasOutline([{kind:'selection',key:'current',children:[outline]}],'current'),false);
});

test('child presentation packets travel with all loaded pages without entering member references',async()=>{
 const fetch=async q=>q.after
   ?{...page('/root',[m('/root/b','/root')]),presentations:[{key:'/root/b'}]}
   :{...page('/root',[m('/root',null,true),m('/root/a','/root')],'/root/a'),presentations:[{key:'/root'},{key:'/root/a'}]};
 const loader=new TreeSource('/root','z',fetch);
 loader.request(m('/root',null,true),true);loader.request(m('/root',null,true),true);
 const source=await loader.read();
 assert.deepEqual(source.presentations.map(p=>p.key),['/root','/root/a','/root/b']);
 assert(source.members.every(m=>!m.presentations));
});
