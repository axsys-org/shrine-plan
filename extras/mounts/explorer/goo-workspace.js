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
    let revision=0, request, controller, lifetime;
    const report = message => { controller.status.textContent = message; };
    const refresh = async () => {
      const current=++revision; request?.abort(); request=new AbortController();
      try {
        const data=await root.GooActions.load(host.dataset.target,{workspace:host.dataset.workspace,view:host.dataset.view,context:root.GooActions.context(host),signal:request.signal});
        if(current!==revision) return;
        const nextLifetime=JSON.stringify([data.snapshot.subject||data.snapshot.target,data.snapshot.life,data.view]);
        if(lifetime && lifetime!==nextLifetime && !controller.session.closed) {
          if(!(await controller.close()) || current!==revision) return;
        }
        if(controller.session.closed) controller=createController();
        lifetime=nextLifetime;
        await controller.update(data.description,data.snapshot,{signal:request.signal,onApplied:()=>{
          if(current!==revision) return;
          root.GooInspection?.record(host,data,()=>controller.inspectionState());
          host.dataset.renderContext=JSON.stringify(data.context); host.dataset.profileRevision=data.profile.revision;
        }});
      } catch(error) { if(error.name!=='AbortError' && current===revision) report(error.message); }
    };
    const createController = () => new root.GooPanes(host, {
      target:host.dataset.target, view:host.dataset.view, workspace:host.dataset.workspace, operations, report,
      navigate: path => { const url = new URL(root.location.href); url.searchParams.set('path',path); root.location.assign(url); },
      refresh
    });
    controller=createController();
    root.GooActions.observe(host,refresh);
    refresh();
  }
})(globalThis);
