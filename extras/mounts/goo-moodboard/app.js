/* Board chrome delegates every edit to ordinary, admitted Goo controls. */
(() => {
  'use strict';
  const main = document.querySelector('main[data-target]');
  if (!main) return;
  document.body.classList.add('moodboard-app');
  const header = document.querySelector('body>header');
  const nav = document.createElement('nav');
  nav.setAttribute('aria-label', 'Add to board');
  for (const [kind, label] of [['note', '+ Note'], ['image', '+ Image'], ['presentation', '+ Live Goo']]) {
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = label;
    button.onclick = () => fill('Add card', {tag:kind, title:kind === 'presentation' ? 'Live presentation' : 'Untitled', value:kind === 'presentation' ? main.dataset.target.replace(/\/board$/, '/brief') : kind === 'image' ? '/goo-moodboard/study.svg' : '', slot:'/sys/slot/content'}, true);
    nav.append(button);
  }
  header.append(nav);
  const rail = document.createElement('aside'); rail.className = 'board-index';
  const heading = document.createElement('h2'); heading.textContent = 'ON THIS BOARD';
  const list = document.createElement('div'); list.setAttribute('aria-label', 'Cards');
  const hint = document.createElement('p'); hint.textContent = 'Drag a Move handle, or click it for arrow controls. Pan the empty canvas with two fingers; Alt-scroll to zoom.';
  rail.append(heading, list, hint); main.before(rail);
  const status = document.createElement('p'); status.className = 'board-status'; status.setAttribute('role','status'); main.after(status);
  let snapshot, selected, request = 0, queued = new Map(), timer;
  function form(label) {
    return [...main.querySelectorAll('button')].find(b => b.textContent.trim() === label)?.closest('.goo-native');
  }
  function fill(label, values, focus = false) {
    queued.set(label, {values, focus}); applyFill(label);
  }
  function applyFill(label) {
    const scope = form(label), pending = queued.get(label);
    if (!pending || !scope?.dataset.renderKey || scope.dataset.loadingKey) return;
    for (const input of scope.querySelectorAll('input[data-input-slot]')) {
      const key = input.dataset.inputSlot.split('/').at(-1);
      if (Object.hasOwn(pending.values,key)) {
        input.value = pending.values[key]; input.dispatchEvent(new Event('input',{bubbles:true}));
      }
    }
    queued.delete(label);
    if (pending.focus) scope.querySelector('input')?.focus({preventScroll:true});
    scope.scrollIntoView({block:'nearest'});
  }
  function decorate() {
    for (const node of main.querySelectorAll('goo-patch-node')) {
      const card = snapshot?.cards.find(card => card.id === node.dataset.key);
      if (card && node.dataset.kind !== card.kind) node.dataset.kind = card.kind;
    }
    for (const label of queued.keys()) applyFill(label);
  }
  function choose(id, reveal = false) {
    const card = snapshot?.cards.find(card => card.id === id); if (!card) return;
    selected = id; fill('Save card', card); fill('Delete card', {id});
    for (const button of list.querySelectorAll('button')) button.setAttribute('aria-pressed',String(button.dataset.id === id));
    if (reveal) {
      const node = main.querySelector(`goo-patch-node[data-key="${id}"]`);
      node?.querySelector('[data-patch-select]')?.click();
      main.querySelector('goo-patch')?.reveal([{kind:'node',node:id,lifetime:`card:${id}`}]);
    }
  }
  async function refresh() {
    const seq = ++request, response = await fetch('/goo-moodboard/state',{cache:'no-store'});
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json(); if (seq !== request) return;
    const changed = JSON.stringify(data.cards) !== JSON.stringify(snapshot?.cards);
    snapshot = data;
    status.textContent = `${data.cards.length} cards · saved in Shrine · revision ${data.revision}`;
    if (changed) {
      list.replaceChildren(...data.cards.map(card => {
        const b = document.createElement('button'); b.type='button'; b.dataset.id=card.id;
        b.textContent=`${card.kind === 'presentation' ? '↗' : card.kind === 'image' ? '▧' : '≡'}  ${card.title}`;
        b.setAttribute('aria-pressed',String(card.id===selected)); b.onclick=()=>choose(card.id,true); return b;
      }));
    }
    decorate();
  }
  main.addEventListener('goo-patch-selection-accepted', event => {
    const target = event.detail.find(target=>target.kind==='node'); if(target) choose(target.node);
  });
  const observer = new MutationObserver(() => { clearTimeout(timer);timer=setTimeout(decorate,40); });
  observer.observe(main,{childList:true,subtree:true,attributes:true,attributeFilter:['data-render-key','data-loading-key']});
  const stop = GooActions.subscribeOutcomes(() => refresh().catch(error=>{status.textContent=error.message;}));
  addEventListener('pagehide',()=>{observer.disconnect();stop?.();clearTimeout(timer);},{once:true});
  refresh().catch(error=>{status.textContent=error.message;});
})();
