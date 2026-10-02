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

test('render context measures content width and observes scale/direction without noisy rerenders',()=>{
  const {actions,observers,frame}=setup(()=>{throw Error('unexpected fetch');});
  const style={paddingLeft:'12px',paddingRight:'8px',direction:'rtl',getPropertyValue:()=> '1.25'};
  const element={clientWidth:500,style,isConnected:true,getBoundingClientRect:()=>({width:900})};
  assert.deepEqual(JSON.parse(JSON.stringify(actions.context(element))),{width:480,textScale:1.25,direction:'rtl'});
  const seen=[];const stop=actions.observe(element,value=>seen.push(JSON.parse(JSON.stringify(value))));
  observers.forEach(observer=>observer.callback());frame();assert.equal(seen.length,0);
  element.clientWidth=600;observers.forEach(observer=>observer.callback());frame();
  assert.deepEqual(seen,[{width:580,textScale:1.25,direction:'rtl'}]);
  style.direction='ltr';style.getPropertyValue=()=> '2';observers[1].callback();frame();
  assert.deepEqual(seen[1],{width:580,textScale:2,direction:'ltr'});
  stop();element.clientWidth=700;observers[0].callback();frame();assert.equal(seen.length,2);
  assert(observers.every(observer=>observer.disconnected));
  style.getPropertyValue=()=> 'nope';assert.throws(()=>actions.context(element),/Invalid Goo text scale/);
});

test('prepared context excludes the mounted Explorer presentation chrome',()=>{
  const {actions}=setup(()=>{throw Error('unexpected fetch');});
  const content={clientWidth:458,style:{paddingLeft:'0',paddingRight:'0',direction:'rtl',getPropertyValue:()=> '1.25'},getBoundingClientRect:()=>({width:458})};
  const outer={querySelector:()=>content,clientWidth:500};
  assert.deepEqual(JSON.parse(JSON.stringify(actions.context(outer))),{width:458,textScale:1.25,direction:'rtl'});
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
