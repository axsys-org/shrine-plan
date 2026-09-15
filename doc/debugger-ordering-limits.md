# Inherited raw-float ordering limitation

Status: reproduced, **not fixed**. This is a release gate for unrestricted
physical-key access, not a reason to change the comparator of a running store.
The diagnostic used disposable compiler state; the user's namespace was neither
read nor changed.

`foil-builtins.rvr` implements the same-aura float comparison with an IEEE order
key. Negative-sign payloads use saturating natural subtraction from `2^width-1`.
For raw `rs` payloads larger than 32 bits, or `rd` payloads larger than 64 bits,
multiple distinct payloads can consequently get the same comparison key.
`iota_lt` tests raw inequality and then non-strict key order, so both
`lt(a,b)` and `lt(b,a)` can be true. Normal-width IEEE patterns do not have this
specific collision. The structural codec correctly preserves the raw payload;
identity preservation does not repair the storage comparator.

## Reproduction

For width 32 (`rs`) or 64 (`rd`), construct keys with raw payload:

```
2^width + 2^(width - 1) + n
```

Insert `n = 0..count-1` into `bee[nat]` and into
`mop[path nat lt_pith]` (wrapping each key in a one-segment path). Compare physical
`tap` with repeated `range_after(after, 2)`, displaying only the first entry,
using that exact key as the next cursor, and stopping when no lookahead remains.
A finite diagnostic iteration cap prevents an endless test.

| Collection | Stored keys | Displayed sequence |
| --- | ---: | --- |
| Bee | 3 | `0,1,0,1,…` |
| Bee | 20 | `0,8,9,8,9,…` |
| Mop | 20 | `19,18,17,16,19,…` |

The result holds for both auras. Two-key pagination happens to finish, so a
two-key test alone misses the defect. All inserted keys remain in `tap`;
ordinary `get` also misses some physically stored entries. Thus the violated
index invariant predates the new paging helpers.

[Diagnostic source](/private/tmp/shrine-overwidth-range.atMK7A/diagnostic.rvr)
and [native output](/var/folders/rm/90r2fz8d4811tzy8q1_x49k40000gn/T/shrine-overwidth-pagination-vdpq01nh/out.log:76084)
record the exact experiment. The owned worker completed in 2.957 seconds and
closed normally. This is diagnostic evidence of an unresolved defect, not a
passing correctness assertion or a live-data observation.

## Current containment and next work

Each physical request remains entry/byte bounded. The client rejects repeated
keys across merged pages without replacing the previous immutable collection;
it must never auto-retry a failed continuation. This prevents a successful-looking
infinite load, but does **not** restore access to every affected record. Do not
claim arbitrary raw-float collections paginate correctly.

Do not silently normalize these keys, discard them, constrain the identity codec
to conceal them, or change the global comparator beneath existing indexes.
Changing ordering requires an explicit compatibility/migration plan. A separate
debugger-safe approach is epoch-bound physical traversal handles, keeping raw
identity distinct from traversal position; that may also address oversized-key
access. It needs its own seek/budget, tamper/staleness, and full-access tests.

The normal-key HTTP fixture and this pathological diagnostic must remain separate:
do not weaken successful pagination tests to accommodate cycles, and do not treat
the known bad fixture as evidence of complete namespace coverage.
