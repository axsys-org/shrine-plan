# Syncing worlds: the design the hands are built for

Not built yet. Networking comes later (libmesa over a tailnet, see the plan). What is written here
is the shape every hand already keeps to, so that when two worlds sync, their knowledge of shared
things clicks together without a migration.

## What a sync moves

Records, signed, at paths, with cases. Never slots copied out of another world. A world that
knows about Tlon reads the other world's Tlon record by reference (`/0x22/user/orgs/tlon`, live or
pinned at a case) and composes; it does not merge. The union view at a record (its own slots,
what points at it, and the same thing in other worlds) is where two worlds' knowledge meets, on
read, with no conflict possible because nothing is written twice.

## Identity: which records are one thing

A path is local. Identity across worlds rests on strong keys and on `same` links:

- strong keys are slots whose value identifies the thing outside any world: `website` (its domain),
  `handle`, `email`, `github`, `aliases`, a registry id. The links hand already indexes these as
  aliases; the same index, fed a peer's records, finds the peer's record for a thing of mine.
- a `same` slot points at the other world's record for the thing. Either world writes its own
  `same`; the link is signed by whoever asserts it and never needs agreement.
- the agent is asked, never automatic: a peer's record that shares a strong key with mine becomes
  a weave item (`/agent/weave/same/<slug>` {mine, theirs, why}); the agent decides and writes `same`.

## Moves never break references

A record that moves (regrouped under a parent, reclassified) leaves a forward at its old path:
`{moved_to: <reference>}`. The old path is never culled. Local references are repointed by the
agent (the index says what points where); remote references follow the forward on read. A
reference that lands on a `moved_to` resolves one hop further.

## Provenance travels with every fact

Every fact slot that came from outside has a `source` reference to the region, row or text it came
from; every write carries its signer in the history. A peer that reads my record can read its
sources too, in my world, by reference. Nothing is restated; the chain stays walkable across worlds.

## What a peer sees of a path

A peer subscribes to a path at a care: x (the record), y (with what is beneath), z (the whole
subtree), live or pinned. A talk lives beneath the record it is about (`<record>/talk`), so a peer
synced to the record at y or z sees the conversation about it, by the same rule as everything
else. Pinned reads are immutable and so cacheable by any relay; live ones are read again on change.

## New relationships between two users' knowledge

The links index is the engine. Fed both worlds' records, it answers in milliseconds: what of
theirs points at something of mine, which texts of theirs mention my things, which of their things
share a strong key with mine. Each answer is a weave item for the agent, in its own time: a `same`
to assert, a reference to add, a thing to place. The world grows and reforms; it never has to be
right at once.
