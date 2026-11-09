const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

// Exercise the document host through the same bound controls as the browser.
// The transport double distinguishes a committed write from a lost reply.
async function setup({lostReply=false,failedRefresh=false,normalize=value=>value}={}) {
  class Element {
    constructor(){this.children=[];this.dataset={};this.handlers={};this.attrs={};}
    setAttribute(k,v){this.attrs[k]=v;}
    getAttribute(k){return this.attrs[k];}
    addEventListener(k,f){this.handlers[k]=f;}
    before(){}
    append(node){node.parent=this;this.children.push(node);}
    remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
    insertBefore(node,at){node.remove();node.parent=this;this.children.splice(at?this.children.indexOf(at):this.children.length,0,node);}
    contains(){return false;}
    querySelector(){return null;}
  }
  const main=new Element(), messages=[], captures=[], calls=[], contexts=new Map(), events={};
  const manifest={root:'/doc',epoch:'1',blocks:[{target:'/doc/0',view:'/edit',kind:'prose'}]};
  main.clientWidth=720;main.dataset.manifest=JSON.stringify(manifest);
  let saved='original',writes=0,ready;
  const opened=new Promise(resolve=>ready=resolve);
  const api={
    context:()=>({width:720,textScale:1,direction:'ltr'}),
    feedback:async(_node,message)=>{messages.push(message);if(message==='Ready')ready();},
    load:async()=>({snapshot:{life:'1',expected:String(writes+1)},view:'/edit',controls:['save','split'].map(editCommand=>({editCommand}))}),
    mount(element,_data,preserve){
      if(!preserve||!element.input){
        const input=new Element(),area=new Element();area.focus=()=>{};
        input.dataset.inputSlot='/text';input.dataset.gooInputKey='0.1';input.value=saved;
        input.gooEditor={area,selection:()=>({a:2,b:2}),restore:()=>{}};
        element.input=input;
      }
      element.input.setAttribute('value',saved);return element;
    },
    bind(element,context){contexts.set(context.target,context);context.input('0.1',element.input,new AbortController().signal);},
    captureActivation(element,_context,control){const capture={value:element.input.value,command:control.editCommand};captures.push(capture);return capture;},
    async activateCaptured(capture,args){
      calls.push({capture,args:JSON.stringify(args)});
      if(!capture.accepted){capture.accepted=true;saved=normalize(capture.value);writes++;manifest.epoch=String(writes+1);}
      if(lostReply){lostReply=false;throw Object.assign(Error('Outcome unknown'),{code:'outcome-unknown'});}
      return {savedInputs:new Map([['0.1',capture.value]])};
    }
  };
  const sandbox={GooActions:api,AbortController,setTimeout,console,
    location:{href:'/nenex/edit?path=/doc'},addEventListener:(k,f)=>events[k]=f,
    document:{querySelector:selector=>selector==='main[data-goo-document]'?main:null,createElement:()=>new Element(),activeElement:null},
    DOMParser:class{parseFromString(){return {querySelector:()=>({dataset:{manifest:JSON.stringify(manifest)}})};}},
    fetch:async()=>{if(failedRefresh&&writes){failedRefresh=false;throw Error('Refresh unavailable');}return {ok:true,text:async()=>''};}
  };
  vm.runInNewContext(fs.readFileSync(require.resolve('../goo-document.js'),'utf8'),sandbox);
  await opened;
  return {main,messages,captures,calls,events,get writes(){return writes;},
    input:()=>main.children[0].input,
    act:command=>contexts.get('/doc/0').activate({editCommand:command}),
    resume:()=>main.handlers.keydown({ctrlKey:true,key:'s',preventDefault(){}})};
}

test('unknown structural outcomes resume the exact capture before accepting another intent',async()=>{
  const host=await setup({lostReply:true});host.input().value='draft';
  await assert.rejects(host.act('split'),/unknown/);
  assert.equal(host.input().gooFrozen,true);
  assert.equal(host.writes,1);
  // Ctrl/Cmd+S must resume even though this is a split, not capture a new Save.
  await host.resume();
  assert.equal(host.captures.length,1);assert.equal(host.calls.length,2);
  assert.equal(host.calls[0].capture,host.calls[1].capture);
  assert.equal(host.calls[0].args,host.calls[1].args);
  assert.equal(host.writes,1);assert.equal(host.input().gooFrozen,false);
  assert.equal(host.messages.at(-1),'Saved');
});

test('accepted structure changes survive a failed refresh without repeating the write',async()=>{
  const host=await setup({failedRefresh:true});host.input().value='draft';
  await assert.rejects(host.act('split'),/Refresh unavailable/);
  let guarded=false;host.events.beforeunload({preventDefault(){guarded=true;}});
  assert.equal(guarded,true);
  await host.resume();
  assert.equal(host.captures.length,1);assert.equal(host.calls.length,1);
  assert.equal(host.writes,1);assert.equal(host.messages.at(-1),'Saved');
});

test('confirmed saves adopt the native value when no newer local draft exists',async()=>{
  const host=await setup({normalize:value=>value.toUpperCase()});host.input().value='draft';
  await host.act('save');
  assert.equal(host.input().value,'DRAFT');assert.equal(host.messages.at(-1),'Saved');
});

test('document structure waits for composition and pending text commands',async()=>{
  const host=await setup();host.input().gooComposing=true;
  await assert.rejects(host.act('split'),/Finish the current text edit/);
  host.input().gooComposing=false;host.input().gooEditor.pending=true;
  await assert.rejects(host.act('split'),/Finish the current text edit/);
  assert.equal(host.writes,0);assert.equal(host.captures.length,0);
});

function composableHost({fetch,intersection=false}={}){
  class Element{
    constructor(tag='section'){this.children=[];this.dataset={};this.handlers={};this.attrs={};this.clientWidth=720;this.tagName=tag.toUpperCase();}
    get parentNode(){return this.parent;}
    setAttribute(k,v){this.attrs[k]=v;}
    getAttribute(k){return this.attrs[k];}
    addEventListener(k,f){this.handlers[k]=f;}
    before(){}
    append(node){node.remove();node.parent=this;this.children.push(node);}
    remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);this.parent=null;}
    insertBefore(node,at){node.remove();node.parent=this;this.children.splice(at?this.children.indexOf(at):this.children.length,0,node);}
    contains(){return false;}
    querySelector(){return null;}
    replaceChildren(...nodes){this.children=[];for(const node of nodes)this.append(node);}
  }
  const contexts=new Map(),loads=[],writes=[],values=new Map(),revisions=new Map(),events={};
  const api={
    context:()=>({width:720,textScale:1,direction:'ltr'}),feedback:async()=>{},
    load:async(target,selector)=>{loads.push({target,selector});return {target,snapshot:{life:'1',expected:String(revisions.get(target)||1)},view:selector.view||selector.slot,controls:[{editCommand:'save'}]};},
    mount(element,data,preserve){
      if(!preserve||!element.input){const input=new Element(),area=new Element();area.focus=()=>{};input.value=values.get(data.target)||'original';input.dataset.inputSlot='/text';input.dataset.gooInputKey='0.1';input.gooEditor={area,selection:()=>({a:0,b:0}),restore:()=>{}};element.input=input;}
      element.input.setAttribute('value',values.get(data.target)||'original');return element;
    },
    bind(element,context){contexts.set(context.target,context);context.input('0.1',element.input,new AbortController().signal);},
    captureActivation(element,context,control){return {target:context.target,value:element.input.value,command:control.editCommand};},
    async activateCaptured(captured,args){writes.push({captured,args});values.set(captured.target,captured.value);revisions.set(captured.target,(revisions.get(captured.target)||1)+1);return {savedInputs:new Map([['0.1',captured.value]])};}
  };
  const observers=[],messages=[],feedbackWidths=[];api.feedback=async(_element,message,width)=>{messages.push(message);feedbackWidths.push(width);};
  const sandbox={GooActions:api,AbortController,setTimeout,console,URLSearchParams,fetch,addEventListener:(k,f)=>events[k]=f};
  if(intersection)sandbox.IntersectionObserver=class{constructor(callback){this.callback=callback;observers.push(this);}observe(target){this.target=target;}disconnect(){}};
  vm.runInNewContext(fs.readFileSync(require.resolve('../goo-topoi.js'),'utf8'),sandbox);
  vm.runInNewContext(fs.readFileSync(require.resolve('../goo-document.js'),'utf8'),sandbox);
  sandbox.document={createElement:tag=>new Element(tag),activeElement:null};
  return {Element,contexts,loads,writes,values,revisions,events,observers,messages,feedbackWidths,mount:sandbox.GooDocument.mount,mountTree:sandbox.GooDocument.mountTree};
}

test('composed native pages retain independent drafts, epochs and structural scopes',async()=>{
  const host=composableHost(),first=new host.Element(),second=new host.Element();
  const a={root:'/a',epoch:'11',blocks:[{target:'/a/0',view:'/edit',kind:'prose'}]},b={root:'/b',epoch:'29',blocks:[{target:'/b/0',view:'/edit',kind:'prose'}]};
  await host.mount(first,a,async()=>({...a,epoch:'12'}));
  await host.mount(second,b,async()=>({...b,epoch:'30'}));
  first.children[0].input.value='saved a';second.children[0].input.value='unsaved b';
  await host.contexts.get('/a/0').activate({editCommand:'save'});
  assert.equal(host.writes.length,1);assert.equal(host.writes[0].captured.target,'/a/0');
  assert.equal(host.writes[0].args.find(([slot])=>slot==='/epoch')[1],'11');
  assert.equal(second.children[0].input.value,'unsaved b');
  await second.handlers.keydown({ctrlKey:true,key:'s',preventDefault(){}});
  assert.equal(host.writes.length,2);assert.equal(host.writes[1].captured.target,'/b/0');
  assert.equal(host.writes[1].args.find(([slot])=>slot==='/epoch')[1],'29');
});

test('an authored embed prepares the declared view against the real receiver',async()=>{
  const host=composableHost(),main=new host.Element();
  const manifest={root:'/page',epoch:'1',blocks:[
    {key:'/page/0',target:'/subject/work/flow',view:'/gov/flows/occurrence',kind:'ref',editor:false},
    {key:'/page/1',target:'/subject/work/flow',view:'/gov/flows/occurrence',kind:'ref',editor:false}
  ]};
  await host.mount(main,manifest,async()=>manifest);
  assert.equal(main.children.length,2);assert.equal(host.loads.length,2);
  assert.ok(host.loads.every(({target,selector})=>target==='/subject/work/flow'&&selector.view==='/gov/flows/occurrence'));
  const context=host.contexts.get('/subject/work/flow');
  assert.equal(context.activate,undefined);assert.equal(context.textCommand,undefined);
});

test('page tool views prepare on disclosure and use the shared action binding',async()=>{
  const host=composableHost(),main=new host.Element();
  const manifest={root:'/page',epoch:'1',blocks:[],tools:[{key:'source',target:'/page',view:'/source',kind:'presentation',label:'Source'}]};
  const view=await host.mount(main,manifest,async()=>manifest);
  assert.equal(host.loads.length,0);
  const disclosure=main.children[0];disclosure.open=true;disclosure.handlers.toggle();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(host.loads.length,1);
  const context=host.contexts.get('/page');
  assert.equal(context.activate,undefined);assert.equal(context.textCommand,undefined);
  assert.equal(typeof context.saved,'function');
  // Completion can remove the last action form. Its sibling feedback still
  // uses the visible host allocation rather than the now-hidden form's zero.
  manifest.tools=[];main.clientWidth=0;main.parentElement={clientWidth:360};
  await context.saved({},new Map());await context.report('Saved.');
  assert.equal(host.feedbackWidths.at(-1),360);
  main.parentElement.clientWidth=320;await view.update(manifest);
  assert.equal(host.feedbackWidths.at(-1),320);assert.equal(host.messages.at(-1),'Saved.');
});

test('compact documents keep native content and embeds live while page controls prepare on disclosure',async()=>{
  const host=composableHost(),main=new host.Element();
  const manifest={root:'/page',epoch:'1',blocks:[
    {target:'/page',view:'/header',kind:'presentation'},
    {target:'/page/0',view:'/edit',kind:'prose'},
    {key:'/page/1',target:'/flow',view:'/occurrence',kind:'ref',editor:false}
  ],tools:[{target:'/source',view:'/source',kind:'presentation',label:'Source'}]};
  await host.mount(main,manifest,async()=>manifest,async()=>{},{compact:true});
  assert.deepEqual(host.loads.map(load=>load.target),['/page/0','/flow']);
  const [body,inspector]=main.children,inspection=inspector.children[1];
  const original=body.children[0];original.input.value='working prose';
  inspector.open=true;await inspector.handlers.toggle();
  assert.equal(body.children[0],original);assert.equal(original.input.value,'working prose');
  assert.ok(host.loads.some(load=>load.target==='/page'));
  assert.ok(!host.loads.some(load=>load.target==='/source'));
  const source=inspection.children[1];source.open=true;source.handlers.toggle();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(host.contexts.get('/source').activate,undefined);
  assert.equal(typeof host.contexts.get('/source').saved,'function');
  await host.contexts.get('/page/0').activate({editCommand:'save'});
  assert.equal(host.writes[0].captured.target,'/page/0');
  assert.equal(host.writes[0].captured.value,'working prose');
});

test('closing compact inspection retains page-action drafts and still guards receiver replacement',async()=>{
  const host=composableHost(),main=new host.Element();
  const header={target:'/page',view:'/header',kind:'presentation'};
  const manifest={root:'/page',epoch:'1',blocks:[header]};
  const view=await host.mount(main,manifest,async()=>manifest,async()=>{},{compact:true});
  const inspector=main.children[1];inspector.open=true;await inspector.handlers.toggle();
  const frame=inspector.children[1].children[0];frame.input.value='unsubmitted action';
  inspector.open=false;await inspector.handlers.toggle();
  await view.update({...manifest,epoch:'2'});
  assert.equal(frame.input.value,'unsubmitted action');assert.equal(view.dirty(),true);
  await assert.rejects(view.update({...manifest,blocks:[]}),/unsaved draft/);
});

test('content-only documents omit wiki chrome while retaining native edits and authored embeds',async()=>{
  const host=composableHost(),main=new host.Element();
  const manifest={root:'/page',epoch:'8',blocks:[
    {target:'/page',view:'/header',kind:'presentation'},
    {target:'/page/0',view:'/edit',kind:'prose'},
    {key:'/page/1',target:'/flow',view:'/occurrence',kind:'ref',editor:false}
  ],tools:[{target:'/history',view:'/history',kind:'presentation',label:'History'}]};
  const view=await host.mount(main,manifest,async()=>manifest,async()=>{},{compact:true,chrome:false});
  assert.equal(main.children.length,1);assert.deepEqual(host.loads.map(load=>load.target),['/page/0','/flow']);
  assert.equal(host.contexts.get('/flow').activate,undefined);
  const prose=main.children[0].children[0];prose.input.value='draft';
  await assert.rejects(view.update({...manifest,blocks:[]}),/unsaved draft/);
  await host.contexts.get('/page/0').activate({editCommand:'save'});
  assert.equal(host.writes[0].captured.target,'/page/0');assert.equal(host.writes[0].captured.value,'draft');
  assert.equal(host.writes[0].args.find(([slot])=>slot==='/epoch')[1],'8');
});

test('closed tool views retain drafts without preparing at zero width and refresh on reopening',async()=>{
  const host=composableHost(),main=new host.Element();
  const manifest={root:'/page',epoch:'1',blocks:[],tools:[{target:'/source',view:'/source',kind:'presentation',label:'Source'}]};
  const view=await host.mount(main,manifest,async()=>manifest);
  const disclosure=main.children[0];disclosure.open=true;disclosure.handlers.toggle();
  await new Promise(resolve=>setImmediate(resolve));
  const frame=disclosure.children[1];frame.input.value='unsaved source';
  disclosure.open=false;frame.clientWidth=0;
  const before=host.loads.length;await view.update({...manifest,epoch:'2'});
  assert.equal(host.loads.length,before);assert.equal(view.dirty(),true);
  frame.clientWidth=390;disclosure.open=true;disclosure.handlers.toggle();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(host.loads.at(-1).selector.context.width,390);
  assert.equal(frame.input.value,'unsaved source');
});

test('replacing an embedded receiver refuses before dropping its local input',async()=>{
  const host=composableHost(),main=new host.Element();
  const manifest={root:'/page',epoch:'1',blocks:[{key:'/page/0',target:'/old',view:'/declared',kind:'ref',editor:false}]};
  const document=await host.mount(main,manifest,async()=>manifest);
  main.children[0].input.value='unsubmitted binding';
  await assert.rejects(document.update({...manifest,blocks:[{...manifest.blocks[0],target:'/new'}]}),/unsaved draft/);
  assert.equal(main.children[0].input.value,'unsubmitted binding');assert.equal(host.loads.length,1);
});


test('native tree pages load lazily and per-page saves refresh only their own manifest',async()=>{
  const calls=[],parent={root:'/parent',epoch:'10',blocks:[{target:'/parent/0',view:'/edit',kind:'prose'}]},child={root:'/parent/child',epoch:'11',blocks:[{target:'/parent/child/0',view:'/edit',kind:'prose'}]};
  const host=composableHost({intersection:true,fetch:async url=>{calls.push(url);const path=new URL(url,'http://fixture').searchParams.get('path');return {ok:true,json:async()=>path==='/parent'?{...parent,epoch:'12'}:child};}});
  const tree=new host.Element();
  await host.mountTree(tree,{root:'/parent',pages:[parent],documentUrl:'/document',childrenUrl:'/children',frontier:{root:'/parent',epoch:'10',life:'1',hasChildren:true,next:null,members:[{root:'/parent/child',document:true,label:'Child',life:'2',hasChildren:false}]}});
  assert.deepEqual(calls,[],'unopened page content is not prepared');
  host.observers[0].callback([{isIntersecting:true}]);await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.length,1);assert.match(calls[0],/^\/document\?path=%2Fparent%2Fchild$/);
  const pages=tree.children[1],childHolder=pages.children[0];
  childHolder.children[0].input.value='unsaved child';tree.children[0].children[0].input.value='saved parent';
  await host.contexts.get('/parent/0').activate({editCommand:'save'});
  assert.equal(calls.length,2);assert.match(calls[1],/^\/document\?path=%2Fparent$/);
  assert.equal(childHolder.children[0].input.value,'unsaved child');assert.equal(host.writes.length,1);
});

test('TreeSource refreshes a stale native continuation without discarding an already open page draft',async()=>{
  const calls=[],child={root:'/tree/child',epoch:'5',blocks:[{target:'/tree/child/0',view:'/edit',kind:'prose'}]};
  let epoch='11',stale=true;
  const first=()=>({root:'/tree',epoch,life:'1',hasChildren:true,next:'native-cursor',members:[{root:'/tree/child',document:true,label:'Child',life:'2',hasChildren:false}]});
  const host=composableHost({fetch:async url=>{calls.push(url);const query=new URL(url,'http://fixture');if(query.pathname==='/document')return {ok:true,json:async()=>child};
    if(query.searchParams.has('after')){if(stale){stale=false;epoch='12';return {ok:false,text:async()=> 'Native frontier changed'};}return {ok:true,json:async()=>({root:'/tree',epoch,life:'1',hasChildren:true,next:null,members:[]})};}
    return {ok:true,json:async()=>first()};}});
  const tree=new host.Element();await host.mountTree(tree,{root:'/tree',pages:[],documentUrl:'/document',childrenUrl:'/children',frontier:first()});
  const pages=tree.children[0],childHolder=pages.children[0],more=pages.children.find(node=>node.type==='button');
  childHolder.children[0].input.value='retained draft';
  await more.handlers.click();assert.equal(more.disabled,false);assert.equal(childHolder.children[0].input.value,'retained draft');
  assert.ok(host.messages.some(message=>message.includes('Native frontier changed')));
  await more.handlers.click();
  assert.equal(childHolder.children[0].input.value,'retained draft');assert.equal(pages.children.includes(more),false);
  const cursorCalls=calls.filter(url=>url.includes('after='));assert.equal(cursorCalls.length,2);
  assert.match(cursorCalls[0],/epoch=11/);assert.match(cursorCalls[1],/epoch=12/);
  assert.equal(host.writes.length,0,'topology navigation cannot invoke native work');
});

test('generic source controls retain a later local draft after their accepted write refreshes',async()=>{
  const host=composableHost(),main=new host.Element();
  const manifest={root:'/page',epoch:'1',blocks:[{key:'source',target:'/page',view:'/source',kind:'presentation'}]};
  const document=await host.mount(main,manifest,async()=>({...manifest,epoch:'2'}));
  main.children[0].input.value='later local draft';host.values.set('/page','submitted');host.revisions.set('/page',2);
  await host.contexts.get('/page').saved({},new Map([['0.1','submitted']]));
  assert.equal(main.children[0].input.value,'later local draft');assert.equal(main.children[0].input.getAttribute('value'),'submitted');
  assert.equal(host.contexts.get('/page').snapshot.expected,'2');assert.equal(document.dirty(),true);
});

test('accepted page actions refresh a complete native frontier without remounting a dirty sibling',async()=>{
  const calls=[],library={root:'/tree',epoch:'1',blocks:[{target:'/tree',view:'/create',kind:'presentation'}]};
  const page=root=>({root,epoch:'1',blocks:[{target:root+'/0',view:'/edit',kind:'prose'}]});
  let created=false;
  const member=root=>({root,document:true,label:root,life:'2',hasChildren:false});
  const frontier=()=>({root:'/tree',epoch:created?'2':'1',life:'1',hasChildren:true,next:null,members:[member('/tree/first'),...(created?[member('/tree/second')]:[])]});
  const host=composableHost({fetch:async url=>{calls.push(url);const query=new URL(url,'http://fixture'),path=query.searchParams.get('path');
    return {ok:true,json:async()=>query.pathname==='/children'?frontier():path==='/tree'?{...library,epoch:'2'}:page(path)};}});
  const tree=new host.Element();await host.mountTree(tree,{root:'/tree',pages:[library],documentUrl:'/document',childrenUrl:'/children',frontier:frontier()});
  const pages=tree.children[1],first=pages.children[0],input=first.children[0].input;
  input.value='keep this existing page draft';created=true;
  await host.contexts.get('/tree').saved({},new Map());
  assert.equal(pages.children.length,2);assert.equal(pages.children[0],first);
  assert.equal(first.children[0].input,input);assert.equal(input.value,'keep this existing page draft');
  assert.ok(host.contexts.has('/tree/second/0'),'the new native sibling is usable immediately');
  assert.equal(calls.filter(url=>url==='/document?path=%2Ftree%2Ffirst').length,1,'unchanged page content is not reloaded');
  assert.equal(calls.filter(url=>url==='/children?path=%2Ftree').length,1,'the existing complete frontier is re-read after acceptance');
});

test('embedded trees refresh changed native versions without replacing drafts or rereading unchanged pages',async()=>{
  const calls=[];let version='1';
  const frontier=()=>({root:'/wiki',epoch:version,version,life:'1',hasChildren:false,next:null,members:[]});
  const page=()=>({root:'/wiki',epoch:version,blocks:[{target:'/wiki/0',view:'/edit',kind:'prose'}]});
  const host=composableHost({fetch:async url=>{calls.push(url);return {ok:true,json:async()=>url.startsWith('/children')?frontier():page()};}});
  const element=new host.Element(),tree=await host.mountTree(element,{root:'/wiki',pages:[page()],frontier:frontier(),documentUrl:'/document',childrenUrl:'/children'});
  await tree.refresh();assert.equal(calls.some(url=>url.startsWith('/document')),false);
  const input=element.children[0].children[0].input;input.value='Local wiki draft';version='2';
  await tree.refresh();assert.equal(tree.dirty(),true);assert.equal(input.value,'Local wiki draft');
  assert.equal(calls.some(url=>url.startsWith('/document')),false);
  input.value=input.getAttribute('value');await tree.refresh();
  assert.equal(calls.filter(url=>url.startsWith('/document')).length,1);assert.equal(tree.dirty(),false);
  await tree.refresh();assert.equal(calls.filter(url=>url.startsWith('/document')).length,1);
});
