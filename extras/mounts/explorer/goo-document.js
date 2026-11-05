/* Continuous native Goo surfaces. The server owns topology, block kinds and writes.
   This host holds only prepared controls, their input drafts and platform focus. */
(function(root){
  'use strict';
  async function mountDocument(main,initial,reload,onSaved=async()=>{}){
    const api=root.GooActions, frames=new Map();let manifest=initial, busy=false, failed=false, pendingChange=null;
    const notice=document.createElement('div');notice.setAttribute('role','status');main.before(notice);
    const report=message=>api.feedback(notice,message,720);
    const editable=frame=>frame.block.editor!==false && frame.block.kind!=='presentation';
    const dirty=frame=>frame.inputs?[...frame.inputs.values()].some(input=>input.value!==input.getAttribute('value')):Boolean(frame.input && frame.input.value!==frame.input.getAttribute('value'));
    async function readManifest(){
      const next=await reload(manifest.root);
      if(next.root!==manifest.root || !Array.isArray(next.blocks))throw Error('Document changed identity. Your drafts are retained.');
      return next;
    }
    function area(frame){return frame?.input?.gooEditor?.area;}
    function focus(frame,at=0){const input=frame?.input;if(!input)return;area(frame).focus();input.gooEditor.restore({a:at,b:at});}
    function ordered(){return manifest.blocks.map(block=>frames.get(block.key||block.target)).filter(frame=>frame?.input&&editable(frame));}
    function navigate(frame,direction){const list=ordered(),at=list.indexOf(frame),next=list[at+direction];if(next)focus(next,direction<0?root.GooRichInput.text(next.input.gooEditor.runs).length:0);}
    async function render(frame,preserve,ownCommit=false){
      const selector=frame.recipe?{slot:frame.recipe}:frame.block.view?{view:frame.block.view}:{slot:'/sys/slot/synthetic'};
      const data=await api.load(frame.block.target,{...selector,context:{...api.context(main),width:Math.min(main.clientWidth,720),layout:undefined}});
      if(preserve && frame.data && (frame.data.snapshot.life!==data.snapshot.life || (!ownCommit && frame.data.snapshot.expected!==data.snapshot.expected)) && dirty(frame))throw Error('A block was replaced. Your draft is retained.');
      const retainDraft=preserve&&dirty(frame);
      const content=api.mount(frame.element,data,preserve,false);frame.data=data;
      frame.inputs ||= new Map();
      const context={target:frame.block.target,view:data.view,snapshot:data.snapshot,controls:data.controls,actionScope:frame,report,
        input:(_key,input,signal)=>{frame.inputs.set(_key,input);if(editable(frame))frame.input=input;
          if(!retainDraft)input.value=input.getAttribute('value')??input.value;
          input.addEventListener('input',()=>{failed=false;report('Unsaved changes');},{signal});
          input.addEventListener('focusout',event=>{if(editable(frame)&&!frame.element.contains(event.relatedTarget))setTimeout(()=>{if(!busy&&!failed&&dirty(frame)&&!area(frame)?.contains(document.activeElement))execute(frame,'save').catch(()=>{});},0);},{signal});
        },
        ...(editable(frame)?{activate:control=>execute(frame,control.editCommand||'save')}:{}),
        become:async slot=>{if(dirty(frame))throw Error('Save the current action inputs before changing presentation.');frame.recipe=slot;frame.inputs.clear();await render(frame,false);},
        saved:async(_result,savedInputs)=>{for(const [key,value]of savedInputs){const input=frame.inputs.get(key);if(input)input.setAttribute('value',value);}await reconcile(await readManifest(),false,frame);await onSaved();},
        ...(editable(frame)?{textCommand:(command,range)=>execute(frame,command==='paragraph-break'?'split':command,range),
          documentNavigate:direction=>navigate(frame,direction)}:{})
      };
      frame.context=context;if(!frame.block.readonly)api.bind(content,context);
      else{const link=document.createElement('a');link.href='/ns'+frame.block.target;await api.feedback(link,'Inspect this native record and its history',720);frame.element.append(link);}
      // Block chrome is itself a prepared Grove row. Platform focus reveals it.
      const chrome=frame.element.querySelector('[data-slot="/sys/slot/block_actions"]');
      if(chrome&&editable(frame)){const anchor=document.createComment('native block controls');chrome.before(anchor);
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
    async function reconcile(next,structural=false,ownCommit=null){
      if(structural && [...frames.values()].some(dirty))throw Error('Unsaved edits must be saved before changing block structure.');
      const nextParts=[...next.blocks,...(next.tools||[])],nextByKey=new Map(nextParts.map(block=>[block.key||block.target,block]));
      for(const [key,frame]of frames){const block=nextByKey.get(key);if(dirty(frame)&&(!block||frame.block.target!==block.target||frame.block.view!==block.view))throw Error('A removed or replaced block has an unsaved draft.');}
      manifest=next;
      const seen=new Set();let position=0;
      const parts=[...manifest.blocks,...(manifest.tools||[])];
      for(const block of parts){
        const key=block.key||block.target;seen.add(key);let frame=frames.get(key);
        if(frame && (structural || frame.block.view!==block.view || frame.block.target!==block.target)){frame.holder.remove();frames.delete(key);frame=null;}
        if(!frame){const element=document.createElement('section');element.setAttribute('aria-label',`${block.kind} ${block.target}`);let holder=element;
          if(block.label){holder=document.createElement('details');const summary=document.createElement('summary');holder.append(summary);await api.feedback(summary,block.label,720);holder.append(element);}
          main.append(holder);frame={block,element,holder};frames.set(key,frame);
          if(block.label)holder.addEventListener('toggle',()=>{if(holder.open&&!frame.data)render(frame,false).catch(error=>report(error.message));});
        }
        frame.block=block;const at=main.children[position++];if(at!==frame.holder)main.insertBefore(frame.holder,at||null);
        if((block.view||block.readonly)&&(!block.label||frame.holder.open||frame.data)){
          try{await render(frame,Boolean(frame.data),frame===ownCommit);}
          catch(error){if(frame.data)throw error;frame.error=error.message;await api.feedback(frame.element,`Block ${block.target}: ${error.message}`,720);}
        }
        else if(!block.view&&!block.readonly&&block.reference){const link=document.createElement('a');link.href='/ns'+block.reference;await api.feedback(link,(block.descriptor?'Presentation unavailable; source descriptor retained. ':'')+block.reference,720);frame.element.replaceChildren(link);}

      }
      for(const [key,frame] of frames)if(!seen.has(key)){if(dirty(frame))throw Error('A removed block has an unsaved draft.');frame.holder.remove();frames.delete(key);}
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
      for(const [slot,value] of savedInputs)if((frame.input?.dataset.gooInputKey||frame.input?.dataset.inputSlot)===slot)frame.input.setAttribute('value',value);
    }
    async function execute(frame,command,range){
      if(busy)throw Error('Wait for the current document change.');
      if([...frames.values()].some(entry=>[...(entry.inputs?.values()||[])].some(input=>input.gooComposing||input.gooEditor?.pending)))throw Error('Finish the current text edit before changing the document.');
      if(command!=='save'&&[...frames.values()].some(entry=>!editable(entry)&&dirty(entry)))throw Error('Save or discard page action drafts before changing block structure.');
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
    return {update:reconcile,dirty:()=>busy||Boolean(pendingChange)||[...frames.values()].some(dirty)};
  }
  async function mountTree(tree,manifest){
    if(!Array.isArray(manifest.pages)||!manifest.frontier)throw Error('Expected native page manifests and a frontier.');
    const api=root.GooActions;
    async function read(url,params){
      const response=await fetch(url+'?'+new URLSearchParams(params),{cache:'no-store'});
      if(!response.ok)throw Error(await response.text());return response.json();
    }
    const readDocument=path=>read(manifest.documentUrl,{path});
    async function frontier(container,initial,onSaved=async()=>{}){
      let cached=initial,current,refreshing=null,recover=false;
      const entries=new Map();
      const more=document.createElement('button');more.type='button';
      const loader=new root.GooTopoi.TreeSource(initial.root,'y',async(params)=>{
        const page=!params.after&&cached?(cached):await read(manifest.childrenUrl,{path:initial.root,...(params.after?{after:params.after,epoch:params.epoch}:{})});cached=null;
        const members=page.members.map(member=>({...member,key:member.root,parent:page.root,status:member.document?'available':'unavailable'}));
        if(!params.after)members.unshift({key:page.root,parent:null,life:page.life,hasChildren:page.hasChildren,status:'available'});
        return {id:page.root,axis:'y',topology:'tree',incremental:true,life:page.life,epoch:page.epoch,parent:page.root,members,next:page.next};
      });
      async function reconcile(source){
        const members=source.members.filter(member=>member.key!==source.id),seen=new Set(members.map(member=>member.key));
        for(const [key,entry]of entries){const next=members.find(member=>member.key===key);if(entry.document?.dirty()&&(!next||entry.life!==next.life))throw Error('A removed or replaced page has an unsaved draft. Its original page and inputs are retained.');}
        for(const [key,entry]of entries)if(!seen.has(key)){entry.stop?.();entry.holder.remove();entries.delete(key);}
        let position=0;
        for(const member of members){
          let entry=entries.get(member.key);
          if(entry&&entry.life!==member.life){entry.stop?.();entry.holder.remove();entries.delete(member.key);entry=null;}
          if(!entry){
            const holder=document.createElement('section');holder.setAttribute('aria-label',member.root);container.insertBefore(holder,more.parentNode===container?more:null);
            entry={holder,life:member.life};entries.set(member.key,entry);
            let opening,refreshChildren;
            const open=()=>opening||=(async()=>{
              if(member.document){holder.replaceChildren();entry.document=await mountDocument(holder,await readDocument(member.root),readDocument,async()=>{await refreshAfterWrite();await onSaved();await refreshChildren?.();});}
              const branch=document.createElement('details'),summary=document.createElement('summary');branch.append(summary);holder.append(branch);await api.feedback(summary,member.document?'Child pages':member.label||member.root,720);
              let expanded=false,pending=false;
              branch.addEventListener('toggle',async()=>{if(!branch.open||expanded||pending)return;pending=true;try{const page=await read(manifest.childrenUrl,{path:member.root});refreshChildren=await frontier(branch,page,async()=>{await refreshAfterWrite();await onSaved();});expanded=true;}catch(error){await api.feedback(summary,error.message,720);}finally{pending=false;}});
            })().catch(async error=>{opening=null;await api.feedback(holder,error.message,720);});
            if(member.document){await api.feedback(holder,member.label||member.root,720);if(typeof root.IntersectionObserver==='function'){const observer=new root.IntersectionObserver(events=>{if(events.some(event=>event.isIntersecting)){observer.disconnect();open();}},{rootMargin:'720px'});entry.stop=()=>observer.disconnect();observer.observe(holder);}else await open();}
            else await open();
          }
          const at=[...container.children].filter(node=>node!==more&&node.tagName!=='SUMMARY')[position++];if(at!==entry.holder)container.insertBefore(entry.holder,at||more.parentNode===container&&more||null);
        }
        current=source;loader.commit(source);
        if(source.members.find(member=>member.key===source.id)?.moreChildren){container.append(more);await api.feedback(more,'Load more pages',720);}else more.remove();
      }
      async function refresh(advance){
        if(refreshing)return refreshing;
        refreshing=(async()=>{
          more.disabled=true;
          try{if(advance)loader.request(current.members.find(member=>member.key===current.id),true);await reconcile(await loader.read());recover=false;}
          catch(error){recover=true;container.append(more);await api.feedback(more,error.message+' Activate again to refresh the native frontier.',720);}
          finally{more.disabled=false;}
        })();
        try{await refreshing;}finally{refreshing=null;}
      }
      // An accepted foreground action invalidates its existing native frontier.
      // Wait for an older read before re-reading; retain unchanged page holders.
      async function refreshAfterWrite(){await refreshing;await refresh(false);}
      more.addEventListener('click',()=>refresh(!recover));
      await refresh(false);
      return refreshAfterWrite;
    }
    let ready;
    const frontierReady=new Promise(resolve=>ready=resolve);
    for(const page of manifest.pages){const holder=document.createElement('section');holder.setAttribute('aria-label',page.root);tree.append(holder);await mountDocument(holder,page,readDocument,async()=>{await (await frontierReady)();});}
    const pages=document.createElement('section');tree.append(pages);ready(await frontier(pages,manifest.frontier));
  }
  async function start(){
    const tree=document.querySelector('main[data-goo-document-tree]');
    const single=tree?null:document.querySelector('main[data-goo-document]');
    if(!tree&&!single)return;
    async function readTree(){
      const response=await fetch(location.href,{cache:'no-store'});if(!response.ok)throw Error(await response.text());
      const page=new DOMParser().parseFromString(await response.text(),'text/html');
      const host=page.querySelector(tree?'[data-goo-document-tree]':'[data-goo-document]');
      if(!host)throw Error('Document surface is unavailable. Your drafts are retained.');
      return JSON.parse(host.dataset.manifest);
    }
    if(single){await mountDocument(single,JSON.parse(single.dataset.manifest),async()=>readTree());return;}
    await mountTree(tree,JSON.parse(tree.dataset.manifest));
  }
  root.GooDocument={mount:mountDocument,mountTree};
  if(typeof document!=='undefined')start().catch(error=>root.alert?.(error.message));
})(globalThis);
