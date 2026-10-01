(function(root) {
  'use strict';
  const SYNTHETIC = '/sys/slot/synthetic';
  function path(value) {
    if (typeof value !== 'string' || !value.startsWith('/') || /[\u0000-\u001f\u007f?#\\]/.test(value)) throw new Error('Enter an absolute namespace path.');
    value = value.replace(/\/+$/, '') || '/';
    if (value !== '/' && value.slice(1).split('/').some(s => !s || s === '.' || s === '..')) throw new Error('Empty, . and .. path segments are not supported.');
    return value;
  }
  const urlPath = value => path(value).split('/').map(encodeURIComponent).join('/');
  const link = value => '/goo-inspector?' + new URLSearchParams({path:path(value)});
  const parent = value => path(value).split('/').slice(0,-1).join('/') || '/';
  function composition(source, usable) {
    const native = html => ({kind:'native',html,controls:[],children:[]});
    const pane = (key, children) => ({kind:'pane',key,children});
    const details = {kind:'deck',key:'/inspection',children:[
      pane('/Values', [native('<section id="current-values"></section>'), ...(usable ? [{kind:'follow',key:'/value',selection:'/object',slot:SYNTHETIC,children:[]}] : [])]),
      pane('/Views',[native('<section id="view-catalog"></section>')]),
      pane('/Evidence',[native('<section id="evidence"></section>')])
    ]};
    const browser = pane('/Namespace', [native('<section id="navigation"></section>'), ...(usable ? [{kind:'list',key:'/children',source,selection:'/object',slot:'/sys/slot/inspector_summary',children:[]}] : [])]);
    const body = [{kind:'split',children:[browser,details]}];
    return [pane('/Inspector', usable ? [{kind:'selection',key:'/object',source,children:body}] : body)];
  }
  function descriptor(value, requested) {
    if (!value || value.version !== 1 || path(value.path) !== path(requested) || !Array.isArray(value.children) || value.children.length > 40 || !value.collection || typeof value.hasRecord !== 'boolean') throw new Error('Invalid inspection read descriptor.');
    const prefix = requested === '/' ? '/' : requested + '/';
    const seen = new Set();
    for (const child of value.children) {
      const p = path(child.path);
      if (!p.startsWith(prefix) || !p.slice(prefix.length) || p.slice(prefix.length).includes('/') || seen.has(p)) throw new Error('Invalid child reference.');
      seen.add(p);
    }
    for (const key of ['epoch','childCount','slotCount']) {
      if (!(key === 'epoch' && value.collection[key] === null) && (typeof value.collection[key] !== 'string' || !/^(0|[1-9][0-9]*)$/.test(value.collection[key]))) throw new Error('Invalid observation evidence.');
    }
    for (const key of ['nextChildren','nextSlots']) if (value.collection[key] !== null && (typeof value.collection[key] !== 'string' || !value.collection[key] || value.collection.epoch === null)) throw new Error('Invalid continuation.');
    return value;
  }
  // Each read carries its own generation; obsolete completions cannot publish.
  class Generation {
    constructor() { this.value = 0; }
    next() { return ++this.value; }
    current(ticket) { return ticket === this.value; }
  }
  const api = {SYNTHETIC,path,urlPath,link,parent,composition,descriptor,Generation};
  root.GooInspector = api;
  if (typeof module !== 'undefined') module.exports = api;
})(globalThis);
