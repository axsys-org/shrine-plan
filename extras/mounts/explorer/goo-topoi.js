/* A topos presents membership; the selection port remains the choice authority. */
(function(root) {
  'use strict';
  const renderers = new Set(['list', 'diagram_tree', 'list_tree']);
  const hasOutline = (nodes, selection) => nodes.some(node => node.kind!=='selection' &&
    ((node.renderer==='list_tree' && node.selection===selection) || hasOutline(node.children||[],selection)));
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
  // Materialization requests only; semantic membership remains in GooSession.
  class TreeSource {
    constructor(path, axis, fetchPage) {
      this.path=path;this.axis=axis;this.fetchPage=fetchPage;this.requested=new Map();
    }
    request(member, more=false) {
      const previous=this.requested.get(member.key);
      const pages=previous?.life===member.life ? previous.pages : 0;
      this.requested.set(member.key,{life:member.life,pages:more?Math.max(1,pages)+1:Math.max(1,pages)});
    }
    commit(source) {
      const live=new Map(source.members.map(member=>[member.key,member.life]));
      for(const [key,plan] of this.requested)if(live.get(key)!==plan.life)this.requested.delete(key);
    }
    async read(signal, fetchPage=this.fetchPage) {
      const wanted=new Map(this.requested), records=new Map(), presentations=[];
      let omitted=0;
      const first=await fetchPage({},signal);
      const check=(page,parent)=> {
        if(page.id!==this.path || page.axis!==this.axis || page.topology!=='tree' || !page.incremental ||
           page.life!==first.life || page.epoch!==first.epoch || page.parent!==parent || !Array.isArray(page.members))
          throw new Error('Tree page changed; refresh before continuing.');
      };
      const add=(page,parent,initial=false)=> {
        check(page,parent);
        if(page.omitted!==undefined && (!Number.isSafeInteger(page.omitted)||page.omitted<0||page.omitted>64))throw new Error('Invalid omitted tree count.');
        omitted+=page.omitted||0;
        if(page.presentations)presentations.push(...page.presentations);
        if(page.members.length>(initial?65:64))throw new Error('Tree child page exceeds its bound.');
        for(const member of page.members) {
          const isRoot=initial && member.key===this.path && member.parent===null;
          if(!isRoot && member.parent!==parent)throw new Error('Invalid tree child parent.');
          if(records.has(member.key))throw new Error('Duplicate tree child.');
          records.set(member.key,{...member,childrenLoaded:!member.hasChildren});
        }
        if(records.size>4096)throw new Error('Loaded tree exceeds 4096 nodes; inspect a smaller subtree.');
      };
      add(first,this.path,true);
      if(!records.has(this.path))throw new Error('Missing tree root.');
      const queue=[{parent:this.path,page:first}];
      for(let index=0;index<queue.length;index++) {
        const {parent,page}=queue[index], member=records.get(parent);
        const plan=wanted.get(parent);
        const desired=plan?.life===member.life?plan.pages:1;
        let next=page.next, pages=1;
        const cursors=new Set();
        while(next && pages<desired) {
          if(cursors.has(next))throw new Error('Repeated tree cursor.');cursors.add(next);
          const continuation=await fetchPage({parent,after:next,epoch:first.epoch},signal);
          add(continuation,parent);next=continuation.next;pages++;
        }
        member.childrenLoaded=true;member.moreChildren=!!next;
        // Only explicitly expanded branches are requested; never recursively walk
        // an unopened subtree. Parent order also drops requests for removed nodes.
        for(const child of records.values()) {
          if(child.parent!==parent || !child.hasChildren || wanted.get(child.key)?.life!==child.life)continue;
          const page=await fetchPage({parent:child.key,epoch:first.epoch},signal);
          add(page,child.key);queue.push({parent:child.key,page});
        }
      }
      topology([...records.values()],'list_tree');
      return {...first,omitted,members:[...records.values()],...(first.presentations?{presentations}:{})};
    }
  }
  const sameMember = (a, b) => !!a && !!b && ['key','life','source','sourceLife'].every(key => a[key] === b[key]) && (a.axis || 'z') === (b.axis || 'z');
  const focusable = member => member && (member.status === 'available' || member.hasChildren);
  const focusMember = (members, focused) => members.find(member => focusable(member) && sameMember(member, focused)) || members.find(focusable) || null;
  const interactive = event => !!event.target.closest('button,a,input,select,textarea,summary,[contenteditable],[data-goo-tree-interactive]');
  class Topos {
    constructor(host, key, select, focus, loadChildren) {
      this.host=host; this.key=key; this.select=select; this.focus=focus;this.loadChildren=loadChildren;
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
            if(event.detail.expanded) {
              const member=this.members.get(event.detail.subject);
              if(member?.hasChildren && !member.childrenLoaded)this.load(member);
            }
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
            const m=this.members.get(member.key); if(focusable(m)) this.focus(m);
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
          item.toggleAttribute('branch',!!member.hasChildren);
          item.disabled=member.status!=='available' && !member.hasChildren;
          if(member.moreChildren && this.loadChildren) {
            if(!item.moreButton) {
              item.moreButton=document.createElement('button');item.moreButton.type='button';
              item.moreButton.textContent='Load more children';
              item.moreButton.addEventListener('click',()=>this.load(this.members.get(member.key),true));
              item.append(item.moreButton);
            }
            item.moreButton.setAttribute('aria-label',`Load more children of ${member.key}`);
          } else {item.moreButton?.remove();item.moreButton=null;}
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
    async load(member,more=false) {
      const item=this.items.get(member?.key);
      if(!item || item.loadingChildren || !this.loadChildren)return;
      item.loadingChildren=true;item.setAttribute('aria-busy','true');
      if(item.moreButton)item.moreButton.disabled=true;
      try {await this.loadChildren(member,more);}
      finally {
        item.loadingChildren=false;item.removeAttribute('aria-busy');
        if(item.moreButton)item.moreButton.disabled=false;
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
      return focusable(member) ? member : members.find(m=>focusable(m) && visible(m));
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
  root.GooTopoi={Topos,TreeSource,topology,focusMember,hasOutline};
  if(typeof module!=='undefined') module.exports=root.GooTopoi;
})(globalThis);
