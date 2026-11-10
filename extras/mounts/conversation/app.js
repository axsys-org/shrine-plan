/* Conversation is an arrangement of Nenex projections. Goo owns controls and
   admission; native hands own execution. Refresh reads presentation state only. */
(async function () {
  'use strict';
  const host = document.getElementById('conversation');
  if (!host) return;
  const api = globalThis.GooActions, documents = globalThis.GooDocument;
  globalThis.GooInspection?.setPickerLabel?.('I');
  const notice = document.getElementById('conversation-notice');
  const composer = document.getElementById('conversation-composer');
  const turns = document.getElementById('conversation-turns'), frames = new Map();
  const history = document.getElementById('conversation-history');
  const latest = document.getElementById('conversation-latest');
  const navigation=document.getElementById('conversation-navigation');
  const panel=document.getElementById('conversation-panel'),panelNotice=document.getElementById('conversation-panel-notice');
  const wiki=document.getElementById('conversation-wiki'),work=document.getElementById('conversation-work');
  const page = host.dataset.page, vocabulary = host.dataset.vocabulary;
  const inputs = new Map(), actionScope = {};
  const navigationScope={},views={chat:'/sys/slot/conversation_chat',wiki:'/sys/slot/conversation_wiki',work:'/sys/slot/conversation_work'};
  let selected='chat',navigationKey,wikiTree,wikiLoading,emptyWork;
  let refreshing = null, composerData, composerVersion, composerWidth, closed = false, following = true, followedTop = null;
  let lastNotice='', refreshError='';
  host.dataset.mode = page ? 'chat' : 'create';
  navigation.hidden=!page;
  composer.textContent='Opening composer…';
  composer.setAttribute('aria-busy','true');
  const composerDirty = () => [...inputs.values()].some(input=>input.value!==input.getAttribute('value'));
  const report = text => {lastNotice=text;return api.feedback(notice, text, Math.min(composer.clientWidth,720));};
  const href = path => '/nenex?'+new URLSearchParams({path});
  async function read(url, path) {
    const response = await fetch(url+'?'+new URLSearchParams({path}), {cache:'no-store'});
    if (!response.ok) throw Error(await response.text());
    return response.json();
  }
  const readDocument = async path => {
    const manifest=await read('/nenex/document',path),blocks=manifest.blocks;
    // The Nenex writer appends a terminal section containing only the root
    // receipt reference. Chat already exposes that work through its trace.
    // Select by the exact native relationship, never by authored heading text;
    // keep references elsewhere and any section with additional content.
    const [section,receipt]=blocks.slice(-2);
    if(section?.kind==='sect'&&section.depth===2&&receipt?.kind==='ref'&&receipt.depth===3&&
      receipt.target===section.target+'/0'&&receipt.reference===manifest.root+'/flows/latest'&&!receipt.descriptor&&!receipt.view)
      return {...manifest,blocks:blocks.slice(0,-2)};
    return manifest;
  };
  const readWork = path => read('/conversation/work', path);
  const readInputs = path => read('/conversation/inputs', path);
  const panelReport=text=>api.feedback(panelNotice,text,Math.min(panelNotice.clientWidth||panel.clientWidth||720,720));
  async function renderNavigation(target){
    const context=api.context(navigation),slot=views[selected],width=context.width,key=slot+':'+width;
    if(!width||navigationKey===key)return;
    const data=await api.load(target,{slot,context:{...context,width:Math.min(width,720),layout:undefined}});
    if(slot!==views[selected])return;
    const content=api.mount(navigation,data,true,false);navigationKey=key;
    api.bind(content,{target,view:data.view,snapshot:data.snapshot,controls:data.controls,actionScope:navigationScope,report:panelReport,become:selectView});
  }
  function arrangeWork(){
    for(const frame of frames.values()){
      if(selected==='work'){if(frame.details.parentNode!==work)work.append(frame.details);}
      else if(frame.details.parentNode!==frame.element)frame.element.insertBefore(frame.details,frame.element.children[frame.message?1:0]||null);
    }
  }
  async function selectView(slot){
    const choice=Object.keys(views).find(key=>views[key]===slot);
    if(!choice)throw Error('This conversation view is unavailable.');
    selected=choice;host.dataset.panel=choice;panel.hidden=choice==='chat';wiki.hidden=choice!=='wiki';work.hidden=choice!=='work';
    arrangeWork();
    if(choice==='work'&&frames.size&&![...frames.values()].some(frame=>frame.details.open))[...frames.values()].at(-1).details.open=true;
    await panelReport('');await refresh();
  }
  async function renderPanel(state){
    if(selected==='wiki'){
      if(!wikiTree){
        wikiLoading ||= (async()=>{
          const [document,frontier]=await Promise.all([read('/nenex/document',state.wiki),read('/nenex/children',state.wiki)]);
          wikiTree=await documents.mountTree(wiki,{root:state.wiki,pages:[document],frontier,documentUrl:'/nenex/document',childrenUrl:'/nenex/children'},{compact:true});
        })().finally(()=>{wikiLoading=null;});
        await wikiLoading;
      }else await wikiTree.refresh();
    }
    if(selected==='work'){
      if(!frames.size&&!emptyWork){emptyWork=document.createElement('div');work.append(emptyWork);await api.feedback(emptyWork,'No work yet. Send a message to begin.',Math.min(work.clientWidth,720));}
      if(frames.size&&emptyWork){emptyWork.remove();emptyWork=null;}
    }
  }
  const dirtyWork=frame=>Boolean(frame.work?.dirty()||[...(frame.inspections?.values()||[])].some(dirtyWork));
  async function renderWork(frame){
    if(!frame.details.open||frame.loadingWork||!frame.trace.clientWidth)return;
    frame.loadingWork=true;
    try{
      const target=frame.turn?.controller||frame.target,width=frame.trace.clientWidth;
      // Only a turn has an external subtree version. Nested inspections may
      // follow a hole outside that subtree, so read their own native manifest.
      if(!frame.work||!frame.turn||frame.workVersion!==frame.turn.workVersion||frame.workWidth!==width){
        const manifest=await readWork(target),version=manifest.version||frame.turn?.workVersion;
        if(!frame.work)frame.work=await documents.mount(frame.trace,manifest,readWork,refresh,{quiet:true});
        else if(!frame.work.dirty()&&(frame.workVersion!==version||frame.workWidth!==width))await frame.work.update(manifest);
        else if(frame.work.dirty()&&frame.workWidth!==width){await frame.work.update();frame.workWidth=width;}
        if(!frame.work.dirty()){frame.workVersion=version;frame.workWidth=width;}
        if(frame.note){frame.note.textContent=manifest.note||'';frame.note.hidden=!manifest.note;frame.status.textContent=manifest.status||'';}
        if(!frame.inspections){
          frame.inspections=new Map();frame.outline=document.createElement('div');frame.outline.className='conversation-inspections';
          frame.heading=document.createElement('h3');frame.outline.append(frame.heading);frame.details.insertBefore(frame.outline,frame.trace);
        }
        frame.heading.textContent=manifest.itemsLabel||'Retained work';
        const items=[...(manifest.items||[]),...(manifest.previous||[]).map(item=>({...item,label:'Earlier: '+item.label}))];
        const wanted=new Set(items.map(item=>item.path));
        for(const [path,child] of frame.inspections)if(!wanted.has(path)){
          if(dirtyWork(child))throw Error('An inspected work record changed. Your draft is retained.');
          child.details.remove();frame.inspections.delete(path);
        }
        let position=1;
        for(const item of items){
          let child=frame.inspections.get(item.path);
          if(!child){
            const details=document.createElement('details');details.className='conversation-inspection';
            const summary=document.createElement('summary'),label=document.createElement('span'),status=document.createElement('span');
            status.className='conversation-inspection-status';summary.append(label,status);
            const note=document.createElement('p');note.className='conversation-work-reason';
            const trace=document.createElement('section');details.append(summary,note,trace);
            child={target:item.path,details,label,status,note,trace};frame.inspections.set(item.path,child);
            details.addEventListener('toggle',()=>renderWork(child));
          }
          child.label.textContent=(item.current?'Current · ':'')+item.label;
          child.status.textContent=item.status||'';child.details.dataset.current=String(Boolean(item.current));
          const at=frame.outline.children[position++];
          if(at!==child.details)frame.outline.insertBefore(child.details,at||null);
        }
        frame.outline.hidden=!items.length;
      }
      for(const child of frame.inspections?.values()||[])await renderWork(child);
    }catch(error){await (selected==='work'?panelReport:report)(error.message);}
    finally{frame.loadingWork=false;}
  }
  function link(label, path) {
    const a = document.createElement('a'); a.textContent = label; a.href = href(path); return a;
  }
  function follow() {
    if(!history.clientWidth)return;
    // Reading or editing an earlier document must never be interrupted by a
    // response or by a later refresh of the same turn.
    if (following && !turns.contains(document.activeElement)) {
      history.scrollTop = history.scrollHeight;
      followedTop = history.scrollTop;
    }
    latest.hidden = !frames.size || history.scrollHeight-history.clientHeight-history.scrollTop < 48;
  }
  history.addEventListener('scroll', () => {
    // A native document can grow between our scroll and its browser event.
    // That event isn't a person choosing to leave the bottom.
    if (followedTop!==null && Math.abs(history.scrollTop-followedTop)<1) {followedTop=null;follow();return;}
    followedTop=null;
    following = history.scrollHeight-history.clientHeight-history.scrollTop < 48;
    latest.hidden = following || !frames.size;
  }, {passive:true});
  latest.addEventListener('click', () => { following=true; history.focus({preventScroll:true}); follow(); });
  async function renderComposer(target, create, preserve = true) {
    const width=composer.clientWidth;
    const data = await api.load(target, {view:vocabulary+(create?'/create':'/composer'),
      context:{...api.context(composer),width:Math.min(width,720),layout:undefined}});
    if (composerData && preserve && composerDirty() && composerData.snapshot.life!==data.snapshot.life) throw Error('The conversation was replaced. Your draft is retained.');
    const content = api.mount(composer, data, preserve, false); composerData = data; composerWidth=width;
    composer.setAttribute('aria-busy','false');
    if (lastNotice) await report(lastNotice);
    inputs.clear();
    api.bind(content, {target, view:data.view, snapshot:data.snapshot, controls:data.controls, actionScope, report,
      input:(key, input) => {
        inputs.set(key, input);
        if (!create && input.dataset.inputSlot==='/source') {
          const area=input.gooEditor?.area || input;
          area.setAttribute('aria-label','Message');
          area.setAttribute('data-placeholder','Ask anything');
        }
      },
      saved:async (_result, saved) => {
        if (create) {
          if (!saved.size) { await report('Published conversation operations selected. Republish a flow to capture them.'); return; }
          const nameKey = [...inputs].find(([,input])=>input.dataset.inputSlot==='/name')?.[0];
          const name = saved.get(nameKey);
          if (!name) throw Error('Created conversation; open its page from Nenex.');
          for (const [key,value] of saved) {
            const input=inputs.get(key);
            if (input?.value===value) input.setAttribute('value',value);
          }
          location.assign('/conversation?'+new URLSearchParams({path:target.split('/').slice(0,2).join('/')+'/app/nenex/w/'+name}));
          return;
        }
        // Clear only the admitted draft. A newer edit made while admission was
        // in flight belongs to the person and stays in the existing Goo input.
        const unchanged = [...saved].every(([key,value])=>inputs.get(key)?.value===value);
        await renderComposer(target, false, !unchanged);
        following=true;
        await refresh();
        // Return focus only when the admitted draft was cleared. A newer edit
        // or a person already working elsewhere keeps its current focus.
        if (unchanged && (composer.contains(document.activeElement) || document.activeElement===document.body)) {
          const input=[...inputs.values()].find(input=>input.dataset.inputSlot==='/source');
          (input?.gooEditor?.area || input)?.focus({preventScroll:true});
        }
      }
    });
  }
  // Keyboard submission activates the very same declared Goo control. Its
  // receipt, in-flight guard and retry behavior remain owned by GooActions.
  composer.addEventListener('keydown', event => {
    if (!page || !composerData || event.defaultPrevented || event.key!=='Enter' || event.shiftKey || event.ctrlKey || event.metaKey || event.altKey || event.isComposing || event.keyCode===229) return;
    const input=[...inputs.values()].find(input=>input.dataset.inputSlot==='/source');
    if (!input?.contains(event.target) && input!==event.target) return;
    if (input.gooComposing || input.gooEditor?.pending) return;
    event.preventDefault();
    const text=input.gooEditor ? globalThis.GooRichInput.text(input.gooEditor.runs) : input.value;
    if (!text.trim()) return;
    const action=composerData.controls.find(control=>control.kind==='action');
    const button=[...composer.querySelectorAll('[data-node]')].find(node=>node.dataset.node===action?.id);
    if (button && !button.disabled) button.click();
  });
  async function projection(frame, kind, path, version) {
    const prior = frame[kind];
    const width=history.clientWidth;
    if(!width)return;
    if (prior && ((prior.version===version && prior.width===width) || prior.view.dirty())) return;
    const manifest = await readDocument(path);
    if (prior) { await prior.view.update(manifest); prior.version=version; prior.width=width; return; }
    const wrapper=document.createElement('div');wrapper.className='conversation-'+kind;
    wrapper.setAttribute('aria-label',kind==='reply'?'Assistant response':kind==='clarification'?'Your clarification':'Your message');
    const holder = document.createElement('section');wrapper.append(holder);
    if(kind==='message'&&frame.details?.parentNode===frame.element)frame.element.insertBefore(wrapper,frame.details);else frame.element.append(wrapper);
    const view = await documents.mount(holder, manifest, readDocument, refresh,{compact:true,chrome:false});
    frame[kind] = {view, version, width,wrapper};
  }
  async function update() {
    if (!page) {await renderComposer(host.dataset.create,true);return;}
    const state = await read('/conversation/manifest', page);
    await renderNavigation(state.composer);
    // The input is usable while earlier documents prepare their native views.
    if (composer.clientWidth && (!composerData || composerVersion!==state.composerVersion || composerWidth!==composer.clientWidth)) {
      await renderComposer(state.composer,false);composerVersion=state.composerVersion;
    }
    for (const turn of state.turns.sort((a,b)=>a.sequence-b.sequence)) {
      let frame=frames.get(turn.id);
      if (!frame) {
        const element=document.createElement('article');element.className='conversation-turn';
        const details=document.createElement('details');details.className='conversation-work';
        const summary=document.createElement('summary'),label=document.createElement('span'),status=document.createElement('span');
        label.textContent='Work and trace';status.className='conversation-work-status';summary.append(label,status);
        const reason=document.createElement('p');reason.className='conversation-work-reason';
        const trace=document.createElement('section');details.append(summary,reason,trace);element.append(details);turns.append(element);
        frame={element,details,summary,status,reason,trace};frames.set(turn.id,frame);
        label.textContent='Turn '+(turn.sequence+1)+' - Work and trace';
        details.addEventListener('toggle',()=>renderWork(frame));
      }
      frame.turn=turn;
      // The native manifest projects current requests/workers. Rendering has
      // no lifecycle of its own; retained publication remains independent.
      frame.status.textContent=(turn.published?'Published · ':'')+(turn.statusLabel||turn.status||'Pending');
      frame.details.dataset.status=turn.status;
      frame.reason.textContent=turn.reason||'';frame.reason.hidden=!turn.reason;
      await projection(frame, 'message', turn.message, turn.messageVersion);
      // These are ordinary Nenex answers and declared Goo controls. Their
      // admission, stale-target checks, drafts and receipts stay with Goo.
      if (history.clientWidth && (turn.clarifications?.length || turn.input?.blocks.length || frame.continuation)) {
        if (!frame.continuation) {
          frame.continuation=document.createElement('section');frame.continuation.className='conversation-continuation';
          frame.answers=document.createElement('div');frame.answerForm=document.createElement('section');
          frame.inputReason=document.createElement('p');frame.inputReason.className='conversation-work-reason';
          frame.answerForm.className='conversation-answer';frame.continuation.append(frame.answers,frame.inputReason,frame.answerForm);
          if(frame.reply)frame.element.insertBefore(frame.continuation,frame.element.children[frame.element.children.length-1]);
          else frame.element.append(frame.continuation);
          frame.clarifications=new Map();
        }
        for (const answer of [...(turn.clarifications||[])].sort((a,b)=>a.sequence-b.sequence)) {
          let entry=frame.clarifications.get(answer.message);
          if(!entry){entry={element:frame.answers};frame.clarifications.set(answer.message,entry);}
          await projection(entry,'clarification',answer.message,answer.version);
        }
        if (!frame.input && turn.input?.blocks.length) {
          frame.inputReason.textContent=turn.reason||'';
          frame.input=await documents.mount(frame.answerForm,turn.input,readInputs,refresh);
          frame.inputVersion=turn.workVersion;frame.inputWidth=history.clientWidth;
        } else if (frame.input && (frame.inputVersion!==turn.workVersion || frame.inputWidth!==history.clientWidth) && !frame.input.dirty()) {
          frame.inputReason.textContent=turn.input?.blocks.length?(turn.reason||''):'';
          await frame.input.update(turn.input);frame.inputVersion=turn.workVersion;frame.inputWidth=history.clientWidth;
        }
      }
      if (turn.published) await projection(frame, 'reply', turn.reply, turn.replyVersion);
      if (!frame.links) {frame.links=document.createElement('div');frame.links.className='conversation-links';const record=link('Browse all retained work',turn.controller);record.href='/views'+turn.controller+'/work';frame.replyLink=link('Open response document',turn.reply);frame.links.append(frame.replyLink,record);frame.details.append(frame.links);}
      frame.replyLink.hidden=!turn.published;
    }
    arrangeWork();
    for(const frame of frames.values())await renderWork(frame);
    try{await renderPanel(state);}catch(error){await panelReport(error.message);}
    follow();
  }
  function refresh() {
    if (refreshing) return refreshing;
    let failed=false;
    refreshing=update().then(()=>{
      // A recovered presentation read must not leave its old warning beside a
      // working composer. Action/admission errors retain their own notice.
      if(refreshError&&lastNotice===refreshError)report('');
      refreshError='';
    }).catch(error=>{
      failed=true;
      if (!composerData) {composer.textContent='The composer could not load. Reload to try again.';composer.setAttribute('aria-busy','false');}
      refreshError=error.message;return report(refreshError);
    }).finally(()=>{
      refreshing=null;
      // A resize during a native render leaves another width to prepare.
      if (!failed && !closed && composer.clientWidth && composerWidth!==composer.clientWidth) return refresh();
    });
    return refreshing;
  }
  try {
    await refresh();
    // Reflow native presentations when their allocated width changes. Height
    // changes only adjust following; they never rerender a working draft.
    let width=[composer.clientWidth,panel.clientWidth,navigation.clientWidth].join(':');
    const resize=new ResizeObserver(() => {
      follow();
      const next=[composer.clientWidth,panel.clientWidth,navigation.clientWidth].join(':');
      if (width===next || closed) return;
      width=next;
      refresh();
    });
    resize.observe(composer);resize.observe(turns);resize.observe(history);resize.observe(panel);resize.observe(navigation);
    // Only an open, visible presentation reads for changes. Closing this tab
    // stops these reads; native work continues independently in the world.
    async function observe() {
      if(closed)return;
      if(!document.hidden)await refresh();
      if(!closed)setTimeout(observe,1500);
    }
    addEventListener('pagehide',()=>{closed=true;resize.disconnect();},{once:true});
    addEventListener('beforeunload',event=>{if(composerDirty()){event.preventDefault();event.returnValue='';}});
    if (page) setTimeout(observe,1500);
  } catch(error) {report(error.message);}
})();
