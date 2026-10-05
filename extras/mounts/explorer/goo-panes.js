/* Retained Goo descriptions -> the explorer's page-local semantic session.
 * Subject templates are always rendered by the existing Foil/Goo backend. */
(function (root) {
  'use strict';
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; };
  const id = (owner, kind, key) => owner + '|' + JSON.stringify([kind, key, []]);
  const interactive = event => !!event.target.closest('button,input,textarea,select,a,[contenteditable=true]');
  class GooPanes {
    constructor(host, context) {
      this.host = host; this.context = context; this.session = new root.GooSession();
      this.treeSources = new Map();
      this.elements = new Map(); this.wrappers = new Map(); this.loading = new Map(); this.rendered = new Map(); this.serial = 0;
      this.observations=new Map(); this.requests=new Map(); this.nativeWorks=new Map(); this.rowWorks=new Map();
      this.context.workspace ||= host.dataset.workspace; this.context.view ||= host.dataset.view;
      this.inspection = el('details', 'goo-runtime-inspection');
      this.inspection.append(el('summary', '', 'Inspect local runtime')); this.output = el('pre'); this.inspection.append(this.output);
      this.status = el('p', 'goo-local-status'); this.status.setAttribute('role', 'status');
      this.body = host.querySelector('[data-goo-body]') || el('div');
      this.serverNodes = new Map([...this.body.querySelectorAll('[data-goo-node]')].map(n => [n.dataset.gooNode,n]));
      host.replaceChildren(this.status, this.body, this.inspection);
      this.session.subscribe(() => { if (!this.updating) this.paint(); });
      this.inspection.addEventListener('toggle', () => this.reflect());
    }
    async source(path, topology = '', axis = 'z', signal, incremental = true) {
      if(topology==='tree' && incremental) {
        const key=JSON.stringify([path,axis]);
        let loader=this.treeSources.get(key);
        if(!loader) {
          loader=new root.GooTopoi.TreeSource(path,axis,async(params,signal)=> {
            const response=await fetch(`/goo/source?${new URLSearchParams({target:path,topology:'tree',axis,paged:'1',...params})}`,{cache:'no-store',signal});
            if(!response.ok)throw new Error(await response.text());
            return response.json();
          });
          this.treeSources.set(key,loader);
        }
        return loader.read(signal);
      }
      const response = await fetch(`/goo/source?${new URLSearchParams({target: path, topology, axis: axis || 'z'})}`, {cache: 'no-store',signal});
      if (!response.ok) throw new Error('Source unavailable');
      const value = await response.json();
      if (!value.bounded) throw new Error('Finite source exceeds 64 members.');
      return value;
    }
    async update(description, snapshot, options={}) {
      const {signal}=options;
      if(signal?.aborted || this.session.closed) return {status:'superseded'};
      const sequence=++this.serial, current=()=>sequence===this.serial && !signal?.aborted && !this.session.closed;
      if (this.composing()) {
        this.deferredUpdate = [description, snapshot,options]; return {status:'deferred'};
      }
      const sources = new Map(), sourceValues = new Map();
      this.memberLoads = new Map();
      const prepare = async nodes => Promise.all(nodes.map(async node => {
        const out = {...node, children: await prepare(node.children || [])};
        if (node.kind === 'selection') {
          // Only an outline provides disclosure. Standalone diagram/flat views
          // keep their complete-source behavior; shared views use its projection.
          const incremental=root.GooTopoi.hasOutline(node.children||[],node.key);
          const key = JSON.stringify([node.source,node.topology,node.axis,incremental]);
          if (!sources.has(key)) sources.set(key, this.source(node.source,node.topology,node.axis,signal,incremental));
          out.source = await sources.get(key);
          sourceValues.set(key,out.source);
          if (node.initial != null) {
            out.initial = out.source.members.find(m => m.key === node.initial) || {key: node.initial};
          }
        }
        if (node.kind === 'patch') out.children = root.GooPatchHost.population(node);
        if (['list','topos'].includes(node.kind)) out.type = 'namespace-record';
        return out;
      }));
      let nodes;
      try {nodes=await prepare(description);} catch(error) {if(!current())return {status:'superseded'};throw error;}
      if (!current()) return {status:'superseded'};
      if(this.composing()) {this.deferredUpdate=[description,snapshot,options];return {status:'deferred'};}
      const retiringWork = this.retiringWork(nodes);
      for (const work of retiringWork) {
        const allowed=await this.session.depart(work,{kind:'presentation-retirement'},{signal});
        if(!current())return {status:'superseded'};
        if(!allowed)return {status:'refused'};
      }
      if(this.composing()) {this.deferredUpdate=[description,snapshot,options];return {status:'deferred'};}
      this.updating = (this.updating||0)+1;
      let result;
      try { result = await this.session.reconcile(nodes,{signal}); } finally { this.updating--; }
      if(!current())return {status:'superseded'};
      if(result.status!=='accepted')return {status:result.status};
      const trees=new Set();
      for(const source of sourceValues.values()) {
        if(source.incremental) {
          const key=JSON.stringify([source.id,source.axis||'z']);trees.add(key);
          this.treeSources.get(key)?.commit(source);
        }
      }
      for(const key of this.treeSources.keys())if(!trees.has(key))this.treeSources.delete(key);
      for (const work of retiringWork) work.release?.();
      this.snapshot = snapshot; this.description = nodes; this.rawDescription=description;
      this.usedWrappers = new Set();
      const focus = this.host.contains(document.activeElement) ? document.activeElement : null;
      this.layout(nodes, this.body, 'session', []);
      if (focus?.isConnected && document.activeElement !== focus) focus.focus({preventScroll:true});
      for (const key of this.wrappers.keys()) if (!this.usedWrappers.has(key)) this.wrappers.delete(key);
      for (const [key, element] of this.elements) if (!this.session.owners.has(key)) { element.remove(); this.elements.delete(key); this.rendered.delete(key); }
      for (const [element,held] of this.observations) if (!element.isConnected) { held.stop(); this.observations.delete(element); this.requests.get(element)?.abort(); this.requests.delete(element); }
      this.paint();
      if(current())options.onApplied?.();
      return {status:'applied'};
    }
    composing() {
      return [...this.session.owners.values(),...this.nativeWorks.values(),...this.rowWorks.values()]
        .some(work=>[...work.inputs.values()].some(value=>value.composing));
    }
    wrapperKey(owner,node,scopes,serverKey) {
      const descendants = nodes => nodes.flatMap(n => n.key ? [[n.kind,n.key]] : descendants(n.children || []));
      return JSON.stringify([owner,node.kind,node.key,scopes,descendants([node]),node.kind==='native'?node.node||serverKey:null]);
    }
    retiringWork(nodes) {
      const plan=this.session.plan(nodes), nativeKeys=new Set();
      const visit=(nodes,owner='session',scopes=[],route=[])=>{
        for(const [ordinal,node] of nodes.entries()) {
          const here=[...route,ordinal], key=id(owner,node.kind,node.key);
          if(['native','patch'].includes(node.kind)) {
            const wrapper=this.wrapperKey(owner,node,scopes,here.join('.'));
            const prior=[...this.nativeWorks.values()].find(work=>work.wrapperKey===wrapper);
            if(node.kind!=='patch'||!prior||prior.encounter?.id===node.scene.header.encounter)nativeKeys.add(wrapper);
          }
          visit(node.children||[],node.kind==='pane'?key:owner,node.kind==='selection'?[...scopes,key]:scopes,here);
        }
      };
      visit(nodes);
      const retired=[...this.nativeWorks.values()].filter(work=>!nativeKeys.has(work.wrapperKey));
      for(const work of this.rowWorks.values()) {
        const topoi=plan.get(work.ownerId), selection=topoi && plan.get(topoi.selectionId);
        const member=selection?.source.members.find(member=>member.key===work.member.key);
        if(!member || member.status!=='available' || selection.source.deleted?.includes(member.key) ||
          JSON.stringify([member.source,member.sourceLife,member.axis||'z',member.key,member.life,member.subject,topoi.slot])!==work.binding) retired.push(work);
      }
      // Retiring semantic owners already admit/release their attached work via
      // GooSession. Only surviving owners need this additional presentation gate.
      return retired.filter(work=>!work.ref || plan.has(this.session.get(work.ref).id));
    }
    state(owner, kind, key) { return this.session.owners.get(id(owner, kind, key)); }
    layout(nodes, parent, owner, scopes, route = []) {
      const desired = [];
      for (const [ordinal, node] of nodes.entries()) {
        const here = [...route,ordinal], serverKey = here.join('.');
        const server = this.serverNodes.get(serverKey);
        this.serverNodes.delete(serverKey);
        let adopted = false;
        let element, children = node.children || [], nextOwner = owner, nextScopes = scopes;
        const state = this.state(owner, node.kind, node.key);
        if (state) {
          element = this.elements.get(state.id);
          if (!element) {
            element = server || el('div', `goo-${node.kind}`); adopted = !!server; this.elements.set(state.id, element); element.dataset.owner = state.id;
            if (node.kind === 'follow') this.registerWork(state, element);
          }
        } else {
          // This key retains a rendering wrapper only; it never becomes an
          // ownership/addressing ancestor. Semantic child keys survive reorder.
          const wrapperKey = this.wrapperKey(owner,node,scopes.map(s=>s.id),serverKey);
          this.usedWrappers.add(wrapperKey);
          element = this.wrappers.get(wrapperKey);
          if (!element) { element = server || el('div', `goo-${node.kind}`); adopted = !!server; this.wrappers.set(wrapperKey,element); }
          element.gooWrapperKey=wrapperKey;
        }
        if (adopted) element.removeAttribute('data-goo-node');
        if (node.kind === 'pane') { nextOwner = state.id; element.setAttribute('aria-label', node.key); }
        if (node.kind === 'selection') {
          nextScopes = [...scopes, state];
          if (!state.notice) { state.notice = el('p', 'goo-local-status'); element.prepend(state.notice); }
        }
        if (node.kind === 'patch') {
          root.GooPatchHost.render(this,node,element,scopes,owner);
        } else if (node.kind === 'native') {
          this.native(node,element,scopes,owner,adopted);
        } else if (['navigate','operation','operation_status'].includes(node.kind)) {
          if (!adopted && !state.hostBound) element.innerHTML = node.html;
          this.hostControl(state, element, node);
        }
        else if (['list','topos'].includes(node.kind)) this.list(state, element, node, scopes);
        else if (node.kind === 'follow') { /* Tracked render scheduled in paint. */ }
        else if (node.kind === 'deck') {
          if (!state.tabs) { state.tabs = el('div'); state.tabs.setAttribute('role', 'tablist'); element.prepend(state.tabs); }
          if (!state.empty) { state.empty = el('p', 'goo-local-status', 'No panes in this deck.'); element.append(state.empty); }
          state.empty.hidden = !!state.active;
          this.layout(children, element, owner, scopes, here);
          state.tabButtons ||= new Map();
          const paneStates = state.children.map(key => this.session.owners.get(key));
          for (const [key, button] of state.tabButtons) if (!state.children.includes(key)) { button.remove(); state.tabButtons.delete(key); }
          for (const pane of paneStates) {
            let button = state.tabButtons.get(pane.id);
            if (!button) {
            button = el('button', '', pane.key); button.type = 'button'; button.setAttribute('role', 'tab'); button.dataset.pane = pane.id;
            button.addEventListener('click', () => this.session.activate(state.ref, pane.ref));
            button.addEventListener('keydown', event => {
              if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
              event.preventDefault(); const buttons = [...state.tabs.children], at = buttons.indexOf(button);
              const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (at + (event.key === 'ArrowLeft' ? -1 : 1) + buttons.length) % buttons.length;
              buttons[next].focus();
            });
            state.tabButtons.set(pane.id, button);
            }
            const at = paneStates.indexOf(pane);
            if (state.tabs.children[at] !== button) state.tabs.insertBefore(button, state.tabs.children[at] || null);
          }
        } else this.layout(children, element, nextOwner, nextScopes, here);
        desired.push(element);
      }
      // Keyed elements are moved only when order changes, preserving native
      // focus/composition and buffers during a compatible evaluation.
      const owned = new Set(desired);
      for (const child of [...parent.children]) {
        if (!owned.has(child) && !child.classList.contains('goo-local-status') && child.getAttribute('role') !== 'tablist') child.remove();
      }
      let before = [...parent.children].find(n => owned.has(n)) || null;
      for (const element of desired) {
        if (element !== before) parent.insertBefore(element, before);
        before = element.nextElementSibling;
      }
    }
    observe(element, callback) {
      let held = this.observations.get(element);
      if (held) { held.callback = callback; return; }
      held = {callback}; this.observations.set(element,held);
      held.stop = root.GooActions.observe(element, () => {
        Promise.resolve(held.callback()).catch(error => { if (error.name !== 'AbortError') this.context.report(error.message); });
      });
    }
    async request(element, target, selector, basis) {
      this.requests.get(element)?.abort();
      const request = new AbortController(); this.requests.set(element,request);
      const data = await root.GooActions.load(target,{...selector,context:root.GooActions.context(element),signal:request.signal,owner:element,basis});
      if (this.requests.get(element) !== request || !element.isConnected) return null;
      return data;
    }
    native(node, element, scopes, owner, adopted) {
      this.observe(element, () => this.renderNative(node,element,scopes,owner));
      if (!this.nativeWorks.has(element)) {
        const parent = this.session.owners.get(owner) || scopes.at(-1);
        const work = {id:`native:${owner}:${node.node}`,kind:'native',live:true,inputs:new Map(),generation:0,encounter:{id:node.node},ref:parent?.ref,wrapperKey:element.gooWrapperKey};
        this.nativeWorks.set(element,work);
        this.registerWork(work,element);
      }
      // Adopted SSR remains visible while the actual container is prepared.
      if (adopted) element.removeAttribute('data-goo-node');
      this.renderNative(node,element,scopes,owner).catch(error => { if (error.name !== 'AbortError') this.context.report(error.message); });
    }
    nativeSnapshotCurrent(snapshot) {
      const parent=this.snapshot;
      const same=parent && (parent.subject||parent.target)===(snapshot.subject||snapshot.target) &&
        ['life','displayed','publication'].every(key=>parent[key]===snapshot[key]);
      if(same) return true;
      // A native fragment shares its enclosing description's scopes and action
      // authority. Refresh that description before accepting a new publication.
      if(!this.session.closed && !this.parentRefresh && this.context.refresh) {
        this.parentRefresh=Promise.resolve().then(()=>{if(!this.session.closed)return this.context.refresh();})
          .catch(error=>this.context.report(error.message)).finally(()=>{this.parentRefresh=null;});
      }
      return false;
    }
    async renderNative(node, element, scopes, owner) {
      const work = this.nativeWorks.get(element);
      if (!work?.live || [...work.inputs.values()].some(value => value.composing)) return;
      const context = root.GooActions.context(element);
      if (!context.width) return;
      const key = JSON.stringify([node.node,this.snapshot,context]);
      if (element.dataset.renderKey === key || element.dataset.loadingKey === key) return;
      element.dataset.loadingKey = key;
      try {
        const data = await this.request(element,this.context.target,{view:this.context.view,node:node.node,workspace:this.context.workspace},JSON.stringify([node.node,this.snapshot]));
        if (!data || !work.live || element.dataset.loadingKey !== key || [...work.inputs.values()].some(value => value.composing)) return;
        if(!this.nativeSnapshotCurrent(data.snapshot)) return;
        const lifetime = JSON.stringify([data.snapshot.subject,data.snapshot.life,data.snapshot.publication]);
        if (work.lifetime && work.lifetime !== lifetime) {
          if (!(await this.session.depart(work,{kind:'native-replaced'}))) return;
          if (!work.live || !element.isConnected || element.dataset.loadingKey!==key || [...work.inputs.values()].some(value=>value.composing)) return;
          if(!this.nativeSnapshotCurrent(data.snapshot)) return;
          work.inputs.clear(); work.generation++;
        }
        const preserve = !work.lifetime || work.lifetime === lifetime; work.lifetime = lifetime;
        root.GooActions.mount(element,data,preserve,false);
        root.GooActions.bind(element,this.actionContext(this.context.target,data.view,data.snapshot,data.controls,scopes,work));
        element.dataset.renderKey = key;
      } finally { if (element.dataset.loadingKey === key) delete element.dataset.loadingKey; }
    }
    hostControl(state, element, node) {
      if (state.hostBound) return;
      state.hostBound = true;
      if (node.kind === 'navigate') {
        const form = element.querySelector('form'), link = element.querySelector('a');
        const navigate = async event => {
          if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
          event.preventDefault();
          const path = form ? form.querySelector('input').value : new URL(link.href, location.href).searchParams.get('path');
          if (!path?.startsWith('/')) { this.context.report('Enter an absolute namespace path.'); return; }
          if (!this.context.navigate) { this.context.report('Workspace navigation is unavailable.'); return; }
          if (await this.close()) this.context.navigate(path);
        };
        (form || link)?.addEventListener(form ? 'submit' : 'click', navigate);
        return;
      }
      const operations = this.context.operations;
      if (!operations) { element.textContent = 'Workspace operations are unavailable.'; return; }
      const button = element.querySelector('button'), details = element.querySelector('details');
      const paint = () => {
        const status = operations.state(node.operation);
        if (button) { button.disabled = status.phase === 'pending'; button.setAttribute('aria-busy', String(button.disabled)); }
        if (details) { details.hidden = status.phase === 'idle'; details.open = status.phase === 'error' || status.phase === 'pending'; details.dataset.phase = status.phase; details.querySelector('pre').textContent = status.message; }
      };
      const unsubscribe = operations.subscribe(paint);
      this.session.resource(state.ref, {release:unsubscribe});
      if (button) button.addEventListener('click', async () => {
        if (operations.state(node.operation).phase === 'pending') return;
        // Reload will discard local buffers; use the same departure guards.
        for (const owner of this.session.owners.values()) if (!(await this.session.depart(owner, {kind:'host-operation'}))) return;
        if (!state.live) return;
        try { await operations.run(node.operation); } catch (error) { this.context.report(error.message); }
      });
      paint();
    }
    async select(state, member) {
      try { await this.session.deliver(this.session.intent(state.selection || state.ref, member)); }
      catch (error) { this.context.report(error.message); }
    }
    list(state, element, node, scopes) {
      const selection = this.session.get(state.selection, 'selection'), source = selection.source;
      if (!state.topos) {
        const clear=el('button','','Clear selection'); clear.type='button'; clear.addEventListener('click',()=>this.select(state,null));
        state.rows=new Map(); state.serverRows=new Map([...element.querySelectorAll('[data-goo-members] > [data-key]')].map(row=>[row.dataset.key,row]));
        element.replaceChildren(clear);
        state.topos=new root.GooTopoi.Topos(element,node.key,member=>this.select(state,member),member=>this.session.focus(state.ref,member),async(member,more)=> {
          const loader=this.treeSources.get(JSON.stringify([source.id,source.axis||'z']));
          if(!loader || !state.live)return;
          loader.request(member,more);
          // Shared refresh owns cancellation, input guards, composition and source
          // admission; child materialization has no independent application state.
          try {
            if(this.context.refresh)await this.context.refresh();
            else await this.update(this.rawDescription,this.snapshot);
          }catch(error){this.context.report(error.message);}
        });
      }
      const renderer=node.renderer||'list';
      const projected=source.members.map(member=>selection.members.get(member.key)||member);
      const members=renderer==='list'?projected.filter(member=>member.status==='available'):projected;
      const keys=new Set(members.map(member=>member.key));
      for(const [key,row] of state.rows) if(!keys.has(key)) { row.remove();state.rows.delete(key); }
      state.topos.reconcile(renderer,members,member=> {
        let row=state.rows.get(member.key);
        if(!row || row.dataset.life!==member.life || (member.status==='available' && !this.rowWorks.has(row))) {
          row?.remove(); row=state.serverRows.get(member.key)||el('div','goo-member',member.key); state.serverRows.delete(member.key);
          row.dataset.life=member.life; row.dataset.key=member.key; state.rows.set(member.key,row);
        }
        if(member.status!=='available') { row.textContent=member.hasChildren?member.key:`${member.key}: unavailable`; return row; }
        let work=this.rowWorks.get(row);
        if(!work) {
          const binding=JSON.stringify([member.source,member.sourceLife,member.axis||'z',member.key,member.life,member.subject,node.slot]);
          work={id:`member:${state.id}:${member.key}`,kind:'member',live:true,inputs:new Map(),generation:0,encounter:{id:binding},ref:state.ref,ownerId:state.id,member,binding};
          this.rowWorks.set(row,work);this.registerWork(work,row);
        }
        const render = async () => {
          if (!state.live || !work.live || !row.isConnected || member.status !== 'available' || [...work.inputs.values()].some(value=>value.composing)) return;
          const context = root.GooActions.context(row);
          if (!context.width) return;
          const expected=JSON.stringify([member.subject,member.life,member.expected,node.slot,this.snapshot?.publication,context]);
          if (row.dataset.expected===expected || row.dataset.loadingKey===expected) return;
          row.dataset.loadingKey=expected; if(!row.dataset.expected) row.inert=true;
          try {
            const data=await this.request(row,member.subject,{slot:node.slot},JSON.stringify([member,work.binding,this.snapshot]));
            if (!data || !state.live || !work.live || row.dataset.loadingKey!==expected || data.snapshot.life!==member.life || [...work.inputs.values()].some(value=>value.composing)) return;
            if (data.description) throw new Error('Member presentations must be views.');
            const lifetime=JSON.stringify([data.view,data.snapshot.subject||data.snapshot.target,data.snapshot.life,data.snapshot.publication]);
            if(work.lifetime && work.lifetime!==lifetime) {
              if(!(await this.session.depart(work,{kind:'member-view-replaced'}))) return;
              if(!work.live || !row.isConnected || row.dataset.loadingKey!==expected || [...work.inputs.values()].some(value=>value.composing)) return;
              work.inputs.clear();work.generation++;
            }
            const preserve=!work.lifetime || work.lifetime===lifetime;work.lifetime=lifetime;
            root.GooActions.mount(row,data,preserve);
            if (node.browse) {
              const navigation=el('a','',node.browse); navigation.dataset.gooNavigation='';
              navigation.href=`?path=${encodeURIComponent(member.subject)}`;
              navigation.addEventListener('click',async event=> {
                if(event.metaKey||event.ctrlKey||event.shiftKey||event.altKey||!this.context.navigate) return;
                event.preventDefault(); if(await this.close()) this.context.navigate(member.subject);
              }); row.append(navigation);
            }
            root.GooActions.bind(row,this.actionContext(member.subject,data.view,data.snapshot,data.controls,scopes,work));
            row.dataset.expected=expected;
          } catch (error) { if(error.name!=='AbortError' && state.live && row.dataset.loadingKey===expected) this.context.report(`${member.key}: ${error.message}`); }
          finally { if(row.dataset.loadingKey===expected) {delete row.dataset.loadingKey;row.inert=false;} }
        };
        this.observe(row,render); render();
        return row;
      });
    }
    registerPatchSurface(surface, work) {
      if(!work.live) throw new Error('Retired patch owner');
      work.patchSurfaces ||= new Set();work.patchSurfaces.add(surface);
      return ()=>work.patchSurfaces.delete(surface);
    }
    registerWork(state, element) {
      if(state.release) return;
      state.guards ||= new Set();
      const guard = async (reason,{signal}={}) => {
        if(signal?.aborted) return false;
        if (!state.live) return true;
        if ([...state.inputs.values()].some(v => v.composing)) { state.diagnostic = 'composition-in-progress'; return false; }
        if (![...state.inputs.values()].some(v => v.dirty)) return true;
        if (state.departure) state.departure.finish(false);
        return new Promise(resolve => {
          const prompt = el('div', 'goo-departure'); prompt.setAttribute('role', 'status');
          prompt.append(el('p', '', 'Unsaved input: stay here, or discard it and leave.'));
          const stay = el('button', '', 'Stay'), leave = el('button', '', 'Discard and leave');
          stay.type = leave.type = 'button'; prompt.append(stay, leave);
          // Suspended deck contents and pending/inert presentations cannot host
          // an actionable prompt. Keep its guard on the same work, but present
          // the decision in the visible session shell.
          const promptHost=state.suspended || element.closest?.('[hidden],[inert]') ? this.host : element;
          promptHost.append(prompt);
          const finish = allowed => {
            if (state.departure?.prompt !== prompt) return;
            signal?.removeEventListener('abort',cancel);prompt.remove(); state.departure = null; resolve(allowed);
          };
          const cancel=()=>finish(false);
          state.departure = {prompt, finish}; stay.addEventListener('click', () => finish(false));
          leave.addEventListener('click', () => finish(![...state.inputs.values()].some(v => v.composing)));
          signal?.addEventListener('abort',cancel,{once:true});if(signal?.aborted)cancel();
        });
      };
      state.guards.add(guard);
      const unguard = state.ref ? this.session.guard(state.ref, guard) : ()=>{};
      let unregister=()=>{}, released=false;
      state.release=()=>{
        if(released) return;released=true;
        state.departure?.finish(false);state.live=false;state.generation++;
        for(const surface of state.patchSurfaces||[])surface.retire();state.patchSurfaces?.clear();
        unguard();unregister();state.guards.delete(guard);state.inputs.clear();element.remove();
        this.requests.get(element)?.abort();this.requests.delete(element);
        this.observations.get(element)?.stop();this.observations.delete(element);
        this.nativeWorks.delete(element);this.rowWorks.delete(element);this.loading.delete(state.id);this.rendered.delete(state.id);
      };
      const resource={
        suspend: () => { for(const surface of state.patchSurfaces||[])surface.suspend(); for (const media of element.querySelectorAll('video,audio')) media.pause(); },
        resume: () => { for(const surface of state.patchSurfaces||[])surface.resume(); this.rendered.delete(state.id); },
        release: state.release
      };
      if(state.ref) unregister=this.session.resource(state.ref,resource);
    }
    actionContext(target, view, snapshot, controls, scopes, follower) {
      const encounter = follower?.encounter?.id, generation = follower?.generation;
      const continuing = () => follower?.live && follower.encounter?.id === encounter && follower.generation === generation;
      return {target, view, snapshot, controls, actionScope:follower, report: this.context.report,
        input: (key, input, signal) => {
          if (!follower) return;
          let work = follower.inputs.get(key);
          if (!work) { work = {value: input.value, dirty: false, composing: false}; follower.inputs.set(key, work); }
          if (!work.dirty && !work.composing) work.value = input.getAttribute?.('value') ?? input.value;
          input.value = work.value;
          input.addEventListener('input', () => { work.value = input.value; work.dirty = true; this.reflect(); },{signal});
          input.addEventListener('compositionstart', () => { work.composing = true; },{signal});
          input.addEventListener('compositionend', () => { work.value = input.value; work.composing = false;
            for(const surface of follower.patchSurfaces||[])surface.flushDeferred();
            if (this.deferredUpdate) { const args = this.deferredUpdate; this.deferredUpdate = null; this.update(...args).catch(e=>this.context.report(e.message)); }
            else { this.paint(); for (const held of this.observations.values()) Promise.resolve(held.callback()).catch(e=>this.context.report(e.message)); } },{signal});
        },
        releaseCapture: invocation => this.session.releaseCapture(invocation),
        capture: (operands, invocation) => {
          const refs = operands.map(op => {
            const state = [...scopes].reverse().find(s => s.key === op.selection);
            if (!state) throw new Error('Unbound capture selection'); return state.ref;
          });
          const values = this.session.capture(refs, invocation).values;
          return operands.map((op, index) => ({slot: op.slot, value: values[index]}));
        },
        become: async slot => {
          if (!follower || follower.kind !== 'follow') throw new Error('This control requires a present encounter.');
          if (!continuing()) return;
          if (!(await this.session.depart(follower, {kind: 'recipe'}))) return;
          if (!continuing()) return;
          follower.inputs.clear(); this.session.become(follower.ref, slot);
        },
        saved: async (_result, savedInputs = new Map()) => {
          if (continuing()) {
            for (const [key, work] of follower.inputs) if (savedInputs.get(key) === work.value) work.dirty = false;
            this.rendered.delete(follower.id);
          }
          if (this.context.refresh) await this.context.refresh();
          else await this.update(this.rawDescription, await root.GooActions.status(this.context.target));
        }
      };
    }
    paint() {
      const session = this.session;
      for (const state of session.owners.values()) {
        const element = this.elements.get(state.id); if (!element) continue;
        if (state.kind === 'selection' && state.notice) {
          state.notice.textContent = state.pending ? `Pending choice: ${state.pending.member?.key || 'none'}; accepted: ${state.accepted?.key || 'none'}` : state.diagnostic || `Selected: ${state.accepted?.key || 'none'}`;
        }
        if (state.kind === 'pane') { element.hidden = state.suspended; element.inert = state.suspended; }
        if (state.kind === 'deck' && state.tabs) for (const tab of state.tabs.children) {
          const active = tab.dataset.pane === state.active; tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;
          if (!state.active) element.dataset.empty = 'true';
        }
        if (['list','topos'].includes(state.kind) && state.topos) {
          state.topos.paint(session.read(state.selection).accepted,state.focus);
        }
        if (state.kind === 'follow' && !state.suspended) this.follow(state, element);
      }
      this.reflect();
    }
    async follow(state, element) {
      this.observe(element, () => this.follow(state,element));
      const selection = this.session.read(state.selection), ticket = this.session.ticket(state.ref);
      const context = root.GooActions.context(element);
      if (!context.width) return;
      const key = JSON.stringify([{...ticket,ref:undefined},context]);
      if (this.rendered.get(state.id) === key || this.loading.get(state.id) === key) return;
      if ([...state.inputs.values()].some(value => value.composing)) return;
      const member = selection.accepted;
      if (!member || member.status !== 'available') {
        this.requests.get(element)?.abort(); this.loading.delete(state.id); element.inert=false; element.removeAttribute('aria-busy');
        element.textContent = member ? 'Selected member is unavailable.' : 'Choose a member.';
        this.rendered.set(state.id,key); return;
      }
      this.loading.set(state.id,key); element.setAttribute('aria-busy','true');
      // Keep an existing editor interactive during context-only preparation.
      if (element.dataset.encounter !== String(ticket.encounter)) element.inert=true;
      element.dataset.status='loading'; this.status.textContent='Loading accepted selection…';
      try {
        const data=await this.request(element,member.subject,{slot:state.encounter.recipe},JSON.stringify([{...ticket,ref:undefined},this.snapshot]));
        if (!data || !this.session.current(ticket) || state.suspended || this.loading.get(state.id)!==key) return;
        if (data.snapshot.life!==member.life || (data.snapshot.subject||data.snapshot.target)!==member.subject) throw new Error('Selected subject was removed or replaced.');
        if (data.description) throw new Error('Nested local-session member views are not supported.');
        if ([...state.inputs.values()].some(value=>value.composing)) return;
        const preserve=element.dataset.encounter===String(ticket.encounter);
        root.GooActions.mount(element,data,preserve);
        element.dataset.encounter=String(ticket.encounter);
        const scopes=state.spec.scopes.map(id=>this.session.owners.get(id));
        root.GooActions.bind(element,this.actionContext(member.subject,data.view,data.snapshot,data.controls,scopes,state));
        this.rendered.set(state.id,key); element.dataset.status='current';
      } catch (error) {
        if (error.name!=='AbortError' && this.session.current(ticket) && this.loading.get(state.id)===key) {
          if(element.dataset.encounter===String(ticket.encounter)) {
            element.dataset.status='error';this.context.report(error.message);
          } else {
            element.textContent=error.message;element.dataset.status='unavailable';this.rendered.set(state.id,key);
          }
        }
      } finally {
        if(this.loading.get(state.id)===key) { this.loading.delete(state.id);element.removeAttribute('aria-busy');element.inert=false;this.status.textContent=''; }
      }
    }
    reflect() { if (this.inspection.open) this.output.textContent = JSON.stringify({...this.session.inspect(), domainActions: root.GooActions.metrics}, null, 2); }
    async close() {
      ++this.serial;this.deferredUpdate=null;
      for(const work of [...this.nativeWorks.values(),...this.rowWorks.values()]) if(!work.ref && !(await this.session.depart(work,{kind:'retirement'}))) return false;
      const result=await this.session.reconcile([]);if(result.status!=='accepted') return false;
      this.session.closed=true;
      for(const work of [...this.nativeWorks.values(),...this.rowWorks.values()]) work.release?.();
      for(const held of this.observations.values()) held.stop();this.observations.clear();
      for(const request of this.requests.values()) request.abort();this.requests.clear();return true;
    }
  }
  root.GooPanes = GooPanes;
})(globalThis);
