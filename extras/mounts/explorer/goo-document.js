/* Continuous native Goo surfaces. The server owns topology, block kinds and writes.
   This host holds only prepared controls, their input drafts and platform focus. */
(function(root){
  'use strict';
  async function start(){
    const main=document.querySelector('main[data-goo-document]');if(!main)return;
    const api=root.GooActions, frames=new Map();let manifest=JSON.parse(main.dataset.manifest), busy=false, failed=false, pendingChange=null;
    const notice=document.createElement('div');notice.setAttribute('role','status');main.before(notice);
    const report=message=>api.feedback(notice,message,720);
    const dirty=frame=>frame.input && frame.input.value!==frame.input.getAttribute('value');
    async function readManifest(){
      const response=await fetch(location.href,{cache:'no-store'});if(!response.ok)throw Error(await response.text());
      const page=new DOMParser().parseFromString(await response.text(),'text/html');
      const next=JSON.parse(page.querySelector('[data-goo-document]').dataset.manifest);
      if(next.root!==manifest.root || !Array.isArray(next.blocks))throw Error('Document changed identity. Your drafts are retained.');
      return next;
    }
    function area(frame){return frame?.input?.gooEditor?.area;}
    function focus(frame,at=0){const input=frame?.input;if(!input)return;area(frame).focus();input.gooEditor.restore({a:at,b:at});}
    function ordered(){return manifest.blocks.map(block=>frames.get(block.target)).filter(frame=>frame?.input);}
    function navigate(frame,direction){const list=ordered(),at=list.indexOf(frame),next=list[at+direction];if(next)focus(next,direction<0?root.GooRichInput.text(next.input.gooEditor.runs).length:0);}
    async function render(frame,preserve,ownCommit=false){
      const data=await api.load(frame.block.target,{view:frame.block.view,context:{...api.context(main),width:Math.min(main.clientWidth,720),layout:undefined}});
      if(preserve && frame.data && (frame.data.snapshot.life!==data.snapshot.life || (!ownCommit && frame.data.snapshot.expected!==data.snapshot.expected)) && dirty(frame))throw Error('A block was replaced. Your draft is retained.');
      const retainDraft=preserve&&dirty(frame);
      const content=api.mount(frame.element,data,preserve,false);frame.data=data;
      const context={target:frame.block.target,view:data.view,snapshot:data.snapshot,controls:data.controls,actionScope:frame,report,
        input:(_key,input,signal)=>{frame.input=input;
          if(!retainDraft)input.value=input.getAttribute('value')??input.value;
          input.addEventListener('input',()=>{failed=false;report('Unsaved changes');},{signal});
          input.addEventListener('focusout',event=>{if(!frame.element.contains(event.relatedTarget))setTimeout(()=>{if(!busy&&!failed&&dirty(frame)&&!area(frame)?.contains(document.activeElement))execute(frame,'save').catch(()=>{});},0);},{signal});
        },
        activate:control=>execute(frame,control.editCommand||'save'),
        textCommand:(command,range)=>execute(frame,command==='paragraph-break'?'split':command,range),
        documentNavigate:direction=>navigate(frame,direction)
      };
      frame.context=context;api.bind(content,context);
      // Block chrome is itself a prepared Grove row. Platform focus reveals it.
      const chrome=frame.element.querySelector('[data-slot="/sys/slot/block_actions"]');
      if(chrome){const anchor=document.createComment('native block controls');chrome.before(anchor);
        frame.chromeBinding?.abort();frame.chromeBinding=new AbortController();
        frame.element.addEventListener('focusin',()=>{if(!chrome.isConnected)anchor.after(chrome);},{signal:frame.chromeBinding.signal});
        frame.element.addEventListener('focusout',event=>{if(!frame.element.contains(event.relatedTarget))chrome.remove();},{signal:frame.chromeBinding.signal});
        for(const control of data.controls||[])if(control.kind==='action'){
          const button=[...chrome.querySelectorAll('[data-node]')].find(node=>node.dataset.node===control.id);
          if(button && ['split','merge','paragraph','heading','bullet','quote','code'].includes(control.editCommand))button.remove();
        }
        if(!frame.element.contains(document.activeElement))chrome.remove();
      }
    }
    async function reconcile(next,structural=false){
      if(structural && [...frames.values()].some(dirty))throw Error('Unsaved edits must be saved before changing block structure.');
      manifest=next;
      const seen=new Set();let position=0;
      for(const block of manifest.blocks){
        seen.add(block.target);let frame=frames.get(block.target);
        if(frame && (structural || frame.block.view!==block.view)){frame.element.remove();frames.delete(block.target);frame=null;}
        if(!frame){const element=document.createElement('section');element.setAttribute('aria-label',`${block.kind} ${block.target}`);main.append(element);frame={block,element};frames.set(block.target,frame);}
        frame.block=block;const at=main.children[position++];if(at!==frame.element)main.insertBefore(frame.element,at||null);
        if(block.view){
          try{await render(frame,Boolean(frame.data));}
          catch(error){if(frame.data)throw error;frame.error=error.message;await api.feedback(frame.element,`Block ${block.target}: ${error.message}`,720);}
        }
        else frame.element.innerHTML=block.markup||'';
      }
      for(const [key,frame] of frames)if(!seen.has(key)){if(dirty(frame))throw Error('A removed block has an unsaved draft.');frame.element.remove();frames.delete(key);}
    }
    async function commit(frame,command,range){
      let step=pendingChange.steps.get(frame);
      if(!step){
        const control=frame.data.controls.find(control=>control.editCommand===command);if(!control)throw Error('This block does not publish that command.');
        const current=range||frame.input.gooEditor.selection();
        step={captured:api.captureActivation(frame.element,frame.context,control),
          arguments:[['/start',String(current.a)],['/end',String(current.b)],['/epoch',manifest.epoch]]};
        pendingChange.steps.set(frame,step);
      }
      const {savedInputs}=await api.activateCaptured(step.captured,step.arguments);
      step.accepted=true;
      for(const [slot,value] of savedInputs)if(frame.input?.dataset.inputSlot===slot)frame.input.setAttribute('value',value);
    }
    async function execute(frame,command,range){
      if(busy)throw Error('Wait for the current document change.');
      if(ordered().some(entry=>entry.input.gooComposing||entry.input.gooEditor.pending))throw Error('Finish the current text edit before changing the document.');
      busy=true;failed=false;
      // Resume the captured operation before accepting any new intent. A lost
      // response is not permission to mint another invocation or renumber again.
      const change=pendingChange||(pendingChange={frame,command,range,index:ordered().indexOf(frame),steps:new Map(),committed:false});
      ({frame,command,range}=change);
      // Freeze platform editing during structural writes, including other drafts.
      const index=change.index,structural=command!=='save';
      if(structural)for(const entry of ordered()){entry.input.gooFrozen=true;area(entry).contentEditable='false';}
      try{
        report('Saving...');
        if(!change.committed){
          if(structural){for(const entry of ordered())if(entry!==frame&&dirty(entry)){
            await commit(entry,'save');manifest=await readManifest();
          }
          // Refresh after the other saves, including when resuming a lost reply.
          if(change.steps.size&&!change.steps.has(frame))manifest=await readManifest();
          if(!change.steps.has(frame))await render(frame,true);
          frame.input.gooFrozen=true;area(frame).contentEditable='false';
          }
          await commit(frame,command,range);change.committed=true;
        }
        const next=await readManifest();
        if(structural)await reconcile(next,true);
        else{manifest=next;await render(frame,true,true);}
        const list=ordered();
        if(structural){const nextIndex=command==='split'||command==='add'?index+1:command==='up'||command==='merge'?index-1:command==='down'?index+1:index;focus(list[Math.max(0,Math.min(list.length-1,nextIndex))]);}
        pendingChange=null;
        report([...frames.values()].some(dirty)?'Unsaved changes':'Saved');
      }catch(error){
        const confirmed=[...change.steps.values()].some(step=>step.accepted);
        if(error.code!=='outcome-unknown'&&!change.committed&&(!confirmed||error.rejected))pendingChange=null;
        failed=true;report(error.message+' Your draft is retained.'+(pendingChange?' Press Ctrl/Cmd+S to resume the same change.':''));throw error;
      }
      finally{busy=false;for(const entry of ordered()){const frozen=Boolean(pendingChange&&pendingChange.command!=='save');entry.input.gooFrozen=frozen;area(entry).contentEditable=frozen?'false':'true';}}
    }
    root.addEventListener('beforeunload',event=>{if(busy||pendingChange||[...frames.values()].some(dirty)){event.preventDefault();event.returnValue='';}});
    main.addEventListener('keydown',async event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='s'){
      event.preventDefault();
      if(pendingChange){try{await execute(pendingChange.frame,pendingChange.command);}catch{}return;}
      for(const frame of ordered())if(dirty(frame)){try{await execute(frame,'save');}catch{break;}}
    }});
    report("Opening document...");
    await reconcile(manifest);
    report([...frames.values()].some(frame=>frame.error)?"Some blocks require a renderer that supports their content. Their source is preserved.":"Ready");
  }
  if(typeof document!=='undefined')start().catch(error=>root.alert?.(error.message));
})(globalThis);
