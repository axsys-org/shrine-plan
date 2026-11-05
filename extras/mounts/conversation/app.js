/* Conversation is an arrangement of Nenex projections. Goo owns controls and
   admission; native hands own execution. Refresh reads presentation state only. */
(async function () {
  'use strict';
  const host = document.getElementById('conversation');
  if (!host) return;
  const api = globalThis.GooActions, documents = globalThis.GooDocument;
  const notice = document.getElementById('conversation-notice');
  const composer = document.getElementById('conversation-composer');
  const turns = document.getElementById('conversation-turns'), frames = new Map();
  const page = host.dataset.page, vocabulary = host.dataset.vocabulary;
  const inputs = new Map(), actionScope = {};
  let refreshing = null, composerData, composerVersion, closed = false;
  const composerDirty = () => [...inputs.values()].some(input=>input.value!==input.getAttribute('value'));
  const report = text => api.feedback(notice, text, 720);
  const href = path => '/nenex?'+new URLSearchParams({path});
  async function read(url, path) {
    const response = await fetch(url+'?'+new URLSearchParams({path}), {cache:'no-store'});
    if (!response.ok) throw Error(await response.text());
    return response.json();
  }
  const readDocument = path => read('/nenex/document', path);
  const readWork = path => read('/conversation/work', path);
  function link(label, path) {
    const a = document.createElement('a'); a.textContent = label; a.href = href(path); return a;
  }
  async function renderComposer(target, create, preserve = true) {
    const data = await api.load(target, {view:vocabulary+(create?'/create':'/composer'), context:api.context(composer)});
    if (composerData && preserve && composerDirty() && composerData.snapshot.life!==data.snapshot.life) throw Error('The conversation was replaced. Your draft is retained.');
    const content = api.mount(composer, data, preserve, false); composerData = data;
    inputs.clear();
    api.bind(content, {target, view:data.view, snapshot:data.snapshot, controls:data.controls, actionScope, report,
      input:(key, input) => inputs.set(key, input),
      saved:async (_result, saved) => {
        if (create) {
          if (!saved.size) { await report('Published conversation operations selected. Republish a flow to capture them.'); return; }
          const nameKey = [...inputs].find(([,input])=>input.dataset.inputSlot==='/name')?.[0];
          const name = saved.get(nameKey);
          if (!name) throw Error('Created conversation; open its page from Nenex.');
          location.assign('/conversation?'+new URLSearchParams({path:target.split('/').slice(0,2).join('/')+'/app/nenex/w/'+name}));
          return;
        }
        // Clear only the admitted draft. A newer edit made while admission was
        // in flight belongs to the person and stays in the existing Goo input.
        const unchanged = [...saved].every(([key,value])=>inputs.get(key)?.value===value);
        await renderComposer(target, false, !unchanged);
        await refresh();
      }
    });
  }
  async function projection(frame, kind, path, version) {
    const prior = frame[kind];
    if (prior && (prior.version===version || prior.view.dirty())) return;
    const manifest = await readDocument(path);
    if (prior) { await prior.view.update(manifest); prior.version=version; return; }
    const holder = document.createElement('section');holder.className='conversation-'+kind;
    frame.element.insertBefore(holder, frame.details);
    const view = await documents.mount(holder, manifest, readDocument, refresh);
    frame[kind] = {view, version};
  }
  async function update() {
    const state = await read('/conversation/manifest', page);
    document.getElementById('conversation-wiki').href = href(state.wiki);
    for (const turn of state.turns.sort((a,b)=>a.sequence-b.sequence)) {
      let frame=frames.get(turn.id);
      if (!frame) {
        const element=document.createElement('article');element.className='conversation-turn';
        const details=document.createElement('details'), summary=document.createElement('summary');
        const trace=document.createElement('section');details.append(summary, trace);element.append(details);turns.append(element);
        frame={element,details,summary,trace};frames.set(turn.id,frame);
        details.addEventListener('toggle',async()=>{if(!details.open||frame.work)return;
          try {
            const manifest=await readWork(turn.controller);
            frame.work=await documents.mount(trace,manifest,readWork,refresh);
          } catch(error) { report(error.message); }
        });
      }
      frame.summary.textContent = (turn.published?'Published response · ':'')+turn.status+' — '+turn.reason;
      await projection(frame, 'message', turn.message, turn.messageVersion);
      if (turn.published) await projection(frame, 'reply', turn.reply, turn.replyVersion);
      if (!frame.links) {frame.links=document.createElement('div');frame.links.className='conversation-links';const work=link('Work and trace',turn.controller);work.href='/ns'+turn.controller;frame.links.append(link('Reply document',turn.reply),work);frame.details.append(frame.links);}
      if (frame.work && frame.workVersion!==turn.workVersion && !frame.work.dirty()) {
        const manifest=await readWork(turn.controller);
        await frame.work.update(manifest);frame.workVersion=turn.workVersion;
      }
    }
    if (!composerData || composerVersion!==state.composerVersion) {
      await renderComposer(state.composer,false);composerVersion=state.composerVersion;
    }
  }
  function refresh() {
    if (refreshing) return refreshing;
    refreshing=update().catch(error=>report(error.message)).finally(()=>{refreshing=null;});
    return refreshing;
  }
  try {
    if (!page) {document.getElementById('conversation-wiki').hidden=true;await renderComposer(host.dataset.create,true);return;}
    await refresh();
    // Only an open, visible presentation reads for changes. Closing this tab
    // stops these reads; native work continues independently in the world.
    async function observe() {
      if(closed)return;
      if(!document.hidden)await refresh();
      if(!closed)setTimeout(observe,1500);
    }
    addEventListener('pagehide',()=>{closed=true;},{once:true});
    addEventListener('beforeunload',event=>{if(composerDirty()){event.preventDefault();event.returnValue='';}});
    setTimeout(observe,1500);
  } catch(error) {report(error.message);}
})();
