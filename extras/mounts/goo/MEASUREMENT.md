# Validated measurement transport (item 07)

`measurement.foil` defines nominal size, recursive plan/row, axis, trace, raw
measurement, and checked result types. These are independent of the source and
compiler-phase IR. No measurement or layout algorithm is implemented here.

`decode_result` checks versioned JSON and calls `make`. The factory validates
finite nonnegative scalar values, local size/row constraints, semantic tree
structure, exact metric coverage, plan identities and root width, complete row
partitions, direction-specific gaps, and one trace per semantic edge. Trace axis,
cut, preferred gap and planned gap must agree with the owning row boundary.
The existing strict 0.011 gap tolerance is preserved, including binary64
subtraction rounding.

As with other Foil records, trusted internal constructors are visible. The raw
and checked result types are nominally distinct; external producers must use
`decode_result` or `make`. Public `encode` revalidates even a checked wrapper, so
constructing a wrapper directly cannot bypass the serialization boundary.
Future layout/render consumers must use the same factory/consumer checks.

The `validate-measurement` action accepts:

```json
{"version":1,"action":"validate-measurement","result":{"version":1,"tree":null,"width":1,"sizes":{},"plan":null,"trace":[]}}
```

It returns the existing oracle envelope with semantic, metric, layout and trace
projections, or a protocol rejection. The full `fixture` layout action remains
unimplemented until the backend algorithms are ported.

`host/measurement_checks.py` replays frozen prepared results against the actual
Haskell production validator and tests missing/extra metrics, invalid primitives,
identity and ownership mutations, malformed partitions, missing/extra traces,
invalid numeric values, and both sides of the trace-gap tolerance. Foil unit tests
also exercise the internal construction boundary with nonfinite and negative
bit patterns. See Gate S evidence for the recorded results.
