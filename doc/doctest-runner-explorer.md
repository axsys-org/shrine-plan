# The doctest runner and the environment explorer

*Design document. Companion to `doc/shrine-apps.md` (landed) and
`doc/foil-lore.md` — this picks up foil-lore.md §5 (doctest evaluation,
staleness) and §6 (rendered overlays) now that lore is real namespace data.
**Design notes** are skippable; **Provisional** boxes flag open choices.
Part I (runner) and Part II (explorer) share one contract — the verdict slot
(§I.3) — and are otherwise independent; build them in parallel against that
contract.*

**The one-line design:** doctests stop being inert data — a driver evaluates
them against the live image and pokes verdicts onto the documented nodes —
and the explorer stops being a debug page: lore-first, kind-aware, verdict-
chipped, searchable, and honest about staleness, all still server-rendered
from live values.

---

# Part I — a real doctest runner

## 1. Motivation

Every documented entry now carries its doctests at `['lore]` (tests as
`[[src want] ..]` text pairs), and the compile cache holds the same tests
parsed (`["DT" line lhs-rex rhs-rex]`, foil-lore.rvr).  forge executes
doctests, but only inside its own request loop (`run-doctest` / `eval-rex`,
[forge.rvr](../src/reaver/forge.rvr)) against forge's own compile — the
namespace image never learns the results.  shrine-apps.md §7.3 named the
target: *a runner (an /io driver holding the compiled subject, mirroring the
fetch request/response pattern) executes them against the live image and
pokes results back.*

## 2. The user's view

- **On demand:** make a request record under the driver —
  `/io/doctest/r<N>` carrying a target path — and the answer pokes back onto
  the request node *and* the verdict lands on the documented node itself.
  The explorer's "run" affordance is exactly this make.
- **Sweep:** a request whose target is a subtree (`/boot`, or one module's
  node) runs every documented entry beneath it.  A boot flag
  (`doctest-sweep? 0` default) runs the full sweep at the end of
  `run-lain-boot`, after mounts, so a freshly booted image can be born
  fully verified.
- **Reading results without the explorer:** peek any documented node; the
  verdict is one more slot, self-describing like everything else.

## 3. The verdict contract (shared with Part II)

One new **child node** under the documented node, written only by the
runner (made on first run, poked thereafter):

```text
<node>/dt  ['dt]  the verdict pail: when=nat case=nat
                  results=row[[i=nat pass=nat got=nat]]
```

> **Design note — child, not slot (revised during implementation).**  The
> first draft put the verdict at a `['dt]` slot on the documented node
> itself.  That self-invalidates: the verdict poke mints a new moment of
> the node, so `case` (captured before the poke) is behind the node's
> current version the instant the verdict lands — every verdict reads as
> stale.  A child node keeps the entry's version clean as the anchor;
> verdict churn versions only the child.  This is exactly the churn escape
> the lore-placement decision reserved (shrine-apps.md §4.2 design note),
> taken here because the churn is structural, not hypothetical.

- `results` is index-aligned with the lore's `tests` row; `got` is the
  rendered actual value on failure, `0` on pass (values can be huge; the
  text is capped at the driver, provisional §5).
- `case` is the documented node's **own version at run time** — the
  staleness anchor.  A reader (the explorer, an agent) compares `case`
  against the node's current version: equal → verdict is current; else →
  stale, render grey, offer re-run.  This is foil-lore.md §5's staleness
  story with zero new machinery: versions already exist per node.
- `when` is the host clock at run time (display only, never compared).
- The pail type (`dt_verdict`) lives in pact next to `lore`, so the type is
  in the namespace and `mani`-style self-description holds.

> **Design note — why poke the documented node and not a results subtree.**
> Same argument as lore placement (shrine-apps.md §4.2): one subject, one
> path.  A verdict poke does mint a new moment of the entry node — but
> entry nodes are mirror records, nothing pins them, and the churn is one
> slot write per run.  If sweep-churn ever measures badly the escape is the
> same one lore reserved: slot-level care, not a second path.

## 4. Mechanics

**A new module `src/reaver/doctest.rvr`** — the evaluation core, hoisted out
of forge exactly as lore capture was (precedent: foil-lore.rvr, commit
`c561db2`):

- `eval-rex` and `run-doctest` move here (forge rebinds, same idiom as its
  lore rebinds).  They need the compiled subject + codegen — this module
  binds `foil`/`cgen`, sits above them, below forge/helm.
- New: `run-lore l sut` → the results row (maps `run-doctest` over the DT
  rows, skipping DTBAD), and `verdict-tasks` — given (cache entry, node
  path, sut, version) produce the `vine_poke` for the `['dt]` slot.
- Parsed tests come from the compile cache (5th field); the driver holds
  the core, and the core holds the cache — no re-parsing, no reading text
  back out of the namespace.

**The driver** — clone of the fetch pattern
([helm-http.rvr](../src/reaver/helm-http.rvr) `mk-worker` /
`helm-fetch:mk-fetch-worker`):

- `mk-doctest-worker helpers name`: on `["change" ...]` for a fresh request
  record under `/io/doctest`, resolve the target path against the core's
  cache (mirror-node path → module + entry key, the inverse of the
  `mod-segs`/`ent-task` mapping in [helm.rvr](../src/reaver/helm.rvr)),
  evaluate in the worker, send the verdict pokes back through the
  coordinator as tasks (the synchronous `["task" t]` barrier the drivers
  already use).
- The worker holds `(core-sut core)` — evaluation is against the live
  image's own compile, so a doctest exercising `bst/size` runs the same
  compiled law the image dispatches.
- Registered like the other drivers: seeded config record at
  `/io/doctest`, branch in `run-lain-boot`'s `mk-worker`.

> **Provisional — MAIN-only evaluation.**  Compiles must run in MAIN
> (spawned actors have no compiler — the `run-lain-boot` warm comment).
> `eval-rex` compiles the doctest's rex.  Either (a) the driver ships each
> request to MAIN via the coordinator (making the runner effectively
> serial), or (b) the boot warms `eval-rex`'s call graph the way it warms
> the socket path, and workers evaluate freely.  (b) is the design intent;
> prove it with a probe before committing — if a doctest can mention an
> entry whose lowering was never forced, (b) needs a `DeepSeq` over the
> subject at boot, which the sweep flag amortizes anyway.

## 5. Decisions and provisionals

| Decision | Choice |
|---|---|
| Evaluation site | driver worker against the core's own sut |
| Verdict placement | `['dt]` slot on the documented node (§3) |
| Staleness | verdict pins the node's version (`case`); readers compare |
| Request shape | fetch-style records under `/io/doctest`; subtree targets sweep |
| Eval core | new `src/reaver/doctest.rvr`; forge rebinds |
| Boot sweep | flag-gated, default off, runs post-mount |

> **Provisional — failure text cap.**  `got` renders through the same
> pail-text path as the explorer; cap at ~500 bytes at the driver.  Pick
> the exact cap when the first giant value shows up.

> **Provisional — app doctests.**  App modules' entries mirror with lore
> and are swept like kernel code (same cache).  A doctest in an app that
> pokes the namespace *cannot* — `eval-rex` evaluates values, it does not
> run events.  Effectful "scenario tests" are a different feature; do not
> let them creep in here.

## 6. Phases and verification

1. `doctest.rvr` (move + rebind + `run-lore`); forge behavior identical
   (its suite is the regression net — `rm -rf snap && x/test forge-tests`,
   grep `^("ERROR"`).
2. `dt_verdict` pail in pact + `verdict-tasks`; unit: verdict poke lands,
   results align with the lore fixture (`bst` — forge-tests already pins
   its doctests green).
3. The driver + `/io/doctest` registration; end-to-end: boot `x/lain`,
   make a request for `/boot/bst/1/size` — hmm `/boot/bst/2/bst/size` —
   use the mirror path as rendered; assert `['dt]` appears with all-pass,
   then edit nothing and re-run: `case` unchanged.  Kill the booted wisp
   (yours, by port — never `pkill -o`).
4. Sweep + boot flag; measure (the perf roadmap owns the budget); assert a
   deliberately wrong doctest in a fixture app yields `pass=0` with `got`,
   and the *app* still mounts (verdicts are data, not gates).

---

# Part II — a real environment explorer

## 1. Motivation

The hex explorer ([lainapp.foil](../src/foil/lainapp.foil) `ns_page`,
`show_pail`, `ns_css`) is a competent debug page: breadcrumbs, slots, kid
links, a version pane, lore-first sort with head-only rendering.  What it is
not: a way to *understand* a system.  shrine-apps.md §7's promise — start at
`/` and learn everything — is held up by the namespace's data now; the
rendering is the remaining gap.

## 2. What "real" means, concretely

Each item is one affordance, roughly in priority order; all stay
server-rendered weft trees (no client framework — at most the htmx-style
`hx-get` links forge already uses):

1. **Lore as the page's voice.**  Head as the node's subtitle under the
   breadcrumbs; body lines as a paragraph (fold behind `details` past ~6
   lines); doctests as `src ?= want` code rows.  `show_pail`'s lore arm
   stays the one-line form for *slot* rendering; the full treatment is the
   page's, driven by reading `['lore]` directly in `ns_page`.
2. **Verdict chips** (the Part I contract): beside each doctest row, green
   `pass` / red `got: ...` / grey `stale (vN)` from the `<node>/dt` child's
   `['dt]` pail vs the documented node's current version (missing child =
   "never run"); a "run" link that makes the `/io/doctest` request for
   this node (the explorer's first write — see the design note).
3. **Kind-aware rendering.**  `[src]` slices in `<pre>` with the existing
   css; `[kind]` as a chip; kook refs as links to their form nodes (they
   are paths — `show_pail` already prints them, make them `<a>`);
   `[module]` on app cards links to the mirrored module; every path-valued
   pail is a link, everywhere.
4. **Index pages that orient.**  `/ns/boot`: modules grouped kernel / apps,
   each with its header lore head.  `/ns/app`: one card per app — status
   chip (live green / failed red), lore head, err text for tombstones,
   wants-vs-grants rows once Part II of the grants spec lands.
   `/ns/kook`: forms with their lore heads.
5. **Search.**  `GET /ns?q=` — substring over path segments and lore heads,
   walked from the mirror + live roots server-side.  No index maintenance:
   walk on demand, cap results, link through.  (The namespace is small; when
   it isn't, the carer index is the real answer — out of scope.)
6. **Time travel affordances.**  The version pane becomes a scrubber row:
   case links `1..N` with the current one marked, mint times shown, and the
   existing `view live` escape.  No new mechanism — `/h` already answers
   everything; this is layout.

> **Design note — the explorer's first write.**  The "run" link makes a
> namespace record (a doctest request).  Today hex is GET-only and the
> driver ignores non-poke traffic.  Keep writes POST, keep them exactly one
> kind (make-request), and route them through the coordinator's existing
> `["task" t]` barrier — the explorer gains no private channel, it emits
> the same event any client could.  If this ever grows past doctest-runs,
> stop and write the capability story first (grants exist now — the
> explorer is an app-shaped thing and could be mounted as one; see below).

> **Provisional — the explorer as an app.**  It is the perfect dogfood for
> the whole stack: recast hex as `foil/apps/hex/main.foil` with a
> `($gserve port)` want, mounted through the pipeline, self-describing at
> `/app/hex`.  Blocked on: multi-file apps (hex + weft helpers will not fit
> one file comfortably) and `$gserve` provisioning (grants spec Part II).
> Keep it as the acceptance milestone that ties all four workstreams
> together, not a v1 requirement — v1 improves the explorer where it lives
> (`lainapp` / a new `hexapp.foil` between lainapp and helmapp, splitting
> the ~200 explorer lines out of lainapp either way).

## 3. Decisions

| Decision | Choice |
|---|---|
| Rendering | server-side weft trees, shared `ns_css`; no client JS beyond links/forms |
| Explorer home | split out of lainapp into `src/foil/hexapp.foil` (lainapp keeps the pails and demo forms); app-ification deferred per the provisional |
| Writes | POST → one event kind (doctest request) via the coordinator barrier |
| Search | on-demand walk, no index |
| Verdict rendering | strictly from the `['dt]` contract (§I.3); explorer never evaluates anything itself |

## 4. Phases and verification

1. **Split**: move `ns_*`/`show_*` decls into `hexapp.foil` (import chain:
   lainapp → hexapp → helmapp; same compile-cache diamond as everything
   else).  Suites green, pages byte-identical — this is pure motion, land
   it alone (precedent: every consolidation phase so far).
2. **Lore-first pages + kind-aware slots + link-everything** (items 1, 3).
   helm-http-tests grow assertions per page kind (they already fetch and
   substring-match rendered pages — extend, don't invent a harness).
3. **Index pages + app cards** (item 4) — verify against a boot with the
   demo app and a broken fixture app: the `/ns/app` card row shows one
   green, one red with err text.
4. **Verdict chips + run link** (item 2) — lands after runner phase 3;
   until then the chips render "never run" from a missing `['dt]` slot,
   which is shippable independently.
5. **Search + version scrubber** (items 5, 6).

End-to-end acceptance (the §7 walk, upgraded): from `/`, with no repo
access, reach the demo app, read what it is, see its doctests green, click
into its source and history, and find `hserve` by searching "serving".
Verify with curl greps per page plus one manual browse; kill only your own
server pid; `rm -rf snap` before every suite run; grep logs for
`^("ERROR"`.

## 5. Open questions

1. Does the doctest "run" POST need any rate limit / dedup (double-click →
   two requests)?  Cheap: the request path includes the target's current
   case; the driver drops requests for already-verdicted cases.
2. Search over lore *bodies* too, or heads only?  Heads-only keeps result
   rows one-line; start there.
3. When the explorer becomes an app, `/ns` routing moves behind the app's
   serve grant — decide then whether the kernel keeps a fallback explorer
   for images booted with zero apps (probably yes: it is the flashlight
   you need exactly when app mounting is broken).
