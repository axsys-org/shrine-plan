// Prepared structural bindings. The choices are built from native schemas;
// either a person or a decision model may select these exact choice identities.
export function requirements(definition){
 const held=new Map();
 for(const part of definition.parts)for(const [channel,name]of Object.entries(part.mapping||{})){
  if(!name)continue;const spec=part.properties?.[channel]||{},prior=held.get(name);
  held.set(name,{name,channels:[...(prior?.channels||[]),channel],spec,writable:spec.mode==='input'||prior?.writable,optional:(prior?.optional??true)&&['text','label','colour'].includes(channel)});
 }
 return [...held.values()];
}
export function choicesFor(requirement,schema){
 const {channels,spec}=requirement;
 const compatible=f=>{
  if(channels.includes('row'))return ['Ref','Reference','Enum','Choice'].includes(f.type);
  if(channels.some(c=>['text','label'].includes(c)))return f.type==='Text';
  if(channels.includes('colour'))return ['Enum','Choice'].includes(f.type)&&(!spec.choices?.length||f.choices?.every(v=>spec.choices.includes(v)));
  return f.type===spec.type||['Number','Natural'].includes(f.type)&&['Number','Natural'].includes(spec.type);
 };
 const options=schema.filter(compatible).map(f=>({id:f.label,label:f.label,value:f.label,score:f.label===requirement.name?3:f.role&&f.role===spec.role?2:1}));
 if(channels.includes('width')&&spec.type==='Duration'){
  for(const start of schema.filter(f=>f.type==='Date'&&f.role==='start'))for(const end of schema.filter(f=>f.type==='Date'&&f.role==='end'))
   options.push({id:JSON.stringify({adapter:'end-minus-start',start:start.label,end:end.label}),label:end.label+' − '+start.label+' · date interval',value:{adapter:'end-minus-start',start:start.label,end:end.label},score:1.8});
 }
 return options.sort((a,b)=>b.score-a.score);
}
export function bindPart(part,template,fieldMap,schema){
 for(const [channel,original]of Object.entries(template.mapping||{})){
  const binding=fieldMap[original],spec=template.properties?.[channel]||{};
  if(!binding){delete part.mapping[channel];part.properties[channel]={mode:'static'};continue;}
  if(typeof binding==='object'){
   if(binding.adapter!=='end-minus-start'||channel!=='width')throw Error('Unsupported binding adapter');
   const start=schema.find(f=>f.label===binding.start),end=schema.find(f=>f.label===binding.end);
   if(start?.type!=='Date'||end?.type!=='Date')throw Error('Date interval endpoints are missing');
   part.mapping[channel]=original;part.properties[channel]={...spec,field:original,slot:undefined,type:'Duration',readonly:end.writable===false,adapter:{kind:'end-minus-start',start:start.label,end:end.label,revision:1}};
  }else{
   const field=schema.find(f=>f.label===binding);if(!field)throw Error('The bound field is missing');
   part.mapping[channel]=binding;part.properties[channel]={...spec,field:binding,slot:field.slot,type:field.type,role:field.role,choices:field.choices,readonly:field.writable===false};
  }
 }
 const adapter=part.properties?.width?.adapter;
 if(adapter&&schema.find(f=>f.label===adapter.end)?.writable===false)part.properties.x.readonly=true;
 return part;
}
