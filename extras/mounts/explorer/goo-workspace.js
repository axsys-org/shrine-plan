/* Workspace-host capabilities. Goo names capabilities, never HTTP endpoints. */
(function(root) {
  'use strict';
  class GooWorkspace {
    constructor(operations = [], io = {}) {
      this.capabilities = new Map(operations.map(op => [op.key, op]));
      this.states = new Map(); this.listeners = new Set();
      this.fetch = io.fetch || root.fetch.bind(root);
      this.reload = io.reload || (() => root.location.reload());
      this.sleep = io.sleep || (ms => new Promise(resolve => setTimeout(resolve, ms)));
    }
    subscribe(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
    state(key) { return this.states.get(key) || {phase:'idle', message:''}; }
    publish(key, phase, message) {
      this.states.set(key, {phase, message}); for (const fn of this.listeners) fn(key, this.state(key));
    }
    async run(key) {
      if (this.state(key).phase === 'pending') return;
      const operation = this.capabilities.get(key);
      if (!operation || operation.kind !== 'mount-rescan') throw new Error('Unavailable workspace operation.');
      this.publish(key, 'pending', 'Scanning and publishing...');
      const call = async (action, fields = {}) => {
        const body = new URLSearchParams({source:operation.source, ...fields});
        const response = await this.fetch('/grove/dev/' + action + (action === 'status' ? '?' + body : ''), {
          method:action === 'status' ? 'GET' : 'POST', cache:'no-store', signal:AbortSignal.timeout(600000),
          ...(action === 'status' ? {} : {body})
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `Mount request failed (${response.status})`);
        const unit = result.units.find(unit => unit.source === operation.source);
        if (!unit) throw new Error('Mount source is unavailable.');
        return unit;
      };
      try {
        let unit = await call('status');
        unit = await call('rescan', {scan:unit.requested});
        const requested = unit.requested, deadline = Date.now() + 600000;
        do {
          unit = await call('status');
          if (unit.requested !== requested) throw new Error('Another scan superseded this operation.');
          if (BigInt(unit.completed) >= BigInt(requested)) break;
          if (Date.now() > deadline) throw new Error('Publication is still pending; check mount status before retrying.');
          await this.sleep(350);
        } while (true);
        if (!unit.ready) throw new Error(unit.diagnostic || unit.message || 'Publication failed.');
        this.publish(key, 'success', 'Published.'); this.reload();
      } catch (error) { this.publish(key, 'error', error.message); }
    }
  }
  root.GooWorkspace = GooWorkspace;
  if (typeof module !== 'undefined') module.exports = {GooWorkspace};
  if (!root.document) return;
  for (const host of document.querySelectorAll('.goo-session[data-operations]')) {
    const operations = new GooWorkspace(JSON.parse(host.dataset.operations));
    const report = message => { controller.status.textContent = message; };
    const controller = new root.GooPanes(host, {
      target:host.dataset.target, view:'', operations, report,
      navigate: path => { const url = new URL(root.location.href); url.searchParams.set('path',path); root.location.assign(url); },
      refresh: () => root.location.reload()
    });
    controller.update(JSON.parse(host.dataset.description), {path:host.dataset.target}).catch(error => report(error.message));
  }
})(globalThis);
