# Handoff: finishing Shrine's worlds, properly

> Implementation checkpoint, 2026-10-25: native demand cells, indexed incoming
> references, addressable computed children, local epoch pins and observation
> caches now have isolated passing tests. The named outline operator reads
> available names without evaluating the placed records; gather retains an
> explicit unresolved branch when a member cannot be evaluated. The MCP tests
> verify shallow reads and reusable computation pins. These changes are not
> yet deployed to the saved Explorer world. Core publication succeeds in a
> disposable clone; safe service/mount reconstruction is still being tested.
> Python graph-policy replacement, chat side panel, and equivalent end-to-end
> performance comparison remain unfinished. Do not describe the original plan
> below as the current implementation or claim performance parity.
>
> Latest product clarification: distinguish canonical knowledge, an instantiated
> view, and its reusable definition. New established references should enrich
> existing live views. Task views may reuse other views directly; they need not
> first expand As a World. Structure is observable independently of record
> contents. Coverage is an evidenced claim with an explicit scope, never inferred
> from the number of results or a missing record. Native discovery and compatible
> input bindings can automate routine reuse; choosing an interpretation, asserting
> identity, or judging a source still requires justified semantic decisions.

> Update, 2026-10-25: Ian designated `COMPOSABLE_NAMESPACE.md` as the governing
> product specification for this work. Read it first. The objective is a
> composable namespace, including addressable virtual children, reference
> traversal, complete dependency pins, bounded branch reads, and precise cache
> invalidation. Explorer is a compatibility target; its JSON does not define
> the architecture. The special graph routes proposed in step 2 below are
> superseded by generic kernel mechanisms and named Foil computations. Adding
> a world within a path contributes its matching locality; it never resets to
> that world's root. Structural composition and identity joins are distinct.
> Networking remains out of scope. The five-world example is a target fixture,
> not a claim about implemented peers.

For the next agent. This is the whole context: what we are making, what exists, what is wrong with it, the kernel
facts the plan depends on, the plan in order with acceptance checks, and the rules of the house. Written
2026-10-25 on branch `ic-bare-loop` of the `shrine-cells` checkout, at commit `8386eec` plus the files this handoff
adds. Read VISION.md (Ian's spec, the authority), then ONTOLOGY.md (the scheme and the split), then this.


> **2026-10-25, late.** `ASSEMBLY.md` beside this file is Ian's statement of the finished shape: independent agents
> discover and write back; the kernel's views reveal the routes by which the pieces connect; the routes are the
> agent's research signal. It adds two views to build after the ground below is real: a **conjunction** view (several
> names in, the connecting routes, the shared hub, the disconnected regions with evidence-backed ways forward; the
> Python `between`/`reach` today) and a **working-world summary** (connected, uncertain, missing, reusable views, next
> operations, a few hundred tokens), widened by ASSEMBLY.md part two into a **connection workspace**: components over a set of names, every edge labelled established or tentative, candidate bridges, isolated regions; the relation reader must stop dropping `/web/` targets and label them instead. Its guard applies to all of these: rank paths by evidence, never by count or hop
> distance; a mention or a name match is never an established connection.

## 0. The point, in one paragraph

A world is a set of names. Each name is owned by one world and holds a few literal facts about one thing. That is
all that is stored. Everything else a reader wants (what points at a thing, how things nest from a vantage, what
three worlds together know, where they disagree, what work is pending) is computed from the names, by the world,
at a name of its own, so it can be read, pinned, and followed by a peer. Worlds never merge. What compounds is
reach: a name in my world points at a name in yours, a view is computed over both, a third person follows it into
either of us and pins the version they read. The five laws are in ONTOLOGY.md §1; the test of every piece is: *can
a stranger reach it by name, and would it come out the same tomorrow from the names alone?* If yes, it is the
world's (Foil). If it needs the outside (a page, a model), it is a hand's, and the hand writes the result back as a
record with its source. Python is for what Foil cannot do at all.

The two reference systems Ian pointed at, and what to borrow from each (clones were in a session scratchpad;
re-clone them):
- `https://github.com/gwbtc/libmesa.git`: Mesa, signed bounded reads of a name from another peer, in Rust with a C
  ABI. This is the transport Shrine lacks. Step 6 below.
- `https://github.com/gwbtc/chorus.git`: a Gall agent where ships publish listings, poll each other, vet every value
  by type on the way in, merge all ships' notes into one tree keeping authorship (a colliding path moves under a
  segment naming the ship), and link to one *revision* of a note (an FQSP), so a link never changes meaning. Borrow:
  pin cross-world references to a revision; bring indexes, not bodies; vet on the way in; merge with authorship;
  never copy.

## 1. What exists today

### The world

- One wisp process serves the world on `http://127.0.0.1:8300` (MCP at `/mcp`, live page at `/live`, stream at
  `/mcp/stream`). Boot and resume: `python3 x/eden --extras-root $PWD/extras --world <dir>` from the checkout root.
  The test world used for everything below is `~/.local/share/shrine/worlds/test-20261023` (its log is `out.log`
  inside). Boot takes 45–90 s before `/mcp` answers.
- Your world is `/0x11/user`. Three strangers are **simulated** as subtrees: `/0x11/0x12/user` (a financial
  researcher: companies by ticker, `private/mis`, `deals/...`), `/0x11/0x13/user` (an industry analyst:
  `companies/mckenzie`, `founders/...`), `/0x11/0x14/user` (one record). They are folders, not worlds: the kernel
  refuses writes outside its node and the MCP mount prefixes the local node onto any foreign path
  (`extras/mounts/mcp/mcp_mount.foil:113-121`). Every doc must keep saying so until step 6 lands.
- Each stranger has `/<world>/style` (its naming conventions in prose, which the digest follows) and
  `/<world>/syncs/research` (its page list, with `runs/r<n>` beneath).

### The MCP surface (`extras/mounts/mcp/mcp_mount.foil`)

Four tools: `mcp/read`, `mcp/write`, `mcp/history`, `mcp/apply`. `read` takes `path`, `care` (x record, y record
plus children, z subtree), `case`, `find`, `referencing`, `formula`+`settings` (run a stdlib formula over the read,
no secondary inputs), `limit` (≤500), `next`, `reads` (a batch). `write` takes `records [{path, slots, action
make|poke|cull, if_case, from}]`, `then`, `who`. `who` is a convention: the batch also writes
`/<self>/agent/journal/<who>` so `history` can name the writer (`mcp_mount.foil:93-99, 1067-1090`). A reference
slot is `{type: reference, path, care, case}`; case 0 is live. A cell is a record with `sys/weft` (a reference to
`/weft/stdlib/<name>`) and `sys/tack` (a reference with a care); read its result at `/x/<path>` and its context
(faults, holes) at `/c/x/<path>`. The Python client used by the hands is `World` in `extras/mounts/mcp/hands/hand.py`.

### The hands (`extras/mounts/mcp/hands/`, Python, each a process outside the world)

| file | what it does | keep / move |
|---|---|---|
| `hand.py`, `stream.py` | the base: config at `/agent/hands/<name>`, follow the stream (poll fallback), `line`/`tick`, writes signed `who` | stays while any Python hand remains |
| `links.py` (~1,400 lines) | the index on port 8312: references both ways, names and aliases, `same_as` across worlds, `relations`, `unfold`, `union`, `knows`, `shared`, `reach`, `identity_candidates`, `signals`, the undigested-text queue, talks registry, name candidates, `mentions` caches. Cache file `~/.cache/shrine/links-<node>-<worldid>.json` | **the shadow store: move to the kernel (steps 1–2), keep only as cache until then** |
| `digest.py` | per world: asks a fast model to turn each text into records under that world's conventions; identity guard (a text may only touch a record it names by a longer name); claims instead of overwrites; first source kept, later sources beside | move to a Foil foot (step 4) |
| `sync.py` | a site or page list into a world via Firecrawl; regions named by content hash so a re-sync writes only differences; cursor per page so an interrupted run resumes | move to a Foil foot (step 4, first) |
| `web.py` | answers asks by searching (Firecrawl, Bing, Brave, DDG, Wikipedia) and extracting with a model; pages stored as sources | move to a Foil foot; drop the HTML-scraped engines (step 4) |
| `agent.py` | the one you talk to; reads the record, claims, union and identity candidates; writes judgements (`same`/`different` records with `why`); `preserve_claims` and `keep_sources` live here and are imported by digest; streaming replies on port 8311; `AGENT_BACKGROUND` off by default | move to a Foil foot; streaming is the one thing that may stay Python (step 4) |
| `clock.py`, `source.py` | the world starts these itself | leave |

Launch lines (keys from the environment, never in the repo; Foil has no getenv, see §2):
```
python3 -u extras/mounts/mcp/hands/links.py  http://127.0.0.1:8300 --node 0x11 --peers 0x12,0x13,0x14
OPENROUTER_API_KEY=... python3 -u extras/mounts/mcp/hands/digest.py http://127.0.0.1:8300 --node 0x11
OPENROUTER_API_KEY=... FIRECRAWL_API_KEY=... AGENT_BACKGROUND=off python3 -u extras/mounts/mcp/hands/agent.py http://127.0.0.1:8300 --node 0x11 --name a --model anthropic/claude-sonnet-5.5
OPENROUTER_API_KEY=... FIRECRAWL_API_KEY=... python3 -u extras/mounts/mcp/hands/web.py http://127.0.0.1:8300 --node 0x11
FIRECRAWL_API_KEY=... python3 -u extras/mounts/mcp/hands/sync.py http://127.0.0.1:8300 --node 0x11
```
Start them one at a time, links first (the others ask it for the queue and the graph). Restarting several at once
once crashed the wisp (SIGABRT in `nat.c pl_limb_view`, not root-caused).

### The page (`extras/mounts/explorer/goo-live.js`, `.css`, `.html`)

A record page draws: the card, claims, "as a world" (the unfold from port 8312: closed folders open on demand, each
thing once, world badges), relations, beneath, a collapsed "in N worlds" block (union: what worlds agree and differ
on), mentioned in, the talk box. `goo-live.html` carries version stamps for the js and css; they are set by hand to
the first ten hex of each file's sha1 and the world bakes the page in at boot, so after changing the page: restamp,
reboot. 125 node tests: `node --test extras/mounts/explorer/tests/*.test.cjs`.

### What is right already

- One record per thing; relations as a slot naming the other thing, the inverse never written.
- Claims: `<thing>/claims/<slot>_<hash> {slot, value, by, day, source?, why?, retracted?}`; the preferred value stays
  in the slot; a reading hand only adds a claim.
- Judgements: `<thing>/same/<slug>_<world> {same: <ref>, why}` or `<thing>/different/...`; for two other worlds,
  `/0x11/user/identities/<slug> {subject, same|different, why}`.
- Provenance: `source` on a record; later sources at `<thing>/sources/h<hash> {source, supports}`.
- Sync runs as records with a cursor; pending work is inspectable.
- Placements as gather cells over a live record (`collections/cat_intel/...` is the example).

### What is wrong (the slop)

1. **The index is a shadow store.** Relations both ways, the unfold, the union, candidates: all in `links.py`'s
   memory on a side port. A peer cannot read it, nothing can pin it, it rebuilds on restart, truth is split.
2. **874 stale cells** under `/0x11/user/views/related/...` from the earlier "relations as cells" design. Nothing
   writes or reads them (`links.py` still has `write_related`, dead). Cull them (derived, never primary; history
   keeps them), with Ian's word: he has asked that nothing be removed without it.
3. **Cross-world references are live** (case 0). A `same` judgement about a stranger's record should pin the case
   it judged.
4. **No `/over`.** The paper's apply-a-definition-at-a-name is not possible: `/o` cannot run stdlib formulas
   (`lain_peek.foil:350-393`); only MCP `read formula=` evaluates ad hoc.
5. **Peers are folders** (above).

## 2. Kernel facts the plan depends on (checked against the source; verify again before building on them)

- **Formulas are pure.** A stdlib formula gets the input tree its `/sys/tack` names at that care, its own slots, and
  any other reference slot hydrated under `['views <slot>]`; it cannot read the store (`sys/view.foil:24-29`,
  `lain_peek.foil:764-842`, `weft_std.foil:22`). Live secondary inputs are allowed; a live tack has no past case.
  Output may hold virtual children but they are not path-addressable: read the cell root at y or z. `follow` is one
  hop. No budget inside a formula; a tack chain over 64 edges counts as a cycle (`lain_peek.foil:869-885`).
- **The cycle rule:** a plain input is a cycle when its path is a prefix of (or equal to) the cell's path; for an
  `/x/...` input, when the referenced cell is at or above the cell; message `"cycle: the input contains this
  cell"` (`lain_peek.foil:815`).
- **No reverse-reference index.** `mcp_mount/referenced` (`mcp_mount.foil:487-566`) materialises the subtree, peeks
  every target, runs every cell it meets, and rebuilds the crew index of the whole namespace, per call. The
  precedent for an incremental index is the crew index `hive`/`eyes` (`lain_poke.foil:460-540`), kept across
  events inside the supervisor (`sovereign_cycle_with`, `helm.foil:172-184`).
- **No peers.** `namespace/permitted` requires ownership (`namespace.foil:192-197`); outbound cards are rejected
  with `'outbound_not_supported` (`helm.foil:62-66, 117`).
- **Outbound HTTP exists.** The `Fetch` builtin (`src/reaver/foil-builtins.rvr:545`, ABI in
  `src/reaver/http-client.rvr:13-35`): `Fetch [method url headers body] [connect deadline redirects buffer]` →
  `either[nat [status url headers body]]`; strings are bars (bytes plus a 0x01 sentinel; `bar`/`unbar` helpers in
  `http_foot.foil:155-162` and `extras/mounts/codex/codex_foot.foil:14-21`); synchronous per actor; buffered, no
  streaming; error codes 0–7. `str/cat x y` is y-then-x; use `str/cat_all`. JSON: `json/parse`, `json/show`
  (`src/foil/json.foil`). No getenv: a mount's `host.py` `prepare()` returns the start arguments
  (`extras/mounts/codex/host.py`), handed to the mount's `start \ server=nat arguments=row[str]`
  (`src/reaver/eden.rvr:250-253`). No HTML parser in Foil; Firecrawl returns markdown, which is enough.
- **Feet are the in-kernel loop.** A mount's `start` makes a home record and calls `helm/supervisor/register home
  <foot>/run` (`extras/mounts/codex/codex_driver.foil:15-41`, `helm.foil:320-343`). The foot receives
  `feet/task/init`, then `feet/task/fact binding` after any event that changes its home at y (record plus direct
  children). It reads with `feet/gift/peek` (y only) or `feet/gift/snapshot` (a closure over live state; this
  checkout only), writes with `feet/gift/poke`/`pass`, and in this checkout `feet/gift/batch` sends one atomic
  event that can carry the `agent/journal/<who>` tag. No timer: spawn a helper actor that `Sleep`s (seconds) and
  `Send`s a tick, as `codex_foot/reader` does. **Caveat to verify first:** the resume path re-registers only
  `io/fs` and `io/http` (`eden.foil:142-145, 184-206`); mount start hooks may run only on a fresh boot. If so, a
  foot must be re-registered on resume, or eden must learn to re-run mount starts.
- **Kooks are the pure in-kernel reactors**: a record with `/sys/limb` and `/sys/crew` has its form's `hear` run
  inside the event when a watched path changes (`lain_poke.foil:410-450`); 8 reaction rounds max; `overlay_cache`
  is the pattern for "recompute and write when inputs change" (`overlay_cache.foil`). `hand_std.foil` is the
  helper library (bounded `scan`, `children`, `descendants`, `sum`, `filter`, `diff_*`).
- **Events:** `/<self>/log/<epoch>` holds `namespace_event` (unsigned; `who` only via the journal tag). Forward
  iteration is a loop over epochs (`mcp_mount.foil:993-1032`). Nothing can subscribe to `/log`.
- **Ad hoc evaluation:** MCP `read` with `formula` and `settings` (`mcp_mount.foil:747-753`) runs a stdlib formula
  over the read without secondary inputs.

## 3. The target

See the table in ONTOLOGY.md §3. In short:
- the world owns names, references both ways, every derived reading (relations, the unfold, the union, candidates),
  placements, pins, cycles;
- hands become Foil feet that call `Fetch` (Firecrawl, OpenRouter) and write records with their source;
- Python keeps `host.py` (keys in), optionally a streaming relay for the typing bubble, and the page's JS.

## 4. The plan, in order

Each step leaves the world runnable and is proven on the three-world data before the next. Keep the step's commit
small and named after what it does.

### Step 0: housekeeping (an hour)

- Get Ian's word, then cull the 874 `/0x11/user/views/related/**` cells (one write batch, `who: repair`), and delete
  `write_related`, `related_slots`, `affected` in `links.py`. Record what was culled in the commit message.
- Re-clone libmesa and chorus somewhere outside the repo for reference.
- Run the baseline: `python3 extras/mounts/mcp/tests/strangers/snapshot.py /0x11/user before.json`, then
  `python3 extras/mounts/mcp/tests/strangers/proofs.py before.json`. Expect 11 PASS, 2 UNSUPPORTED (9 peers, 10
  permissions). Keep `before.json`: every later step diffs against it (`snapshot.py --diff before.json after.json`
  must report `overwritten_knowledge: []` and `removed: []`).

### Step 1: the reference index in the kernel, read at `/r/<path>`

Goal: "who points at this name" is the world's, incremental, cheap, and a read at a name.

- Where: the supervisor's kept state, beside `hive`/`eyes`. Fold each admitted event's diffs
  (`namespace_event.changes`): for every record written, remove its old `safe` slots from `into`, add the new ones.
  `into: target → {(holder, slot)}`; `out: holder → [(target, slot)]`. Build it once at resume by one walk, the
  way `sovereign_hive` walks (`lain_poke.foil:460-470`), then never again.
- The read: a new arm in `resolve_view` (`lain_peek.foil`) beside `/x` and `/c/x`: `/r/<path>` answers at y with
  one hollow folder per slot label under which each referencing record appears at its full path, with its own
  slots; at z, the referencing records' subtrees. `/r/<path>` of a prefix includes references into anything beneath
  it (the current `referencing` semantics). Pin: `/h/y/<case>/<len>/r/<path>` reads the index as of that case;
  acceptable first version: live only, with `xv_case`-style case reporting.
- The MCP `read referencing=` becomes a thin call to it. Keep the old answer shape.
- The index needs access from reads: the snapshot reader only sees `state`, not the supervisor's kept index
  (`helm.foil:161-168`). Put the index in `state` (the namespace value) so reads see it, or give readers the
  supervisor's copy. Decide after reading `helm.foil` and `namespace.foil`; the first is simpler.
- Foil checks: `x/check foil:tests/lain_peek` and a new `src/foil/tests/references.foil`: write a record pointing
  at another, read `/r/<target>`, change the slot, read again, cull the holder, read again (empty). Per the house
  rule, running a Foil check starts a wisp, so the test world must be down first (§6).
- Acceptance on the test world: for McKenzie (`/0x11/user/orgs/mckenzie_intelligence_services`), `/r` lists
  `founder`/`works_at` from Forbes, `acquisitions` from Verisk, `same` from the strangers, each holder named; the
  read returns in under 50 ms; `links.py`'s own `into` for the same path matches it exactly (write a one-off
  comparison script; keep it in `tests/strangers/`).

### Step 2: relations, the unfold and the union as kernel reads

Goal: the three views the page and the agent use come from the world at names, bounded, pinnable.

- `relations` (a Foil function in `lain_peek` or a new `views.foil`, given a reader and the index): a thing's
  outgoing reference slots, its incoming from `/r`, and the relation records beneath it (an unnamed child record
  speaks for its nearest named ancestor; its primary reference is the other thing, its other slots are qualifiers:
  this is `links.py` `holder_of`/`primary`/`_relations_one`, port it line for line). Union over `same` links
  (transitive, both directions, read from `/r` with slot `same`), each relation tagged with the asserting world.
  World of a path: `/0x11/0x12/user/...` is `0x12` (until step 6, when it is the real node).
- `/v/<depth>/<path>`: the thing as a world. Port `links.py` `unfold` exactly: breadth first, each thing once by its
  `same` group, opened only where it first appears, folders pointing at a thing closed as counts beyond the
  subject, `cap` per folder, parts (children that are things) by their folder. Output: a tree of hollow folders and
  items with `world`, `worlds`, `by`, `labels`, `note`, `seen`, `more`, `closed`, exactly the JSON the page reads
  today, so `goo-live.js` only changes its URL. Budget: a node count, say 400, reported in the context at `/c/v/...`.
- `/u/<path>`: the union. Port `links.py` `union`: members (the `same` group), worlds, facts (values grouped by
  normalised value whatever slot each world filed them under; relations grouped by the other thing's `same`
  group), `all` (every world asserts it), disagreements per slot including non-retracted claims. Plus `knows`
  (what world A asserts that world B does not) as `/u/<path>?...` is not a path; make it a formula over `/u`
  instead: a stdlib `where` over the union's facts. `shared` (things several worlds describe) and `reach` (pairs
  joined only when every listed world takes part) can stay Python in the cache hand until step 5; they are
  reports, not reads a peer needs.
- Page: `unfold`, `around` and `union` in `goo-live.js` read `/v/3/<path>`, `/r/<path>` and `/u/<path>` through
  the MCP `read` instead of port 8312. Agent (`tree_reading`, `signals_reading`): same.
- Acceptance: the record pages for Verisk, McKenzie and Walkaway render the same tree as before (dump both JSONs
  and diff; differences must be explainable). `proofs.py` checks 1, 2, 13 pass with the index hand stopped.

### Step 3: cross-world references pin their revision

- A `same`/`different` judgement about a record in another world is written with the case the judge read
  (`case: <n>`, not 0). The agent's bootstrap rule and the digest's guard say so; `apply` in `agent.py` fills the
  case from the read it made.
- The union shows, per member, the case the judgement pinned and whether the member has moved on since (compare
  with the live case). That is "previously observed vs currently verified" from VISION §12 made concrete.
- Acceptance: write a judgement, change the stranger's record, read `/u`: the judgement still names the old case,
  the union flags the member as changed.

### Step 4: the hands become Foil feet, simplest first

Pattern for every one (copy `extras/mounts/codex/`): a mount with `mount.json` (`start` entry, `host`), `host.py`
whose `prepare()` reads the keys from the environment and returns them as start arguments, `<hand>_mount.foil`
whose `start` makes `/<node>/io/<hand>` and registers `<hand>_foot/run`, and the foot: a `Recv` loop reacting to
`fact` (new request kids under its home) and to a tick from a helper actor, doing `Fetch` in a spawned worker,
writing back with `feet/gift/batch` carrying the journal tag so history says who. Keep each Python hand running
until its foot passes the same acceptance, then delete the Python file.

1. **sync** (first: no model, pure I/O). Firecrawl `/scrape` with `formats: ["markdown"]`, split markdown at
   headings into regions, name each `h<sha1 of heading+text>` (Foil has no sha1 builtin? check `src/reaver`;
   BLAKE3/mug exist in libmesa but not here; if no hash builtin, use `mug` or a length-plus-prefix key and note
   it), write page + regions, cursor per page in `runs/r<n>`, 429 backoff, `fresh` to bypass Firecrawl's cache.
   Acceptance: `proofs.py`'s re-sync behaviour (an interrupted run resumes at the next page; a re-sync writes only
   changed regions) reproduced with the foot; the Python `sync.py` deleted.
2. **digest**. The rules text and the per-world conventions (`/<world>/style`), OpenRouter chat completions via
   `Fetch`, JSON reply parsed, the identity guard (`names_of`, `guard_identity`), `preserve_claims`, `keep_sources`,
   bad paths dropped, `digested: true` on each text. The undigested queue: until step 5 the Python cache hand still
   serves `/undigested`; the foot can read it over HTTP, or better, make the queue a cell: texts under `/user`
   without `digested`, a `where` over a z read (check the cost on 5,000 records; if too slow, keep the cache).
3. **web**: Firecrawl `/search` and `/scrape` only (drop Bing/Brave/DDG scraping: no HTML parser), extraction via
   the model, rows written under the ask, the priority queue as records (`asks` with `taken`).
4. **agent**: the biggest. Its reading (`tree_reading` over `/r`, `/v`, `/u`), its bootstrap rules (keep the text),
   the turn loop at any `.../talk/turns`, judgements with pinned cases, `preserve_claims`/`keep_sources`. Streaming:
   `Fetch` buffers, so either drop the live bubble (write the reply whole) or keep a 30-line Python relay that
   streams OpenRouter to the page and writes nothing. Decide with Ian.

### Step 5: candidates, mentions and the queue as the world's

- Identity candidates (`identity_candidates` in `links.py`: shared hosts/codes/phrases, both-cite-one-source,
  same-relation-to-one-joined-thing, names as phrases, weighed by rarity, name-only marked): a foot that recomputes
  on a tick and writes `/<node>/user/identities/candidates/<a>_<b> {a, b, score, evidence..., name_only}`; the
  agent reads them as records. Judged pairs (a `same`/`different` exists) are skipped.
- Mentions (`mentions` records under texts): a foot or kook; the alias table is a function of names.
- Delete `links.py`. Delete port 8312 from the page and the agent.

### Step 6: peers, through Mesa

- Outbound routing in the supervisor (`helm.foil:65-66` rejects moves today) and a remote reader: a read of
  `/0x12/...` becomes a Mesa read of that name from the peer, signed, bounded, cached by case. libmesa's C ABI
  (`crates/mesa-ffi/include/mesa.h`) is the transport; the wisp runtime would link it. This is runtime work and a
  separate plan; design it after steps 1–3 exist, because they are what a peer reads.
- When it lands: `world_of` reads the real node, the strangers move to real nodes, and `proofs.py` checks 9 and 10
  stop being UNSUPPORTED.

## 5. Acceptance for the whole

- `proofs.py`: 11 PASS, 2 UNSUPPORTED until step 6, with `links.py` stopped after step 5.
- `snapshot.py --diff` against the step-0 baseline: nothing removed, no knowledge overwritten (talk, mention
  caches and views may change).
- The record page draws the same tree and union from kernel reads; 125 node tests pass.
- A fresh boot of the saved world serves every view with no Python process running except `host.py` at start.
- Every value a reader sees is reachable by name through MCP `read`, and `history` can say who wrote each record.

## 6. Rules of the house (Ian's, verbatim where they matter)

- **One wisp at a time, always.** `pgrep -fl "wisp|x/eden"` before any boot. A Foil check (`x/check foil:...`,
  `x/foil-check`) starts a wisp, so stop the test world first and boot it again after. Use the light world (`--mount
  mcp --mount probe`, no explorer) for suites; the explorer only for a page check, on its own. Tear each world down
  before the next; delete temp world directories (`.check/run-*`, `/var/folders/.../shrine-eden-*`). If a run's RSS
  passes 4 GB or free disk drops under 3 GB, stop and tell Ian.
- **Commits**: under Ian_C, plain message, no Co-Authored-By or attribution line of any kind. Push to
  `ic-bare-loop` only when he says. **No PR without his approval.**
- **Keys**: `OPENROUTER_API_KEY`, `FIRECRAWL_API_KEY` from the environment; never echo them, never commit them.
- **Never cull a thing.** Things get `moved_to`; only derived records (views, caches) may be culled, and only with
  his word. Preserve 0x11's existing knowledge; prove it with `snapshot.py --diff`.
- **No holes, no hardcoded slot or location lists, no statistical synonym guessing.** Identity is evidence plus a
  recorded judgement with `why`. The world knows no meanings.
- **Hands restart with their flags**: agent `AGENT_BACKGROUND=off`; links `--peers 0x12,0x13,0x14`; one hand at a
  time.
- Don't touch the Codex session's `work/`. No Docker. Never capture the namespace in a route closure.

## 7. Where things are

```
extras/mounts/mcp/hands/VISION.md      Ian's spec: the authority
extras/mounts/mcp/hands/ONTOLOGY.md    the scheme, the kernel facts, the split, the build order
extras/mounts/mcp/hands/SYNC.md        the networking design the hands keep to (predates this plan; step 6)
extras/mounts/mcp/hands/hands.md       the original two-hand design and the base's rules
extras/mounts/mcp/hands/*.py           the hands (above)
extras/mounts/mcp/mcp_mount.foil       the MCP surface: tools, read/write/history, find, referencing, formula
extras/mounts/mcp/tests/strangers/     world.py (client), snapshot.py (fingerprint + diff), proofs.py (the 13 checks)
extras/mounts/explorer/goo-live.*      the page; tests/*.test.cjs
extras/mounts/codex/                   the pattern for a mount with a foot and a host.py
src/foil/lain_peek.foil                reads: /x, /c/x, /h, /o; cell_run; cycle rule
src/foil/lain_poke.foil                writes, reactions, the crew index (hive/eyes)
src/foil/helm.foil                     the supervisor, feet, register, gifts
src/foil/namespace.foil                ownership, permitted, the log
src/foil/weft_std.foil                 the stdlib formulas (gather, count, where, follow, ...)
src/foil/sys/view.foil                 the cell type
src/foil/json.foil, fetch.foil         JSON; the (unused) fetch vocabulary; the real call is the Fetch builtin
src/reaver/http-client.rvr             Fetch ABI
x/eden, x/check, x/foil-check          boot a world; run Foil suites
```

## 8. Open questions to settle before each step

1. Do mount start hooks run on resume? (`eden.rvr:250-253` vs `eden.foil:184-206`.) If not, feet die on resume.
2. Can a read see supervisor-kept state, or must the reference index live in the namespace value? (`helm.foil:161-168`.)
3. Is there a hash builtin in the runtime (for region names)? A grep of `src/reaver/foil-builtins.rvr` for sha, blake, hash and mug finds none; check the Rust side under `src/reaver` and the FFI list at lines 523-552 before assuming.
4. Cost of a z read over `/0x11/user` (5,500 records) inside a formula, for the digest queue as a cell.
5. Streaming replies: drop, or keep a Python relay. Ian decides.
6. The SIGABRT in `nat.c pl_limb_view` when several hands restart at once: not root-caused; watch for it.

## State at the end of 2026-10-26 (early hours)

What runs natively now, on a fresh world booted from this tree with records replayed (`extras/mounts/mcp/tests/strangers/replay.py`
writes a `snapshot.py` fingerprint back through MCP, references live):

- the graph registry at `/weft/graph`, seventeen names, `workspace` new: several standings (the input and
  `standing/<key>` slots) as one picture: components over established hops, routes between standings with every hop
  attributed and marked `solid` or `mention`, islands, gaps with the count of tentative routes between the pair;
- edge strength on every relation (`graph_views/relation.strength`): a reference slot or judgement is solid; a stored
  text's `/mentions` record naming the thing is a mention, emitted as an `in` relation labelled `mentioned` to the
  text, drawn tentative in as_world and frontier, never opened further; the walker no longer skips `mentioned`;
- as_world items carry `tentative`, a text's heading or page title stands in for a missing `name`;
- the live page draws as-world with its notes, the mentioned folder with tentative items dashed, and a workspace
  section: add to workspace / drop, meter (components, islands, reached, tentative, opened), islands, routes with
  their hops and notes (soft hops amber), gaps with their tentative-route count. The page writes the workspace cell
  at `/<node>/user/views/workspace` and reads `/x` of it, exactly as an agent would;
- the web hand writes `domain` and `endpoint` on each page record (identity), beside url, title, fetched, digest.

Proof seen in the browser: Verisk, Ian Channer and Double Indemnity as standings: Verisk to Ian is one established
hop; Verisk to the film is five hops, two through one web text region that names both London and California, drawn
tentative end to end, and the film stays an island because only established hops join components.

Open, with evidence:

- (fixed 2026-10-26) `beneath` faulted (`iota-cmp-bad-quip`, HTTP 500) on any folder with children: a row `take`
  past the row's end traps; the width is a cap, so it is applied only when the row is longer. The page still falls
  back to the record's ordinary read when a view faults.
- The saved-world migration: diagnosed by the bisect session on 2026-10-26 before any run: the trap's three arm
  brands are `shrine/ass/{ker,nul,past}` at definition version 2; a raw `shrine.foil` in the stage sources rebrands
  `ass`, and Codex's `prepare_upgrade.py` is the step that rewrites the stage sources to alias those types to the old
  pinned definitions. Mirroring `src/` into `core-upgrade-src` and `retained-src` with rsync skips that rewrite, so
  every run staged that way traps. Regenerate the stage sources through `prepare_upgrade.py`, never by copying.
  Earlier evidence, kept for the record: on a fresh clone (`upgrade-clone-v3`, copy-on-write from the stopped world) `publication:publish-local` traps with a
  three-arm `unreachable` (a pail match over values of another brand) and `up-published-result` stays unbound.
  Codex's own baseline source fails the same way on the old clone, which had accumulated state from every run, so
  bisect on fresh clones only (`cp -c -R` of the world's `snap` is instant). Until then a fresh world plus replay is
  the way to run this kernel over the saved records; history and cases are not carried.
- `read_fuel` is 32768 (was 256) and `graph_world/nodes` 150 (was 200): a loop bound now, not a budget; as_world
  on a thing with a hundred relations reads each opened record's frontier, identities and incoming edges.
- The store answers `unknown`, not `null`, for a name never written. The graph readers (`record`, `frontier`,
  `incoming`) therefore draw an unknown target as a thing with no record instead of failing the view; before this
  one dangling reference made a whole as_world unknown. `replay.py` now writes slotless records too (374 of them),
  since a folder record with no slots is still a record.
- `relations` names its items by `name` only; a text item shows as its slug there (as_world reads heading/title).
- The retained-stage probes in the pipeline (`RETAINED-TYPE-BRAND`, `RETAINED-REFERENCES`) compare against the
  compiler template's kernel and read 0 for any source that differs from Codex's; the migration stage's
  `UPGRADE-VERISK-REFERENCES 55` is the like-for-like count.
- Topics as things, and web identity (domain) as a vertex the overlay joins through, are not yet views; mentions
  carry the grey today. Firecrawl stays in the Python web hand; only its results are namespace records.

## 2026-10-26, later: the saved-world upgrade publishes this kernel

The `publish-local` trap was never a module of this tree. Its three arm keys decode (shrine-brand wire: `SHRINE-BRAND`,
a version byte, the path's segments with strings little-endian, then the case) to `/x/17/lib/shrine/ass/ker`, `ass/nul`
and `ass/past` at case 2. `foil-publication prepare` gives every definition of a module compiled from source the moment
`prior + 1`, and a brand is path plus moment (`foil-context runtime-brand`), so a raw `shrine.foil` rebrands `ass`,
`tome`, `urn` and the rest; the stored history is at case 1, and the first exhaustive `ass` match (`ass/held` under
`sov/x_at`, `ass/yuga`, `physical_read/record`) falls through to the compiler's `unreachable`.

Codex's pipeline never compiled raw sources. `.check/native-views/prepare_upgrade.py` (last run 21:02 on 10-25, four
minutes before its passing publication) rewrites `core-upgrade-src`: it strips the retained record types (shrine: `ass`,
`ass/ker`, `ass/nul`, `ass/past`, `verdict`, `tome`, `urn`, `chest`, `lchunk`, `ledger`; lain_types: `pails/code`; pact,
source_mount, fs_sync, grove_draft), prefixes `- previous_shrine` and friends so those names resolve to the old pinned
artifacts (case 1; the `previous_*` entries of `core-retained` in `core-upgrade.rvr`), and gives `namespace` a
`legacy_system_at`. The bisect helper's rsync of `baseline-1/src` over `core-upgrade-src` and `retained-src` (22:18 on
10-25) discarded that rewrite, and every run since, "baseline" included, compiled a raw shrine. Control tonight, raw
baseline on a fresh clone (`upgrade-clone-rawbase`): `RETAINED-TYPE-BRAND 0`, `RETAINED-REFERENCES 0`, the same two
`unreachable`. The accumulated clone was a red herring; the retained probes read 1 and 55 for any rewritten source.

Recipe, from the repo root: `rsync -a --delete --exclude mounts src/ .check/native-views/core-upgrade-src/`, then
`python3 .check/native-views/prepare_upgrade.py`, then copy `core-upgrade-src` to `retained-src`. Keep the non-Foil
directories at the baseline mtimes (`rsync -a` from `baseline-1/src/reaver` etc., same content): new mtimes miss the
reaver module cache, the modules recompile with their self-tests, and `newtype`'s expected-failure cases print
`("error"` lines that the pipeline's scan counts as a failed stage (`upgrade-clone-rewrite`, retained, otherwise fine).

Result on this tree (the b165999 source as of 01:54; `graph_views`/`graph_world` edits after that are not in it),
`upgrade-clone-rewrite2`: migration 218 s (`UPGRADE-VERISK-REFERENCES 55`), retained 125 s (`RETAINED-TYPE-BRAND 1`,
`RETAINED-REFERENCES 55`), publication 105 s (`UPGRADE-PUBLICATION-EPOCH 3095`, 49 modules, `UPGRADE-RETAINED-*` and
`UPGRADE-HISTORICAL-SYSTEM` 1, no trap). Boot: `UPGRADE_WORK=upgrade-clone-rewrite2 UPGRADE_MOUNTS=mcp,probe,web,goo,explorer
python3 .check/native-views/boot_candidate.py` (explorer's manifest declares web and goo; without them the script
stops before wisp with a KeyError) reached `HTTP foot listening` after about 110 s, 360 MB rss. Through MCP on 8330:
`/0x11/user/orgs/verisk` exists at `/h/x/1/...` with `name` and `description`; its `as_world` view answers 130 nodes,
`in/1/mentioned` count 8 with the verisk_com pages. History and cases ride through; this is the first boot of the
saved world's records on this kernel with their history.

Logs: `upgrade-clone-mig/migration-candidate.log`, `upgrade-clone-rewrite2/{retained,publication}-candidate.log` and
`boot-upgrade.log`, `upgrade-clone-rawbase/{retained,publication}-candidate.log` (control), all under
`.check/native-views`. Snaps deleted except `upgrade-clone-rewrite2/snap`, the published clone, kept bootable
(copy-on-write; delete it when the disk needs it). `core-upgrade-src` and `retained-src` are left as the rewritten
sources. Nothing committed.

Open: the rewrite's retains list is Codex's hand-written set. A retained record type whose fields change would need a
real `previous_*` conversion rather than an alias; `reference_index` changing (span, past) is fine because the index
is rebuilt. The pipeline's error scan should ignore module self-test output.

## Registries phase (2026-10-26, 02:00 onward)

Ian turned from web crawling to public registries of real things; the research and first load are in
`REGISTRIES.md` and `registries.py`. The saved world now runs on this kernel with its history
(`upgrade-clone-final*`): publish with the pipeline (stage sources through `prepare_upgrade.py`), first boot with
`boot_candidate.py` (`UPGRADE_MOUNTS=mcp,probe,web,goo,explorer`, SIGPIPE kept ignored), every later boot with
`resume_candidate.py` (seconds). The viewer on 8330 shows a federal contractor as a world: its awards with their
descriptions as notes, its parent, its candidate facilities, LEIs, CIKs and importer, the subawards that name real
plants. Next: judge candidates into `same` with evidence (the agent's job), the workspace over a contractor, its
facility and a plant it supplies, and the ImportYeti supplier chains as their own standings.
