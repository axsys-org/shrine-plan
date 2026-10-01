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
      this.elements = new Map(); this.wrappers = new Map(); this.loading = new Map(); this.rendered = new Map(); this.serial = 0;
      this.inspection = el('details', 'goo-runtime-inspection');
      this.inspection.append(el('summary', '', 'Inspect local runtime')); this.output = el('pre'); this.inspection.append(this.output);
      this.status = el('p', 'goo-local-status'); this.status.setAttribute('role', 'status');
      this.body = el('div'); host.replaceChildren(this.status, this.body, this.inspection);
      this.session.subscribe(() => { this.paint(); });
      this.inspection.addEventListener('toggle', () => this.reflect());
    }
    async source(path) {
      const response = await fetch(`/goo/source?${new URLSearchParams({target: path})}`, {cache: 'no-store'});
      if (!response.ok) throw new Error('Source unavailable');
      const value = await response.json();
      if (!value.bounded) throw new Error('Finite source exceeds 64 physical members.');
      if (value.life === '0') throw new Error('Source must be an installed namespace record.');
      return value;
    }
    async update(description, snapshot) {
      if ([...this.session.owners.values()].some(s => [...s.inputs.values()].some(v => v.composing))) {
        this.deferredUpdate = [description, snapshot]; return;
      }
      const sequence = ++this.serial, sources = new Map();
      const prepare = async nodes => Promise.all(nodes.map(async node => {
        const out = {...node, children: await prepare(node.children || [])};
        if (node.kind === 'selection') {
          if (!sources.has(node.source)) sources.set(node.source, this.source(node.source));
          out.source = await sources.get(node.source);
          if (node.initial != null) {
            out.initial = out.source.members.find(m => m.key === node.initial) || {key: node.initial};
          }
        }
        if (node.kind === 'list') out.type = 'namespace-record';
        return out;
      }));
      const nodes = await prepare(description);
      if (sequence !== this.serial) return;
      const result = await this.session.reconcile(nodes);
      if (sequence !== this.serial || result.status !== 'accepted') return;
      this.snapshot = snapshot; this.description = nodes;
      this.usedWrappers = new Set();
      const focus = this.host.contains(document.activeElement) ? document.activeElement : null;
      this.layout(nodes, this.body, 'session', []);
      if (focus?.isConnected && document.activeElement !== focus) focus.focus({preventScroll:true});
      for (const key of this.wrappers.keys()) if (!this.usedWrappers.has(key)) this.wrappers.delete(key);
      for (const [key, element] of this.elements) if (!this.session.owners.has(key)) { element.remove(); this.elements.delete(key); this.rendered.delete(key); }
      this.paint();
    }
    state(owner, kind, key) { return this.session.owners.get(id(owner, kind, key)); }
    layout(nodes, parent, owner, scopes) {
      const desired = [];
      for (const node of nodes) {
        let element, children = node.children || [], nextOwner = owner, nextScopes = scopes;
        const state = this.state(owner, node.kind, node.key);
        if (state) {
          element = this.elements.get(state.id);
          if (!element) {
            element = el('div', `goo-${node.kind}`); this.elements.set(state.id, element); element.dataset.owner = state.id;
            if (node.kind === 'follow') this.registerWork(state, element);
          }
        } else {
          // This key retains a rendering wrapper only; it never becomes an
          // ownership/addressing ancestor. Semantic child keys survive reorder.
          const descendants = nodes => nodes.flatMap(n => n.key ? [[n.kind,n.key]] : descendants(n.children || []));
          const wrapperKey = JSON.stringify([owner,node.kind,node.key,scopes.map(s=>s.id),descendants([node]),node.kind === 'native' ? [node.html,node.controls] : null]);
          this.usedWrappers.add(wrapperKey);
          element = this.wrappers.get(wrapperKey);
          if (!element) { element = el('div', `goo-${node.kind}`); this.wrappers.set(wrapperKey,element); }
        }
        if (node.kind === 'pane') { nextOwner = state.id; element.setAttribute('aria-label', node.key); }
        if (node.kind === 'selection') {
          nextScopes = [...scopes, state];
          if (!state.notice) { state.notice = el('p', 'goo-local-status'); element.prepend(state.notice); }
        }
        if (node.kind === 'native') {
          if (element.dataset.boundSnapshot === JSON.stringify(this.snapshot)) { desired.push(element); continue; }
          element.dataset.boundSnapshot = JSON.stringify(this.snapshot);
          element.innerHTML = node.html;
          root.GooActions.bind(element, this.actionContext(this.context.target, this.context.view, this.snapshot, node.controls, scopes));
        } else if (node.kind === 'list') this.list(state, element, node, scopes);
        else if (node.kind === 'follow') { /* Tracked render scheduled in paint. */ }
        else if (node.kind === 'deck') {
          if (!state.tabs) { state.tabs = el('div'); state.tabs.setAttribute('role', 'tablist'); element.prepend(state.tabs); }
          if (!state.empty) { state.empty = el('p', 'goo-local-status', 'No panes in this deck.'); element.append(state.empty); }
          state.empty.hidden = !!state.active;
          this.layout(children, element, owner, scopes);
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
        } else this.layout(children, element, nextOwner, nextScopes);
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
    async select(state, member) {
      try { await this.session.deliver(this.session.intent(state.selection || state.ref, member)); }
      catch (error) { this.context.report(error.message); }
    }
    list(state, element, node, scopes) {
      const selection = this.session.get(state.selection), source = selection.source;
      if (!state.listBody) {
        const clear = el('button', '', 'Clear selection'); clear.type = 'button'; clear.addEventListener('click', () => this.select(state, null));
        state.listBody = el('div'); state.listBody.setAttribute('role', 'listbox'); state.listBody.setAttribute('aria-label', node.key);
        element.append(clear, state.listBody); state.rows = new Map();
      }
      const visible = source.members.filter(m => m.status === 'available'), keys = new Set(visible.map(m => m.key));
      for (const [key, row] of state.rows) if (!keys.has(key)) { row.remove(); state.rows.delete(key); }
      for (const member of visible) {
        let row = state.rows.get(member.key);
        if (!row || row.dataset.life !== member.life) {
          row?.remove(); row = el('div', 'goo-member', member.key); row.dataset.life = member.life; row.dataset.key = member.key;
          row.setAttribute('role', 'option'); row.tabIndex = state.focus?.key === member.key || !state.focus && member === visible[0] ? 0 : -1;
          row.addEventListener('click', event => { if (!interactive(event)) this.select(state, member); });
          row.addEventListener('focus', () => this.session.focus(state.ref, member));
          row.addEventListener('keydown', event => {
            if (interactive(event)) return;
            if (event.key === 'Enter') { event.preventDefault(); this.select(state, member); }
            if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
              event.preventDefault(); const rows = [...state.listBody.children], at = rows.indexOf(row);
              const next = event.key === 'Home' ? 0 : event.key === 'End' ? rows.length - 1 : (at + (event.key === 'ArrowUp' ? -1 : 1) + rows.length) % rows.length;
              rows[next].focus();
            }
          });
          state.rows.set(member.key, row);
          // Bounded row summary fetch; individual namespace controls retain
          // their explicit member receiver and normal admission checks.
        }
        if (row.dataset.expected !== member.expected) {
          row.dataset.expected = member.expected;
          const expected = member.expected;
          row.inert = true;
          root.GooActions.load(member.subject).then(data => {
            if (!state.live || !row.isConnected || row.dataset.expected !== expected || data.snapshot.life !== member.life) return;
            const template = root.GooActions.choose(data.templates, node.slot);
            if (template.querySelector('.goo-session')) throw new Error('Nested local-session member views are not supported.');
            row.replaceChildren(template.cloneNode(true));
            root.GooActions.bind(row, this.actionContext(member.subject, template.dataset.view, data.snapshot, null, scopes));
          }).catch(error => { if (state.live && row.dataset.expected === expected) row.textContent = `${member.key}: ${error.message}`; })
            .finally(() => { if (row.dataset.expected === expected) row.inert = false; });
        }
        // Avoid detach/reappend of stable rows on ordinary reevaluation.
        if (state.listBody.children[[...keys].indexOf(member.key)] !== row) state.listBody.append(row);
      }
    }
    registerWork(state, element) {
      this.session.guard(state.ref, async reason => {
        if ([...state.inputs.values()].some(v => v.composing)) { state.diagnostic = 'composition-in-progress'; return false; }
        if (![...state.inputs.values()].some(v => v.dirty)) return true;
        if (state.departure) state.departure.finish(false);
        return new Promise(resolve => {
          const prompt = el('div', 'goo-departure'); prompt.setAttribute('role', 'status');
          prompt.append(el('p', '', 'Unsaved input: stay here, or discard it and leave.'));
          const stay = el('button', '', 'Stay'), leave = el('button', '', 'Discard and leave');
          stay.type = leave.type = 'button'; prompt.append(stay, leave); element.append(prompt);
          const finish = allowed => {
            if (state.departure?.prompt !== prompt) return;
            prompt.remove(); state.departure = null; resolve(allowed);
          };
          state.departure = {prompt, finish}; stay.addEventListener('click', () => finish(false));
          leave.addEventListener('click', () => finish(![...state.inputs.values()].some(v => v.composing)));
        });
      });
      this.session.resource(state.ref, {
        suspend: () => { for (const media of element.querySelectorAll('video,audio')) media.pause(); },
        resume: () => { this.rendered.delete(state.id); },
        release: () => { element.remove(); this.loading.delete(state.id); this.rendered.delete(state.id); }
      });
    }
    actionContext(target, view, snapshot, controls, scopes, follower) {
      const encounter = follower?.encounter?.id, generation = follower?.generation;
      const continuing = () => follower?.live && follower.encounter?.id === encounter && follower.generation === generation;
      return {target, view, snapshot, controls, report: this.context.report,
        input: (key, input) => {
          if (!follower) return;
          let work = follower.inputs.get(key);
          if (!work) { work = {value: input.value, dirty: false, composing: false}; follower.inputs.set(key, work); }
          input.value = work.value;
          input.addEventListener('input', () => { work.value = input.value; work.dirty = true; this.reflect(); });
          input.addEventListener('compositionstart', () => { work.composing = true; });
          input.addEventListener('compositionend', () => { work.value = input.value; work.composing = false;
            if (this.deferredUpdate) { const args = this.deferredUpdate; this.deferredUpdate = null; this.update(...args).catch(e=>this.context.report(e.message)); }
            else this.paint(); });
        },
        capture: (operands, invocation) => {
          const refs = operands.map(op => {
            const state = [...scopes].reverse().find(s => s.key === op.selection);
            if (!state) throw new Error('Unbound capture selection'); return state.ref;
          });
          const values = this.session.capture(refs, invocation).values;
          return operands.map((op, index) => ({slot: op.slot, value: values[index]}));
        },
        become: async slot => {
          if (!follower) throw new Error('This control requires a present encounter.');
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
        if (state.kind === 'list' && state.rows) {
          const choice = session.read(state.selection).accepted;
          for (const [key, row] of state.rows) {
            row.setAttribute('aria-selected', String(choice?.key === key && choice.life === row.dataset.life));
            if (state.focus) row.tabIndex = state.focus.key === key ? 0 : -1;
          }
        }
        if (state.kind === 'follow' && !state.suspended) this.follow(state, element);
      }
      this.reflect();
    }
    async follow(state, element) {
      const selection = this.session.read(state.selection), ticket = this.session.ticket(state.ref);
      const key = JSON.stringify({...ticket, ref: undefined});
      if (this.rendered.get(state.id) === key || this.loading.get(state.id) === key) return;
      if ([...state.inputs.values()].some(v => v.composing)) return;
      const member = selection.accepted;
      if (!member || member.status !== 'available') {
        this.loading.delete(state.id); element.inert = false; element.removeAttribute('aria-busy');
        element.textContent = member ? 'Selected member is unavailable.' : 'Choose a member.';
        this.rendered.set(state.id, key); return;
      }
      this.loading.set(state.id, key); element.setAttribute('aria-busy', 'true');
      element.inert = true;
      element.dataset.status = 'loading'; this.status.textContent = 'Loading accepted selection…';
      try {
        const data = await root.GooActions.load(member.subject);
        if (!this.session.current(ticket) || state.suspended) return;
        if (data.snapshot.life !== member.life || data.snapshot.target !== member.subject) throw new Error('Selected subject was removed or replaced.');
        const template = root.GooActions.choose(data.templates, state.encounter.recipe);
        if (template.querySelector('.goo-session')) throw new Error('Nested local-session member views are not supported.');
        // Never detach an active composition to apply asynchronous rendering.
        if ([...state.inputs.values()].some(v => v.composing)) return;
        if (element.contains(document.activeElement) && document.activeElement.matches('input,textarea')) {
          document.activeElement.addEventListener('blur', () => this.paint(), {once:true}); return;
        }
        element.replaceChildren(template.cloneNode(true));
        const scopes = state.spec.scopes.map(id => this.session.owners.get(id));
        root.GooActions.bind(element, this.actionContext(member.subject, template.dataset.view, data.snapshot, null, scopes, state));
        this.rendered.set(state.id, key); element.dataset.status = 'current';
      } catch (error) {
        if (this.session.current(ticket)) { element.textContent = error.message; element.dataset.status = 'unavailable'; this.rendered.set(state.id, key); }
      } finally {
        if (this.loading.get(state.id) === key) { this.loading.delete(state.id); element.removeAttribute('aria-busy'); element.inert = false; this.status.textContent = ''; }
      }
    }
    reflect() { if (this.inspection.open) this.output.textContent = JSON.stringify({...this.session.inspect(), domainActions: root.GooActions.metrics}, null, 2); }
    async close() { const result = await this.session.reconcile([]); if (result.status !== 'accepted') return false; this.serial++; this.session.closed = true; return true; }
  }
  const update = GooPanes.prototype.update;
  GooPanes.prototype.update = function (description, snapshot) { this.rawDescription = description; return update.call(this, description, snapshot); };
  root.GooPanes = GooPanes;
})(globalThis);
