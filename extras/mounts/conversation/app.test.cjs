const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

async function setup({create=false}={}) {
  class Element {
    constructor(){this.children=[];this.dataset={};this.events={};this.attrs={};this.clientWidth=680;this.clientHeight=400;this.scrollHeight=400;this.scrollTop=0;}
    get parentNode(){return this.parent;}
    remove(){if(this.parent){this.parent.children=this.parent.children.filter(child=>child!==this);this.parent=null;}}
    append(...nodes){for(const node of nodes){node.remove();this.children.push(node);node.parent=this;}}
    insertBefore(node,at){if(node===at)return;node.remove();const index=this.children.indexOf(at);this.children.splice(index<0?this.children.length:index,0,node);node.parent=this;}
    addEventListener(name,fn){this.events[name]=fn;}
    getAttribute(name){return this.attrs[name];}
    setAttribute(name,value){this.attrs[name]=value;}
    contains(node){return node===this || this.children.some(child=>child.contains(node));}
    get scrollTop(){return this.top||0;}
    set scrollTop(value){this.top=Math.max(0,Math.min(value,this.scrollHeight-this.clientHeight));}
    focus(){doc.activeElement=this;}
    click(){this.clicks=(this.clicks||0)+1;this.events.click?.({});}
    querySelectorAll(){return this.children.flatMap(child=>[child,...child.querySelectorAll()]);}
  }
  const page='/0x11/app/nenex/w/chat', nodes=new Map();
  for(const id of ['conversation','conversation-notice','conversation-composer','conversation-turns','conversation-history','conversation-latest','conversation-navigation','conversation-panel','conversation-panel-notice','conversation-wiki','conversation-work'])nodes.set(id,new Element());
  nodes.get('conversation').dataset={page:create?'':page,create:'/0x11/app/conversation',vocabulary:'/0x11/gov/conversation'};
  let input=new Element();input.dataset.inputSlot=create?'/name':'/source';input.value='';input.attrs.value='';
  const button=new Element();button.dataset.node='send';
  const doc={hidden:false,body:new Element(),getElementById:id=>nodes.get(id),createElement:()=>new Element()};doc.activeElement=doc.body;
  let bound, navigationBinding, target, navigate, serial=1;
  const timers=[],events={},notices=[],feedbackWidths=[],loads=[],mounts=[],reads=[],resizes=[];
  const state={page,composer:page+'/conversation',composerVersion:'1',wiki:page+'/wiki',turns:[]};
  const docs=new Map(),manifests=new Map();
  const api={context:()=>({width:720}),feedback:async(_el,text,width)=>{notices.push(text);feedbackWidths.push(width);},
    load:async(name,options)=>{target=name;loads.push([name,options]);return {view:options.view||options.slot,snapshot:{expected:String(serial++)},controls:[{kind:'action',id:'send'}]};},
    mount:(element,_data,preserve)=>{if(element===nodes.get('conversation-navigation'))return element;if(!preserve){input=new Element();input.dataset.inputSlot=create?'/name':'/source';input.value='';input.attrs.value='';}element.children=[];element.append(input,button);return element;},
    bind:(_element,context)=>{if(context.become){navigationBinding=context;return;}bound=context;context.input('native-input-contract',input);}
  };
  const sandbox={URLSearchParams,Map,console,GooActions:api,
    GooDocument:{mount:async(element,manifest,reload,onSaved,options)=>{const control={manifest,options,reload,onSaved,dirty:()=>control.edited,edited:false,updates:[],update:async value=>control.updates.push(value)};mounts.push(manifest.root);docs.set(manifest.root,control);return control;},mountTree:async(element,manifest,options)=>{const tree={manifest,options,refreshes:0,refresh:async()=>tree.refreshes++,dirty:()=>tree.edited};mounts.push(manifest.root);docs.set(manifest.root,tree);return tree;}},
    document:doc,
    ResizeObserver:class {constructor(callback){this.callback=callback;resizes.push(this);}observe(){}disconnect(){this.disconnected=true;}},
    location:{assign:value=>navigate=value},addEventListener:(name,fn)=>events[name]=fn,
    setTimeout:fn=>timers.push(fn),
    fetch:async url=>{reads.push(url);const query=new URL(url,'http://localhost');const path=query.searchParams.get('path');
      return {ok:true,json:async()=>query.pathname==='/conversation/manifest'?structuredClone(state):structuredClone(manifests.get(path)||{root:path,blocks:[],tools:[]})};}
  };
  await vm.runInNewContext(fs.readFileSync(require.resolve('./app.js'),'utf8'),sandbox);
  return {state,nodes,docs,manifests,mounts,reads,loads,events,notices,feedbackWidths,button,resizes,doc,api,
    report:message=>bound.report(message),
    get input(){return input;},get navigation(){return navigate;},
    save:value=>bound.saved({},new Map([['native-input-contract',value]])),
    selectOperations:()=>bound.saved({},new Map()),
    selectView:name=>navigationBinding.become('/sys/slot/conversation_'+name),
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

test('chat omits only the terminal native receipt section and asks for content without wiki chrome',async()=>{
  const app=await setup();app.addTurn();const root=app.state.turns[0].reply;
  const authored={target:root+'/0/0',kind:'ref',reference:'/some/other/flows/latest',depth:2};
  const section={target:root+'/0/1',kind:'sect',depth:2};
  const receipt={target:root+'/0/1/0',kind:'ref',depth:3,reference:root+'/flows/latest'};
  const manifest={root,blocks:[authored,section,receipt],tools:[{kind:'presentation',target:root,view:'/history'}]};
  app.manifests.set(root,manifest);await app.tick();
  const view=app.docs.get(root);assert.equal(view.options.chrome,false);assert.equal(view.options.compact,true);
  assert.deepEqual(view.manifest.blocks,[authored]);assert.equal(manifest.blocks.length,3);
  // Additional prose makes this authored content, not the writer's bare footer.
  manifest.blocks.push({target:root+'/0/1/1',kind:'prose',depth:3});
  app.state.turns[0].replyVersion='2';await app.tick();assert.equal(view.updates.at(-1).blocks.length,4);
});

test('recovered refreshes clear stale selection warnings without clearing action errors',async()=>{
  const app=await setup(),load=app.api.load;
  app.state.composerVersion='2';app.api.load=async()=>{throw Error('View selection is unavailable or ambiguous.');};
  await app.tick();assert.equal(app.notices.at(-1),'View selection is unavailable or ambiguous.');
  app.api.load=load;await app.tick();assert.equal(app.notices.at(-1),'');
  await app.report('The send was rejected.');await app.tick();assert.equal(app.notices.at(-1),'The send was rejected.');
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
  const app=await setup({create:true});app.input.value='my_chat';
  let warned=false;app.events.beforeunload({preventDefault(){warned=true;}});assert.equal(warned,true);
  await app.save('my_chat');
  const url=new URL(app.navigation,'http://localhost');assert.equal(url.pathname,'/conversation');
  assert.equal(url.searchParams.get('path'),'/0x11/app/nenex/w/my_chat');
  warned=false;app.events.beforeunload({preventDefault(){warned=true;}});assert.equal(warned,false);
});

test('selecting published operations retains the creation draft',async()=>{
  const app=await setup({create:true});app.input.value='my_chat';await app.selectOperations();
  assert.equal(app.navigation,undefined);assert.equal(app.input.value,'my_chat');
  assert.match(app.notices.at(-1),/Republish a flow/);
});

test('opening work uses the existing native work projection; closing stops presentation reads',async()=>{
  const app=await setup();app.addTurn();await app.tick();
  const article=app.nodes.get('conversation-turns').children[0];const details=article.children.find(node=>node.events.toggle);
  details.open=true;await Promise.all([details.events.toggle(),details.events.toggle()]);
  assert.ok(app.mounts.includes('/0x11/app/nenex/w/chat/work/first'));
  assert.equal(app.reads.filter(url=>url.startsWith('/conversation/work?')).length,1);
  app.events.pagehide();const count=app.reads.length;await app.tick();assert.equal(app.reads.length,count);
  assert.equal(app.resizes[0].disconnected,true);
});

test('chat renders each native status snapshot without inferring a UI lifecycle',async()=>{
  const app=await setup();app.addTurn();const turn=app.state.turns[0];
  turn.published=false;turn.controllerStatus='blocked';
  for(const [status,statusLabel,reason] of [
    ['working','Working','The native provider is working.'],
    ['waiting','Waiting for input','Which database should I inspect?'],
    ['blocked','Blocked','flow_prompt_limit'],
    ['working','Working','Retrying through the native hand.'],
    ['paused','Paused','Paused'],
    ['watching','Watching for changes','Watching for evidence changes.']
  ]) {
    Object.assign(turn,{status,statusLabel,reason});await app.tick();
    const work=app.nodes.get('conversation-turns').children[0].children.find(node=>node.events.toggle);
    assert.equal(work.dataset.status,status);
    assert.equal(work.children[0].children[1].textContent,statusLabel);
    assert.equal(work.children[1].textContent,reason);
  }
  Object.assign(turn,{published:true,status:'blocked',statusLabel:'Blocked'});await app.tick();
  const work=app.nodes.get('conversation-turns').children[0].children.find(node=>node.events.toggle);
  assert.equal(work.children[0].children[1].textContent,'Published · Blocked');
  // Status does not need to open/read the retained work and trace subtree.
  assert.equal(app.reads.filter(url=>url.startsWith('/conversation/work?')).length,0);
});

test('Enter activates the declared action; multiline, composition and pending edits remain with Goo',async()=>{
  const app=await setup();app.input.value='A question';
  const key=(extra={})=>{const event={key:'Enter',target:app.input,preventDefault(){this.defaultPrevented=true;},...extra};app.nodes.get('conversation-composer').events.keydown(event);return event;};
  assert.equal(key().defaultPrevented,true);assert.equal(app.button.clicks,1);
  for(const extra of [{shiftKey:true},{ctrlKey:true},{metaKey:true},{altKey:true},{isComposing:true},{keyCode:229},{defaultPrevented:true}])key(extra);
  assert.equal(app.button.clicks,1);
  app.input.gooComposing=true;key();app.input.gooComposing=false;
  app.input.gooEditor={pending:true};key();delete app.input.gooEditor;
  app.button.disabled=true;key();app.button.disabled=false;
  app.input.value='  ';key();assert.equal(app.button.clicks,1);
  assert.equal(app.input.attrs['aria-label'],'Message');
});

test('waiting input mounts declared Goo and never moves a draft to a replacement request',async()=>{
  const app=await setup();app.addTurn();const turn=app.state.turns[0];turn.published=false;
  turn.status='waiting';turn.reason='Which database?';
  turn.input={root:turn.controller,blocks:[{target:turn.controller+'/work/request_1',view:'/0x11/gov/conversation/answer_input',kind:'presentation',label:'',readonly:false}],tools:[]};
  await app.tick();const form=app.docs.get(turn.controller);
  assert.deepEqual(form.manifest,turn.input);
  await form.reload(turn.controller);assert.ok(app.reads.at(-1).startsWith('/conversation/inputs?'));
  const section=app.nodes.get('conversation-turns').children[0].children.find(n=>n.className==='conversation-continuation');
  assert.equal(section.children[1].textContent,'Which database?');
  form.edited=true;turn.workVersion='2';turn.input.blocks[0].target=turn.controller+'/work/request_2';
  await app.tick();assert.equal(form.updates.length,0);assert.ok(form.manifest.blocks[0].target.endsWith('/request_1'));
  form.edited=false;await app.tick();assert.equal(form.updates.length,1);assert.ok(form.updates[0].blocks[0].target.endsWith('/request_2'));
  app.nodes.get('conversation-history').clientWidth=320;await app.tick();
  assert.equal(form.updates.length,2);assert.ok(form.updates[1].blocks[0].target.endsWith('/request_2'));
});

test('admitted clarification projects a Nenex answer and retains the same response destination',async()=>{
  const app=await setup();app.addTurn();const turn=app.state.turns[0];turn.published=false;
  turn.input={root:turn.controller,blocks:[{target:turn.controller+'/work/request_1',view:'/0x11/gov/conversation/answer_input',kind:'presentation'}],tools:[]};
  await app.tick();const form=app.docs.get(turn.controller),reply=turn.reply;
  const answer=turn.message+'/clarifications/request_1';
  turn.clarifications=[{message:answer,version:'1',sequence:3}];turn.input.blocks=[];turn.workVersion='2';turn.status='working';
  await form.onSaved();assert.equal(form.updates.length,1);assert.equal(form.updates[0].blocks.length,0);
  assert.ok(app.mounts.includes(answer));assert.equal(app.docs.get(answer).options.compact,true);
  turn.published=true;turn.status='watching';turn.replyVersion='2';await app.tick();
  assert.ok(app.mounts.includes(reply));assert.ok(app.reads.every(url=>!url.includes('/op/')));
});

test('responses follow the bottom until someone reads earlier work; explicit latest resumes following',async()=>{
  const app=await setup(),history=app.nodes.get('conversation-history'),latest=app.nodes.get('conversation-latest');
  app.addTurn();history.scrollHeight=1200;await app.tick();assert.equal(history.scrollTop,800);
  history.scrollTop=100;history.events.scroll();history.scrollHeight=1600;await app.tick();
  assert.equal(history.scrollTop,100);assert.equal(latest.hidden,false);
  latest.click();assert.equal(history.scrollTop,1200);assert.equal(latest.hidden,true);
  // An actively edited projection keeps its position even while following.
  app.doc.activeElement=app.nodes.get('conversation-turns').children[0];
  history.scrollHeight=2000;await app.tick();assert.equal(history.scrollTop,1200);
});

test('incremental document rendering does not mistake an earlier automatic scroll for a person scrolling away',async()=>{
  const app=await setup(),history=app.nodes.get('conversation-history');
  app.addTurn();history.scrollHeight=1200;await app.tick();
  // More native blocks arrive before the browser delivers the preceding scroll.
  history.scrollHeight=1600;history.events.scroll();
  assert.equal(history.scrollTop,1200);
  history.scrollTop=500;history.events.scroll();
  history.scrollHeight=2000;app.resizes[0].callback();assert.equal(history.scrollTop,500);
});

test('a resize retains the composer draft and refreshes only clean projections',async()=>{
  const app=await setup();app.addTurn();await app.tick();
  app.input.value='Keep this draft';app.input.focus();
  await app.report('The send was rejected.');
  const reply=app.docs.get(app.mounts[1]);reply.edited=true;
  app.nodes.get('conversation-history').clientWidth=350;app.nodes.get('conversation-composer').clientWidth=320;
  await app.tick();
  assert.equal(app.input.value,'Keep this draft');assert.equal(reply.updates.length,0);
  assert.equal(app.loads.at(-1)[1].context.width,320);
  assert.equal(app.feedbackWidths.at(-1),320);assert.equal(app.notices.at(-1),'The send was rejected.');
  reply.edited=false;await app.tick();assert.equal(reply.updates.length,1);
});

test('native navigation keeps the composer and wiki mounted, and hidden wiki stops refreshing',async()=>{
  const app=await setup();app.input.value='Unsent message';const input=app.input;
  assert.ok(app.loads.some(([,selector])=>selector.slot==='/sys/slot/conversation_chat'));
  await app.selectView('wiki');
  const tree=app.docs.get(app.state.wiki);tree.edited=true;
  assert.equal(tree.manifest.frontier.root,app.state.wiki);
  assert.equal(tree.manifest.documentUrl,'/nenex/document');
  assert.equal(tree.options.compact,true);
  assert.equal(app.nodes.get('conversation-panel').hidden,false);
  await app.selectView('chat');const refreshed=tree.refreshes;
  await app.tick();assert.equal(tree.refreshes,refreshed);
  await app.selectView('wiki');assert.equal(app.mounts.filter(root=>root===app.state.wiki).length,1);
  assert.equal(app.input,input);assert.equal(input.value,'Unsent message');assert.equal(tree.edited,true);
});

test('work panel reuses the exact turn controls and refreshes stale work when reopened',async()=>{
  const app=await setup();app.addTurn();await app.tick();
  const article=app.nodes.get('conversation-turns').children[0],details=article.children.find(node=>node.events.toggle);
  await app.selectView('work');
  assert.equal(details.parentNode,app.nodes.get('conversation-work'));assert.equal(details.open,true);
  const view=app.docs.get(app.state.turns[0].controller);view.edited=true;
  await app.selectView('chat');assert.equal(details.parentNode,article);
  assert.equal(app.docs.get(app.state.turns[0].controller),view);
  details.open=false;view.edited=false;app.state.turns[0].workVersion='2';
  const reads=app.reads.length;await app.tick();assert.equal(app.reads.slice(reads).some(url=>url.startsWith('/conversation/work?')),false);
  details.open=true;await details.events.toggle();assert.equal(view.updates.length,1);
  assert.equal(app.mounts.filter(path=>path===app.state.turns[0].controller).length,1);
});

test('narrow wiki mode does not prepare the hidden composer at zero width',async()=>{
  const app=await setup();app.input.value='Keep this draft';
  app.nodes.get('conversation-composer').clientWidth=0;app.nodes.get('conversation-history').clientWidth=0;
  await app.selectView('wiki');
  assert.equal(app.loads.some(([,selector])=>selector.context.width===0),false);
  app.nodes.get('conversation-composer').clientWidth=320;app.nodes.get('conversation-history').clientWidth=320;
  await app.selectView('chat');assert.equal(app.input.value,'Keep this draft');
  assert.equal(app.loads.at(-1)[1].context.width,320);
});
