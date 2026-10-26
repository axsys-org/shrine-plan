# Cells, views and the reverse-reference index: the world computes how things connect

Branch `ic-bare-loop-main`: `ic-bare-loop` merged with main and reduced to the kernel, the mounts and the
launcher; the research hands, skills and notes are on `ic-bare-loop-notes` for a second PR. Kernel first, then
what rides on it. Every number
has its reason in the code; every kernel edit has its sentence here.

## 1. The store knows what points at what (`reference_index`, `shrine`)

A record's reference slots are the only edges the world has. `sov` now carries a reverse index of them, maintained
in `apply` where every change already passes, rebuildable from the journal (`reindex_references`), with bounded
snapshots (`span` 64) so a pinned read at an older epoch sees the edges of its time and a live read takes the
current edges without unpinning anything. `/r/<len>/<path>` reads the edges naming a thing, length-prefixed like
`/h`: nothing is searched for, everything is named. A reference inside prose, a path in brackets in any text
slot (`[/0x11/user/orgs/verisk]`), is collected by the same one function as a reference in a slot, held by the
slot the prose sits in: a text's names are edges without a second record, and what names a thing is `/r` and
nothing else.

Why in the kernel: a second store (the Python index we had) would be a copy with its own clock; here the index is
derived state committed with the epoch that changed it.

## 2. Reads: `/r`, `/o`, the woven evaluator (`lain_peek`, `lain_types`)

A view is a record with a formula and an input. Reading it runs the formula through the demand protocol: the plan
asks for names, the kernel reads them, records each observation, and bounds the whole by fuel. `/o/<case>/…/<def>/…/<data>`
applies a definition to data without a cell; `/x` and `/c/x` read a cell and its context, observations included.
`read_fuel` (32768) is the ceiling, not a budget: a cell declares its own at `/sys/view/fuel`. A cycle through a
reference answers unknown with the reason. The view protocol types live in `lain_types` because an upgrade retains
the old `sys/*` modules for brand stability and compiles everything else afresh; the rule is written beside the
types.

## 3. The graph overlay (`graph`, one module)

One module, five sections and a registry: `op` (what every view reads with), `view` (a thing's relations: forward
from its own slots, backward from the index, through its `same` judgements; each edge carries its holder, the
record whose slot points across, and is attributed to the world asserting it; a cell that reads a thing is a
backward edge under the cell's name whose contents are what the cell computes), `world` (one thing as a world:
relations as folders, breadth first, each thing once, bounded by `depth`, `cap`, `deeper` and `nodes` read from
the cell with documented defaults), `union` (what every world says about one thing), `overlay` (any number of
standings as one picture: a breadth-first walk over every reference, standings that meet share a connected
component, a standing nothing reaches is an island; the result is one virtual root `/<n>` per component with its
standings unfolded as worlds beneath, a standing reached inside another's unfolding listed as seen; the walk
follows parts as well as slots, so a bucket reaches its records, and is bounded by the cell's `/nodes`). Three
names registered under `/weft/graph`: `overlay`, `frontier`, `union`. A folder is the slot the reference sits
in, as its author spelled it, a note's slot when the reference is in prose, or the cell that reads the thing; the
kernel invents no vocabulary of its own (no `mentioned`, no `candidate`, no `_of`, no `tentative`), and the page
decides what to draw dashed. A titled text is a thing. A pinned standing reads its backward edges at its own
epoch. Nothing a view draws is written back.

## 4. Not in this PR, on purpose

No supervisor card (a batch-read `look` existed; nothing called it), no change to `weft_std` (main's library as
it is), no change under `src/reaver` (the saved-world upgrade pipeline lives outside the tree), no in-memory view
cache (its only reader was that card). The kept-world keep hook (`helm/supervisor/run_keeping`, from the
persistence work) is the one supervisor change, twelve lines.

## 5. Mounts and the page (`extras/mounts/mcp`, `extras/mounts/explorer`)

MCP stays four tools (read, write, history, apply). The live page draws a record and the thing as a world from
the one `overlay` name: folders are slots, lines are things with the source's note beside them, what references
the thing is a folder under its holder's name marked `←` (a slot, a text's `mentions`, a cell with its result
beneath), and the standings the person gathers read as components and islands through a workspace cell the page
writes. No Python index, no fallback routes.

## 6. Kept worlds and hands (`x/eden`, `x/eden_hands.py`, `SETUP.md`)

`x/eden --world DIR` keeps a world and resumes it; the hands named in `world.json` run beside it; the mounts come
from the checkout on every run, the snapshot is the world's.

## Tests

Foil suites under `src/foil/tests`: references, reference reactivity, reference walk, queries, query transport,
composition, view publication, working views, cells, overlay cache, value read, supervisor, graph, graph world,
graph workspace, graph union. On main's runtime after the merge, the whole Foil group: 1,521 checks pass, none
fail; the four suite errors
(`lain_store`, `lain_fixture`, `grove_publication` need-fail at completion, `fs_sync` compile) are main's own, as
pristine main shows on the same runtime. The test inventory is brought up to date so `x/check` runs at all.

## Kept from the Codex review, named as such

`namespace/system_at` (an epoch's own system publication for a frozen computation), `lain_poke`'s trigger
spelling for `/r`, and `sys/slots` with the regenerated catalogue. Each is needed by the reads above.

## Not in this PR

The research hands (`registries.py`, `web.py`, `digest.py`, `links.py`, `agent.py`), the agent skills and the design
notes: a second PR on top of this one.
