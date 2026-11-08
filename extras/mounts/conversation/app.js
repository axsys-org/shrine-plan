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
  const page = host.dataset.page, vocabulary = host.dataset.vocabulary;
  const inputs = new Map(), actionScope = {};
  let refreshing = null, composerData, composerVersion, composerWidth, closed = false, following = true, followedTop = null;
  let lastNotice='', refreshError='';
  host.dataset.mode = page ? 'chat' : 'create';
  composer.textContent='Opening composer…';
  composer.setAttribute('aria-busy','true');
  const composerDirty = () => [...inputs.values()].some(input=>input.value!==input.getAttribute('value'));
  const report = text => {lastNotice=text;return api.feedback(notice, text, 720);};
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
  function link(label, path) {
    const a = document.createElement('a'); a.textContent = label; a.href = href(path); return a;
  }
  function follow() {
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
    if (prior && ((prior.version===version && prior.width===width) || prior.view.dirty())) return;
    const manifest = await readDocument(path);
    if (prior) { await prior.view.update(manifest); prior.version=version; prior.width=width; return; }
    const wrapper=document.createElement('div');wrapper.className='conversation-'+kind;
    const holder = document.createElement('section');wrapper.append(holder);
    if(kind==='message'&&frame.details)frame.element.insertBefore(wrapper,frame.details);else frame.element.append(wrapper);
    const view = await documents.mount(holder, manifest, readDocument, refresh,{compact:true,chrome:false});
    frame[kind] = {view, version, width};
  }
  async function update() {
    if (!page) {await renderComposer(host.dataset.create,true);return;}
    const state = await read('/conversation/manifest', page);
    // The input is usable while earlier documents prepare their native views.
    if (!composerData || composerVersion!==state.composerVersion || composerWidth!==composer.clientWidth) {
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
        details.addEventListener('toggle',async()=>{if(!details.open||frame.work||frame.loadingWork)return;
          frame.loadingWork=true;
          try {
            const manifest=await readWork(turn.controller);
            frame.work=await documents.mount(trace,manifest,readWork,refresh);
          } catch(error) { report(error.message); } finally {frame.loadingWork=false;}
        });
      }
      // The native manifest projects current requests/workers. Rendering has
      // no lifecycle of its own; retained publication remains independent.
      frame.status.textContent=(turn.published?'Published · ':'')+(turn.statusLabel||turn.status||'Pending');
      frame.details.dataset.status=turn.status;
      frame.reason.textContent=turn.reason||'';frame.reason.hidden=!turn.reason;
      await projection(frame, 'message', turn.message, turn.messageVersion);
      // These are ordinary Nenex answers and declared Goo controls. Their
      // admission, stale-target checks, drafts and receipts stay with Goo.
      if (turn.clarifications?.length || turn.input?.blocks.length || frame.continuation) {
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
          frame.inputVersion=turn.workVersion;
        } else if (frame.input && frame.inputVersion!==turn.workVersion && !frame.input.dirty()) {
          frame.inputReason.textContent=turn.input?.blocks.length?(turn.reason||''):'';
          await frame.input.update(turn.input);frame.inputVersion=turn.workVersion;
        }
      }
      if (turn.published) await projection(frame, 'reply', turn.reply, turn.replyVersion);
      if (!frame.links) {frame.links=document.createElement('div');frame.links.className='conversation-links';const work=link('Work and trace',turn.controller);work.href='/ns'+turn.controller;frame.replyLink=link('Open response document',turn.reply);frame.links.append(frame.replyLink,work);frame.details.append(frame.links);}
      frame.replyLink.hidden=!turn.published;
      if (frame.work && frame.details.open && frame.workVersion!==turn.workVersion && !frame.work.dirty()) {
        const manifest=await readWork(turn.controller);
        await frame.work.update(manifest);frame.workVersion=turn.workVersion;
      }
    }
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
      if (!failed && !closed && composerWidth!==composer.clientWidth) return refresh();
    });
    return refreshing;
  }
  try {
    await refresh();
    // Reflow native presentations when their allocated width changes. Height
    // changes only adjust following; they never rerender a working draft.
    let width=composer.clientWidth;
    const resize=new ResizeObserver(() => {
      follow();
      if (width===composer.clientWidth || closed) return;
      width=composer.clientWidth;
      refresh();
    });
    resize.observe(composer);resize.observe(turns);resize.observe(history);
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
