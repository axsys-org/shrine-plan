import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
const script = fs.readFileSync(new URL('./goo-dev.js', import.meta.url), 'utf8');
const source = '/0x11/gov/demo', root = '/0x11/app/demo';
function setup(failure = false) {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {value:'', dataset:{}, style:{}, attrs:{}, disabled:false,
      setAttribute(k,v){this.attrs[k]=v;}, getAttribute(k){return this.attrs[k];},
      replaceChildren(...nodes){this.children=nodes;},
      set src(v){this.attrs.src=v;}, get src(){return this.attrs.src;}});
    return elements.get(id);
  };
  let requested='1', completed='1', version='1', installed='1', expected='7';
  const calls=[];
  const snapshot=()=>({units:[{source, home:'/0x11/io/fs/$grove-dev', mount:'grove-dev', files:['demo.grove'], version, requested, completed, ready:!(failure && completed==='2'), diagnostic:failure && completed==='2'?'demo.grove:5: invalid declaration':''}], source, root, installed, expected, occupied:installed!==null, selected:root+'/notes/welcome'});
  const context={URLSearchParams, BigInt, Date, Error, Promise,
    location:{search:'?selected='+root+'/notes/welcome'},history:{replaceState(){}},
    setTimeout:resolve=>setTimeout(resolve,0),
    document:{getElementById:element,createElement:()=>({})},
    fetch:async (url,options)=>{
      const op=url.split('/').at(-1).split('?')[0];
      const data=Object.fromEntries(new URLSearchParams(options.body||''));calls.push({op,data});
      if(op==='rescan'){requested='2';completed='2';if(!failure)version='2';}
      if(op==='replace'){assert.equal(data.expected,'7');installed=version;expected='8';}
      if(op==='delete'){installed=null;expected='9';}
      if(op==='install'){installed=version;expected='10';}
      return {ok:true,text:async()=>JSON.stringify(snapshot())};
    }};
  vm.runInNewContext(script,context);
  return {element,calls};
}
const settle=()=>new Promise(r=>setTimeout(r,10));
for(const fail of [false,true]){
  const {element,calls}=setup(fail);await settle();
  assert.equal(element('root').value,root);
  assert.equal(element('inspector').src,'/views'+root+'/notes/welcome');
  await element('rebuild').onclick();
  assert.equal(calls.some(x=>x.op==='replace'),!fail);
  assert.equal(element('rebuild').disabled,false);
  if(fail){assert.match(element('diagnostic').textContent,/demo.grove:5/);assert.equal(element('status').dataset.error,true);}
  else{
    await element('delete').onclick();assert.equal(element('root').value,root);assert.equal(element('install').disabled,false);
    await element('install').onclick();assert.equal(element('delete').disabled,false);
    element('internals').onclick({preventDefault(){}});assert.match(element('inspector').src,/^\/debug/);
    let navigated;
    element('inspector').contentDocument={addEventListener(name,callback){assert.equal(name,'debug:navigate');navigated=callback;}};
    element('inspector').contentWindow={location:{pathname:'/debug'+root+'/notes/welcome'}};
    await element('inspector').onload();
    element('inspector').contentWindow.location.pathname='/debug'+root+'/notes/second';
    await navigated();
    assert.equal(element('selection').value,root+'/notes/second');
  }
}
console.log('PASS: development controller rebuild, failure preservation, delete/install and navigation');
