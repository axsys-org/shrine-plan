const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {randomUUID} = require('node:crypto');

const profileFile = require('../../goo/profile/profile.json');
const profile = Object.fromEntries(['id','version','revision'].map(key=>[key,profileFile[key]]));
const context = {width:437.5,textScale:1.5,direction:'rtl'};
const snapshot = {target:'/item',subject:'/item',expected:'2',displayed:'2',publication:'3',life:'4'};
const envelope = () => ({version:1,ok:true,profile:{...profile},context:{...context},snapshot:{...snapshot},
  view:'/editor',kind:'view',slot:'/content',role:'/record',html:'<p>Prepared</p>',controls:[],
  display:{profile:{...profile},context:{...context},nodes:[]}});
const response = (value,ok=true,status=ok?200:400) => ({ok,status,json:async()=>value,text:async()=>JSON.stringify(value)});
const defer=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
function setup(fetch) {
  const calls=[], callbacks=[], observers=[];
  class Observer {
    constructor(callback) {this.callback=callback;this.disconnected=false;observers.push(this);}
    observe(element,options) {this.element=element;this.options=options;}
    disconnect() {this.disconnected=true;}
  }
  const sandbox={URLSearchParams,AbortController,crypto:{randomUUID},console,
    fetch:async(url,options={})=>{calls.push({url,options});return fetch(url,options);},
    getComputedStyle:element=>element.style,
    requestAnimationFrame:callback=>callbacks.push(callback), ResizeObserver:Observer,MutationObserver:Observer,
    document:{querySelector:()=>null,documentElement:{}}};
  vm.runInNewContext(fs.readFileSync(require.resolve('../goo-actions.js'),'utf8'),sandbox);
  return {actions:sandbox.GooActions,calls,observers,frame:()=>{for(const callback of callbacks.splice(0)) callback();}};
}

test('render transport requires context before making any request',async()=>{
  const {actions,calls}=setup(()=>{throw Error('unexpected fetch');});
  for(const invalid of [undefined,{...context,width:NaN},{...context,width:-1},{...context,width:100001},
    {...context,textScale:0},{...context,textScale:11},{...context,direction:'RTL'}])
    await assert.rejects(actions.load('/item',{context:invalid}),/valid render context/);
  assert.equal(calls.length,0);
});

test('render transport carries explicit context and selector through /goo/render',async()=>{
  const data=envelope(), signal=new AbortController().signal;
  const {actions,calls}=setup(url=>response(url==='/static/goo-profile.json'?profile:data));
  assert.deepEqual(await actions.load('/item',{context,view:'/editor',slot:'/content',role:'/record',node:'node-7',workspace:'/work',signal}),data);
  const request=calls.find(call=>call.url==='/goo/render');
  assert.equal(request.options.method,'POST'); assert.equal(request.options.cache,'no-store');assert.equal(request.options.signal,signal);
  assert.deepEqual(Object.fromEntries(request.options.body),{target:'/item',width:'437.5',textScale:'1.5',direction:'rtl',view:'/editor',slot:'/content',role:'/record',node:'node-7',workspace:'/work'});
  assert.equal(calls.some(call=>call.url.startsWith('/views')),false);
  await actions.load('/item',{context,view:'/editor'});
  assert.equal(calls.filter(call=>call.url==='/static/goo-profile.json').length,1);
});

test('render transport rejects profile, context and malformed presentation drift',async()=>{
  const mutations=[
    [data=>data.profile.revision='other',/renderer profile mismatch/],
    [data=>data.profile.id='other',/renderer profile mismatch/],
    [data=>data.context.width++,/render context mismatch/],
    [data=>data.context.textScale=1,/render context mismatch/],
    [data=>data.context.direction='ltr',/render context mismatch/],
    [data=>data.display.profile.version++,/display profile mismatch/],
    [data=>data.display.context.width++,/display context mismatch/],
    [data=>data.version=2,/Unsupported/],
    [data=>delete data.snapshot,/Unsupported/],
    [data=>data.controls={},/Invalid Goo presentation/],
    [data=>data.html=null,/Invalid Goo presentation/]
  ];
  for(const [mutate,error] of mutations) {
    const data=envelope();mutate(data);
    const {actions}=setup(url=>response(url==='/static/goo-profile.json'?profile:data));
    await assert.rejects(actions.load('/item',{context}),error);
  }
});

test('failed profile loading is retriable and server diagnostics reach the caller',async()=>{
  let attempts=0;
  const {actions}=setup(url=>url==='/static/goo-profile.json'?response(profile,++attempts>1):response(envelope()));
  await assert.rejects(actions.load('/item',{context}),/profile is unavailable/);
  await actions.load('/item',{context});assert.equal(attempts,2);
  const failed=setup(url=>url==='/static/goo-profile.json'?response(profile):response({ok:false,error:'Not admitted'},false));
  await assert.rejects(failed.actions.load('/item',{context}),/Not admitted/);
  const malformed=setup(url=>url==='/static/goo-profile.json'?response(profile):{ok:false,status:400,headers:{get:()=> 'text/plain'},text:async()=> 'Invalid node route'});
  await assert.rejects(malformed.actions.load('/item',{context}),/Invalid node route/);
});

test('catalogue keeps valid views usable alongside an individual preparation diagnostic',async()=>{
  const valid=envelope(), invalid={view:'/broken',kind:'view',slot:'/content',role:'/record',error:'Unsupported primitive'};
  const catalogue={version:1,ok:true,profile,context,snapshot,views:[valid,invalid]};
  const {actions}=setup(url=>response(url==='/static/goo-profile.json'?profile:catalogue));
  const result=await actions.load('/item',{context});
  assert.equal(result.views[0].html,valid.html);assert.equal(result.views[1].error,'Unsupported primitive');
});

test('pane allocation selects breakpoints and observes scale/direction without within-class rerenders',()=>{
  const {actions,observers,frame}=setup(()=>{throw Error('unexpected fetch');});
  const style={paddingLeft:'12px',paddingRight:'8px',direction:'rtl',getPropertyValue:()=> '1.25'};
  const element={clientWidth:500,style,isConnected:true,getBoundingClientRect:()=>({width:900})};
  assert.deepEqual(JSON.parse(JSON.stringify(actions.context(element))),{width:480,textScale:1.25,direction:'rtl',layout:'md'});
  const seen=[];const stop=actions.observe(element,value=>seen.push(JSON.parse(JSON.stringify(value))));
  observers.forEach(observer=>observer.callback());frame();assert.equal(seen.length,0);
  element.clientWidth=600;observers.forEach(observer=>observer.callback());frame();
  assert.deepEqual(seen,[]);
  element.clientWidth=740;observers[0].callback();frame();
  assert.deepEqual(seen,[{width:720,textScale:1.25,direction:'rtl',layout:'lg'}]);
  style.direction='ltr';style.getPropertyValue=()=> '2';observers[1].callback();frame();
  assert.deepEqual(seen[1],{width:720,textScale:2,direction:'ltr',layout:'lg'});
  stop();element.clientWidth=700;observers[0].callback();frame();assert.equal(seen.length,2);
  assert(observers.every(observer=>observer.disconnected));
  style.getPropertyValue=()=> 'nope';assert.throws(()=>actions.context(element),/Invalid Goo text scale/);
});

test('pane context reads the host allocation, excludes chrome and ignores oversized prepared content',()=>{
  const {actions}=setup(()=>{throw Error('unexpected fetch');});
  const content={clientWidth:458,style:{paddingLeft:'0',paddingRight:'0',direction:'rtl',getPropertyValue:()=> '1.25'},getBoundingClientRect:()=>({width:458})};
  content.style.paddingLeft='20px';content.style.paddingRight='22px';
  const outer={querySelector:()=>content,clientWidth:500,style:{paddingLeft:'0',paddingRight:'0',direction:'rtl',getPropertyValue:()=> '1.25'}};
  assert.deepEqual(JSON.parse(JSON.stringify(actions.context(outer))),{width:240,textScale:1.25,direction:'rtl',layout:'sm'});
  content.clientWidth=2000;content.getBoundingClientRect=()=>{throw Error('child geometry read');};
  assert.equal(actions.context(outer).width,240);
  outer.clientWidth=222;assert.equal(actions.context(outer).width,180);
  outer.clientWidth=0;assert.equal(actions.context(outer).width,0);
});

const paneContext=(width,layout)=>({width,textScale:1.5,direction:'rtl',layout});
const bundle=(requested)=>({version:1,ok:true,layoutPolicy:'pane-v1',context:requested,
  layouts:[['sm',Math.min(240,requested.width)],['md',480],['lg',720]].map(([size,width])=>{
    const render=envelope();render.context={...context,width};render.display.context={...render.context};
    render.html=`<p>${size}</p>`;return {size,render};
  })});
test('server layouts are selected per owner and cached only within the same semantic basis',async()=>{
  const owner={}, other={}, requests=[];
  const {actions}=setup((url,options)=>{
    if(url==='/static/goo-profile.json')return response(profile);
    const width=Number(options.body.get('width'));requests.push(options.body);
    assert.equal(options.body.get('layouts'),'pane-v1');
    return response(bundle({...context,width}));
  });
  const load=(width,layout,basis='v1',host=owner)=>actions.load('/item',{context:paneContext(width,layout),owner:host,basis,slot:'/content'});
  assert.equal((await load(240,'sm')).layout,'sm');
  assert.equal((await load(720,'lg')).html,'<p>lg</p>');
  assert.equal((await load(480,'md')).display.context.width,480);
  assert.equal(requests.length,1,'crossing a breakpoint uses an already resolved layout');
  await load(480,'md','v2');assert.equal(requests.length,2,'semantic refresh invalidates variants');
  await load(480,'md','v2',other);assert.equal(requests.length,3,'cache is scoped to its presentation owner');
  await load(180,'sm','v2');assert.equal(requests.length,4,'sub-sm panes request a fitting small layout');
  await load(240,'sm','v2');assert.equal(requests.length,5,'a clipped small variant is not reused as full sm');
});
test('all layout variants are validated before admission, including unselected ones',async()=>{
  for(const mutate of [
    data=>data.layouts[2].render.snapshot.life='other',
    data=>data.layouts[2].render.display.context.width=999,
    data=>data.layouts[1].size='sm',
    data=>data.layouts.pop(),
    data=>data.layouts[1].render.profile.revision='stale',
    data=>data.context.width=800
  ]) {
    const requested=paneContext(240,'sm'),data=bundle(requested);mutate(data);
    const {actions}=setup(url=>response(url==='/static/goo-profile.json'?profile:data));
    await assert.rejects(actions.load('/item',{context:requested,owner:{},basis:'v1'}));
  }
});
test('an aborted layout request cannot populate the retained owner cache',async()=>{
  const gate=defer(),owner={},controller=new AbortController();let renders=0;
  const requested=paneContext(240,'sm');
  const {actions}=setup(url=>url==='/static/goo-profile.json'?response(profile):(renders++,gate.promise));
  const first=actions.load('/item',{context:requested,owner,basis:'v1',signal:controller.signal});
  controller.abort();gate.resolve(response(bundle(requested)));
  await assert.rejects(first,{name:'AbortError'});
  await actions.load('/item',{context:requested,owner,basis:'v1'});assert.equal(renders,2);
});

class Control {
  constructor(id) {this.dataset={node:id};this.listeners=[];this.disabled=false;}
  addEventListener(type,listener,{signal}={}) {this.listeners.push({type,listener,signal});}
  fire(type) {return Promise.all(this.listeners.filter(value=>value.type===type&&!value.signal?.aborted).map(value=>value.listener({stopPropagation(){}})));}
}
function bindingFixture(actions) {
  const button=new Control('save'), input={dataset:{inputSlot:'/req'},value:'first draft'}, reports=[], saved=[];
  const container={querySelector:()=>null,querySelectorAll:selector=>selector==='[data-node]'?[button]:selector==='input[data-input-slot]'?[input]:[]};
  const context={target:'/item',view:'/editor',snapshot,controls:[{kind:'button',id:'save',control:'/save',slot:'/saved'}],
    report:value=>reports.push(value),saved:(...value)=>saved.push(value),capture:()=>[]};
  actions.bind(container,context);return {button,input,container,context,reports,saved};
}

test('action retries retain one invocation, capture and exact working inputs',async()=>{
  const bodies=[],gate=defer();
  const {actions}=setup((_url,options)=>{bodies.push(options.body.toString());if(bodies.length===1)throw Error('network dropped');return gate.promise;});
  const fixture=bindingFixture(actions);
  const first=fixture.button.fire('click');
  await Promise.resolve();await Promise.resolve();
  fixture.input.value='later draft';await fixture.button.fire('click');
  assert.equal(bodies.length,2);assert.equal(bodies[0],bodies[1]);
  const form=new URLSearchParams(bodies[0]);assert.equal(form.get('input:/req'),'first draft');assert(form.get('invocation'));
  gate.resolve(response({ok:true}));await first;
  assert.equal(fixture.saved.length,1);assert.equal(fixture.saved[0][1].get('/req'),'first draft');
  assert.equal(actions.metrics.activations,1);assert.equal(actions.metrics.dispatches,2);assert.equal(fixture.button.disabled,false);
});

test('rebinding a retained action removes its stale listener and keeps pending invocation unique',async()=>{
  const gate=defer();let dispatched=0;
  const {actions}=setup(()=>{dispatched++;return gate.promise;});
  const fixture=bindingFixture(actions);
  actions.bind(fixture.container,fixture.context);
  const first=fixture.button.fire('click');assert.equal(dispatched,1);
  actions.bind(fixture.container,fixture.context);
  const second=fixture.button.fire('click');
  assert.equal(dispatched,1,'a layout refresh cannot admit the pending action a second time');
  gate.resolve(response({ok:true}));await Promise.all([first,second]);
  assert.equal(actions.metrics.activations,1);assert.equal(fixture.saved.length,1);
});

test('independent action owners may invoke the same control with their own working inputs',async()=>{
  const gate=defer(),bodies=[];
  const {actions}=setup((_url,options)=>{bodies.push(options.body.toString());return gate.promise;});
  const first=bindingFixture(actions), second=bindingFixture(actions);
  first.context.actionScope={};second.context.actionScope={};second.input.value='other pane';
  actions.bind(first.container,first.context);actions.bind(second.container,second.context);
  const a=first.button.fire('click'),b=second.button.fire('click');
  assert.equal(bodies.length,2);
  const forms=bodies.map(body=>new URLSearchParams(body));
  assert.notEqual(forms[0].get('invocation'),forms[1].get('invocation'));
  assert.equal(forms[0].get('input:/req'),'first draft');assert.equal(forms[1].get('input:/req'),'other pane');
  gate.resolve(response({ok:true}));await Promise.all([a,b]);
});

test('shared captured activation cannot change protected evidence or arguments on retry',async()=>{
  const bodies=[];const {actions}=setup((_url,options)=>{bodies.push(options.body.toString());return response({ok:true});});
  const fixture=bindingFixture(actions),control=fixture.context.controls[0];
  const captured=actions.captureActivation(fixture.container,fixture.context,control);
  fixture.context.target='/different';fixture.input.value='later';
  await actions.activateCaptured(captured,[['/gesture','{"kind":"move-nodes"}']]);
  await actions.activateCaptured(captured,[['/gesture','{"kind":"move-nodes"}']]);
  assert.equal(bodies.length,1);const form=new URLSearchParams(bodies[0]);
  assert.equal(form.get('target'),'/item');assert.equal(form.get('input:/req'),'first draft');assert.equal(form.get('invocation'),captured.operationId);
  await assert.rejects(actions.activateCaptured(captured,[['/gesture','changed']]),/arguments changed/);
  await assert.rejects(actions.activateCaptured({...captured},[]),/Unknown captured/);
});

test('unknown operation survives owner disposal, reconciles later, and retry keeps exact ID',async()=>{
  const bodies=[];let online=false;
  const {actions}=setup((_url,options)=>{bodies.push(options.body.toString());if(!online)throw Error('offline');return response({ok:true});});
  const fixture=bindingFixture(actions),captured=actions.captureActivation(fixture.container,fixture.context,fixture.context.controls[0]);
  const receipts=[];const stop=actions.subscribeOutcomes(r=>receipts.push(r));
  await assert.rejects(actions.activateCaptured(captured),/Outcome unknown/);assert.equal(actions.outcome(captured.operationId).outcome,'unknown');
  stop();online=true;await actions.activateCaptured(captured);assert.equal(actions.outcome(captured.operationId).outcome,'accepted');
  assert.equal(receipts.length,1);assert.equal(new Set(bodies).size,1);
});

test('definite rejection is terminal; a server failure remains unknown',async()=>{
  for(const status of [400,500]){
    let calls=0;const {actions}=setup(()=>{calls++;return response({error:'Not committed?'},false,status);});
    const fixture=bindingFixture(actions),captured=actions.captureActivation(fixture.container,fixture.context,fixture.context.controls[0]);
    await assert.rejects(actions.activateCaptured(captured));
    assert.equal(actions.outcome(captured.operationId).outcome,status===400?'rejected':'unknown');
    if(status===400){await assert.rejects(actions.activateCaptured(captured));assert.equal(calls,1);}
  }
});

test('cancelled unsent capture releases common selection evidence without dispatch',async()=>{
  const {actions,calls}=setup(()=>{throw Error('unexpected fetch');});const fixture=bindingFixture(actions);const released=[];
  fixture.context.releaseCapture=id=>released.push(id);
  const captured=actions.captureActivation(fixture.container,fixture.context,fixture.context.controls[0]);actions.discardCaptured(captured);
  await assert.rejects(actions.activateCaptured(captured),/Unknown captured/);assert.deepEqual(released,[captured.operationId]);assert.equal(calls.length,0);
});
