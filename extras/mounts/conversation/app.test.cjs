const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

async function setup({create=false}={}) {
  class Element {
    constructor(){this.children=[];this.dataset={};this.events={};this.attrs={};}
    append(...nodes){this.children.push(...nodes);}
    insertBefore(node,at){this.children.splice(this.children.indexOf(at),0,node);}
    addEventListener(name,fn){this.events[name]=fn;}
    getAttribute(name){return this.attrs[name];}
    setAttribute(name,value){this.attrs[name]=value;}
  }
  const page='/0x11/app/nenex/w/chat', nodes=new Map();
  for(const id of ['conversation','conversation-notice','conversation-composer','conversation-turns','conversation-wiki'])nodes.set(id,new Element());
  nodes.get('conversation').dataset={page:create?'':page,create:'/0x11/app/conversation',vocabulary:'/0x11/gov/conversation'};
  let input=new Element();input.dataset.inputSlot=create?'/name':'/source';input.value='';input.attrs.value='';
  let bound, target, navigate, serial=1;
  const timers=[],events={},notices=[],loads=[],mounts=[],reads=[];
  const state={page,composer:page+'/conversation',composerVersion:'1',wiki:page+'/wiki',turns:[]};
  const docs=new Map();
  const api={context:()=>({width:720}),feedback:async(_el,text)=>notices.push(text),
    load:async(name,options)=>{target=name;loads.push([name,options]);return {view:options.view,snapshot:{expected:String(serial++)},controls:[]};},
    mount:(element,_data,preserve)=>{if(!preserve){input=new Element();input.dataset.inputSlot=create?'/name':'/source';input.value='';input.attrs.value='';}return element;},
    bind:(_element,context)=>{bound=context;context.input('native-input-contract',input);}
  };
  const sandbox={URLSearchParams,Map,console,GooActions:api,
    GooDocument:{mount:async(element,manifest)=>{const control={dirty:()=>control.edited,edited:false,updates:[],update:async value=>control.updates.push(value)};mounts.push(manifest.root);docs.set(manifest.root,control);return control;}},
    document:{hidden:false,getElementById:id=>nodes.get(id),createElement:()=>new Element()},
    location:{assign:value=>navigate=value},addEventListener:(name,fn)=>events[name]=fn,
    setTimeout:fn=>timers.push(fn),
    fetch:async url=>{reads.push(url);const query=new URL(url,'http://localhost');const path=query.searchParams.get('path');
      return {ok:true,json:async()=>query.pathname==='/conversation/manifest'?structuredClone(state):{root:path,blocks:[],tools:[]}};}
  };
  await vm.runInNewContext(fs.readFileSync(require.resolve('./app.js'),'utf8'),sandbox);
  return {state,nodes,docs,mounts,reads,loads,events,notices,
    get input(){return input;},get navigation(){return navigate;},
    save:value=>bound.saved({},new Map([['native-input-contract',value]])),
    selectOperations:()=>bound.saved({},new Map()),
    tick:async()=>{const next=timers.shift();if(next)await next();},
    addTurn:()=>state.turns.push({id:'/first',sequence:0,message:page+'/messages/first',reply:page+'/replies/first',
      controller:page+'/work/first',published:true,messageVersion:'1',replyVersion:'1',workVersion:'1',status:'running',reason:'Watching published definition and source inputs'})};
}

test('assistant messages mount the existing Nenex projection and retain dirty edits during refresh',async()=>{
  const app=await setup();app.addTurn();await app.tick();
  assert.deepEqual(app.mounts,['/0x11/app/nenex/w/chat/messages/first','/0x11/app/nenex/w/chat/replies/first']);
  const reply=app.docs.get(app.mounts[1]);reply.edited=true;app.state.turns[0].replyVersion='2';await app.tick();
  assert.equal(reply.updates.length,0);
  reply.edited=false;await app.tick();assert.equal(reply.updates.length,1);
  assert.ok(app.reads.every(url=>url.startsWith('/conversation/')||url.startsWith('/nenex/document?')));
});

test('an admitted send clears its draft but preserves a newer edit',async()=>{
  const app=await setup();app.input.value='sent text';await app.save('sent text');assert.equal(app.input.value,'');
  app.input.value='newer text';await app.save('older admitted text');assert.equal(app.input.value,'newer text');
  let warned=false;app.events.beforeunload({preventDefault(){warned=true;}});assert.equal(warned,true);
});

test('another participant advances the native composer selection while preserving the local draft',async()=>{
  const app=await setup();app.input.value='My draft';const before=app.loads.length;
  app.state.composerVersion='2';await app.tick();assert.equal(app.input.value,'My draft');assert.equal(app.loads.length,before+1);
});

test('creation follows the admitted Goo input contract instead of guessing a slot-keyed receipt',async()=>{
  const app=await setup({create:true});app.input.value='my_chat';await app.save('my_chat');
  const url=new URL(app.navigation,'http://localhost');assert.equal(url.pathname,'/conversation');
  assert.equal(url.searchParams.get('path'),'/0x11/app/nenex/w/my_chat');
});

test('selecting published operations retains the creation draft',async()=>{
  const app=await setup({create:true});app.input.value='my_chat';await app.selectOperations();
  assert.equal(app.navigation,undefined);assert.equal(app.input.value,'my_chat');
  assert.match(app.notices.at(-1),/Republish a flow/);
});

test('opening work uses the existing native work projection; closing stops presentation reads',async()=>{
  const app=await setup();app.addTurn();await app.tick();
  const article=app.nodes.get('conversation-turns').children[0];const details=article.children.find(node=>node.events.toggle);
  details.open=true;await details.events.toggle();assert.ok(app.mounts.includes('/0x11/app/nenex/w/chat/work/first'));
  app.events.pagehide();const count=app.reads.length;await app.tick();assert.equal(app.reads.length,count);
});
