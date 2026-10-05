// Grove's seven-part contract, derived from the actual mapped parts. No model
// can add a write that is absent here. Shapes are checked by fit/check-wire.
export const CONTRACT_REVISION='grove.component-contract/1';
export function fieldShape(field){
  const t=field.type;
  if(t==='Enum'||t==='Choice')return {t:'Enum',values:field.choices||[]};
  if(t==='Reference'||t==='Ref')return {t:'Ref',of:{t:'Record',open:true,fields:[]}};
  if(t==='Many')return {t:'Many',of:{t:'Ref',of:{t:'Record',open:true,fields:[]}}};
  if(t==='Image')return {t:'Media',kind:'image'};
  if(['Text','Date','Duration','Number'].includes(t))return {t};
  if(t==='Natural')return {t:'Number'};
  if(t==='Boolean')return {t:'Bool'};
  throw Error('The '+t+' channel needs a declared structural shape before this component can be published.');
}
export function componentContract(parts,schema,name,revision=1){
  const fields=new Map(),intents=[],outputs=[{name:'selection',kind:'selection'}];
  for(const part of parts)for(const [channel,label]of Object.entries(part.mapping||{})){
    if(!label)continue;
    const spec=part.properties?.[channel]||{},field=schema.find(f=>f.slot===spec.slot)||schema.find(f=>f.label===label);
    if(!field)throw Error('The '+label+' field is missing. Keep this component as a draft or choose a source.');
    fields.set(label,{name:label,type:fieldShape(field),required:!['text','label','colour'].includes(channel),role:field.role||'',slot:field.slot});
    if(spec.mode==='input'){
      if(field.writable===false||spec.readonly)throw Error(label+' is read-only at its source.');
      if(!['x','y','width','height','angle','value'].includes(channel))throw Error(channel+' has no declared write inverse.');
      const event=['width','height'].includes(channel)?'resized':channel==='angle'?'rotated':channel==='value'?'changed':'moved';
      intents.push({name:event+'_'+part.id+'_'+channel,part:part.id,channel,event,writes:{op:'set',field:label,slot:field.slot},inverse:{implementation:'grove.encodings/3',channel,axis:spec.axis||{}}});
      if(!outputs.some(o=>o.name===event))outputs.push({name:event,kind:'event'});
    }
  }
  const item={t:'Record',open:true,fields:[...fields.values()]},reference={t:'Ref',of:item};
  return {revision:CONTRACT_REVISION,name,definitionRevision:revision,
    slots:parts.map(p=>({id:p.id,parent:p.parent,name:p.content?.[0]?.text||p.shape||p.part,part:p.shape||p.part})),
    inputs:fields.size?[{name:'items',type:{t:'Many',of:item},required:true}]:[],
    params:[{name:'selection',type:{t:'Many',of:reference}}],
    outputs:outputs.map(o=>({...o,type:o.kind==='selection'?{t:'Many',of:reference}:reference})),
    intents,labels:parts.flatMap(p=>(p.content||[]).map(c=>({part:p.id,content:c.id,text:c.text||''}))),completion:[]};
}
export function contractDescription(contract){
  const fields=contract.inputs[0]?.type.of.fields||[];
  return fields.length?'Many<{'+fields.map(f=>f.name+(f.required?'': '?')+': '+f.type.t).join(', ')+'}>':'No data input';
}
