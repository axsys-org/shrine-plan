# Native layout (items 19–24)

`src/layout.foil` ports `Goo.Layout` using finite binary64 arithmetic. It accepts
leaf-size and leaf-height callbacks, summarizes the semantic tree, allocates
leaf/stack plans, enumerates flow candidates, memoizes `(node ID, quantized
width)`, and emits adjacency traces. Successful results pass the existing
measurement validator. Neither this module nor its host resolves semantic rules.

Widths use `max(1, floor(w * 100 + 0.5) / 100)`. Arithmetic rounds after each
operation. Candidate endpoints ascend, suffixes run right to left, and an
incumbent is replaced only when the new cost is smaller by more than `1e-6`.
Feasibility permits `0.05`; infeasible singletons incur 128 compression cost.
Weak-edge spare space goes to gaps, never into leaf widths. Stack plans respect
group grow overrides; leaf grow comes from the injected measurer. The cache is
request-local and includes plans evaluated for unchosen candidates.

`layout_api.foil` exposes two version-1 requests:

```json
{"version":1,"action":"layout","tree":null,"width":200,"textScale":1}
```

`layout` accepts a checked semantic wire tree (or null), uses the bundled ASCII
measurer, and returns `{version, ok, measurement, textLines}`. `measurement` is
the existing validated transport: tree, quantized width, all size summaries,
plan, and trace. Width is finite, nonnegative, and at most 100000; textScale is
positive and at most 10, defaulting to 1. Unicode measurement remains excluded.

`plan` instead accepts `measurements.sizes` keyed by leaf ID, and
`measurements.heights` keyed by leaf ID then quantized decimal width (e.g.
`"96.00"`). A numeric per-leaf height is available for synthetic tests. A missing
sample fails planning, including samples needed only by a discarded candidate.
`measurements.constantHeight` supplies one shared height for fixture tests.
It returns `{version, ok, measurement}` and never invokes the ASCII measurer.
This separation preserves the original browser measurements without pretending
they match the current bundled font metrics.

`backend.foil` connects successful semantic compilation to the same typed planner
and preserves layout rejection/exception attribution. `source` now projects
metrics, layout, and traces, followed by native prepared/HTML stages (see [HTML.md](HTML.md)).
The `fixture` action accepts normalized wire trees, runs native visibility and
adjacency, and uses recorded measurements when supplied. Its stage envelope
matches the item-01 oracle through trace. The Python boundary only frames requests.

Run from the parent repository:

```sh
goo/scripts/porting/build-layout-oracle.sh
extras/mounts/goo/bin/goo build
extras/mounts/goo/bin/goo test-layout
python3 goo/scripts/porting/check-layout-rules.py
```

The test-only Haskell oracle calls unchanged `Goo.Layout.planWith` and `layout`.
The gate suite keeps recorded browser replays and ASCII integration separate.
Numeric geometry comparisons use the original replay tolerance
`max(1e-6, 1e-10 * max(abs(a), abs(b)))`; fields, IDs, order, partitions, and trace
provenance compare structurally. Native checks exercise quantized cache reuse
with a throwing callback and reject invalid injected values. Prior measurement
transport tests continue to reject malformed result plans/traces.
