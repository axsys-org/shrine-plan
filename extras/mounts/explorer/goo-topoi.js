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
  const sameMember = (a, b) => !!a && !!b && ['key','life','source','sourceLife'].every(key => a[key] === b[key]) && (a.axis || 'z') === (b.axis || 'z');
  const focusMember = (members, focused) => members.find(member => member.status === 'available' && sameMember(member, focused)) || members.find(member => member.status === 'available') || null;
  const interactive = event => !!event.target.closest('button,a,input,select,textarea,summary,[contenteditable],[data-goo-tree-interactive]');
  class Topos {
    constructor(host, key, select, focus) {
      this.host=host; this.key=key; this.select=select; this.focus=focus;
      this.items=new Map(); this.expanded=new Set(); this.lives=new Map(); this.renderer=null; this.members=new Map();
    }
    reconcile(renderer, members, content) {
      const next = topology(members, renderer);
      const active = this.body?.contains(document.activeElement) ? document.activeElement : null;
      const changedRenderer = this.renderer !== renderer;
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
            this.scheduleFocus();
          });
          // WA restores a tab stop on its tree after blur. The adapter projects
          // one member tab stop, including when focus is outside the tree.
          this.body.addEventListener('focusout',()=>this.scheduleFocus());
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
      if (changedRenderer && renderer === 'list_tree') {
        // A diagram/list may have focused a descendant that the newly created
        // hierarchy would otherwise hide. Reveal its ancestry without choosing it.
        let parent = focusMember(members,this.focused)?.parent;
        while (parent != null) { this.expanded.add(parent); parent=next.get(parent)?.parent; }
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
          // The wrapper preserves declarative expansion during WA connection;
          // set the attribute before insertion as well as the live property.
          item.toggleAttribute('expanded',expanded);
          if (item.expanded!==expanded) item.expanded=expanded;
          item.disabled=member.status!=='available';
        } else {
          item.setAttribute('aria-disabled',String(member.status!=='available'));
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
      if (active) {
        // Reparented caller controls keep drafts/caret and retain their exact
        // element. Removed members/renderer hosts recover at the valid tab stop.
        this.restoreFocus=active;
        this.scheduleFocus();
      }
    }
    choose(key) { const member=this.members.get(key); if(member?.status==='available') this.select(member); }
    paint(choice, focused) {
      this.choice=choice; this.focused=focused;
      for (const [key,item] of this.items) {
        const selected=choice?.key===key && choice.life===item.dataset.life;
        if(this.renderer==='list_tree') { if(item.selected!==selected) item.selected=selected; }
        else item.setAttribute('aria-selected',String(selected));
      }
      this.syncFocus(); this.scheduleFocus();
    }
    tabStop() {
      const members=[...this.members.values()];
      let member=focusMember(members,this.focused);
      if(this.renderer!=='list_tree') return member;
      const visible=m=> {
        for(let parent=m.parent; parent!=null; parent=this.members.get(parent)?.parent) if(!this.expanded.has(parent)) return false;
        return true;
      };
      while(member && !visible(member)) member=this.members.get(member.parent);
      return member?.status==='available' ? member : members.find(m=>m.status==='available' && visible(m));
    }
    syncFocus() {
      const target=this.tabStop();
      for(const [key,item] of this.items) item.tabIndex=key===target?.key?0:-1;
      if(this.renderer==='list_tree') this.tree.tabIndex=-1;
    }
    scheduleFocus() {
      if(this.focusQueued) return;
      this.focusQueued=true;
      this.ready=Promise.resolve().then(async()=> {
        const body=this.body;
        await Promise.all([body,this.tree,...this.items.values()].map(item=>item?.updateComplete));
        if(this.renderer==='list_tree') {
          // The wrapper restores declared branch expansion after descendants'
          // first update. Focus only after that connection work has painted.
          await new Promise(resolve=>requestAnimationFrame(resolve));
        }
        this.focusQueued=false;
        if(body!==this.body) { this.scheduleFocus(); return; }
        this.syncFocus();
        const previous=this.restoreFocus; this.restoreFocus=null;
        if(!previous) return;
        // Do not reclaim focus after a user moved to another control while
        // custom elements were updating.
        const active=document.activeElement;
        if(active!==previous && active!==document.body && !body.contains(active)) return;
        const owner=previous.closest('.goo-topos-member');
        const retained=owner && this.items.get(owner.dataset.key)===owner && this.members.get(owner.dataset.key)?.status==='available';
        const target=retained && previous.isConnected ? previous : this.items.get(this.tabStop()?.key);
        if(target && active!==target) target.focus({preventScroll:true});
      });
    }
  }
  root.GooTopoi={Topos,topology,focusMember};
  if(typeof module!=='undefined') module.exports=root.GooTopoi;
})(globalThis);
