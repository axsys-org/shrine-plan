# Task: a shop that sleeps

The owner runs a small machine shop. It makes fixtures and needs, every
month, widgets, gizmos and needles from suppliers; it cannot run at all
without VRAM, which is currently unavailable. The owner has put the shop to
sleep (`/sleep` says since when and why) and wants to resume on a dime the
day VRAM is available again. Your task while the shop sleeps: keep the
minimum set of supplier relationships warm, know when it is no longer
satisfied, and tell the owner the day everything needed is in place.

## What the owner needs, in the owner's words

Read `/needs/*`. Each says what, how much, the price ceiling, and how many
suppliers must be able to deliver (`want`). Typical: three widget suppliers
under the ceiling, two for gizmos, one for needles with no more than five
days' notice, and VRAM available at all.

## What counts as evidence

- A supplier satisfies a need when its latest statement, from any channel
  or from `/her/<peer>`, says it can deliver within the ceiling and is still
  in business, and the statement has not expired.
- In business is a statement too: a reply this month, a published name that
  moved, a site that still takes orders. Silence for longer than the need's
  own cadence is a question, not a fact; write it as unresolved with a due.
- A price above the ceiling is not ok, however friendly the supplier; say so
  in the judgment and look for another candidate under the need's standing
  approval. Candidates come from the owner's own history first
  (`/relationships/*`), then from referrals in `/her/*`, then from what a
  listing peer publishes to this world (`/her/<peer>/suppliers/<name>`: what
  they make, a `node` when they run Shrine, a mailbox or number when they do
  not; a listing is a pointer, not a statement about the supplier), then from
  the web.
- A candidate that runs Shrine (a `node` in its listing, or `peer` on its
  relationship) is asked natively: make `/relationships/<name>` with `peer`,
  write the inquiry as `/our/<node>/inquiry/<need>` (`what`, how much, by when,
  a note; never the ceiling), which the host publishes to that node, and
  declare a wake on `/her/<node>`; its terms arrive at `/her/<node>/<name>` and
  are read there from then on. No mail to a world that runs Shrine.
- A candidate with only a mailbox or number is asked through the gateway, as
  any supplier is, under the need's standing approval.

## What the owner sees

After every judgment pass, write one status record per need, poked each time:
`/needs/<name>/status {ok: yes | no, have: <suppliers judged ok>, want: <the
need's want>, by: <who, at what price, one line>, note: <what is short or
pending>, at}`. The owner's page reads these records and the judgments; nothing
else computes the shop's state.

## Cadence

Check each warm supplier as often as its terms expire or as the need's
`every` says, not more. One message per check. Prefer `/her/<peer>` over a
message whenever the peer publishes.

## VRAM, the key dependency

`/needs/vram` is satisfied by a statement that it is available: from
`/her/<supplier>/vram` when a supplier of it publishes to this world, else from
the owner on the need itself. The day it is available, judge every need again:
if each has `want` suppliers ok, write `/attention/<n>` "ready to resume" with
the list of who covers what; if not, say exactly what is short and keep
working on it.

## When to tell the owner

Write `/attention/<n>` when: every need has `want` suppliers judged ok and
VRAM is available (say "ready to resume"); a need drops below `want` and no
candidate answered within a week; a supplier's terms change outside the
ceiling. Otherwise work quietly.
