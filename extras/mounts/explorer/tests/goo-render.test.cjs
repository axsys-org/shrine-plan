// Deterministic adapter tests: use the real follow/gesture adapter with a tiny
// DOM port. Real browser rehearsal is separately recorded in PANES-VERIFICATION.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const {GooSession} = require('../goo-session.js');
class Element {
  constructor(tag='div') { this.tagName=tag; this.dataset={}; this.children=[]; this.attrs={}; this.listeners={}; this.isConnected=true; this.className=''; this.textContent=''; this.inert=false; }
  append(...nodes) { for(const node of nodes) { node.parentElement=this; this.children.push(node); } }
  prepend(node) { node.parentElement=this; this.children.unshift(node); }
  replaceChildren(...nodes) { this.children=[]; this.append(...nodes); }
  get classList() { return {contains: name => this.className.split(' ').includes(name)}; }
  get nextElementSibling() { const nodes=this.parentElement?.children || []; return nodes[nodes.indexOf(this)+1] || null; }
  insertBefore(node, before) {
    if(node.parentElement) node.parentElement.children=node.parentElement.children.filter(n=>n!==node);
    const at=before?this.children.indexOf(before):this.children.length; this.children.splice(at,0,node); node.parentElement=this; node.isConnected=true;
  }
  setAttribute(k,v) { this.attrs[k]=v; }
  removeAttribute(k) { delete this.attrs[k]; }
  getAttribute(k) { return this.attrs[k]; }
  addEventListener(k,fn) { (this.listeners[k] ||= []).push(fn); }
  remove() { if(this.parentElement) this.parentElement.children=this.parentElement.children.filter(n=>n!==this); this.isConnected=false; }
  querySelectorAll() { return []; }
  querySelector() { return null; }
  contains(node) { return this===node || this.children.some(c=>c.contains(node)); }
  cloneNode() { const e=new Element(this.tagName); e.dataset={...this.dataset}; e.textContent=this.textContent; return e; }
  closest() { return null; }
  focus() { for(const fn of this.listeners.focus || []) fn({target:this}); }
  async fire(kind,fields={}) { const event={target:this,preventDefault(){},stopPropagation(){},...fields}; for(const fn of this.listeners[kind] || []) await fn(event); }
}
const defer=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
const A={key:'A',subject:'/a',life:'1',source:'/cards',sourceLife:'1',type:'namespace-record',expected:'1',status:'available'};
const B={...A,key:'B',subject:'/b'}, C={...A,key:'C',subject:'/c'};
const tree=[{kind:'pane',key:'workspace',children:[{kind:'selection',key:'current',source:{id:'/cards',life:'1',type:'namespace-record',members:[A,B,C]},initial:A,children:[
 {kind:'pane',key:'detail',children:[{kind:'follow',key:'subject',selection:'current',slot:'content'}]},
 {kind:'pane',key:'queue',children:[{kind:'list',key:'rows',selection:'current',source:'/cards',type:'namespace-record',slot:'summary'}]}
]}]}];
const state=(s,kind)=>[...s.owners.values()].find(x=>x.kind===kind);
async function setup() {
 const pending=[], context={GooSession, console, structuredClone, confirm:()=>true};
 context.document={createElement:tag=>new Element(tag),activeElement:null};
 let invocations=0;
 context.GooActions={load:target=>{const d=defer(); pending.push({target,...d}); return d.promise;}, choose:templates=>templates[0], bind:()=>{invocations++;},metrics:{dispatches:0}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../goo-panes.js'),'utf8'),context);
 const controller=new context.GooPanes(new Element(),{target:'/study',view:'/view',report:()=>{}});
 await controller.session.reconcile(tree);
 const follower=state(controller.session,'follow'), selection=state(controller.session,'selection'), list=state(controller.session,'list');
 const element=new Element(); controller.elements.set(follower.id,element);
 return {controller,follower,selection,list,element,pending,context,bindings:()=>invocations};
}
function response(target,label) { const template=new Element(); template.dataset.view='/content';template.textContent=label;return {snapshot:{life:'1',target},templates:[template]}; }
test('S15: actual follow adapter discards delayed A after accepted B and older recipe after become',async()=>{
 const {controller:c,follower:f,selection:s,element:e,pending:p}=await setup();
 const old=c.follow(f,e); assert.equal(p.length,1);
 await c.session.deliver(c.session.intent(s.ref,B)); assert.equal(p.length,2);
 p[1].resolve(response('/b','B')); await Promise.resolve(); await Promise.resolve();
 p[0].resolve(response('/a','A')); await old;
 assert.equal(e.children[0].textContent,'B');
 c.session.become(f.ref,'edit'); assert.equal(p.length,3);
 c.session.become(f.ref,'provenance'); assert.equal(p.length,4);
 p[3].resolve(response('/b','Provenance')); await Promise.resolve(); await Promise.resolve();
 p[2].resolve(response('/b','Editor')); await Promise.resolve(); await Promise.resolve();
 assert.equal(e.children[0].textContent,'Provenance');
});
test('S02/S07/S14: real row listeners select locally, separate focus and suppress nested controls',async()=>{
 const {controller:c,list,selection:s,context}=await setup(); const body=new Element();
 c.list(list,body,{slot:'summary',key:'rows'},[]);
 const b=list.rows.get('B');
 await b.fire('focus'); assert.equal(s.accepted.key,'A'); assert.equal(list.focus.key,'B');
 await b.fire('click',{target:{closest:()=>({tagName:'button'})}}); assert.equal(s.accepted.key,'A');
 await b.fire('keydown',{key:'Enter'}); await Promise.resolve(); await Promise.resolve(); assert.equal(s.accepted.key,'B');
 for(const key of ['C','B']) { await list.rows.get(key).fire('click'); await Promise.resolve(); await Promise.resolve(); }
 assert.equal(s.accepted.key,'B'); assert.equal(context.GooActions.metrics.dispatches,0);
});
test('S16/S17/S27: actual text input guard retains draft and newer candidate supersedes inline prompt',async()=>{
 const {controller:c,follower:f,selection:s,element:e}=await setup();
 c.registerWork(f,e); f.inputs.set('/req',{value:'unsaved',dirty:true,composing:false});
 const b=c.session.deliver(c.session.intent(s.ref,B)); assert.equal(s.accepted.key,'A'); assert(f.departure);
 const oldPrompt=f.departure;
 const next=c.session.deliver(c.session.intent(s.ref,C)); assert.notEqual(f.departure,oldPrompt);
 assert.equal((await b).status,'superseded'); f.departure.finish(false); assert.equal((await next).status,'refused');
 assert.equal(f.inputs.get('/req').value,'unsaved');
 f.inputs.get('/req').composing=true; assert.equal((await c.session.deliver(c.session.intent(s.ref,B))).status,'refused');
 assert.equal(s.accepted.key,'A');
});
test('S25: successful pane action refreshes enclosing observations, and retired continuation cannot clear new work',async()=>{
 const {controller:c,follower:f,selection:s}=await setup(); let refreshed=0;
 c.context.refresh=async()=>{refreshed++;};
 const action=c.actionContext('/a','/view',{target:'/a'},[],[],f);
 f.inputs.set('/req',{value:'A work',dirty:true,composing:false});
 await c.session.deliver(c.session.intent(s.ref,B));
 f.inputs.set('/req',{value:'B work',dirty:true,composing:false});
 await action.saved();
 assert.equal(refreshed,1); assert.equal(f.inputs.get('/req').dirty,true);
 assert.equal(f.inputs.get('/req').value,'B work');
});
test('S15/S17: delayed recipe departure cannot change a newer subject encounter',async()=>{
 const {controller:c,follower:f,selection:s}=await setup(); const gate=defer();
 c.session.guard(f.ref,reason=>reason.kind==='recipe'?gate.promise:true);
 const action=c.actionContext('/a','/view',{target:'/a'},[],[],f);
 const changing=action.become('old-A-editor');
 await c.session.deliver(c.session.intent(s.ref,B)); gate.resolve(true); await changing;
 assert.equal(s.accepted.key,'B'); assert.equal(f.encounter.recipe,'content');
});
test('S27: a completed save must not mark text typed after activation as saved',async()=>{
 const {controller:c,follower:f}=await setup(); c.context.refresh=async()=>{};
 f.inputs.set('/req',{value:'newer draft',dirty:true,composing:false});
 const action=c.actionContext('/a','/view',{target:'/a'},[],[],f);
 await action.saved({},new Map([['/req','submitted text']])); assert.equal(f.inputs.get('/req').dirty,true);
 await action.saved({},new Map([['/req','newer draft']])); assert.equal(f.inputs.get('/req').dirty,false);
});
test('S27: native input/composition listeners own the work used by departure guards',async()=>{
 const {controller:c,follower:f,selection:s,element:e}=await setup(); c.registerWork(f,e);
 const input=new Element('input'); input.value='initial';
 const action=c.actionContext('/a','/view',{target:'/a'},[],[],f); action.input('/req',input);
 await input.fire('compositionstart'); input.value='composing proposal'; await input.fire('input');
 assert.equal(f.inputs.get('/req').value,'composing proposal'); assert.equal(f.inputs.get('/req').composing,true);
 assert.equal((await c.session.deliver(c.session.intent(s.ref,B))).status,'refused');
 assert.equal(s.accepted.key,'A'); await input.fire('compositionend'); assert.equal(f.inputs.get('/req').composing,false);
});
test('S20/S21: actual deck renderer retains keyed tab controls through reevaluation/reorder',async()=>{
 const {controller:c}=await setup();
 const a={kind:'pane',key:'a'}, b={kind:'pane',key:'b'};
 const tabs=children=>[{kind:'deck',key:'tabs',children}];
 const render=async tree=>{await c.session.reconcile(tree);c.usedWrappers=new Set();c.layout(tree,c.body,'session',[]);};
 await render(tabs([a,b])); const deck=state(c.session,'deck'), first=deck.tabs.children[0], second=deck.tabs.children[1];
 await render(tabs([a,b])); assert.equal(deck.tabs.children[0],first); assert.equal(deck.tabs.children[1],second);
 await render(tabs([b,a])); assert.equal(deck.tabs.children[0],second); assert.equal(deck.tabs.children[1],first);
 assert.equal(deck.active,state(c.session,'pane').id);
});
