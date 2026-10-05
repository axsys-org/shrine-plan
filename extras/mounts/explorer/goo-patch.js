/* Goo pane realization for server-prepared patches. No domain model or layout. */
(function(root) {
  'use strict';
  const key = target => JSON.stringify(target);
  function population(node) {
    const scene=node.scene, records=[];
    const add=(target,record)=>records.push({key:key(target),subject:record.selectorRef,life:record.lifetime,
      source:node.key,sourceLife:scene.header.encounter,type:'patch-occurrence',axis:'z',status:'available',target});
    for(const n of scene.nodes) {
      add({kind:'node',node:n.key,lifetime:n.lifetime},n);
      for(const p of n.ports)add({kind:'port',node:n.key,nodeLifetime:n.lifetime,port:p.key,lifetime:p.lifetime},p);
    }
    for(const c of scene.connections) {
      add({kind:'connection',connection:c.key,lifetime:c.lifetime},c);
      for(const p of c.parts)add({kind:'connection-part',connection:c.key,connectionLifetime:c.lifetime,part:p.key,lifetime:p.lifetime},p);
    }
    return [{kind:'selection',key:JSON.stringify(['patch-selection',node.key,node.scene.header.encounter]),multiple:true,
      source:{id:node.key,life:scene.header.encounter,type:'patch-occurrence',members:records},children:[]}];
  }
  function render(panes,node,element,scopes,owner) {
    const api=root.GooPatchComponents;
    if(!api)throw new Error('Patch components are unavailable. Build Explorer with the patch-enabled Mash package.');
    let work=panes.nativeWorks.get(element);
    if(!work) {
      work={id:JSON.stringify(['patch',owner,node.key]),kind:'patch',live:true,inputs:new Map(),generation:0,
        encounter:{id:node.scene.header.encounter},ref:panes.session.owners.get(owner)?.ref,wrapperKey:element.gooWrapperKey};
      panes.nativeWorks.set(element,work);panes.registerWork(work,element);
    }
    if(work.encounter.id!==node.scene.header.encounter)throw new Error('Patch encounter changed without retirement.');
    let surface=work.surface;
    const selection=panes.state(owner,'selection',JSON.stringify(['patch-selection',node.key,node.scene.header.encounter]));
    if(!surface) {
      surface=document.createElement('goo-patch');work.surface=surface;
      surface.setAttribute('aria-label',node.label||node.key);surface.style.cssText='display:block;width:100%;height:600px';
      work.operationsHost=document.createElement("div");
      element.replaceChildren(surface,work.operationsHost);work.offers=new Map();
      api.attachGooPatch(surface,root.GooActions,panes,work,work.offers,{
        select: async request=>{
          try {
            const members=request.targets.map(target=>selection.members.get(key(target)));
            if(members.some(member=>!member))throw new Error('Selection target is unavailable.');
            await panes.session.deliver(panes.session.intentMany(selection.ref,members,request.mode));
            surface.setSelection(panes.session.read(selection.ref).acceptedMany.map(member=>member.target));
          }catch(error){panes.context.report(error.message);}
        },
        // No offer means unknown compatibility; the bound action remains authority.
        query:()=>{},
        repair:code=>{panes.context.report(`Patch presentation: ${code}`);
          if(work.repairAt!==panes.snapshot.projectionSeq){work.repairAt=panes.snapshot.projectionSeq;queueMicrotask(()=>panes.context.refresh?.());}
        },
        reconcileOperation:async operationId=>{
          const response=await fetch(`/goo/operation-status?${new URLSearchParams({target:panes.context.target,invocation:operationId})}`,{cache:'no-store'});
          if(!response.ok)return;
          const receipt=await response.json();root.GooActions.recordOutcome(operationId,receipt.outcome,receipt);
          if(receipt.outcome==='accepted')await panes.context.refresh?.();
        }
      });
    }
    const scene={...node.scene,header:{...node.scene.header,surface:work.id,encounter:String(work.encounter.id),viewSeq:panes.snapshot.projectionSeq}};
    const nodes=new Map(),connections=new Map();
    for(const content of node.contents) {
      if(content.kind==='patch_node')nodes.set(content.key,content);
      if(content.kind==='patch_connection')connections.set(content.key,content);
    }
    const contextFor=data=>panes.actionContext(panes.context.target,panes.context.view,panes.snapshot,data.controls,scopes,work);
    const result=surface.admit({scene,dom:{kind:'complete'},coveredOperationIds:panes.snapshot.coveredOperationIds||[],prepare:()=>{
      const plan=api.prepareGooDOM(root.GooActions,surface,scene,{nodes,connections,actionContext:(_key,_kind,data)=>contextFor(data)});
      const operations=node.contents.filter(content=>content.kind==='patch_operation');
      const stages=operations.map(content=>{
        const container=work.operationElements?.get(content.key)||document.createElement('div');container.dataset.patchOperation=content.key;
        const prepared=root.GooActions.prepareMount(container,content,!!container.isConnected,false);
        return {content,container,prepared};
      });
      return {proposed:plan.proposed,commit(){
        plan.commit();
        work.table ||= document.createElement('div');work.table.slot='controls';
        work.table.style.cssText='position:absolute;bottom:24px;right:0;max-height:100px;overflow:auto;background:Canvas';
        work.table.innerHTML=node.controlsHTML;if(!work.table.isConnected)surface.append(work.table);
        work.offers.clear();work.operationElements ||= new Map();
        const desired=new Set(stages.map(stage=>stage.content.key));
        for(const [id,container] of work.operationElements)if(!desired.has(id)){container.remove();work.operationElements.delete(id);}
        for(const {content,container,prepared} of stages){
          prepared.commit();if(!container.isConnected)work.operationsHost.append(container);
          work.operationElements.set(content.key,container);
          const context=contextFor(content);root.GooActions.bind(container,context);
          const offer=node.offerBindings.find(offer=>offer.kind===content.key);
          if(!offer)throw new Error('Missing offered patch binding');
          work.offers.set(content.key,{...offer,context,container});
        }
      }};
    }});
    surface.setSelection(panes.session.read(selection.ref).acceptedMany.map(member=>member.target));
    if(result==='rejected')panes.context.report('Patch projection rejected; previous scene retained.');
  }
  root.GooPatchHost={population,render};
})(globalThis);
