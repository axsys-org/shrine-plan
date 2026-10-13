// End-to-end development gate: actual Grove publication, namespace, HTML and actions.
// No fabricated /goo/render or /goo/act responses.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const [base,mash,output='/tmp/goo-patch-live']=process.argv.slice(2);
const require=createRequire(resolve(mash,'tests/integration/package.json'));
const engines=require('@playwright/test');
const results=[];await mkdir(output,{recursive:true});
for(const name of (process.env.BROWSERS||'chromium,firefox,webkit').split(',')) {
 const browser=await engines[name].launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1100}});
 const errors=[],actions=[];page.setDefaultTimeout(30000);
 page.on('pageerror',error=>errors.push(error.message));
 page.on('request',request=>{if(new URL(request.url()).pathname==='/goo/act')actions.push(request.postData());});
 try {
  await page.goto(base+'/views/0x11/app/patch_demo/board');
  await page.waitForFunction(()=>document.querySelector('goo-patch')?.installedScene);
  const scene=()=>page.locator('goo-patch').evaluate(surface=>surface.installedScene);
  const initial=await scene();const x=initial.nodes.find(n=>n.key==='source').rect.x;
  await page.getByRole('button',{name:'Move source right',exact:true}).click();
  await page.waitForFunction(x=>document.querySelector('goo-patch')?.installedScene.nodes.find(n=>n.key==='source').rect.x===x+10,x);
  await page.waitForFunction(()=>document.querySelector('goo-patch').pending.size===0);
  const graphical=new URLSearchParams(actions.at(-1));
  // A reload must read persisted domain state rather than retain a browser preview.
  await page.reload();await page.waitForFunction(()=>document.querySelector('goo-patch')?.installedScene);
  assert.equal((await scene()).nodes.find(n=>n.key==='source').rect.x,x+10);
  await page.getByRole('button',{name:'source out',exact:true}).click();
  await page.getByRole('button',{name:'sink in',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('goo-patch')?.installedScene.connections.length===1);
  await page.waitForFunction(()=>document.querySelector('goo-patch').pending.size===0);
  assert.equal((await scene()).connections[0].segments[0].commands.length,2);
  await page.getByRole('button',{name:'Reconnect wire to',exact:true}).click();
  await page.getByRole('button',{name:'transform in',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('goo-patch')?.installedScene.connections[0]?.endpoints[1].port.node==='transform');
  await page.getByRole('button',{name:'Disconnect wire',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('goo-patch')?.installedScene.connections.length===0);
  const current=await scene();const node=current.nodes.find(n=>n.key==='source');
  const args={kind:'move-nodes',nodes:[{target:{kind:'node',node:node.key,lifetime:node.lifetime},baseOrigin:{x:node.rect.x,y:node.rect.y},proposedOrigin:{x:node.rect.x+10,y:node.rect.y}}]};
  const ordinary=page.locator('[data-patch-operation="move-nodes"]');
  await ordinary.locator('input').fill(JSON.stringify(args));
  await ordinary.getByRole('button',{name:'Apply move-nodes',exact:true}).click();
  await page.waitForFunction(x=>document.querySelector('goo-patch')?.installedScene.nodes.find(n=>n.key==='source').rect.x===x+20,x);
  const native=new URLSearchParams(actions.at(-1));
  for(const field of ['target','subject','view','control'])assert.equal(native.get(field),graphical.get(field),field);
  assert.notEqual(native.get('invocation'),graphical.get('invocation'));
  const status=await page.request.get(base+'/goo/status?target='+encodeURIComponent(native.get('target')));
  const snapshot=await status.json();
  assert(snapshot.coveredOperationIds.includes(native.get('invocation')));
  const before=await scene();
  const settled=before.nodes.find(n=>n.key==='source');
  args.nodes[0].baseOrigin={x:settled.rect.x,y:settled.rect.y};
  args.nodes[0].proposedOrigin={x:settled.rect.x+10,y:settled.rect.y};
  const tampered=new URLSearchParams(native);tampered.set('invocation',crypto.randomUUID());
  for(const field of ['expected','displayed','publication'])tampered.set(field,snapshot[field]);
  const input=[...tampered.keys()].find(key=>key.startsWith('input:'));
  args.nodes[0].target.lifetime='retired-lifetime';tampered.set(input,JSON.stringify(args));
  const rejected=await page.request.post(base+'/goo/act',{form:Object.fromEntries(tampered)});
  assert.equal(rejected.status(),409);
  // Independently alter receiver and binding with otherwise current arguments.
  args.nodes[0].target.lifetime=settled.lifetime;
  tampered.set(input,JSON.stringify(args));
  for(const [field,value] of [['subject','/0x11/app/patch_demo/missing'],['control','999.999']]) {
   const altered=new URLSearchParams(tampered);altered.set(field,value);altered.set('invocation',crypto.randomUUID());
   const response=await page.request.post(base+'/goo/act',{form:Object.fromEntries(altered)});
   assert.equal(response.status(),409,field+' tamper rejection');
  }
  const receipt=await page.request.get(base+'/goo/operation-status?'+new URLSearchParams({target:native.get('target'),invocation:native.get('invocation')}));
  assert.equal((await receipt.json()).outcome,'accepted');
  await page.reload();await page.waitForFunction(()=>document.querySelector('goo-patch')?.installedScene);
  assert.equal((await scene()).nodes.find(n=>n.key==='source').rect.x,before.nodes.find(n=>n.key==='source').rect.x);
  assert.deepEqual(errors,[]);
  await page.screenshot({path:resolve(output,name+'.png'),fullPage:true});
  results.push({engine:name,version:browser.version(),actions:actions.length,passed:true});
  console.log(JSON.stringify(results.at(-1)));
 }catch(error){await page.screenshot({path:resolve(output,name+'-failure.png'),fullPage:true});console.error(await page.locator('body').innerText());throw error;}
 finally{await browser.close();}
}
await writeFile(resolve(output,'results.json'),JSON.stringify(results,null,2)+'\n');
