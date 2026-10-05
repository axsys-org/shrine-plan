function makerPorts(root,node){
 let contract;try{contract=componentContract(active(),nativeNode(collection(root))?.properties||[],title(root));}catch{return;}
 for(const side of ['in','out']){
  const nub=element('button',side==='in'?'←':'→','port-nub '+side);nub.setAttribute('aria-label','Pull '+(side==='in'?'input':'output')+' ports');
  const expose=()=>{root.exposedPorts={...root.exposedPorts,[side]:true};save(root);renderItem(root,true);log('Exposed '+(side==='in'?'typed inputs':'typed outputs'),'local','Ports derived from the component contract');};
  nub.onclick=expose;nub.onpointerdown=e=>{e.stopPropagation();e.preventDefault();const x=e.clientX;nub.setPointerCapture(e.pointerId);nub.onpointermove=move=>{move.stopPropagation();nub.style.transform='translateX('+(move.clientX-x)+'px)';};nub.onpointerup=up=>{up.stopPropagation();nub.onpointermove=null;nub.style.transform='';if(Math.abs(up.clientX-x)>12)expose();};};node.append(nub);
  if(root.exposedPorts?.[side]){const ports=element('div',undefined,'exposed-ports '+side);for(const port of side==='in'?contract.inputs:contract.outputs){const chip=element('button',port.name,side==='in'?'source-port':'output-port');chip.title=JSON.stringify(port.type);chip.dataset.port=port.name;if(side==='in'){chip.onclick=()=>say('Drop a native collection on this component');}else fieldDraggable(chip,{sourceId:root.id,property:port.name});ports.append(chip);}node.append(ports);}
 }
}
