/* A topos presents membership; the selection port remains the choice authority. */
(function(root) {
  'use strict';
  const renderers = new Set(['list', 'diagram_tree', 'list_tree']);
  function topology(members, renderer) {
    if (!renderers.has(renderer)) throw new Error('Unknown topos renderer');
    const byKey = new Map();
    for (const member of members) {
      if (byKey.has(member.key)) throw new Error('Duplicate topos member');
      byKey.set(member.key, member);
    }
    if (renderer === 'list' || !members.length) return byKey;
    if (members.filter(m => m.parent == null).length !== 1) throw new Error('Tree topoi require one root; use selection topology = "tree".');
    for (const member of members) {
      const seen = new Set([member.key]); let parent = member.parent;
      while (parent != null) {
        if (!byKey.has(parent)) throw new Error('Missing topos parent');
        if (seen.has(parent)) throw new Error('Cyclic topos parent relation');
        seen.add(parent); parent = byKey.get(parent).parent;
      }
    }
    return byKey;
  }
  const interactive = event => !!event.target.closest('button,a,input,select,textarea,summary,[contenteditable],[data-goo-tree-interactive]');
  class Topos {
    constructor(host, key, select, focus) {
      this.host=host; this.key=key; this.select=select; this.focus=focus;
      this.items=new Map(); this.expanded=new Set(); this.lives=new Map(); this.renderer=null; this.members=new Map();
    }
    reconcile(renderer, members, content) {
      const next = topology(members, renderer);
      if (this.renderer !== renderer) {
        this.body?.remove(); this.items.clear(); this.renderer=renderer;
        this.body=document.createElement(renderer === 'diagram_tree' ? 'goo-tidy-tree' : renderer === 'list_tree' ? 'goo-tree' : 'div');
        this.body.className='goo-topos-members'; this.host.append(this.body);
        if (renderer === 'list_tree') {
          this.body.setAttribute('selection','single');
          this.tree=document.createElement('wa-tree'); this.tree.setAttribute('aria-label',this.key); this.body.append(this.tree);
          this.body.addEventListener('goo-tree-select',event=> {
            const key=event.detail.subjects[0], member=this.members.get(key);
            if (member?.status === 'available') this.select(member);
            this.paint(this.choice,this.focused);
          });
          this.body.addEventListener('goo-tree-toggle',event=> {
            event.detail.expanded ? this.expanded.add(event.detail.subject) : this.expanded.delete(event.detail.subject);
          });
        } else {
          this.tree=this.body;
          this.body.setAttribute('role','listbox'); this.body.setAttribute('aria-label',this.key);
          if (renderer === 'diagram_tree') { this.body.setAttribute('zoom',''); this.body.setAttribute('fit',''); }
        }
      }
      this.members=next;
      for(const key of this.lives.keys()) if(!next.has(key)) { this.lives.delete(key); this.expanded.delete(key); }
      for(const member of members) if(this.lives.get(member.key)!==member.life) {
        this.expanded.delete(member.key); if(member.parent==null) this.expanded.add(member.key);
        this.lives.set(member.key,member.life);
      }
      for (const [key,item] of this.items) if (!next.has(key)) { item.remove(); this.items.delete(key); this.expanded.delete(key); }
      for (const member of members) {
        let item=this.items.get(member.key);
        if (item && item.dataset.life !== member.life) { item.remove(); this.items.delete(member.key); item=null; }
        if (!item) {
          item=document.createElement(renderer === 'diagram_tree' ? 'goo-tree-node' : renderer === 'list_tree' ? 'wa-tree-item' : 'div');
          item.dataset.life=member.life; item.dataset.key=member.key;
          item.setAttribute('subject',member.key); item.classList.add('goo-topos-member');
          this.items.set(member.key,item);
          item.addEventListener('focusin',event=> {
            if(renderer==='list_tree' && event.composedPath?.().find(n=>n.tagName?.toLowerCase()==='wa-tree-item')!==item) return;
            const m=this.members.get(member.key); if(m?.status==='available') this.focus(m);
          });
          if (renderer !== 'list_tree') {
            item.setAttribute('role','option');
            item.addEventListener('click',event=> { if (!interactive(event)) this.choose(member.key); });
            item.addEventListener('keydown',event=> {
              if (interactive(event)) return;
              if (event.key==='Enter' || event.key===' ') { event.preventDefault(); this.choose(member.key); }
              if (['ArrowDown','ArrowUp','Home','End'].includes(event.key)) {
                event.preventDefault(); const keys=[...this.members.values()].filter(m=>m.status==='available').map(m=>m.key), at=keys.indexOf(member.key);
                const next=event.key==='Home'?0:event.key==='End'?keys.length-1:(at+(event.key==='ArrowUp'?-1:1)+keys.length)%keys.length;
                this.items.get(keys[next])?.focus();
              }
            });
          }
        }
        const label=content(member);
        if (label.parentElement!==item) item.prepend(label);
        if (renderer==='diagram_tree') member.parent==null ? item.removeAttribute('parent') : item.setAttribute('parent',member.parent);
        if (renderer==='list_tree') {
          const expanded=this.expanded.has(member.key);
          if (item.expanded!==expanded) item.expanded=expanded;
        }
      }
      // Reconcile the one real hierarchy; preserve labels and component instances.
      const positions=new Map();
      for (const member of members) {
        const parent=renderer==='list_tree' && member.parent!=null ? this.items.get(member.parent) : this.tree;
        const siblings=[...parent.children].filter(n=>n.classList.contains('goo-topos-member'));
        const index=positions.get(parent)||0, item=this.items.get(member.key);
        if(siblings[index]!==item) parent.insertBefore(item,siblings[index]||null);
        positions.set(parent,index+1);
      }
      this.paint(this.choice,this.focused);
    }
    choose(key) { const member=this.members.get(key); if(member?.status==='available') this.select(member); }
    paint(choice, focused) {
      this.choice=choice; this.focused=focused;
      const first=[...this.members.values()].find(m=>m.status==='available');
      for (const [key,item] of this.items) {
        const selected=choice?.key===key && choice.life===item.dataset.life;
        if(this.renderer==='list_tree') { if(item.selected!==selected) item.selected=selected; }
        else { item.setAttribute('aria-selected',String(selected)); item.tabIndex=(focused?.key||first?.key)===key?0:-1; }
      }
    }
  }
  root.GooTopoi={Topos,topology};
  if(typeof module!=='undefined') module.exports=root.GooTopoi;
})(globalThis);
