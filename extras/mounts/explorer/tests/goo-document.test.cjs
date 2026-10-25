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
        input.dataset.inputSlot='/text';input.value=saved;
        input.gooEditor={area,selection:()=>({a:2,b:2}),restore:()=>{}};
        element.input=input;
      }
      element.input.setAttribute('value',saved);return element;
    },
    bind(element,context){contexts.set(context.target,context);context.input('/text',element.input,new AbortController().signal);},
    captureActivation(element,_context,control){const capture={value:element.input.value,command:control.editCommand};captures.push(capture);return capture;},
    async activateCaptured(capture,args){
      calls.push({capture,args:JSON.stringify(args)});
      if(!capture.accepted){capture.accepted=true;saved=normalize(capture.value);writes++;manifest.epoch=String(writes+1);}
      if(lostReply){lostReply=false;throw Object.assign(Error('Outcome unknown'),{code:'outcome-unknown'});}
      return {savedInputs:new Map([['/text',capture.value]])};
    }
  };
  const sandbox={GooActions:api,AbortController,setTimeout,console,
    location:{href:'/nenex/edit?path=/doc'},addEventListener:(k,f)=>events[k]=f,
    document:{querySelector:()=>main,createElement:()=>new Element(),activeElement:null},
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
