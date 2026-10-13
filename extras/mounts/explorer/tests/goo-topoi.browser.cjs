const assert = require('node:assert/strict');

// Called by the live Explorer integration gate with the actual Mash elements
// and Goo client scripts loaded. No DOM or custom-element test doubles.
async function exerciseTopoi(page) {
  await page.evaluate(async () => {
    await Promise.all(['goo-tree','goo-tidy-tree'].map(name=>customElements.whenDefined(name)));
    const host=document.createElement('section'); host.id='focus-contract';
    const outside=document.createElement('button'); outside.id='focus-outside'; outside.textContent='Outside';
    document.body.append(host,outside);
    const member=(key,parent=null,life='1',status='available')=>({key,parent,life,status,subject:`/${key}`,source:'/focus',sourceLife:'1',type:'namespace-record',expected:'1'});
    const session=new GooSession(), labels=new Map(); let renderer='list', intentCount=0;
    const initial=[member('A'),member('B','A'),member('C','B')];
    const description=members=>[{kind:'pane',key:'focus',children:[{kind:'selection',key:'chosen',source:{id:'/focus',life:'1',type:'namespace-record',members},initial:initial[1],children:[{kind:'topos',key:'members',renderer,selection:'chosen'}]}]}];
    await session.reconcile(description(initial));
    const state=[...session.owners.values()].find(owner=>owner.kind==='topos');
    const selection=session.get(state.selection);
    const topoi=new GooTopoi.Topos(host,'members',m=>{intentCount++; void session.deliver(session.intent(selection.ref,m));},m=>session.focus(state.ref,m));
    session.subscribe(()=>topoi.paint(session.read(state.selection).accepted,state.focus));
    const content=m=>{
      const key=`${m.key}:${m.life}`;
      if(!labels.has(key)) {
        const label=document.createElement('span'); label.textContent=m.key;
        if(m.key==='B') {const input=document.createElement('input');input.value='draft';input.setAttribute('aria-label','Member draft');label.append(input);}
        labels.set(key,label);
      }
      return labels.get(key);
    };
    const reconcile=async (mode,members)=>{
      renderer=mode;
      await session.reconcile(description(members));
      topoi.reconcile(mode,members,content); topoi.paint(session.read(state.selection).accepted,state.focus);
      await topoi.ready;
      // WA expansion and d3 layout finish after their first update promise.
      for(let i=0;i<3;i++) await new Promise(resolve=>requestAnimationFrame(resolve));
    };
    window.focusContract={host,outside,member,session,state,selection,topoi,reconcile,initial,get intentCount(){return intentCount;}};
    await reconcile('list',initial);
  });
  const snapshot=()=>page.evaluate(()=>{
    const c=focusContract;
    return {active:document.activeElement?.closest('.goo-topos-member')?.dataset.key||null,
      focused:c.state.focus?.key||null,accepted:c.selection.accepted?.key||null,
      acceptedLife:c.selection.accepted?.life||null,intents:c.intentCount,
      tabs:[...c.topoi.items].filter(([,item])=>item.tabIndex===0).map(([key])=>key),
      containerTab:c.topoi.tree.tabIndex};
  });
  assert.equal((await snapshot()).intents,0);
  await page.evaluate(()=>focusContract.topoi.items.get('C').focus());
  for(const renderer of ['diagram_tree','list_tree','list']) {
    await page.evaluate(renderer=>focusContract.reconcile(renderer,focusContract.initial),renderer);
    const state=await snapshot();
    assert.equal(state.active,'C',`${renderer} must restore the focused member`);
    assert.deepEqual(state.tabs,['C']); assert.equal(state.accepted,'B'); assert.equal(state.intents,0);
    if(renderer==='list_tree') assert.equal(state.containerTab,-1);
  }
  // A retained native input is the same element, with its caret and buffer,
  // even when its containing renderer changes.
  await page.evaluate(()=>{
    const input=focusContract.topoi.items.get('B').querySelector('input');
    window.retainedDraft=input; input.focus(); input.value='unsaved text'; input.setSelectionRange(2,6);
  });
  await page.evaluate(()=>focusContract.reconcile('list_tree',focusContract.initial));
  assert.deepEqual(await page.evaluate(()=>({same:document.activeElement===retainedDraft,value:retainedDraft.value,start:retainedDraft.selectionStart,end:retainedDraft.selectionEnd})),
    {same:true,value:'unsaved text',start:2,end:6});
  await page.evaluate(async()=>{
    focusContract.topoi.items.get('C').focus();
    await focusContract.reconcile('list_tree',focusContract.initial.slice(0,2));
  });
  let state=await snapshot(); assert.equal(state.active,'A'); assert.deepEqual(state.tabs,['A']); assert.equal(state.accepted,'B');
  await page.evaluate(async()=>{
    const c=focusContract;
    await c.reconcile('list_tree',[c.member('A',null,'1','unavailable'),c.member('B','A')]);
  });
  state=await snapshot(); assert.equal(state.active,'B'); assert.deepEqual(state.tabs,['B']); assert.equal(state.accepted,'B');
  await page.evaluate(async()=>{
    const c=focusContract;
    await c.reconcile('diagram_tree',[c.member('A'),c.member('B','A','2')]);
  });
  state=await snapshot(); assert.equal(state.active,'A'); assert.deepEqual(state.tabs,['A']); assert.equal(state.acceptedLife,'1'); assert.equal(state.intents,0);
  await page.evaluate(async()=>{
    const c=focusContract;c.outside.focus();
    await c.reconcile('list_tree',[c.member('A'),c.member('B','A','2')]);
  });
  assert.equal(await page.evaluate(()=>document.activeElement===focusContract.outside),true);
  state=await snapshot(); assert.deepEqual(state.tabs,['A']); assert.equal(state.containerTab,-1); assert.equal(state.intents,0);
  await page.evaluate(()=>{focusContract.host.remove();focusContract.outside.remove();delete window.focusContract;delete window.retainedDraft;});
  return {cases:9};
}

module.exports={exerciseTopoi};
