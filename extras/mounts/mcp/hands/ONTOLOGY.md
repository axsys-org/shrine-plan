# The scheme: what we are making, and what belongs where

VISION.md says what the world should feel like. This file says how it is built, and it is written against what the
kernel can actually do today (checked 2026-10-25 against src/foil and extras/mounts/mcp). Where the code falls short
of the scheme, this file says so.

## 1. The idea

A world is a set of names. Each name is owned by one world and holds a few literal facts about one thing. That is
all that is ever stored.

Everything a reader wants beyond that (what points at a thing, how things nest from a vantage, what three worlds
together know, where they disagree, what is waiting to be done) is computed from the names, by the world itself,
at a name of its own. A computed view is read like a record, pinned like a record, followed by a peer like a
record, and never written down as if it were one.

### The five laws

1. **One thing, one name, one owner.** A thing lives at one path in one world. Every other place it belongs is a
   placement that names it, never a copy.
2. **A slash means part of.** The stored hierarchy is parthood and nothing else. London under the United Kingdom
   needs no slot. Every other hierarchy is a vantage, computed.
3. **A relation is asserted once.** On the record it belongs to, as a slot (or a small child record, when it has
   qualifiers) that names the other thing. The inverse is never written. Reading it the other way is the world's job.
4. **Synthetic data is never primary.** Counts, inverses, unions, trees, candidates: all of it is a cell, a function of
   names, recomputed on read. If a view cannot be reproduced from the names, it is not a view, it is a lie.
5. **Judgement is kept, with its origin.** The world knows no meanings: not what "founder" is, not whether two names
   are one thing, not which founding year is right. A model or a person judges, and the judgement is a record that
   says who judged, from what evidence, and why. Disagreement is kept beside it, never erased.

### Why a world, and not a database with an API

Because the point is the network. A stranger's world can follow a name into mine, read the view I computed over it,
and pin the version they read. They cannot do that with a process on a side port. A view at a name is addressable,
versioned, and the same for every reader; a view in a process is none of those.

### The test of every piece

Ask of any value: *can a stranger reach it by name, and would it come out the same tomorrow from the names alone?*
If yes, it is the world's. If it needs the outside (a page, a model), it is a hand's, and the hand writes the result
back as a record with its source. Python is for what Foil cannot do at all, and nothing else.

## 2. What the kernel can do today (facts, with where to look)

- **Cells are pure.** A formula gets the input tree its `/sys/tack` names (at that care), its own slots, and any
  other reference slot hydrated under `['views <slot>]`. It cannot read the store. (`sys/view.foil:24-29`,
  `lain_peek.foil:764-842`, `weft_std.foil:22`.) Live secondary inputs are allowed; a live tack cannot be read at a
  past case. A formula may return virtual children, but they are not addressable by path: read the cell's root at
  y or z. `follow` is one hop (`weft_std.foil:1671-1693`).
- **There is no reverse-reference index.** "Who points at this name" is answered by `mcp_mount/referenced`, which
  materialises the whole subtree, peeks every target, runs every cell it meets, and rebuilds the crew index of the
  entire namespace, on every call (`mcp_mount.foil:487-566`). The kernel does keep an incremental index for crew
  dependencies (`hive`, `eyes`: `lain_poke.foil:460-540`), which is the precedent to follow.
- **There are no peers.** The kernel refuses any write outside its own node (`namespace.foil:192-197`,
  `helm.foil:62-66`: `outbound_not_supported`). The MCP mount puts the local node in front of any foreign path
  (`mcp_mount.foil:113-121`), which is why `/0x12/...` lands at `/0x11/0x12/...`. The strangers in this checkout are
  folders, not worlds.
- **`/o` cannot run stdlib formulas**, and there is no `/over` route (`lain_peek.foil:350-393`). The only ad hoc
  evaluation is MCP `read` with `formula` and `settings` (`mcp_mount.foil:747-753`).
- **Foil can reach the outside.** The `Fetch` builtin does outbound HTTP from a long-running actor (a *foot*),
  synchronously per actor, with timeouts, no streaming (`src/reaver/http-client.rvr:13-35`). JSON parses and prints
  (`json.foil`). There is no getenv: a mount's `host.py` passes keys as start arguments (`codex/host.py:26`,
  `eden.rvr:250-253`). There is no HTML parser.
- **Foil can run loops and react.** A foot is registered by a mount's start hook (`helm.foil:320-343`,
  `codex_driver.foil:12-42`), wakes when its home folder changes, can tick with `Sleep` from a helper actor, reads
  at y or through a snapshot closure over live state (`feet/gift/snapshot`), and writes atomically with a journal
  tag so history records who (`feet/gift/batch`, `mcp_mount.foil:93-99`). A *kook* is a pure in-kernel hand that
  runs inside the triggering event when a watched path changes (`lain_poke.foil:410-450`); `overlay_cache` is the
  pattern for "recompute and write when inputs change".

## 3. The split

| concern | belongs to | today | because |
|---|---|---|---|
| names, facts, history, cases, references | the world | the world | its job |
| who points at a name | the world: an incremental reference index in the supervisor, read at `/r/<path>` | `links.py` in memory | Foil can keep it the way it keeps `hive`; the per-call rescan is the only reason Python has it |
| a thing's relations, both ways, across its `same` links | the world: a kernel read built on `/r` | `links.py` | pure function of names and the index |
| the thing as a world (the unfold), union, knows, shared, reach | the world: kernel reads with a depth and a node budget, pinned like any derived read | `links.py` | pure functions of names; a peer must be able to read them |
| placements (overlay cells), hygiene counts, saved arrangements | the world: cells | cells | already right |
| claims, same/different judgements, sync runs and cursors | records, written by hands | records | already right |
| identity candidates with evidence | a Foil foot, writing candidate records with their evidence | `links.py` | it is scoring over names, not judgement; a foot can do it |
| fetching pages, mapping sites (Firecrawl) | a Foil foot calling `Fetch`; Firecrawl returns markdown, so no HTML parser is needed | `sync.py`, `web.py` | Foil can |
| calling the model, deciding what a text says, judging identity | a Foil foot calling `Fetch` to OpenRouter | `digest.py`, `agent.py` | Foil can |
| name resolution inside texts (which names a text mentions) | a Foil foot or kook writing `mentions` records | `links.py` | pure over names |
| search engines by scraping HTML (Bing, Brave, DDG) | dropped, or Python | `web.py` | Foil has no HTML parser; Firecrawl search returns JSON and replaces them |
| streaming a reply word by word to the page | Python relay, or dropped | `agent.py` on 8311 | `Fetch` buffers; this is the one thing Foil cannot do today |
| passing API keys in | `host.py` `prepare()` | environment | Foil has no getenv |
| the page | JS | JS | its job |

So Python keeps three small things: the key hand-off, an optional streaming relay, and nothing else. Everything the
hands do that is a function of names moves into the world as reads; everything that needs the outside moves into
Foil feet that call `Fetch`.

## 4. Build order

Each step leaves the world runnable and is tested on the three-world data before the next.

1. **Reference index in the kernel.** The supervisor keeps `into`: target → {(holder, slot)} for every `safe` slot,
   updated from each event's diffs the way `hive` is. A new derived read `/r/<path>` answers at y with one hollow
   folder per slot label holding the referencing records. `referencing` on the MCP read becomes a thin call to it.
   This removes the only structural reason the Python index exists.
2. **Relations and the unfold as kernel reads.** `/v/<depth>/<path>`: the thing as a world, union over `same`,
   bounded by depth and a node budget, each thing once, computed from `/r` and the store. `/u/<path>` for the union
   with per-world tags and disagreements. Both pin at a case like `/x`. The page and the agent read these instead of
   port 8312.
3. **Hands as feet, simplest first.** `sync` (Firecrawl, cursor per page), then `digest` (model, one world's
   conventions, identity guard), then `web`, then `agent`. Each is a mount with `host.py` passing keys and a foot
   registered at `/<node>/io/<hand>`. The Python hand is deleted as its foot passes the same checks.
4. **Candidates and mentions as a foot.** Identity scoring and text resolution move last; until then `links.py`
   runs with its graph code removed, as a cache only.
5. **Peers.** Real worlds need outbound routing (`helm.foil:65-66`) and a remote reader. Out of scope here; the
   folder simulation stays, and every doc says so.

## 5. Research notes

Kernel: cells are pure functions of their slots, tack tree and secondary inputs, recomputed on read
(`sys/view.foil:24-29`, `lain_peek.foil:764-842`); `gather` with no secondary inputs returns its input unchanged,
so an overlay is a native cell today. Prior art: Freebase compound value types and Wikidata qualifiers (facts with
qualifiers as their own nodes), polyhierarchy in faceted classification (one item under several broader terms),
ISO 25964's split of broader terms, and owl:sameAs taken as a judgement. The design here keeps one real record per
thing and expresses every other placement as an overlay, which is polyhierarchy without duplication.
