/* Continuous native Goo surfaces. The server owns topology, block kinds and writes.
   This host holds only prepared controls, their input drafts and platform focus. */
(function(root){
  'use strict';
  async function mountDocument(main,initial,reload,onSaved=async()=>{},{compact=false,chrome=true,inspectionLabel='Document',quiet=false}={}){
    const api=root.GooActions, frames=new Map();let manifest=initial, busy=false, failed=false, pendingChange=null;
    const notice=document.createElement('div');notice.className='goo-document-notice';notice.setAttribute('role','status');main.before(notice);
    let noticeMessage='',noticeWidth;
    const feedbackWidth=()=>Math.min(notice.clientWidth||main.clientWidth||main.parentElement?.clientWidth||720,720);
    const report=message=>{
      notice.hidden=(compact||quiet)&&message==='Ready';
      // A fulfilled action can leave an empty, hidden document host. Its
      // sibling notice still owns a visible allocation; never prepare it at 0.
      noticeMessage=message;noticeWidth=feedbackWidth();
      return api.feedback(notice,notice.hidden?'':message,noticeWidth);
    };
    // Embedded documents keep the same frames, bindings and edit guards. Only
    // their page presentations and tools move into a lazy disclosure.
    let body=main,inspector,inspection;
    if(compact){
      body=document.createElement('div');body.className='goo-document-body';main.append(body);
    }
    if(compact&&chrome){
      inspector=document.createElement('details');inspector.className='goo-document-inspector';
      const summary=document.createElement('summary');summary.textContent=inspectionLabel;inspector.append(summary);
      inspection=document.createElement('div');inspector.append(inspection);main.append(inspector);
      inspector.addEventListener('toggle',async()=>{if(!inspector.open)return;
        try{for(const frame of frames.values())if(frame.holder.parentNode===inspection&&(!frame.block.label||frame.holder.open))await render(frame,Boolean(frame.data));}
        catch(error){report(error.message);}
      });
    }
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
      const data=await api.load(frame.block.target,{...selector,context:{...api.context(frame.element),width:Math.min(frame.element.clientWidth,720),layout:undefined}});
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
      else{const link=document.createElement('a');link.href='/ns'+frame.block.target;await api.feedback(link,'Inspect this native record and its history',feedbackWidth());frame.element.append(link);}
      // Block chrome is itself a prepared Grove row. Platform focus reveals it.
      const chrome=frame.element.querySelector('[data-slot="/sys/slot/block_actions"]');
      if(chrome&&editable(frame)){
        // The prepared row's gap belongs to its controls. A compact projection
        // hides that row as a unit instead of leaving an empty spacer behind.
        const chromeHost=compact&&chrome.parentElement?.classList.contains('goo-row')&&chrome.parentElement.childElementCount===1?chrome.parentElement:chrome;
        const anchor=document.createComment('native block controls');chromeHost.before(anchor);
        frame.chromeBinding?.abort();frame.chromeBinding=new AbortController();
        frame.element.addEventListener('focusin',()=>{if(!chromeHost.isConnected)anchor.after(chromeHost);},{signal:frame.chromeBinding.signal});
        frame.element.addEventListener('focusout',event=>{if(!frame.element.contains(event.relatedTarget))chromeHost.remove();},{signal:frame.chromeBinding.signal});
        for(const control of data.controls||[])if(control.kind==='action'){
          const button=[...chrome.querySelectorAll('[data-node]')].find(node=>node.dataset.node===control.id);
          if(button && ['split','merge','paragraph','heading','bullet','quote','code'].includes(control.editCommand))button.remove();
        }
        if(!frame.element.contains(document.activeElement))chromeHost.remove();
      }
    }
    async function reconcile(next,structural=false,ownCommit=null){
      if(structural && [...frames.values()].some(dirty))throw Error('Unsaved edits must be saved before changing block structure.');
      const parts=chrome?[...next.blocks,...(next.tools||[])]:next.blocks.filter(block=>block.kind!=='presentation');
      const nextByKey=new Map(parts.map(block=>[block.key||block.target,block]));
      for(const [key,frame]of frames){const block=nextByKey.get(key);if(dirty(frame)&&(!block||frame.block.target!==block.target||frame.block.view!==block.view))throw Error('A removed or replaced block has an unsaved draft.');}
      manifest=next;
      const seen=new Set(),positions=new Map();
      const tools=new Set(manifest.tools||[]);
      for(const block of parts){
        const key=block.key||block.target;seen.add(key);let frame=frames.get(key);
        if(frame && (structural || frame.block.view!==block.view || frame.block.target!==block.target)){frame.holder.remove();frames.delete(key);frame=null;}
        if(!frame){const element=document.createElement('section');element.setAttribute('aria-label',`${block.kind} ${block.target}`);let holder=element,summary;
          if(block.label){holder=document.createElement('details');summary=document.createElement('summary');holder.append(summary);holder.append(element);}
          body.append(holder);frame={block,element,holder,summary};frames.set(key,frame);
          if(block.label)holder.addEventListener('toggle',()=>{if(holder.open)render(frame,Boolean(frame.data)).catch(error=>report(error.message));});
        }
        frame.block=block;
        const parent=compact&&(tools.has(block)||block.kind==='presentation')?inspection:body;
        const position=positions.get(parent)||0,at=parent.children[position];positions.set(parent,position+1);
        if(at!==frame.holder)parent.insertBefore(frame.holder,at||null);
        if(block.label){const summary=frame.summary,width=Math.min(summary.clientWidth||main.clientWidth||feedbackWidth(),720);
          if(frame.labelWidth!==width){await api.feedback(summary,block.label,width);frame.labelWidth=width;}}
        if(parent===inspection&&!inspector.open)continue;
        if((block.view||block.readonly)&&(!block.label||frame.holder.open)){
          try{await render(frame,Boolean(frame.data),frame===ownCommit);}
          catch(error){if(frame.data)throw error;frame.error=error.message;await api.feedback(frame.element,`Block ${block.target}: ${error.message}`,720);}
        }
        else if(!block.view&&!block.readonly&&block.reference){const link=document.createElement('a');link.href='/ns'+block.reference;await api.feedback(link,(block.descriptor?'Presentation unavailable; source descriptor retained. ':'')+block.reference,Math.min(frame.element.clientWidth,720));frame.element.replaceChildren(link);}

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
    return {async update(next=manifest,...args){await reconcile(next,...args);if(noticeWidth!==feedbackWidth())await report(noticeMessage);},
      dirty:()=>busy||Boolean(pendingChange)||[...frames.values()].some(dirty)};
  }
  async function mountTree(tree,manifest,{compact=false}={}){
    if(!Array.isArray(manifest.pages)||!manifest.frontier)throw Error('Expected native page manifests and a frontier.');
    const api=root.GooActions,feedbackWidth=()=>Math.min(tree.clientWidth||720,720);
    const pageOptions={compact,inspectionLabel:'Inspect page'};
    async function read(url,params){
      const response=await fetch(url+'?'+new URLSearchParams(params),{cache:'no-store'});
      if(!response.ok)throw Error(await response.text());return response.json();
    }
    const readDocument=path=>read(manifest.documentUrl,{path});
    // Hosts may hide a tree without unmounting it. Refresh only on their demand;
    // retain the same document controls, open frontiers and unsaved drafts.
    async function refreshPage(entry,version){
      if(!entry.document || !entry.holder.clientWidth || (compact&&entry.holder.tagName==='DETAILS'&&!entry.holder.open))return;
      const width=entry.holder.clientWidth;
      if(entry.document.dirty()){
        // Re-layout the retained manifest, never replace it with a new source
        // snapshot just because the host resized. Native edit guards still apply.
        if(width!==entry.width){await entry.document.update();entry.width=width;}
        return;
      }
      if(version===entry.version && width===entry.width)return;
      await entry.document.update(await readDocument(entry.root));entry.version=version;entry.width=width;
    }
    async function frontier(container,initial,onSaved=async()=>{}){
      let cached=initial,current,refreshing=null,recover=false;
      const entries=new Map();
      const more=document.createElement('button');more.type='button';
      const heading=compact?document.createElement('h3'):null;
      if(heading){heading.textContent='Pages';container.className='goo-document-children';container.append(heading);}
      const loader=new root.GooTopoi.TreeSource(initial.root,'y',async(params)=>{
        const page=!params.after&&cached?(cached):await read(manifest.childrenUrl,{path:initial.root,...(params.after?{after:params.after,epoch:params.epoch}:{})});cached=null;
        const members=page.members.map(member=>({...member,key:member.root,parent:page.root,status:member.document?'available':'unavailable'}));
        if(!params.after)members.unshift({key:page.root,parent:null,life:page.life,version:page.version,hasChildren:page.hasChildren,status:'available'});
        return {id:page.root,axis:'y',topology:'tree',incremental:true,life:page.life,epoch:page.epoch,parent:page.root,members,next:page.next};
      });
      async function reconcile(source){
        const members=source.members.filter(member=>member.key!==source.id),seen=new Set(members.map(member=>member.key));
        for(const [key,entry]of entries){const next=members.find(member=>member.key===key);if((entry.document?.dirty()||entry.frontier?.dirty())&&(!next||entry.life!==next.life))throw Error('A removed or replaced page has an unsaved draft. Its original page and inputs are retained.');}
        for(const [key,entry]of entries)if(!seen.has(key)){entry.stop?.();entry.holder.remove();entries.delete(key);}
        let position=0;
        for(const member of members){
          let entry=entries.get(member.key);
          if(entry&&entry.life!==member.life){entry.stop?.();entry.holder.remove();entries.delete(member.key);entry=null;}
          if(!entry){
            const holder=document.createElement(compact?'details':'section');holder.setAttribute('aria-label',member.root);container.insertBefore(holder,more.parentNode===container?more:null);
            entry={holder,root:member.root,life:member.life,version:member.version};entries.set(member.key,entry);
            const content=compact?document.createElement('div'):holder;
            if(compact){
              holder.className='goo-document-page';content.className='goo-document-page-content';
              entry.title=document.createElement('summary');holder.append(entry.title);holder.append(content);
            }
            let opening;
            const report=async error=>{
              if(!compact){await api.feedback(holder,error.message,feedbackWidth());return;}
              entry.error ||= document.createElement('div');holder.append(entry.error);await api.feedback(entry.error,error.message,feedbackWidth());
            };
            const open=()=>opening||=(async()=>{
              if(member.document&&!entry.document){content.replaceChildren();const page=await readDocument(member.root);entry.document=await mountDocument(content,page,readDocument,async()=>{await refreshAfterWrite();await onSaved();},pageOptions);entry.width=holder.clientWidth;}
              const branch=entry.children ||= document.createElement(compact?'section':'details');
              if(compact){
                holder.append(branch);entry.branch=holder;
                const page=await read(manifest.childrenUrl,{path:member.root});
                entry.frontier=await frontier(branch,page,async()=>{await refreshAfterWrite();await onSaved();});
                entry.error?.remove();entry.error=null;
                return;
              }
              const summary=document.createElement('summary');branch.append(summary);holder.append(branch);await api.feedback(summary,member.document?'Child pages':member.label||member.root,feedbackWidth());
              entry.branch=branch;entry.summary=summary;entry.label=member.document?'Child pages':member.label||member.root;entry.labelWidth=feedbackWidth();
              let expanded=false,pending=false;
              branch.addEventListener('toggle',async()=>{if(!branch.open||pending)return;pending=true;try{if(expanded)await entry.frontier.refresh();else{const page=await read(manifest.childrenUrl,{path:member.root});entry.frontier=await frontier(branch,page,async()=>{await refreshAfterWrite();await onSaved();});expanded=true;}}catch(error){await api.feedback(summary,error.message,feedbackWidth());}finally{pending=false;}});
            })().catch(async error=>{opening=null;await report(error);});
            if(compact)holder.addEventListener('toggle',async()=>{
              if(!holder.open)return;
              try{if(entry.frontier){await refreshPage(entry,entry.currentVersion);await entry.frontier.refresh();}else await open();}
              catch(error){await report(error);}
            });
            else if(member.document){await api.feedback(holder,member.label||member.root,feedbackWidth());if(typeof root.IntersectionObserver==='function'){const observer=new root.IntersectionObserver(events=>{if(events.some(event=>event.isIntersecting)){observer.disconnect();open();}},{rootMargin:'720px'});entry.stop=()=>observer.disconnect();observer.observe(holder);}else await open();}
            else await open();
          }
          entry.currentVersion=member.version;
          const title=member.label||member.root.split('/').filter(Boolean).at(-1);
          const titleWidth=Math.max(1,Math.min(entry.holder.clientWidth||feedbackWidth(),720)-48);
          if(entry.title&&(entry.titleText!==title||entry.titleWidth!==titleWidth)){await api.feedback(entry.title,title,titleWidth);entry.titleText=title;entry.titleWidth=titleWidth;}
          const at=[...container.children].filter(node=>node!==more&&node!==heading&&node.tagName!=='SUMMARY')[position++];if(at!==entry.holder)container.insertBefore(entry.holder,at||more.parentNode===container&&more||null);
          if(entry.summary&&entry.labelWidth!==feedbackWidth()){await api.feedback(entry.summary,entry.label,feedbackWidth());entry.labelWidth=feedbackWidth();}
        }
        current=source;loader.commit(source);
        container.hidden=compact&&!members.length&&!source.members.find(member=>member.key===source.id)?.moreChildren;
        if(source.members.find(member=>member.key===source.id)?.moreChildren){container.append(more);await api.feedback(more,'Load more pages',feedbackWidth());}else more.remove();
      }
      async function refresh(advance){
        if(refreshing)return refreshing;
        refreshing=(async()=>{
          more.disabled=true;
          try{if(advance)loader.request(current.members.find(member=>member.key===current.id),true);await reconcile(await loader.read());for(const [key,entry] of entries){await refreshPage(entry,current.members.find(member=>member.key===key)?.version);if(entry.branch?.open)await entry.frontier?.refresh();}recover=false;}
          catch(error){recover=true;container.hidden=false;container.append(more);await api.feedback(more,error.message+' Activate again to refresh the native frontier.',feedbackWidth());}
          finally{more.disabled=false;}
        })();
        try{await refreshing;}finally{refreshing=null;}
      }
      // An accepted foreground action invalidates its existing native frontier.
      // Wait for an older read before re-reading; retain unchanged page holders.
      async function refreshAfterWrite(){await refreshing;await refresh(false);}
      more.addEventListener('click',()=>refresh(!recover));
      await refresh(false);
      return {refresh:refreshAfterWrite,get version(){return current.members.find(member=>member.key===current.id)?.version;},dirty:()=>[...entries.values()].some(entry=>entry.document?.dirty()||entry.frontier?.dirty())};
    }
    let ready;
    const frontierReady=new Promise(resolve=>ready=resolve);
    const roots=[];
    for(const page of manifest.pages){const holder=document.createElement('section');holder.setAttribute('aria-label',page.root);tree.append(holder);const projection=await mountDocument(holder,page,readDocument,async()=>{await (await frontierReady).refresh();},pageOptions);roots.push({holder,root:page.root,document:projection,version:manifest.frontier.version,width:holder.clientWidth});}
    const pages=document.createElement('section');tree.append(pages);const children=await frontier(pages,manifest.frontier);ready(children);
    return {async refresh(){await children.refresh();for(const entry of roots)await refreshPage(entry,children.version);},dirty:()=>roots.some(entry=>entry.document.dirty())||children.dirty()};
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
