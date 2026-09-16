# Debugger read contract audit

Status: original audit and proposal, 2026-09-14. Follow-through is tracked in
the [typed-value read](debugger-value-read.md) and
[physical selection](debugger-physical-read.md) contracts. Physical selection
is an internal layer, not yet a debugger HTTP endpoint.

Scope: current dirty `debug-prototype` source, based on commit
`243366de4c450c9b6390de8533e0084943b7382b`. The local
`origin/lf/conv-fork` ref resolves to that commit; no separate verified
`lf/conv` checkout/ref was available. The observations below describe that
audited baseline; subsequent repairs are recorded in those contracts and the
[performance report](debugger-performance.md).

## Recommendation

First ship an honest, version-addressed full-value read for text/naturals,
including explicit preview metadata in the existing document. Then replace
general physical debug reads with bounded own-record/direct-child pages.
Do not repurpose `y` care, silently empty derived paths, or advertise bounded
derived evaluation before the evaluator supports that guarantee.

The journal endpoint is now bounded in source. It does not bound the initial
root read, general records, operation registries, or case-link rendering.
Nothing in this audit was deployed into the protected runtime on port 8138.

## Verified behavior at audit time

The disposable native diagnostic passed 9/9 checks against a copied source
tree. These checks deliberately confirm current limitations, not their repair.

| Input/check | Observed result |
| --- | --- |
| 20,017-byte text ending in `END_OF_FULL_VALUE` | Main slot output is 2,051 bytes: 2,048 bytes plus an ellipsis; the tail marker is absent. |
| The same bytes in `/res_body` | Output is 1,027 bytes: 1,024 plus an ellipsis. |
| Natural `2^2048` | Replaced with `257 byte numeric value`, not the original number. |
| A record at `a/deep`, no own record at `a` | `y` retains `a/deep`; it does not turn `a` into a record. |
| Physical root containing 10,000 descendant records | Ordinary `peek []` materializes all 10,000 records. |
| 10,000 local data cases | The inspector helper emits all 10,000 case links. |

Diagnostic source:
`/private/tmp/shrine-read-audit.kJClU3/src/foil/tests/debug_read_audit.foil`.
Log:
`/private/tmp/shrine-read-audit.kJClU3/worker-dk24de1i/read-audit/out.log`.
The group completed normally in **394.424 seconds including compilation and
all checks**. That is not a measured HTTP latency or an isolated `peek`
benchmark. During cleanup the owned process had already exited; the attempted
SIGTERM reported no such process. No live runtime was terminated, contacted,
or mutated. These temporary artifacts are evidence, not checked-in regression
coverage; future implementation should promote the relevant assertions into
focused permanent tests.

The diagnostic used the existing native test harness against the copied source
and a disposable compiler snapshot, not the live Eden snapshot. Reproduction
while those temporary artifacts exist (may take several minutes):

```sh
python3 - <<'PY'
import importlib.util, pathlib, tempfile
spec = importlib.util.spec_from_file_location(
    "runner", "/Users/dd/Documents/GitHub/shrine-plan/x/test_runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner.ROOT = pathlib.Path("/private/tmp/shrine-read-audit.kJClU3")
worker = pathlib.Path(tempfile.mkdtemp(prefix="worker-", dir=runner.ROOT))
result = runner.run_group(
    [dict(name="foil:tests/debug_read_audit", kind="native",
          target="tests/debug_read_audit", group="read-audit")],
    "/Users/dd/.nix-profile/bin/wisp",
    pathlib.Path("/private/tmp/shrine-metadata-check.rpGfz5/snap"),
    worker, 900)
print(result)
raise SystemExit(0 if result["passed"] else 1)
PY
```

## Why current general reads expand too much

1. [`http_foot/plan`](../src/foil/http_foot.foil) special-cases `/debug/log`.
   Other `/debug` targets still construct an ordinary HTTP namespace record.
   [`http/req`](../src/foil/http.foil) declares a `z` dependency on the target,
   plus ancestor face/record dependencies and ancestor `op` registries.
2. [`read`](../src/foil/lain_peek.foil) calls `peek`, applies pending-state
   masking, then calls `sorge`. Physical `peek` uses `idx.dip(path).tap`,
   resolves every descendant history, and rebuilds the live known tree.
   `crew_of` uses this path for each named dependency. Changing the requested
   care from `z` to `x` or `y` therefore does not by itself avoid hydration.
   A separate `read_x` fast path exists but is not what `crew_of` calls.
3. [`explorer/case_links`](../src/foil/web.foil) loops from 1 through the full
   data-case count. `explorer/inspector` renders x/y/z link sets; the frontend
   slices history only after receiving the complete HTML. By contrast,
   [`h_ver`](../src/foil/lain_peek.foil) itself reads bounded clock metadata;
   it is not the history-link enumeration problem.
4. [`explorer/ops_of`](../src/foil/web.foil) enumerates ancestor operation
   registries from already-hydrated crew views. A shallow record replacement
   must not drop available operations or quietly keep this unbounded work.

`y` means the nearest record-bearing **frontier**, not physical immediate
children. [`sov/y_at`](../src/foil/shrine.foil) traverses through transparent or
tombstoned nodes to the next known records. The care contract is documented in
[`shrine_types`](../src/foil/shrine_types.foil). Direct-child pagination must
have a new name and must not alter that meaning.

## Values are currently shortened without a machine-readable warning

[`debug_model/value`](../src/foil/web_debug.foil) clips text to 2,048 bytes,
HTTP cord-valued naturals to 1,024 bytes, and generic formatted values to 768
bytes. Naturals wider than 128 bytes become a size label. Many typed values
(forms, modules, templates, schemas) intentionally become semantic summaries.

[`debugger/record`](../src/foil/web.foil) emits only `data-value-kind` and
`data-reference` on each `sh-limb`. There is **no preview/truncated flag, exact
length, source epoch, or full-value URL**. An ellipsis is only display text and
cannot reliably distinguish truncation from an authored ellipsis.
[`slotOf`](../src/foil/debug/namespace.js) can retain the returned text but
cannot recover what the server discarded. Frontend large-value fixtures are
not evidence of full backend fidelity.

Removing the outer clip is insufficient. [`show/pail`](../src/foil/show.foil)
already limits depth/collection sizes, abbreviates text leaves, and replaces
some values with labels such as `code`, `form`, `law`, or `html fragment`.
`show/clip` slices bytes and can split a UTF-8 sequence. No `show_skim` symbol
was found in this checkout; `show/pail` and the compact Reaver environment
printer are analogous diagnostic renderings, **not canonical serializers**.

Existing routes are not a general raw-value escape hatch:

- `/ns` can render a plain text pail without this outer text clip, but uses the
  same unbounded HTTP read, can dispatch authored application faces, and still
  uses lossy formatting for other kinds.
- `/frag` resolves/render overlays; it is not raw namespace data.
- `/debug/log` returns bounded journal HTML, not arbitrary slot bytes.
- `/post`, `/edit`, `/op`, and `/vine` are mutations, not read alternatives.

No verified current HTTP endpoint exports a lossless arbitrary pail/noun.
The compiler RTTI document describes bounded reflection and explicit opaque or
truncated outcomes; that is a design, not proof that those services exist.
An exact canonical noun/binary export must define representation/version,
sharing/pins, opaque code, limits, and round-trip tests. Do not call the
existing pretty-printer output “raw,” “complete,” or “canonical.”

## First implementation slice: explicit previews and exact typed chunks

Implementation update: this slice is now implemented and verified in disposable
native/HTTP tests and through the production browser parsers. The normative
contract is [debugger-value-read.md](debugger-value-read.md); current verification
commands and activation requirements are in the [PR guide](debugger-pr.md). The audit
and proposal below describe the original gap, not a claim that the protected
live kernel has been upgraded.

Proposed reserved transport route (not an existing route):
`GET /debug-read/value?path=...&slot=...&epoch=...&offset=...&limit=...`.
Route it before the ordinary HTTP-record machinery to a read-only supervisor
request, following the journal correlation/reply pattern.

- `path` is the namespace record address. `slot` is its opaque path-shaped
  record key; never append it to the namespace path. Both require canonical
  path parsing and round-trip validation. Reject duplicates/unknown keys.
- `epoch` is a canonical arbitrary-precision decimal sovereign epoch, not a
  local data-case count or a floating-point JavaScript number. Resolve that
  record through `ass/res epoch (state.hist path)` and look up only the slot.
  Keep known, tombstoned, unknown, missing-slot, and unsupported-type results
  distinct. Do not execute stored code to inspect it.
- `offset` is a canonical decimal byte offset; `limit` is 1..65,536 bytes.
  Return versioned metadata: representation, type, record epoch/case identity,
  exact byte length, offset, next offset or null, and complete. A small
  byte-preserving envelope (for example hex chunks) avoids invalid UTF-8 and
  escaping ambiguity. Text presentation decodes with streaming UTF-8 rules;
  saving/copying exact bytes must not pass through a lossy text decoder.
- Text (`pails/t`) and natural (`pails/n`) can have exact byte representations.
  A natural's byte order and zero representation must be specified and tested.
  Decimal display for enormous naturals is a separate conversion with real
  CPU/memory cost; do not promise it is bounded just because output is paged.
  For naturals used as HTTP cords, preserve the actual stored bytes and label
  the presentation interpretation separately.
- A committed myth is one pinned ordered map, not separately addressable
  per-slot storage. Bounded response bytes and avoided subtree traversal do
  not prove bounded cold record loading. Measure that cost; a hard storage
  bound may require smaller persistent units. Huge variable-width keys also
  need an explicit identifier/output budget or an opaque handle contract.

Existing document markup should expose `data-value-state` as
`complete`, `preview`, or `opaque`, `data-preview-reason` (byte limit,
depth/collection limit, semantic summary, unsupported representation), exact
size when known, source version, and a full-value URL only when supported.
The UI displays “Preview · first N of M bytes” or “Summary · exact inspection
unavailable” rather than presenting a shortened value as complete. Keep the
original semantic summary and references; full value is an explicit reversible
expansion/download, not a replacement for authored meaning. Legacy markup
without metadata must be treated as completeness unknown, not guaranteed full.

For generic pails, add bounded structural inspection as a later explicit
representation. Unknown schemas, laws, and pins must remain honestly opaque
until there is a safe non-executing representation. Derived value chunks need
an immutable evaluation-result identity; rerunning a live view for every chunk
does not preserve one value. A whole-slot raw endpoint is simpler but leaves
unbounded serialization/response cost and is not the recommended release path.

## Second slice: physical record and immediate-child pages

Add a named `inspectPhysical` supervisor read, not a new interpretation of x/y/z.
Capture one state/epoch, obtain `idx.dip(path)`, resolve the own assertion, and
select at most `limit + 1` child keys before resolving displayed children.
Do not call `peek`, `.z`, `tap/drop`, or render descendant records.

Proposed response fields: `resolutionKind=physical`, own resolution state,
epoch, a separately paged own-slot preview collection, `childrenKind=physical`,
child total, ascending page keys, exclusive after cursor, next cursor, limit,
and completeness. Child summaries resolve only the child's own record and
authored label/help metadata, plus slot and physical-child counts. They never
walk grandchildren to invent a preview. Empty structural and tombstoned nodes
are explicit states, not invented empty records.

General child ordering must stay `lt_iota` ascending, as current `kid_tap` does.
Add a seekable ascending `bee/range_after` analogous to `range_rev`; do not
flatten the tree or JavaScript-sort display strings. Its cursor encodes the
complete canonical iota (all auras, not only decimal journal keys). Own-slot
paging needs an equivalent bounded range over the myth's `mop`/`lt_pith` map.
Cap summary bytes, collection sizes, and keys as well as entry count.

The cached `kid.size` is an exact **physical** child count. It includes retained
structural/history paths and is not the count of live children in today's
filtered `peek` result. Label the distinction. Exact live-only counts require
an augmented index or traversal; silently using the physical count is wrong.
Keep expansion available for every physical key and authored reference.

For initial paging, require the previous response epoch on continuation and
return a refresh-required conflict if `state.top` changed. Alternatively use a
bounded, expiring immutable index-snapshot handle and explicit expiry errors.
Do not claim that resolving old record assertions from the current key index
also reconstructs the exact old child set/count: newer physical keys remain in
that index. Cross-page snapshot semantics must be deliberate and tested.

History metadata stays bounded; generate a bounded range of dense local case
IDs from each count, with explicit access to earlier ranges/exact cases.
Operations need a lazy, paged registry contract preserving ancestor precedence
and their actual frontier semantics. Merely retaining the old eager operations
fetch prevents the overall read from being bounded.

## Derived and Grove paths are not physical pages

The authoritative resolver is [`view`](../src/foil/lain_peek.foil):

| Family | Required meaning/evaluation |
| --- | --- |
| `/h` | Care plus local case or `e<epoch>`; recursively resolve the actual physical or derived target. A historical y answer still has frontier semantics. |
| `/o` | Resolve the pinned function and proper input. `dyed`/`knit` consume an x record; `felt`/`sewn` consume a z tree. Evaluate, select the relative output, then apply care. |
| `/x` | Resolve the defining datum, `/sys/weft`, and the pinned y-care `/sys/tack` input; evaluate the `spun` view, then apply care. |

[`grove_trees/value`](../src/foil/grove_trees.foil) and
[`grove_template`](../src/foil/grove_template.foil) install these weft/tack
references. [`grove_sewn/code`](../src/foil/grove_sewn.foil) generates the
transformation and input/output norm checks. The SRS
[`queue` example](../src/grove/srs.grove) selects/sorts real input cards into
derived children. Replacing its y input with physical immediate children or
replacing its output with `idx` keys changes the program.

A physical view-definition page should retain its authored weft/tack metadata
and the real derived-view address. Do not merge virtual output children into
its physical count. Requests for `/h`, `/o`, or `/x` must dispatch to the real
resolver or report an explicit unsupported-capability result; never fall back
to a misleading empty physical record.

Paging an already evaluated axal bounds output, **not evaluation cost**. Current
arbitrary compiled transformations can traverse whole inputs; no verified
fuel/cancellation/isolation budget for this path was found. A client timeout
does not provide that guarantee. A complete bounded derived implementation
needs a proven budgeted evaluator or explicit incremental provider contract,
immutable result identities, and norm/error handling. Until then, preserve the
working derived route and disclose its unbounded evaluation as a release
limitation; do not sell a physical-only replacement as complete namespace
inspection.

## Verification and activation gates

For typed value reads, test text at/beyond the preview threshold, authored
ellipsis, multibyte boundary splits, empty bytes/zero, control bytes, very large
naturals, exact reconstruction across chunks, stale/missing/deleted records,
opaque types, malicious/duplicate queries, safe escaping, and no journal append.
Assert old-version chunks remain identical after a new commit. Test the real
backend output through the production DOM parser, not just supplied fixtures.

For physical paging, test empty/10k fanout, every iota aura, opaque multi-segment
slot keys, exclusive cursors, limit+1 lookup counts, inserted/deleted cursors,
epoch conflict/expiry, tombstones/transparent spines, bounded serialized bytes,
full access through expansion, and no change to sovereign state. Separate
physical count/order checks from y-frontier tests. Retest real Grove SRS views,
historical derived cases, and norm failures before any route migration.

No non-restarting state-preserving activation was verified. The
[`helm/supervisor`](../src/foil/helm.foil) request union exposes register,
install, step, peek, and journal; it has no checkpoint/export/replace/upgrade
request. Duplicate foot registration is rejected. The running sovereign and
compiled actor handlers are held inside spawned closures. Static JS/CSS is
read from disk per request, but that does not replace those handlers.
[`x/eden`](../x/eden) boots fresh state; compiler reload/resync is not a running
supervisor migration. A `Save` primitive alone does not prove safe transfer of
state, pending requests, sockets, actor capabilities, and foot bindings.

Keep port 8138 intact. Test backend slices in disposable runtimes. Before live
activation, implement and prove a checkpoint/restore or supervised handover
contract that preserves namespace state and validates pending I/O ownership;
obtain the necessary user authority for that separate operational change.
