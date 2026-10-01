/* Page-local semantic owners. No namespace action is involved in local intents.
 * Handles are capabilities in this session, not executable reflected snapshots. */
(function (root) {
  'use strict';
  const fail = (code) => { throw Object.assign(new Error(code), {code}); };
  const identity = (value) => JSON.stringify(value);
  const binding = (member) => member && identity([member.subject, member.life, member.policy || 'live']);
  const membership = (member) => member && identity([member.source, member.sourceLife, member.key, member.life]);
  const copy = (value) => structuredClone(value);
  class GooSession {
    constructor() {
      this.owners = new Map(); this.handles = new WeakMap(); this.intents = new WeakSet(); this.serial = 0;
      this.revision = 0; this.listeners = new Set(); this.invocations = new Map();
      this.events = []; this.reconcileOrder = 0; this.closed = false;
    }
    emit(kind, detail = {}) {
      this.revision++;
      this.events.push({kind, ...detail, revision: this.revision});
      if (this.events.length > 64) this.events.shift();
      if (!this.reconciling) for (const fn of this.listeners) fn();
    }
    subscribe(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
    get(ref, kind) {
      const state = this.handles.get(ref);
      if (!state || !state.live || this.owners.get(state.id) !== state) fail('stale-or-foreign-handle');
      if (kind && state.kind !== kind) fail('wrong-handle-kind');
      return state;
    }
    // Planning is pure. Sources advertise a finite, bounded projection and a
    // stable membership map; omitted/unloaded members are not tombstones.
    plan(descriptions) {
      if (this.closed) fail('session-retired');
      const plan = new Map();
      const visit = (nodes, owner, context = [], scopes = []) => {
        for (const node of nodes) {
          const kind = node.kind;
          let parent = owner, nested = scopes;
          if (['pane', 'selection', 'list', 'follow', 'deck', 'navigate', 'operation', 'operation_status'].includes(kind)) {
            if (typeof node.key !== 'string' || !node.key) fail('missing-local-key');
            if (['navigate','operation','operation_status'].includes(kind) && owner === 'session') fail('host-control-requires-pane');
            const id = owner + '|' + identity([kind, node.key, context]);
            if (plan.has(id)) fail('duplicate-local-key');
            const spec = {...node, id, owner, context, scopes};
            if (plan.size >= 256) fail('owner-bound-exceeded');
            plan.set(id, spec);
            if (kind === 'pane') parent = id;
            if (kind === 'selection') nested = [...scopes, id];
          }
          visit(node.children || [], parent, context, nested);
        }
      };
      visit(descriptions, 'session');
      for (const spec of plan.values()) {
        if (spec.kind === 'selection') {
          if (!spec.source || !spec.source.id || !spec.source.life || !spec.source.type) fail('invalid-source');
          if (spec.source.members.length > 64) fail('source-bound-exceeded');
          const keys = new Set();
          for (const member of spec.source.members) {
            if (keys.has(member.key)) fail('duplicate-member-key');
            keys.add(member.key);
            this.validateMember(spec.source, member);
          }
          const old = this.owners.get(spec.id);
          if (old && identity([old.source.id, old.source.life, old.source.type]) !== identity([spec.source.id, spec.source.life, spec.source.type])) fail('incompatible-source-rebinding');
        }
        if (['follow', 'list'].includes(spec.kind)) {
          const selection = [...spec.scopes].reverse().map(id => plan.get(id)).find(s => s.key === spec.selection);
          if (!selection) fail('unbound-selection-port');
          if (spec.source && (spec.source !== selection.source.id || spec.type !== selection.source.type)) fail('incompatible-selection-port');
          spec.selectionId = selection.id;
        }
      }
      return plan;
    }
    validateMember(source, member) {
      if (!member || member.source !== source.id || member.sourceLife !== source.life || member.type !== source.type || typeof member.key !== 'string' || !member.key || !member.subject || !member.life) fail('incompatible-member-reference');
    }
    async reconcile(descriptions) {
      const plan = this.plan(descriptions), order = ++this.reconcileOrder;
      const retiring = [...this.owners.values()].filter(s => !plan.has(s.id));
      const allowed = await Promise.all(retiring.map(s => this.depart(s, {kind: 'retirement'})));
      if (order !== this.reconcileOrder || this.closed) return {status: 'superseded'};
      if (allowed.some(ok => !ok)) { this.emit('retirement-refused'); return {status: 'refused'}; }
      this.reconciling = true;
      try {
        for (const state of retiring) this.retire(state);
        for (const spec of plan.values()) {
          let state = this.owners.get(spec.id);
          if (!state) {
            const ref = Object.freeze({kind: spec.kind, incarnation: ++this.serial});
            state = {id: spec.id, kind: spec.kind, key: spec.key, owner: spec.owner, ref, live: true,
              incarnation: this.serial, revision: 0, intentOrder: 0, pending: null, diagnostic: null,
              inputs: new Map(), guards: new Set(), resources: new Set(), observers: new Set(),
              encounter: null, generation: 0, suspended: false, accepted: null, focus: null};
            this.owners.set(spec.id, state); this.handles.set(ref, state);
            if (spec.kind === 'selection') {
              state.source = copy(spec.source); state.members = new Map(spec.source.members.map(m => [m.key, copy(m)]));
              if (spec.initial != null) {
                try {
                  this.validateMember(state.source, spec.initial);
                  const member = state.members.get(spec.initial.key);
                  if (!member || membership(member) !== membership(spec.initial)) fail('invalid-initial-member');
                  state.accepted = copy(member);
                } catch (error) { state.diagnostic = error.code; }
              }
            }
          }
          state.spec = spec;
          if (state.kind === 'selection') {
            // Keep unprojected known members; explicit tombstones carry deletion.
            for (const member of spec.source.members) state.members.set(member.key, copy(member));
            // The finite projection plus the chosen member is the retention bound.
            const retained = new Set(spec.source.members.map(m => m.key));
            if (state.accepted) retained.add(state.accepted.key);
            for (const key of state.members.keys()) if (!retained.has(key)) state.members.delete(key);
            for (const key of spec.source.deleted || []) {
              const member = state.members.get(key);
              if (member) state.members.set(key, {...member, status: 'unavailable'});
            }
            state.source = copy(spec.source);
            if (state.accepted) {
              const fresh = state.members.get(state.accepted.key);
              if (fresh && membership(fresh) === membership(state.accepted)) state.accepted = copy(fresh);
              else state.accepted = {...state.accepted, status: 'unavailable'};
            }
          }
        }
        for (const state of this.owners.values()) {
          state.observers.clear();
          if (['follow', 'list'].includes(state.kind)) state.selection = this.owners.get(state.spec.selectionId).ref;
          if (state.kind === 'deck') this.reconcileDeck(state, plan);
        }
        for (const state of this.owners.values()) {
          if (state.kind === 'follow') { this.get(state.selection).observers.add(state.id); this.observe(state); }
        }
      } finally { this.reconciling = false; }
      this.emit('reconciled'); return {status: 'accepted'};
    }
    reconcileDeck(state, plan) {
      const panes = [];
      const gather = nodes => { for (const node of nodes) {
        if (node.kind === 'pane') {
          const id = state.owner + '|' + identity(['pane', node.key, state.spec.context]);
          const pane = this.owners.get(id); if (pane) panes.push(pane);
        } else gather(node.children || []);
      }};
      gather(state.spec.children || []);
      state.children = panes.map(p => p.id);
      if (!state.children.includes(state.active)) state.active = state.children[0] || null;
      for (const pane of panes) this.suspend(pane, pane.id !== state.active);
    }
    suspend(state, value) {
      if (state.suspended !== value) {
        state.suspended = value;
        for (const resource of state.resources) value ? resource.suspend?.() : resource.resume?.();
      }
      for (const child of this.owners.values()) if (child.owner === state.id) this.suspend(child, value);
    }
    async activate(ref, paneRef) {
      const deck = this.get(ref, 'deck'), pane = this.get(paneRef, 'pane');
      if (!deck.children.includes(pane.id)) fail('incompatible-deck-child');
      if (deck.active === pane.id) return {status: 'noop'};
      deck.active = pane.id; deck.revision++;
      for (const id of deck.children) this.suspend(this.owners.get(id), id !== pane.id);
      this.emit('deck-activated', {id: deck.id}); return {status: 'accepted'};
    }
    retire(state) {
      state.live = false; state.intentOrder++; state.generation++;
      state.pending = null;
      for (const resource of state.resources) resource.release?.();
      state.resources.clear(); state.guards.clear(); state.inputs.clear(); state.observers.clear();
      this.owners.delete(state.id);
      this.emit('retired', {id: state.id, incarnation: state.incarnation});
    }
    async depart(state, reason) {
      try {
        const outcomes = await Promise.all([...state.guards].map(guard => guard(reason)));
        return outcomes.every(Boolean);
      } catch (error) { state.diagnostic = `departure-failed: ${error.message}`; return false; }
    }
    guard(ref, callback) { const state = this.get(ref); state.guards.add(callback); return () => state.guards.delete(callback); }
    resource(ref, resource) { const state = this.get(ref); state.resources.add(resource); return () => state.resources.delete(resource); }
    intent(ref, member = null) {
      const state = this.get(ref, 'selection');
      // Sequence allocated by the owner at gesture creation; delivery/retry
      // cannot turn a previously delivered gesture into a new one.
      const intent = Object.freeze({ref, order: ++state.intentOrder, member: member && copy(member)});
      this.intents.add(intent); return intent;
    }
    async deliver(intent) {
      if (!this.intents.has(intent)) fail('unknown-local-intent');
      const state = this.get(intent.ref, 'selection');
      if (intent.order !== state.intentOrder || intent.order <= (state.delivered || 0)) return {status: 'superseded'};
      state.delivered = intent.order;
      let member = intent.member;
      if (member) {
        this.validateMember(state.source, member);
        const known = state.members.get(member.key);
        if (!known || membership(known) !== membership(member)) fail('stale-member');
        if (known.status && known.status !== 'available') fail('unavailable-member');
        member = copy(known);
      }
      state.pending = {order: intent.order, member}; state.diagnostic = null;
      this.emit('selection-pending', {id: state.id});
      const followers = [...state.observers].map(id => this.owners.get(id)).filter(Boolean);
      const departing = binding(state.accepted) === binding(member) ? [] : followers;
      const allowed = await Promise.all(departing.map(s => this.depart(s, {kind: 'selection', intent: intent.order, member})));
      if (!state.live || intent.order !== state.intentOrder) return {status: 'superseded'};
      state.pending = null;
      if (member) {
        const fresh = state.members.get(member.key);
        if (!fresh || membership(fresh) !== membership(member) || fresh.status !== 'available') {
          state.diagnostic = 'member-changed-during-departure'; this.emit('selection-refused', {id:state.id}); return {status:'refused'};
        }
        member = copy(fresh);
      }
      if (followers.some(f => !f.live) || followers.length !== state.observers.size) allowed.push(false);
      if (allowed.some(ok => !ok)) { state.diagnostic = 'departure-refused'; this.emit('selection-refused', {id: state.id}); return {status: 'refused'}; }
      if (membership(state.accepted) === membership(member)) { this.emit('selection-noop', {id: state.id}); return {status: 'noop'}; }
      state.accepted = member; state.revision++;
      for (const follower of followers) this.observe(follower);
      this.emit('selection-accepted', {id: state.id, acceptedRevision: state.revision});
      return {status: 'accepted', revision: state.revision};
    }
    observe(follower) {
      const state = this.get(follower.selection, 'selection');
      const next = binding(state.accepted);
      if (follower.encounter?.binding !== next) {
        follower.encounter = next ? {id: ++this.serial, binding: next, recipe: follower.spec.slot} : null;
        follower.generation++; follower.inputs.clear();
      }
    }
    read(ref) {
      const state = this.get(ref, 'selection');
      return copy({accepted: state.accepted, revision: state.revision, pending: state.pending, diagnostic: state.diagnostic});
    }
    focus(ref, member) {
      const state = this.get(ref, 'list'), selection = this.get(state.selection, 'selection');
      this.validateMember(selection.source, member);
      state.focus = copy(member); this.emit('focus', {id: state.id});
    }
    become(ref, recipe) {
      const state = this.get(ref, 'follow');
      if (!state.encounter) fail('empty-encounter');
      state.encounter.recipe = recipe; state.generation++; this.emit('become', {id: state.id});
    }
    ticket(ref) {
      const state = this.get(ref, 'follow'), selection = this.get(state.selection, 'selection');
      return {ref, incarnation: state.incarnation, generation: state.generation, encounter: state.encounter?.id,
        revision: selection.revision, evidence: identity(selection.accepted)};
    }
    current(ticket) {
      try {
        const fresh = this.ticket(ticket.ref);
        return ['incarnation', 'generation', 'encounter', 'revision', 'evidence'].every(k => fresh[k] === ticket[k]);
      } catch { return false; }
    }
    capture(refs, invocation) {
      if (this.invocations.has(invocation)) return this.invocations.get(invocation);
      if (this.invocations.size >= 128) fail('invocation-bound-exceeded');
      const states = refs.map(ref => this.get(ref, 'selection'));
      if (new Set(states.map(s => s.owner)).size > 1) fail('cross-owner-capture-unsupported');
      const values = states.map(s => {
        if (!s.accepted) fail('empty-selection');
        if (s.accepted.status && s.accepted.status !== 'available') fail('unavailable-selection');
        return {selection: s.id, incarnation: s.incarnation, revision: s.revision, member: copy(s.accepted)};
      });
      const freeze = v => { if (v && typeof v === 'object') { Object.values(v).forEach(freeze); Object.freeze(v); } return v; };
      const snapshot = freeze({invocation, values});
      this.invocations.set(invocation, snapshot); this.emit('captured', {invocation}); return snapshot;
    }
    inspect() {
      return copy({revision: this.revision, owners: [...this.owners.values()].map(s => ({
        id: s.id, kind: s.kind, key: s.key, owner: s.owner, incarnation: s.incarnation,
        accepted: s.accepted, revision: s.revision, pending: s.pending, diagnostic: s.diagnostic,
        source: s.source, focus: s.focus, selectionPort: s.selection && this.get(s.selection).id,
        followers: [...s.observers], encounter: s.encounter, generation: s.generation,
        suspended: s.suspended, active: s.active, inputs: [...s.inputs.entries()],
        guards: s.guards.size, resources: s.resources.size
      })), events: this.events, captures: [...this.invocations.values()]});
    }
  }
  root.GooSession = GooSession;
  if (typeof module !== 'undefined') module.exports = {GooSession, binding, membership};
})(typeof globalThis === 'undefined' ? window : globalThis);
