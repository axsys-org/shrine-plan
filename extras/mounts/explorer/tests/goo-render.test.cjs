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
  get classList() { return {contains: name => this.className.split(' ').includes(name), add: name => {this.className += ' '+name;}}; }
  get nextElementSibling() { const nodes=this.parentElement?.children || []; return nodes[nodes.indexOf(this)+1] || null; }
  insertBefore(node, before) {
    if(node.parentElement) node.parentElement.children=node.parentElement.children.filter(n=>n!==node);
    const at=before?this.children.indexOf(before):this.children.length; this.children.splice(at,0,node); node.parentElement=this; node.isConnected=true;
  }
  setAttribute(k,v) { this.attrs[k]=v; }
  removeAttribute(k) { delete this.attrs[k]; }
  toggleAttribute(k,on) { if(on)this.setAttribute(k,'');else this.removeAttribute(k); }
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
const defer=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const A={key:'A',subject:'/a',life:'1',source:'/cards',sourceLife:'1',type:'namespace-record',expected:'1',status:'available'};
const B={...A,key:'B',subject:'/b'}, C={...A,key:'C',subject:'/c'};
const tree=[{kind:'pane',key:'workspace',children:[{kind:'selection',key:'current',source:{id:'/cards',life:'1',type:'namespace-record',members:[A,B,C]},initial:A,children:[
 {kind:'pane',key:'detail',children:[{kind:'follow',key:'subject',selection:'current',slot:'content'}]},
 {kind:'pane',key:'queue',children:[{kind:'list',key:'rows',selection:'current',source:'/cards',type:'namespace-record',slot:'summary'}]}
]}]}];
const state=(s,kind)=>[...s.owners.values()].find(x=>x.kind===kind);
async function setup() {
 const pending=[], context={GooSession, console, structuredClone, AbortController, requestAnimationFrame:setImmediate, confirm:()=>true};
 context.document={createElement:tag=>new Element(tag),activeElement:null};
 let invocations=0;
 context.GooActions={context:()=>({width:400,textScale:1,direction:'ltr'}),observe:()=>()=>{},mount:(element,data)=>{element.replaceChildren(data.template.cloneNode(true));},load:target=>{const d=defer(); pending.push({target,...d}); return d.promise;}, choose:templates=>templates[0], bind:()=>{invocations++;},metrics:{dispatches:0}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../goo-topoi.js'),'utf8'),context);
 vm.runInNewContext(fs.readFileSync(require.resolve('../goo-panes.js'),'utf8'),context);
 const controller=new context.GooPanes(new Element(),{target:'/study',view:'/view',report:()=>{}});
 await controller.session.reconcile(tree);
 const follower=state(controller.session,'follow'), selection=state(controller.session,'selection'), list=state(controller.session,'list');
 const element=new Element(); controller.elements.set(follower.id,element);
 return {controller,follower,selection,list,element,pending,context,bindings:()=>invocations};
}
function response(target,label) { const template=new Element(); template.dataset.view='/content';template.textContent=label;return {snapshot:{life:'1',target},view:'/content',controls:[],template}; }
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
 const b=list.topos.items.get('B');
 await b.fire('focusin'); assert.equal(s.accepted.key,'A'); assert.equal(list.focus.key,'B');
 await b.fire('click',{target:{closest:()=>({tagName:'button'})}}); assert.equal(s.accepted.key,'A');
 await b.fire('keydown',{key:'Enter'}); await Promise.resolve(); await Promise.resolve(); assert.equal(s.accepted.key,'B');
 for(const key of ['C','B']) { await list.topos.items.get(key).fire('click'); await Promise.resolve(); await Promise.resolve(); }
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
test('server pane and native content are adopted without replacing their DOM', async()=>{
 const {controller:c}=await setup();
 const pane=new Element(), native=new Element(), input=new Element('input'); native.append(input);
 c.body.append(pane); pane.append(native);
 c.serverNodes=new Map([['0',pane],['0.0',native]]); c.snapshot={target:'/study'};
 const nodes=[{kind:'pane',key:'server',children:[{kind:'native',html:'server HTML',controls:[]}]}];
 await c.session.reconcile(nodes); c.usedWrappers=new Set(); c.layout(nodes,c.body,'session',[]);
 assert.equal(c.body.children[0],pane); assert.equal(pane.children[0],native);
 assert.equal(native.children[0],input); assert.equal(native.innerHTML,undefined);
 assert.equal(c.serverNodes.size,0);
});

test('follow renders a projection whose writable target differs', async()=> {
 const {controller:c,follower:f,element:e,pending:p}=await setup();
 const loaded=c.follow(f,e), result=response('/concrete-source','Projected values');
 result.snapshot.subject='/a';
 p[0].resolve(result); await loaded;
 assert.equal(e.dataset.status,'current'); assert.equal(e.children[0].textContent,'Projected values');
});
test('follow still rejects a response for the wrong displayed subject', async()=> {
 const {controller:c,follower:f,element:e,pending:p}=await setup();
 const loaded=c.follow(f,e), result=response('/a','Wrong projection');
 result.snapshot.subject='/other';
 p[0].resolve(result); await loaded;
 assert.equal(e.dataset.status,'unavailable'); assert.match(e.textContent,/removed or replaced/);
});

test('virtual and structural sources need no physical lifetime', async()=> {
 const {controller,context}=await setup(); let requested;
 context.URLSearchParams=URLSearchParams;
 const value={id:'/h/z/1/1/root',life:'0',bounded:true,axis:'y',type:'namespace-record',topology:'tree',incremental:true,epoch:'1',parent:'/h/z/1/1/root',next:null,members:[{key:'/h/z/1/1/root',parent:null,life:'0',hasChildren:false}]};
 context.fetch=async url=>{requested=url;return {ok:true,json:async()=>value};};
 assert.equal((await controller.source(value.id,'tree','y')).life,'0');
 assert.match(requested,/paged=1/);
 assert.match(requested,/axis=y/);
});

test('native removal is admitted while its draft is visible and unregisters the surviving pane guard',async()=>{
 const {controller:c}=await setup();
 const native={kind:'native',node:'native-editor',controls:[]};
 const description=children=>[{kind:'pane',key:'survivor',children}];
 await c.update(description([native]),{target:'/study',life:'1',publication:'1'});
 const [element,work]=[...c.nativeWorks][0], parent=c.session.get(work.ref);
 work.inputs.set('/draft',{value:'unsaved',dirty:true,composing:false});
 const refused=c.update(description([]),{target:'/study',life:'1',publication:'2'});await flush();
 assert(work.departure);assert.equal(work.live,true);assert.equal(element.isConnected,true);
 work.departure.finish(false);assert.equal((await refused).status,'refused');assert.equal(c.nativeWorks.get(element),work);
 const accepted=c.update(description([]),{target:'/study',life:'1',publication:'2'});await flush();
 work.departure.finish(true);assert.equal((await accepted).status,'applied');
 assert.equal(work.live,false);assert.equal(c.nativeWorks.size,0);assert.equal(parent.guards.size,0);assert.equal(parent.resources.size,0);
 assert.equal(await c.close(),true,'removed native work cannot leave an invisible departure prompt');
});

test('native replacement cannot mount an old response after an awaited departure guard',async()=>{
 const {controller:c,pending:p}=await setup();
 const native={kind:'native',node:'native-editor'};
 await c.update([{kind:'pane',key:'survivor',children:[native]}],{target:'/study',life:'1',publication:'1'});
 const [element,work]=[...c.nativeWorks][0];
 p.at(-1).resolve({...response('/study','first'),snapshot:{subject:'/study',life:'1',publication:'1'}});await flush();
 work.inputs.set('/draft',{value:'draft',dirty:true,composing:false});
 c.snapshot={target:'/study',life:'1',publication:'2'};
 const old=c.renderNative(native,element,[],c.session.get(work.ref).id);
 p.at(-1).resolve({...response('/study','stale'),snapshot:{subject:'/study',life:'1',publication:'2'}});await flush();assert(work.departure);
 const oldDeparture=work.departure;
 c.snapshot={target:'/study',life:'1',publication:'3'};
 const latest=c.renderNative(native,element,[],c.session.get(work.ref).id);
 oldDeparture.finish(true);await old;
 assert.equal(element.children[0].textContent,'first');assert.equal(work.inputs.get('/draft').value,'draft');
 p.at(-1).resolve({...response('/study','current'),snapshot:{subject:'/study',life:'1',publication:'3'}});await flush();
 work.departure.finish(true);await latest;
 assert.equal(element.children[0].textContent,'current');assert.equal(work.inputs.size,0);
});

test('editable member work defers preparation through composition and guards membership removal',async()=>{
 const {controller:c,list,selection:s,pending:p,context}=await setup();
 const body=new Element();c.list(list,body,{slot:'summary',key:'rows'},[]);
 const row=list.rows.get('B'),work=c.rowWorks.get(row);
 assert(work);assert.equal(work.ref,list.ref);
 p.find(request=>request.target==='/b').resolve(response('/b','original'));await flush();
 const input=new Element('input');input.value='draft';
 c.actionContext('/b','/view',{target:'/b'},[],[],work).input('/draft',input);
 await input.fire('compositionstart');input.value='composing';await input.fire('input');
 const before=p.length;context.GooActions.context=()=>({width:550,textScale:2,direction:'rtl'});
 await c.observations.get(row).callback();assert.equal(p.length,before);
 assert.equal(await c.session.depart(list,{kind:'retirement'}),false);
 const changed=structuredClone(tree);changed[0].children[0].source.members=[A,C];
 c.source=async()=>changed[0].children[0].source;
 const raw=structuredClone(changed);raw[0].children[0].source='/cards';
 await c.update(raw,{target:'/study',publication:'2'});assert(c.deferredUpdate);assert.equal(c.rowWorks.get(row),work);
 await input.fire('compositionend');await flush();
 assert(work.departure);assert.equal(work.inputs.get('/draft').value,'composing');assert.equal(s.accepted.key,'A');
 work.departure.finish(false);await flush();assert.equal(work.live,true);assert.equal(c.rowWorks.get(row),work);
 const remove=c.update(raw,{target:'/study',publication:'2'});await flush();work.departure.finish(true);await remove;
 assert.equal(work.live,false);assert.equal(c.rowWorks.has(row),false);assert.equal(s.accepted.key,'A');
});

test('a suspended or inert editor presents its departure decision in the visible session shell',async()=>{
 const {controller:c,follower:f,element:e}=await setup();c.registerWork(f,e);
 f.inputs.set('/draft',{value:'hidden draft',dirty:true});
 e.closest=selector=>selector==='[hidden],[inert]'?{}:null;
 const departure=c.session.depart(f,{kind:'retirement'});
 assert.equal(f.departure.prompt.parentElement,c.host);assert.equal(e.children.length,0);
 f.departure.finish(false);assert.equal(await departure,false);assert.equal(f.inputs.get('/draft').value,'hidden draft');
});

test('a failed context reprepare keeps the mounted editor and working draft visible for retry',async()=>{
 const {controller:c,follower:f,element:e,pending:p,context}=await setup();
 const reports=[];c.context.report=value=>reports.push(value);
 const original=c.follow(f,e);p[0].resolve(response('/a','Mounted editor'));await original;
 const editor=e.children[0];f.inputs.set('/draft',{value:'unsaved',dirty:true});
 context.GooActions.context=()=>({width:550,textScale:1,direction:'rtl'});
 const failed=c.follow(f,e);p[1].reject(Error('Server temporarily unavailable'));await failed;
 assert.equal(e.children[0],editor);assert.equal(f.inputs.get('/draft').value,'unsaved');
 assert.equal(e.dataset.status,'error');assert.match(reports[0],/temporarily unavailable/);
 const retry=c.follow(f,e);assert.equal(p.length,3);p[2].resolve(response('/a','Retried'));await retry;
 assert.equal(e.dataset.status,'current');assert.equal(e.children[0].textContent,'Retried');
});

test('a replaced member publication admits departure then mounts a fresh input lifetime',async()=>{
 const {controller:c,list,pending:p,context}=await setup();
 const preserved=[];const mount=context.GooActions.mount;
 context.GooActions.mount=(element,data,preserve)=>{preserved.push(preserve);mount(element,data);};
 c.list(list,new Element(),{slot:'summary',key:'rows'},[]);
 const row=list.rows.get('B'),work=c.rowWorks.get(row);
 p.find(request=>request.target==='/b').resolve({...response('/b','original'),snapshot:{target:'/b',life:'1',publication:'1'}});await flush();
 work.inputs.set('/draft',{value:'unsaved',dirty:true});c.snapshot={publication:'2'};
 const render=c.observations.get(row).callback();
 p.at(-1).resolve({...response('/b','replaced'),snapshot:{target:'/b',life:'1',publication:'2'}});await flush();
 assert(work.departure);work.departure.finish(true);await render;
 assert.equal(preserved.at(-1),false);assert.equal(work.inputs.size,0);
});

test('native children reject a parent snapshot mismatch and coalesce enclosing refreshes without losing work',async()=>{
 const {controller:c,pending:p,context}=await setup();
 const parent={target:'/study',subject:'/study',life:'1',displayed:'10',publication:'20'};
 const nodes=[{kind:'native',node:'first'},{kind:'native',node:'second'}];
 const refresh=defer();let refreshed=0;c.context.refresh=()=>{refreshed++;return refresh.promise;};
 await c.update([{kind:'pane',key:'survivor',children:nodes}],parent);
 const entries=[...c.nativeWorks];
 for(const pending of p.splice(0))pending.resolve({...response('/study','mounted'),snapshot:{...parent}});await flush();
 for(const [element,work] of entries)work.inputs.set('/draft',{value:`draft-${work.encounter.id}`,dirty:true});
 context.GooActions.context=()=>({width:600,textScale:1,direction:'ltr'});
 const renders=entries.map(([element,work],index)=>c.renderNative(nodes[index],element,[],c.session.get(work.ref).id));
 p[0].resolve({...response('/study','too new'),snapshot:{...parent,publication:'21'}});
 p[1].resolve({...response('/study','wrong displayed'),snapshot:{...parent,displayed:'11'}});
 await Promise.all(renders);await flush();
 assert.equal(refreshed,1);
 for(const [element,work] of entries) {
   assert.equal(element.children[0].textContent,'mounted');assert.equal(work.inputs.size,1);assert.equal(work.departure,undefined);
 }
 for(const mismatch of [{...parent,subject:'/other'},{...parent,life:'2'}])assert.equal(c.nativeSnapshotCurrent(mismatch),false);
 assert.equal(c.nativeSnapshotCurrent({...parent}),true);
 assert.equal(refreshed,1);refresh.resolve();await flush();
});

test('caller cancellation closes visible retirement prompts without applying the new description',async()=>{
 const {controller:c}=await setup();
 const initial=[{kind:'pane',key:'survivor',children:[{kind:'native',node:'editor'}]}];
 assert.equal((await c.update(initial,{target:'/study'})).status,'applied');
 const [element,work]=[...c.nativeWorks][0];work.inputs.set('/draft',{value:'stay',dirty:true});
 const abort=new AbortController();
 const removing=c.update([{kind:'pane',key:'survivor',children:[]}],{target:'/study'},{signal:abort.signal});await flush();
 const prompt=work.departure.prompt;abort.abort();
 assert.equal((await removing).status,'superseded');assert.equal(prompt.isConnected,false);assert.equal(work.departure,null);
 assert.equal(element.isConnected,true);assert.equal(work.inputs.get('/draft').value,'stay');
 const retireAbort=new AbortController(),retiring=c.update([],{target:'/study'},{signal:retireAbort.signal});await flush();
 assert(work.departure);retireAbort.abort();assert.equal((await retiring).status,'superseded');
 assert.equal(work.departure,null);assert.equal(c.session.get(work.ref).live,true);
});

test('a close begun during an old source read prevents that update from superseding its retirement',async()=>{
 const {controller:c}=await setup();
 const initial=[{kind:'pane',key:'survivor',children:[{kind:'native',node:'editor'}]}];await c.update(initial,{target:'/study'});
 const [element,work]=[...c.nativeWorks][0];work.inputs.set('/draft',{value:'unsaved',dirty:true});
 const source=defer();c.source=()=>source.promise;
 const old=c.update([{kind:'pane',key:'survivor',children:[{kind:'selection',key:'source',source:'/cards',children:[]}]}],{target:'/study'});
 const closing=c.close();await flush();assert(work.departure);
 source.resolve({id:'/cards',life:'1',type:'namespace-record',members:[A]});
 assert.equal((await old).status,'superseded');assert.equal(work.live,true);assert.equal(element.isConnected,true);
 work.departure.finish(true);assert.equal(await closing,true);assert.equal(c.session.closed,true);assert.equal(c.session.owners.size,0);
});

test('an aborted composition-deferred caller cannot replay after composition ends',async()=>{
 const {controller:c}=await setup();await c.update([{kind:'pane',key:'survivor',children:[{kind:'native',node:'editor'}]}],{target:'/study'});
 const [element,work]=[...c.nativeWorks][0],input=new Element('input');input.value='draft';
 c.actionContext('/study','/view',{target:'/study'},[],[],work).input('/draft',input);await input.fire('compositionstart');
 let applied=0;const abort=new AbortController();assert.equal((await c.update([],{target:'/study'},{signal:abort.signal,onApplied:()=>applied++})).status,'deferred');
 abort.abort();await input.fire('compositionend');await flush();
 assert.equal(c.nativeWorks.get(element),work);assert.equal(work.live,true);assert.equal(work.departure,undefined);
 assert.equal(c.rawDescription[0].key,'survivor');
 assert.equal(applied,0);
});

test('an accepted deferred update publishes metadata only when composition has ended',async()=>{
 const {controller:c}=await setup(),description=[{kind:'pane',key:'survivor',children:[{kind:'native',node:'editor'}]}];
 await c.update(description,{target:'/study'});
 const [element,work]=[...c.nativeWorks][0],input=new Element('input');input.value='draft';
 c.actionContext('/study','/view',{target:'/study'},[],[],work).input('/draft',input);
 await input.fire('compositionstart');let applied=0;
 const result=await c.update(description,{target:'/study',publication:'2'},{onApplied:()=>applied++});
 assert.equal(result.status,'deferred');assert.equal(applied,0);
 await input.fire('compositionend');await flush();assert.equal(applied,1);assert.equal(c.snapshot.publication,'2');
 assert.equal(c.nativeWorks.get(element),work);
});

test('prepared tree rows mount before attachment and refresh retains rows until validation completes',async()=>{
 const {controller:c,context}=await setup();
 // Retire the initial fixture without scheduling its follower.
 await c.session.reconcile([]);
 const member={...A,key:'/cards',subject:'/cards',parent:null,hasChildren:false,axis:'z'};
 const source={id:'/cards',life:'1',type:'namespace-record',axis:'z',topology:'tree',incremental:true,epoch:'1',members:[member],presentations:[]};
 const description=[{kind:'selection',key:'selected',source:'/cards',topology:'tree',axis:'z',children:[
   {kind:'topos',key:'outline',selection:'selected',renderer:'list_tree',slot:'/summary'}]}];
 c.source=async()=>source;
 const data=response('/cards','Prepared child');
 const prepared=new Map([[JSON.stringify(['/cards','/summary']),{context:{width:240,textScale:1,direction:'ltr'},layouts:[{render:data}],data}]]);
 context.GooActions.prepareChildren=async()=>prepared;
 context.GooActions.adoptLayouts=()=>{};
 context.GooActions.chooseLayout=bundle=>bundle.data;
 let mounted=0;
 context.GooActions.mount=(row,value)=>{assert(!row.parentElement,'new row is prepared before insertion');row.replaceChildren(value.template.cloneNode(true));mounted++;};
 assert.equal((await c.update(description,{publication:'1'})).status,'applied');
 const top=state(c.session,'topos'), row=top.rows.get('/cards');
 assert.equal(mounted,1);assert.equal(row.textContent,'');assert.equal(row.children[0].textContent,'Prepared child');
 assert.equal(state(c.session,'selection').source.presentations,undefined);
 const gate=defer();context.GooActions.prepareChildren=()=>gate.promise;
 const updating=c.update(description,{publication:'2'});await flush();
 assert.equal(top.rows.get('/cards'),row);assert.equal(row.children[0].textContent,'Prepared child');
 gate.reject(Error('stale prepared page'));await assert.rejects(updating,/stale prepared page/);
 assert.equal(top.rows.get('/cards'),row);assert.equal(c.snapshot.publication,'1');
});


test('unrelated catalogue publications rebind native authority while preserving the recipe input lifetime',async()=>{
 const {controller:c,pending:p}=await setup();
 const node={kind:'native',node:'editor'},parent={target:'/study',subject:'/study',life:'1',displayed:'10',publication:'20',recipePublication:'7'};
 await c.update([{kind:'pane',key:'survivor',children:[node]}],parent);
 const [element,work]=[...c.nativeWorks][0];
 p.at(-1).resolve({...response('/study','first'),snapshot:{...parent}});await flush();
 work.inputs.set('/draft',{value:'unsaved',dirty:true});
 c.snapshot={...parent,publication:'21'};
 const refresh=c.renderNative(node,element,[],c.session.get(work.ref).id);
 p.at(-1).resolve({...response('/study','rebound'),snapshot:{...c.snapshot}});await refresh;
 assert.equal(work.departure,undefined);assert.equal(work.inputs.get('/draft').value,'unsaved');
 assert.equal(element.children[0].textContent,'rebound');
 c.snapshot={...c.snapshot,publication:'22',recipePublication:'8'};
 const replaced=c.renderNative(node,element,[],c.session.get(work.ref).id);
 p.at(-1).resolve({...response('/study','new recipe'),snapshot:{...c.snapshot}});await flush();
 assert(work.departure);work.departure.finish(false);await replaced;
 assert.equal(element.children[0].textContent,'rebound');assert.equal(work.inputs.get('/draft').value,'unsaved');
});

test('preferred-pane tabs follow path-valued face availability on the accepted selection',async()=>{
 const {controller:c,follower:f,selection:s}=await setup();
 f.spec.slot='/sys/slot/panes';
 const pane=c.session.owners.get(f.owner);
 assert.equal(c.paneAvailable(pane),false);
 s.members.set('B',{...B,face:'/gov/cards/workspace'});
 await c.session.deliver(c.session.intent(s.ref,s.members.get('B')));
 assert.equal(c.paneAvailable(pane),true);
 await c.session.deliver(c.session.intent(s.ref,A));
 assert.equal(c.paneAvailable(pane),false);
 f.spec.slot='/sys/slot/documentation';
 assert.equal(c.paneAvailable(pane),true);
});
