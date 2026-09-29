# Native semantic compiler (items 08–13)

The source adapter executes retained Rex parsing followed by native Foil reading,
normalization, identity assignment, visibility, and semantic adjacency. The
canonical oracle stage names are `parse`, `read`, `core`, `normalized`, `visible`,
and `semantic`. The Gate L backend consumes successful semantic compilation and adds metrics,
layout, and traces. The Gate H backend adds prepared output and native HTML, so
the source-to-HTML envelope reports `complete` on success; see [HTML.md](HTML.md). The typed
compiler result itself distinguishes success (including an empty tree), rejection,
synchronous crash, and cancellation.

## Modules and boundaries

- `read.foil` consumes Rex constructors directly, retaining origins and exact
  diagnostic messages. It handles config records, duplicate/unknown fields,
  escaped strings, slot aliases, opt, flows/groups, images and all primitives.
  Its numeric reader preserves Haskell source syntax (including leading zeros,
  hexadecimal and octal); JSON codecs retain their separate strict syntax.
- `passes.foil` implements pure sugar normalization, a preorder identity
  traversal, visibility, hidden-path resolution, and adjacency. Each pass takes
  and returns its own nominal phase type.
- `rules.foil` is generated from the unchanged frozen rules by
  `scripts/porting/generate-foil-rules.py`. The build checks that it is current.
  Rule order, IDs and last-match map semantics are retained. Uniform mode changes
  affinity/provenance while preserving a matched rule ID.
- `compile.foil` assembles typed pass results. Each action and its typed output
  are forced inside `Try`, so synchronous failures retain earlier outputs and
  identify the failed stage. Terminal states skip subsequent callbacks.
- `inspection.foil` projects the typed history into the full-stage test envelope.
  Public wire tree encoding remains separate in `codecs.foil`.

The host handles process framing and a UUIDv4 entropy provider. It implements no
Goo interpretation, normalization, visibility, or adjacency policy. Foil first
computes the number of nodes in the normalized core. The host requests exactly
that many UUIDs; Foil assigns them in preorder **before** pruning. In the current
stateless executable transport, the pure reading/normalization prefix is replayed
when those UUIDs return. Identity allocation is not replayed. Malformed input
allocates no identities. Future persistent execution may retain that prefix
without changing the identity contract.

The retained Haskell executable remains the existing Rex-only boundary. The full
Haskell compiler/renderer is used solely by differential tests.

## Preserved policy

Normalization removes opt wrappers, combining ranks by maximum, and reports an
error unless exactly one core root remains. Groups become row flows and retain
their attributes and boundaries. A flow's children begin with Required rank;
optional rank does not leak across a named flow boundary.

View defaults are Required for `/sys/slots/scar` and `/sys/slots/label`, Compact
for `/sys/slots/summary`, and Full otherwise. An explicit budget overrides this.
The source oracle protocol defaults to `/full`; the reusable `options` function
accepts an explicit compile context, including the existing summary default.

Hidden paths resolve against the complete normalized tree, then contribute node
IDs to the hide set. Nonexistent paths are harmless; hiding an ancestor removes
its descendants. Empty groups disappear, while surviving singleton groups retain
their original identity. Adjacency is rebuilt only among surviving siblings.
Root and final-child outgoing edges are absent. Every other edge carries both
endpoint IDs/slots and its owning parent ID/slot.

## Validation

Build the package and both test-only oracles, then run the suites documented in
[README.md](README.md). `host/gate_checks.py` compares the 397 frozen phase prefixes,
every source/adversarial/domain file at every budget, all ordered rules in normal
and uniform modes, aliases, frontend errors, view defaults and hiding probes.
Only IDs are consistently aliased for structural comparisons; payloads, order,
origins, Rex spans and diagnostics remain exact. Floating config is compared by
binary64 bits, without tolerance.

Independent lifecycle checks verify RFC UUIDv4 shape, uniqueness and freshness,
allocation counts/order before pruning, stable surviving IDs and rebuilt hidden
adjacency. Foil semantic output is sent through the existing Haskell renderer at
multiple widths/scales, checking that semantic, prepared, and HTML identities
remain unchanged. This is a test migration boundary, not a production sidecar.
Unicode remains outside the agreed port scope.
