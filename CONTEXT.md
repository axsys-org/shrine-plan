# Shrine

Shrine is a global, versioned namespace together with an application layer that
runs on top of it. The namespace is a hierarchical tree of **names**; the
application layer is a set of behaviour handlers (**hands**) that react to
changes in names they subscribe to (their **crew**).

This document is a reference. Definitions are meant to be precise. Two kinds of
callout appear throughout: **Design notes** give rationale and are skippable;
**Provisional** boxes flag rules that are real design choices not yet fixed —
implement around them only after confirming. Where something is settled but
specified *elsewhere*, the text says so inline ("out of scope here, fixed by …").

**Scope.** This reference is sufficient to *write hands and apps* against an
existing runtime. The runtime internals, the **versioning layer** (epic
consistency, the `$aeon` version representation and predecessor linkage), and the
**distribution and crypto model** (cross-node fetch, signature/hash verification)
are specified elsewhere; where this document leans on them it says so. It is *not*
yet enough to implement the runtime — the dispatch internals in particular still
carry open `Provisional` questions.

## Glossary

A handhold for each term. The analogies are aimed at a reader fluent in
functional programming and distributed systems but new to Shrine (and to the
Urbit/Clay lineage it descends from). Each leaks somewhere — the precise
definition is in the body.

| Term       | Think of it as                                                        |
|------------|-----------------------------------------------------------------------|
| path       | a filesystem path / URL path                                          |
| slot       | a fully-qualified path used as an opaque key                          |
| moment     | a name at a particular version (a git commit's view of a file)       |
| title      | a name's full history — the stream of its moments                     |
| `$pail`    | a `Dynamic`: a value carrying its own (namespace) type tag            |
| `$myth`    | the record/document at a name: a map of slots to values               |
| `$aeon`    | the version header: history position + signature + content hash       |
| `$saga`    | the data at a version: `(myth, aeon)`                                 |
| `$epic`    | a consistent snapshot of part of the namespace                        |
| care       | read depth: this node / + children / whole subtree (`cat`/`ls`/`ls -R`)|
| `$hunt`    | a query over a name — and a capability to it                          |
| `look`     | the read operation: run a hunt, get an epic                           |
| fact       | a change notification, emitted to carers at commit                    |
| gift       | a tree of changed descendants + values, delivered up to a parent      |
| command    | a write request: Poke (merge), Make (overwrite), Cull (tombstone)     |
| hand       | a reducer / actor receive: `(state, event) -> (effects, state)`       |
| crew       | the hunts (caps) a name holds — what it watches and may write         |
| overlay    | a read-only or bidirectional computed view over the namespace         |

## A tiny Shrine program

Before the formal definitions, here is the whole model in miniature: Alice's
chat client watches a room and reacts when it changes. Two names, both under one
node `0xA1…`:

```text
/0xA1…/chat/room              # the room
  /msg/body  -> "gm"

/0xA1…/chat/alice             # Alice's client
  /sys/hand  -> [ notify ]                            # one behaviour handler
  /sys/crew  -> { /room -> (z, /0xA1…/chat/room) }    # a hunt = a cap to the room
  /app/seen  -> "gm"                                  # last message Alice saw
```

(`/sys/hand`, `/sys/crew`, `/msg/body`, `/app/seen`, `/room` are all slots —
opaque path identifiers, not traversals.) Now someone holding a cap to the room
pokes it:

```text
Poke /0xA1…/chat/room { /msg/body -> "gm2" }
```

What happens:

1. The room's sovereign runs the room's hands on the command. They accept it; the
   room's myth merges to `{ /msg/body -> "gm2" }`, and a new **saga** (the new
   myth plus a freshly minted **aeon**) is committed as the next **moment** of
   the room's title.
2. The change produces a **fact** for `/0xA1…/chat/room`. Its audience is the
   carer index — every name whose crew holds a hunt covering the room. Alice's
   crew holds `(z, /0xA1…/chat/room)`, so she is in the audience.
3. The fact is delivered to Alice as an **event**. Her `notify` hand runs —
   `(old-myth, fact) -> (effects, new-myth)` — updating `/app/seen` to `"gm2"`
   and perhaps emitting a command of its own.

That single trace exercises every core term: slot, myth, hunt, crew, cap, hand,
command, fact, moment, saga, and the carer index. The rest of the document makes
each precise.

## Names

### Paths

A **path** is a list of ASCII characters separated by `/`. A name *is* a path;
the two words are interchangeable when talking about addressing.

Names and slots share this one path-space. A path is a **name** when it is
navigated as an address into the namespace tree, and a **slot** when it is used
as an opaque key — for instance, as a key in a `$myth`. The two uses coincide
syntactically but never decompose into each other: the slot `/sys/hand`
appearing as a key in name `N`'s myth is *not* a child of `N`; it is the
well-known identifier `/sys/hand`, used opaquely.

`/sys/` is a reserved root of the global namespace — the one system-level
exception to the rule (below) that names begin with a node's public-key hash.
Paths beneath it, such as `/sys/hand` and `/sys/crew`, are well-known slot
identifiers that appear as keys in names' myths.

> **Warning — a slot is not a child path.** This is the first thing people
> misread. A slot key inside a myth is an opaque identifier, *not* traversal from
> the current name. The name `/0xA1…/chat/alice` carrying a myth-key `/sys/hand`
> says nothing about a name `/0xA1…/chat/alice/sys/hand`. Same path syntax, two
> different uses:
>
> - **as a name** — navigated as an address into the namespace tree
> - **as a slot** — used as an opaque key inside a myth

### The three aspects of a name

A single name can be looked at in three ways — the reference, one version of it,
and its whole history:

- A **slot** is the name used as an opaque identifier: a fully-qualified path
  (from the root), generally treated atomically. Its meaning comes from use, not
  from decomposing the path. This is the name as a key. (Referential identity.)
- A **moment** is a name at a particular version: a single point in time, with a
  value and the versioning metadata that locates it. (One revision.)
- A **title** is the ordered series of all a name's moments. It is what endures
  as the data changes — the basis of identity *across* time. (Diachronic
  identity.)

So `slot : moment : title` lines up with `reference : one version : the whole
history`. A title is a stream; a moment is an element of it; a slot is the key.

## Data at a name

### `$pail` — a tagged value

The namespace contains type definitions. A **`$pail`** is a value paired with a
tag that says which type it is, where the tag is a **moment** — a specific name
at a version. Read two ways:

- *At runtime*, a pail is just a self-describing value: a payload plus a
  moment-tag. Think Haskell's `Dynamic`, or a boxed value carrying its type.
- *In the type theory*, the pail type is the tagged union of every type in the
  namespace, tagged by name. This is an **open** universe — it grows as names
  are added — not a closed `data` declaration. It is what makes the system
  pervasively polymorphic: any name can hold any namespace type.

Because the tag is a moment (a *versioned* name), type identity is
version-specific. Whether a value tagged at one moment of a type inhabits a
later moment of that type is governed by the elaborator's compatibility rules
(out of scope here, fixed by the elaborator — not an open question).

### `$myth` — user data

A **`$myth`** is the user-defined data living at a name: a `(map slot pail)`.
The keys are slots — fully-qualified paths used as opaque identifiers, whose
meaning comes from use rather than from a fixed schema. This is closer to a
dynamic object keyed by well-known names than to a struct.

### `$aeon` — metadata

An **`$aeon`** is the versioning header for a name. It carries: the version
information needed to locate the name temporally (its position in the title),
a **content hash** of the myth, and a **signature**. The hash content-addresses
the myth (enabling pinning and dedup); the signature is the sovereign's
signature over the name, version, and hash (see Top-level names).

> **Design note — aeons do not chain.** Deliberately, an `$aeon` does *not* commit
> to its predecessor's hash, so a title is not a hash-chain. The reason is
> overlays: a predecessor commitment would force materialising every moment of the
> prior history to validate the chain, which overlays cannot afford. Integrity is
> therefore per-moment — each `$aeon` is independently signed — not chained. The
> exact shape of the version field (counter, vector clock, …) is a versioning-layer
> detail, out of scope here.

### `$saga` — the data at a name

A **`$saga`** is a pair `(myth, aeon)`: the concrete data at a name at a version.
A moment is a name *at* a version; a saga is the data *at* that version — the
thing a moment resolves to.

### `$epic` — a slice of the namespace

An **`$epic`** is a mapping from names to sagas: a temporally consistent slice
of the namespace. "Consistent" means the sagas are coherent as of a single
logical version — a snapshot you could have read atomically, like a checked-out
working tree or a database read-snapshot. (How consistency is achieved across a
distributed subtree is out of scope here, fixed by the versioning layer — not an
open question for this document.)

## Invariants

The deep invariant is **monotonicity**: a title is an append-only stream of
moments. Publishing new data adds a moment; it never destroys an earlier one.
This is why an `$aeon` carries version information, why a `look` can return a
temporally consistent `$epic`, and why subscriptions can be made sound. It is
also why `Cull` (below) publishes an *empty* moment rather than deleting: a
tombstone preserves history.

## Querying

### Cares

A **care** says how much of the tree to read. It is one of `x`, `y`, or `z`:

- `x` — the value at the name only. (`cat`)
- `y` — the value at the name and its immediate children. (`ls`)
- `z` — the entire subtree rooted at the name. (`ls -R`)

A name can simultaneously hold a value *and* have children — care `y` implies it.
Unlike a filesystem, a name is not file-xor-directory: it is both a leaf (its
myth) and an interior node (its descendants) at once.

### Hunts

A **`$hunt`** is a pair `(care, name)`: a fully specified query — what to read
and how deep.

A hunt is also the system's base **capability**: to hold a hunt is to hold
authority over the name it names. Reading is one use of that authority
(subscribe via a crew, or `look`); in the general case, a hunt held in a crew
also implicitly confers authority to **write** (poke) that name. Finer-grained
permissioning — separating read from write, attenuating scope, and so on — is
layered on top by the application layer. The base primitive is just: hold a
hunt, hold authority.

A hunt also names a *scope* through its care: `(z, N)` reaches `N` and its
descendants, `(x, N)` only `N` itself. Within that scope a hunt-cap authorizes
**all** command verbs — `Poke`, `Make`, and `Cull` alike. A write is never
self-executing, though — it is a *request*: holding the cap is authority to ask,
and the target sovereign's hands may accept, modify, or reject it (see Top-level
names).

**Where caps come from.** The root authority is the sovereign keypair: it is the
inherent cap over its public-key-hash prefix, and every hunt-cap within that
subtree derives from it. Any other name gets a cap by *delegation* — a hunt
landing in its `/sys/crew`.

> **Deferred (by decision).** The minting/delegation mechanism — how a hunt first
> enters a name's crew (a sovereign hand `Poke`ing it into `/sys/crew`, cap-passing
> in command payloads, CapTP/OCapN-style introduction), and whether a delegated cap
> can be attenuated at the point of grant — is intentionally left open for now. It
> is the heart of the capability model and will be specified later.

### `look`

`look(care, name) -> epic` is the read operation: run the hunt, get back an
epic. For care `x` the epic is a singleton map.

## Events and behaviour

### Events: commands, facts, gifts

An **event** is what a hand receives as its second argument. There are three
kinds: a **command**, a **fact**, and a **gift**.

A **command** is a write request directed at a name:

```haskell
data Cmd
  = Poke Name Myth  -- shallow per-slot merge into the existing myth
  | Make Name Myth  -- overwrite / create
  | Cull Name       -- publish a new, empty version (tombstone)
```

`Poke` merges the supplied myth into the name's current myth as maps, right-biased
on slot collision: a colliding slot takes the incoming pail wholesale — a shallow,
per-slot merge, with no recursion into pail structure. `Make` replaces the myth
wholesale, and an **empty `Make` is illegal** — `Make` requires a non-empty myth.
`Cull` is the only way to publish an empty moment, and that empty moment is the
**tombstone**; there is therefore no `Make Name {}` to confuse it with.

A **fact** is a notification that a name changed. At the kernel level it carries
no data — just which name changed and its new version:

```haskell
data Fact = Fact
  { changed  :: Name    -- the name whose saga changed
  , aeon     :: Aeon    -- the new version header
  , audience :: [Name]  -- who cares — from the carer index
  }
```

(Where the audience comes from is explained under Crew and The update cycle.)

The fact a *hand* receives is richer than the kernel fact. When a fact wakes a
name's hands, the runtime injects the current values of every member of that
name's crew into the hand's context — so the handler sees fresh data for all the
hunts it holds, not just the one that changed, and need not issue follow-up
`look`s to read its own subscriptions.

A **gift** is the third event kind: an internal, in-transaction notification
delivered to a *parent* summarising what changed beneath it (see Dispatch model).
It is neither a command nor a fact — and it is why a hand's event taxonomy has
three kinds, not two: a hand can be woken by a gift.

A gift is a **tree of changed children and their new values**, rooted at the
recipient. A parent receives **one** gift coalescing all of its changed
descendants (not one gift per changed child), so a handler reads the whole shape
of the change beneath it in a single wake.

### hands

A name carries its behaviour at the well-known slot `/sys/hand`: a key (drawn
from the reserved `/sys/` root) in the name's myth whose value is a list of
handlers called **hands**, each of signature

```
hand(old-state, event) -> (effects, new-state)
```

This is a reducer / actor-receive / Elm-update step. The `effects` are lists of
commands. The hands in the list process an event in order, each seeing the
state left by the previous one.

Here "state" is the name's **whole `$myth`** — including its `/sys/*` slots. hands
never author version metadata: they produce new myths, and the runtime assigns
versions and mints each `$aeon` — version number, content hash, sovereign
signature — at transaction finalization (see Dispatch model), forming the new
`$saga`. So "a hand produces a new saga" is shorthand for "a hand produces a new
myth, which the runtime later commits as a saga."

Because state is the whole myth, a hand **can rewrite its own `/sys/hand` and
`/sys/crew`** — its behaviour and its capability set are themselves mutable data.
The kernel does not protect `/sys/*`; a `Make` that omits `/sys/hand` will blank a
name's behaviour. This self-modifiability is deliberate, and it is precisely why a
richer permission layer is expected to sit on top of the raw crew primitive.

> **Design note — modifying state vs emitting to self.** A hand can effect a
> change two ways: return new state directly, or emit a command targeting its
> own name. A direct change is threaded immediately — the next hand in the list,
> and any inflight read of self, sees it within the current step (structural,
> fold-like). A self-command instead lands on the **self** queue (see Dispatch
> model) and re-runs the name's whole hand list later in the self-drain, on the
> inflight myth. Neither is a synchronous recursive call, and neither is visible
> outside the transaction until finalization. Use a direct update for a local
> transition inside the current handler; use a self-command when the change
> should be reprocessed by the full hand list as its own step.

### Crew

A name's **crew** is the well-known slot `/sys/crew`: a `(map slot hunt)` — the
hunts the name holds. Each is a capability: the name subscribes to the data the
hunt matches (read) and may poke it (write). When matched data changes, the
resulting fact is delivered to the name's hands as an event.

Because a hunt is a cap, the audience of a change is just whoever holds a cap
over the changed name. The system maintains the inverse of all crews — a carer
index — to answer exactly that: when a name changes, it finds which names hold a
hunt covering it, and that set is the audience carried by the fact. A crew is
ordinary myth data (the `/sys/crew` slot), so a hand can rewrite it.

**Subscribing.** Adding a hunt to `/sys/crew` *is* subscribing — it implicitly
registers the subscription. On adding one, the name receives two things: the
ordinary poke event recording that `/sys/crew` changed, and an **init event**
carrying the current value of the newly-watched name (so a subscriber is never
blind — it gets the present state, not only future changes). If the watched name
has no local copy, the init event is deferred until the network fetch completes.

**Cross-node and consistency.** Remote crew members are fetched over the network
(adding the hunt triggers the fetch; the init event waits on it). A carer **must
verify** a fetched myth against the `$aeon`'s signature and content hash before
trusting it — this verification is required, not optional. And injected crew
values **always read committed** state, never inflight — unlike the
Reads-during-dispatch rule for self/descendants, a crew member is external data
and is always seen at its last committed moment.

## Dispatch model

Dispatch is not a call stack and not a plain actor mailbox. A whole change
settles as one **transaction**: effects are accumulated and driven to a fixpoint
over the affected subtree, and only at the end are versions assigned and facts
emitted. A hand never synchronously calls another hand — it returns
`(effects, new-state)` to the runtime.

**Within one name.** Run the name's hands in list order; each hand sees the myth
left by the previous one. Emitted effects are accumulated, not dispatched
mid-chain.

**Driving effects to a fixpoint.** Each batch of accumulated effects is
partitioned by target *relative to the name that emitted them*: **self** (that
name), **kids** (its descendants), and **rest** (anything outside its subtree).
The cycle, from **START**:

1. Drain **self**: run self-effects until the self queue is empty. Each re-runs
   this name's hands on the inflight myth and may emit more effects, which are
   re-partitioned.
2. Drain **kids**: run kid-effects until the kids queue is empty, cascading the
   same way.
3. **Gifts.** With kids drained, topologically sort all the child updates and
   deliver a **gift** to the *parent* of the changed children, **deepest first**.
   A gift is one coalesced, in-transaction notification per parent: a tree of that
   parent's changed descendants and their new values (not one gift per child). It
   is not a fact.
4. A gift may run the parent's hands and produce new effects. If so: **stash the
   undelivered gifts and goto START** with the new effects. On the next gift
   phase, **re-merge** the stashed gifts with any gifts newly generated during the
   cascade and **re-sort** the whole set deepest-first before resuming delivery.
5. When every gift has been delivered and no effects remain, the transaction is
   at fixpoint. The runtime **finalizes**: all pending changes are written and
   assigned version numbers — and *that* is when **facts** are emitted for the
   now-finalized changes.

Dispatch is **fully deterministic**: the runtime imposes a fixed total order over
effects and over children, so replaying the same inputs cannot diverge — essential
for a signed, replicated system. Termination is bounded by a **fuel** limit
(current design): a transaction that fails to reach fixpoint within its fuel is
aborted and rolled back, exactly like a crash (below). This covers
within-transaction runaway — a self-poke loop, or a gift→effects→START cycle that
never settles — which the cross-transaction loop story could not, since such a
transaction never finalizes and so never emits a fact for anything to react to.

So gifts drive change *up* the subtree during the transaction; facts go *out* to
carers only after it commits. A single transaction can finalize many moments
across the subtree and emit many facts at once. **Rest** effects never run inside
the transaction: they are queued and, at finalization, emitted outbound as
commands — each beginning its own transaction at its target.

A consequence worth stating, because it is easy to get wrong: since the partition
is relative to the *emitter*, an explicit poke *upward* (a child poking its
parent) or *sideways* (a sibling) targets a name outside the emitter's subtree, so
it is a **rest** effect — deferred, cross-transaction — even within a single
sovereign. The only *in-transaction* upward path is the automatic **gift**. "Same
sovereign" does not imply "same transaction."

**Atomicity.** The transaction is all-or-nothing. A crash in any handler at any
point before finalization rolls back every pending change — no partial moments,
no facts.

**Reads during dispatch.**

- A read of **self or a descendant** sees the **inflight** (uncommitted) state of
  the in-progress transaction.
- A read **elsewhere** sees the **latest committed** state.

**Loops.** *Cross-transaction* feedback loops (A watches B, B watches A, trading
facts) are allowed and are ordinary program behaviour — this layer provides no
cross-transaction cycle breaker, and detection or timeouts are the application
layer's concern. *Within-transaction* runaway is the kernel's concern and is
handled by the fuel bound described above.

## The update cycle

Zoom out from one transaction and the system is a single loop across names. A
finalized change emits **facts** to its carers — the names whose crews hold a
covering hunt. Each fact is an event at a carer; handling it runs that carer's
hands, which is *itself* a dispatch transaction (above), and may finalize its own
changes and emit further facts. The loop runs until it quiesces.

The symmetry that makes this work: a **command is both an output and an input** —
the content of a hand's effect, and the event another name's hands consume. Facts
flow the same way, fanned out through crews.

## Overlays

A name may be marked as an **overlay**: it defines a lens over the namespace
rather than holding ordinary data. User-defined overlays are addressed at
`/o/[..location-of-overlay]/[..location-of-overlaid-data]`. This lets views,
projections, filtered slices, and access-controlled regions be read and
subscribed to exactly like ordinary names — the overlay computes the saga that
appears at each address.

An overlay may be **read-only** — a view — or **bidirectional** — a lens whose
put direction translates writes through `/o/...` back onto the underlying names.

**Marking.** A name is made an overlay by giving it two well-known slots:
`/sys/soap`, the transformation itself, and `/sys/dish`, metadata about that
transformation.

**Subscribing through an overlay.** Subscriptions to `/o/...` addresses are
allowed. The subsystem that watches crews tracks which concrete underlying path an
overlay resolves to, and when that underlying data changes it emits a fact for the
overlay address — so a watcher of an overlay is notified exactly as if it watched
an ordinary name.

**Put-back (write-through overlays).** A write-through overlay is a lens: its
`/sys/soap` defines a forward map `fwd : T -> U` and a backward map `back : U -> T`,
where `T` and `U` are subsets of a `$myth` — `T` of the underlying name, `U` of the
overlay view. Reads run `fwd`. A write through `/o/...` arrives as a member of `U`;
the runtime pushes it through `back` to obtain a `T`, then applies that `T` to the
underlying name as an ordinary command. So put-back adds nothing new to the write
path — it just reduces an overlay write to a normal underlying write.

## Top-level names

Shrine is distributed. Apart from the reserved `/sys/` root, every name begins
with the public-key hash of the node that produced it. That keypair signs the
datum in each `$aeon`; the holder of the keypair is sovereign over its
subsection of the namespace. A command targeting a name is therefore a *request*
to that name's sovereign: holding a hunt over the name is the authority to make
it, and the sovereign's hands decide whether and how to apply it.

A node, not a name, is the unit of location: every name under one key is served by
that one sovereign node. So the actor analogy is loose — "where a hand runs" is
fixed by the keypair, not by the individual name.

Example name shapes:

```text
/sys/...                                     # a name in the reserved system namespace
/0xA1…/apps/chat/room                        # an app name under one node
/0xB2…/users/alice/profile                   # a name under a different node
/o/0xA1…/views/public/0xB2…/users/alice      # an overlay address
```

`/sys/` is a real, navigable namespace — there are addressable names in it.
Separately, certain `/sys/` paths (`/sys/hand`, `/sys/crew`) are also used as
well-known *slot* keys inside myths; that is the slot-vs-name distinction (use,
not path) at work, not a contradiction. Ordinary app paths are never bare like
`/chat/room`; they are rooted at the producing node's key or at `/sys/`.

**Acks.** A command gets an (n)ack **iff its target is neither self nor a kid** —
that is, for `rest` targets that start their own transaction, the requester
receives an acknowledgement (or rejection). For a command to self or to a kid
there is no separate ack: a kid's effect is acknowledged by the **gift** that
flows back up when the kid changes (the gift is, in effect, the ack), and a
self-command resolves within the same transaction.


