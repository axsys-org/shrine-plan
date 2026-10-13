'use strict';
(function(host){
  const VERSION=1;
  const finite=(n,k)=>{if(!Number.isFinite(n)||n<0)throw Error(k+' must be finite and nonnegative');return n;};
  function validate(tree) {
    const ids = new Set(), active = new Set();
    function visit(n) {
      if (!n || typeof n !== 'object' || active.has(n)) throw Error('Invalid or cyclic node');
      if (typeof n.id !== 'string' || !n.id || ids.has(n.id)) throw Error('Node IDs must be unique and nonempty');
      if (typeof n.slot !== 'string') throw Error('Slots must be opaque strings');
      if (![0,1,2].includes(n.optional ?? 0)) throw Error('Optional rank must be 0–2');
      if (!['group','text','button','input','code','avatar','presence','media','bar'].includes(n.kind)) throw Error('Unsupported primitive: ' + n.kind);
      if (n.src !== undefined && (typeof n.src !== 'string' || !['avatar','media'].includes(n.kind))) throw Error('Invalid image payload');
      if (n.grow !== undefined && ![0,1].includes(n.grow)) throw Error('Grow must be 0 or 1');
      for (const k of ['text','label','optionLabel']) if (n[k] !== undefined && typeof n[k] !== 'string') throw Error(k+' must be a string');
      for (const k of ['primary','toggle']) if (n[k] !== undefined && typeof n[k] !== 'boolean') throw Error(k+' must be a boolean');
      for (const k of ['maxIdeal','value','max']) if (n[k] !== undefined) finite(n[k], k);
      if(n.kind==='bar' && n.value!==undefined && (!(n.max>0) || n.value>n.max)) throw Error('Progress requires max > 0 and 0 <= value <= max');
      ids.add(n.id); active.add(n);
      if (n.kind === 'group') {
        if (!['stack','flow'].includes(n.layout) || !Array.isArray(n.children)) throw Error('Invalid group layout/children');
        if (n.grow !== undefined && ![0,1].includes(n.grow)) throw Error('Group grow must be 0 or 1');
        n.children.forEach(visit);
      } else if (n.children !== undefined) throw Error('Leaf cannot have children');
      active.delete(n);
    }
    if (tree !== null) { visit(tree); checkEdges(tree, null); }
    function checkEdges(n, expected) {
      if (n.after !== expected && JSON.stringify(n.after)!==JSON.stringify(expected)) throw Error('Invalid outgoing edge');
      if(n.origin!==null && n.origin!==undefined && (!Number.isInteger(n.origin.line)||n.origin.line<1||!Number.isInteger(n.origin.column)||n.origin.column<1)) throw Error('Invalid source location');
      if(n.kind!=='group')return;
      if(!n.children.length)throw Error('Empty semantic group');
      n.children.forEach((a,i)=>{
        const b=n.children[i+1],e=a.after;
        if(!b) {if(e!==null)throw Error('Final child has an edge');}
        else {
          if(!e||e.parent!==n.id||e.parentSlot!==n.slot||e.leftId!==a.id||e.rightId!==b.id||e.left!==a.slot||e.right!==b.slot)throw Error('Invalid sibling edge ownership');
          if(!['attached','tight','related','normal','loose','separate'].includes(e.bind)||!['exact','fallback','uniform'].includes(e.source))throw Error('Invalid edge binding');
          if(e.rule!==null&&(!Number.isInteger(e.rule)||e.rule<1))throw Error('Invalid rule ID');
          if(e.source==='exact'&&e.rule===null||e.source==='fallback'&&e.rule!==null||e.source==='uniform'&&e.bind!=='normal')throw Error('Invalid edge provenance');
        }
        checkEdges(a,e);
      });
    }
  }

  function decodeInput(config) {
    if(!config||config.version!==VERSION)throw Error('Unsupported compiler protocol version');
    if(typeof config.viewPath!=='string'||!config.viewPath.startsWith('/'))throw Error('Invalid view path');
    validate(config.tree);return config;
  }

  const api={VERSION,finite,validate,decodeInput};
  if(typeof module!=="undefined"&&module.exports)module.exports=api;else host.GooProtocol=api;
})(typeof window==='undefined'?globalThis:window);
