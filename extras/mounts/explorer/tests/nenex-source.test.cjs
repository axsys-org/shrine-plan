const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function sourceEditor(response) {
  const events={}, handlers={}, requests=[], redirects=[];
  const textarea={value:'Original source',addEventListener(){}}, status={}, button={disabled:false};
  const shell={dataset:{page:'/0x11/app/nenex/w/home',corpus:'/0x11/app/nenex/w'},querySelectorAll:()=>[],addEventListener(){}};
  const editor={action:'/nenex/source',addEventListener:(name,fn)=>handlers[name]=fn,querySelector:()=>button};
  const nodes={'.wiki-shell':shell,'#page-source':textarea,'#editor':editor,'#save-state':status};
  const sandbox={URLSearchParams,AbortSignal,window:{},
    document:{querySelector:key=>nodes[key]||null,addEventListener(){},getElementById:()=>null},
    addEventListener:(name,fn)=>events[name]=fn,
    location:{hash:'',assign:url=>redirects.push(url)},
    MutationObserver:class{observe(){}},
    FormData:class { *[Symbol.iterator](){yield ['page',shell.dataset.page];yield ['epoch','42'];yield ['src',textarea.value];} },
    fetch:async(url,options)=>{requests.push({url,body:options.body.toString()});return response;}
  };
  vm.runInNewContext(fs.readFileSync(require.resolve('../../nenex/interface.js'),'utf8'),sandbox);
  return {textarea,status,button,requests,redirects,events,save:()=>handlers.submit({preventDefault(){}})};
}

test('source conflict keeps the draft and unload protection',async()=>{
  const ui=sourceEditor({ok:false,json:async()=>({error:'nenex_document_changed_retain_draft'})});
  ui.textarea.value='My unsaved flow';await ui.save();
  assert.equal(ui.requests[0].url,'/nenex/source');
  assert.equal(new URLSearchParams(ui.requests[0].body).get('epoch'),'42');
  assert.equal(ui.textarea.value,'My unsaved flow');
  assert.equal(ui.button.disabled,false);assert.deepEqual(ui.redirects,[]);
  assert.match(ui.status.textContent,/nenex_document_changed_retain_draft/);
  let prevented=false;ui.events.beforeunload({preventDefault(){prevented=true;}});
  assert.equal(prevented,true);
});

test('source editor follows the native admitted response',async()=>{
  const ui=sourceEditor({ok:true,json:async()=>({error:'',redirect:'/nenex?path=accepted'})});
  ui.textarea.value='Updated source';await ui.save();
  assert.deepEqual(ui.redirects,['/nenex?path=accepted']);
});
