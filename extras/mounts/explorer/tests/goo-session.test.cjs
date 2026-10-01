const {test} = require('node:test');
const assert = require('node:assert/strict');
const {GooSession} = require('../goo-session.js');
const defer = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };
const member = (key, subject=key, life='1') => ({key,subject,life,source:'/cards',sourceLife:'1',type:'namespace-record',expected:'1',status:'available'});
const A=member('A'), B=member('B'), C=member('C');
const source = (members=[A,B,C]) => ({id:'/cards',life:'1',type:'namespace-record',members});
const description = (initial, members, extra=[]) => [{kind:'pane',key:'workspace',children:[
 {kind:'selection',key:'current',source:source(members),initial,children:[
  {kind:'split',children:[{kind:'pane',key:'queue',children:[{kind:'list',key:'rows',selection:'current',source:'/cards',type:'namespace-record'}]},
    {kind:'pane',key:'detail',children:[{kind:'follow',key:'subject',selection:'current',slot:'content'}]}, ...extra]}
 ]}
]}];
const state=(s,kind,key) => [...s.owners.values()].find(v=>v.kind===kind && (!key || v.key===key));
async function setup(initial, members, extra) { const s=new GooSession(); await s.reconcile(description(initial,members,extra)); return {s,sel:state(s,'selection'),follow:state(s,'follow'),list:state(s,'list')}; }
const select=(s,sel,m) => s.deliver(s.intent(sel.ref,m));
test('S03/S04: empty, clear, creation-only typed seed, invalid seed diagnostic',async()=>{
 const {s,sel}=await setup(); assert.equal(sel.accepted,null);
 await select(s,sel,B); await s.reconcile(description(A)); assert.equal(sel.accepted.key,'B');
 await s.reconcile(description(C)); assert.equal(sel.accepted.key,'B');
 await select(s,sel,null); assert.equal(sel.accepted,null);
 const bad=await setup({subject:'A'}); assert.equal(bad.sel.accepted,null); assert.equal(bad.sel.diagnostic,'incompatible-member-reference');
 const seeded=await setup(A); assert.equal(seeded.sel.accepted.key,'A');
});
test('S05/S06: independent workspaces and selection outlives consumers',async()=>{
 const s=new GooSession(), one=description(A)[0], two={...description(B)[0],key:'second'};
 await s.reconcile([one,two]); const choices=[...s.owners.values()].filter(v=>v.kind==='selection');
 assert.equal(choices.length,2); await select(s,choices[0],C); assert.equal(choices[1].accepted.key,'B');
 const bare=description(A); bare[0].children[0].children=[];
 await s.reconcile([bare[0],two]); assert.equal(choices[0].accepted.key,'C'); assert.equal(choices[0].live,true);
});
test('S07/S08/S14: focus, reorder, duplicate subjects, reusable member controls',async()=>{
 const duplicate=member('another-A','A'); const {s,sel,list,follow}=await setup(A,[A,B,C,duplicate]);
 s.focus(list.ref,B); assert.equal(sel.accepted.key,'A'); assert.equal(list.focus.key,'B');
 await s.reconcile(description(A,[C,duplicate,B,A])); assert.equal(list.focus.key,'B');
 const encounter=follow.encounter.id; await select(s,sel,duplicate); assert.equal(follow.encounter.id,encounter);
 for(const choice of [B,C,B]) await select(s,sel,choice);
 assert.equal(sel.accepted.key,'B');
});
test('S09/S13: projection absence is not deletion; lifetime/source mismatch never retargets',async()=>{
 const {s,sel}=await setup(A); await s.reconcile(description(null,[B,C])); assert.equal(sel.accepted.status,'available');
 const removed=description(null,[B,C]); removed[0].children[0].source.deleted=['A']; await s.reconcile(removed);
 assert.equal(sel.accepted.status,'unavailable');
 await s.reconcile(description(null,[member('A','A','3'),B])); assert.equal(sel.accepted.life,'1');
 await assert.rejects(select(s,sel,A),/stale-member/);
 assert.throws(()=>s.plan(description(null,[{...B,source:'/other'}])),/incompatible-member-reference/);
 const wrong=description(); wrong[0].children[0].source.life='2'; wrong[0].children[0].source.members=[]; assert.throws(()=>s.plan(wrong),/incompatible-source-rebinding/);
 const duplicate=description(); duplicate.push(duplicate[0]); assert.throws(()=>s.plan(duplicate),/duplicate-local-key/);
 const port=description(); port[0].children[0].children[0].children[0].children[0].source='/wrong'; assert.throws(()=>s.plan(port),/incompatible-selection-port/);
});
test('S10/S15: retirement, foreign snapshots, and late outputs cannot resurrect owners',async()=>{
 const {s,sel,follow}=await setup(A); const ticket=s.ticket(follow.ref), intent=s.intent(sel.ref,B);
 await s.reconcile([]); await s.reconcile(description(A));
 assert.equal(s.current(ticket),false); await assert.rejects(s.deliver(intent),/stale-or-foreign-handle/);
 assert.throws(()=>s.get({...sel.ref}),/stale-or-foreign-handle/);
 assert.notEqual(state(s,'selection').incarnation,sel.incarnation);
 const other=await setup(); assert.throws(()=>other.s.get(state(s,'selection').ref),/stale-or-foreign-handle/);
});
test('S11/S12/S15: encounter continuity, recipe generation and out-of-order outputs',async()=>{
 const {s,sel,follow}=await setup(A); s.become(follow.ref,'editor'); const encounter=follow.encounter.id;
 follow.inputs.set('text',{value:'draft',dirty:true}); const old=s.ticket(follow.ref);
 assert.equal((await select(s,sel,A)).status,'noop'); assert.equal(follow.encounter.id,encounter);
 await s.reconcile(description(C,[{...A,expected:'2'},B,C])); assert.equal(follow.encounter.recipe,'editor'); assert.equal(follow.inputs.get('text').value,'draft'); assert.equal(s.current(old),false);
 const before=s.ticket(follow.ref); s.become(follow.ref,'provenance'); assert.equal(s.current(before),false);
 await select(s,sel,B); assert.notEqual(follow.encounter.id,encounter); assert.equal(follow.encounter.recipe,'content');
});
test('S16/S17/S18: all departure guards, failures, supersession and saved checkpoints',async()=>{
 const second={kind:'pane',key:'other',children:[{kind:'follow',key:'other-follow',selection:'current',slot:'content'}]};
 const {s,sel,follow}=await setup(A,undefined,[second]); const other=state(s,'follow','other-follow');
 const b=defer(), c=defer(); let saved=0;
 s.guard(follow.ref,reason=>reason.member.key==='B'?b.promise:c.promise);
 s.guard(other.ref,async()=>{saved++;return true;});
 const pendingB=select(s,sel,B); assert.equal(sel.accepted.key,'A'); assert.equal(sel.pending.member.key,'B');
 const pendingC=select(s,sel,C); b.resolve(true); assert.equal((await pendingB).status,'superseded'); assert.equal(sel.accepted.key,'A');
 c.resolve(false); assert.equal((await pendingC).status,'refused'); assert.equal(sel.accepted.key,'A'); assert.equal(saved,2);
 follow.guards.clear(); s.guard(follow.ref,()=>{throw Error('save failed');}); assert.equal((await select(s,sel,B)).status,'refused'); assert.equal(sel.accepted.key,'A');
 follow.guards.clear(); await select(s,sel,C); assert.equal(sel.accepted.key,'C'); assert.equal(s.read(other.selection).accepted.key,'C');
});
test('S19: an old transport retry cannot undo a newer accepted intent',async()=>{
 const {s,sel}=await setup(A); const first=s.intent(sel.ref,B); await s.deliver(first); await select(s,sel,C);
 assert.equal((await s.deliver(first)).status,'superseded'); assert.equal(sel.accepted.key,'C');
});
test('S20/S21/S22/S27: keyed composition, deck suspension and retirement guard/resources',async()=>{
 const s=new GooSession(); const panes=[{kind:'pane',key:'a'},{kind:'pane',key:'b'}];
 const tree=children=>[{kind:'deck',key:'tabs',children}]; await s.reconcile(tree(panes));
 const deck=state(s,'deck'), a=state(s,'pane','a'), b=state(s,'pane','b'); let suspended=0,released=0;
 a.inputs.set('draft',{value:'composing',composing:true}); s.resource(a.ref,{suspend:()=>suspended++,release:()=>released++});
 await s.activate(deck.ref,b.ref); assert.equal(a.suspended,true); assert.equal(a.inputs.get('draft').value,'composing');
 await s.reconcile(tree([...panes].reverse())); assert.equal(deck.active,b.id); assert.equal(a.incarnation,s.get(a.ref).incarnation);
 await s.reconcile(tree([panes[0]])); assert.equal(deck.active,a.id); assert.equal(a.suspended,false);
 const remove=s.guard(a.ref,()=>false); assert.equal((await s.reconcile(tree([]))).status,'refused'); assert.equal(a.live,true);
 remove(); await s.reconcile(tree([])); assert.equal(deck.active,null); assert.equal(released,1); assert.equal(suspended,1);
 await s.reconcile([{kind:'pane_stack',children:panes}]); const before=state(s,'pane','a').ref;
 await s.reconcile([{kind:'split',children:[...panes].reverse()}]); assert.equal(state(s,'pane','a').ref,before);
});
test('S23/S24: activation capture uses accepted state, immutable payload and retry identity',async()=>{
 const {s,sel,follow}=await setup(A); await select(s,sel,B); const frozen=s.capture([sel.ref],'one');
 await select(s,sel,C); assert.equal(frozen.values[0].member.key,'B'); assert.equal(s.capture([sel.ref],'one'),frozen);
 assert.equal(s.capture([sel.ref],'two').values[0].member.key,'C'); assert(Object.isFrozen(frozen.values[0].member));
 const guard=defer(); s.guard(follow.ref,()=>guard.promise); const pending=select(s,sel,A);
 assert.equal(s.capture([sel.ref],'pending').values[0].member.key,'C'); guard.resolve(false); await pending;
 follow.guards.clear(); await select(s,sel,null); assert.throws(()=>s.capture([sel.ref],'empty'),/empty-selection/);
});
test('S26/S28: pure planning and reflection describe actual owners/ports/dependencies',async()=>{
 const s=new GooSession(); const before=s.inspect(); const planned=s.plan(description(A)); assert.equal(planned.size,6); assert.deepEqual(s.inspect(),before);
 await s.reconcile(description(A)); const sel=state(s,'selection'), follow=state(s,'follow');
 s.capture([sel.ref],'capture'); const reflected=s.inspect();
 const choice=reflected.owners.find(o=>o.kind==='selection'), follower=reflected.owners.find(o=>o.kind==='follow');
 assert.deepEqual(choice.followers,[follow.id]); assert.equal(follower.selectionPort,sel.id); assert.equal(reflected.captures[0].values[0].member.key,'A');
 reflected.owners[0].key='forged'; assert.notEqual(s.inspect().owners[0].key,'forged');
});
