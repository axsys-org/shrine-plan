# Item 04: internal Goo types

`src/types.foil` expresses the Haskell `Types.hs` phase constraints with separate
nominal Foil sum types and attribute records. These are internal IR values, not
JSON DTOs. The source adapter still implements only Rex parsing; no semantic pass
or phase conversion was added.

| Tree | Constructors | Attributes beyond `goo/common` |
|---|---|---|
| `goo/source` | text, image, jet, flow, group, opt | None |
| `goo/core` | text, image, jet, flow | None |
| `goo/normalized` | text, image, jet, flow | Required node ID |
| `goo/visible` | text, image, jet, flow | Required node ID |
| `goo/semantic` | text, image, jet, flow | Required node ID and optional outgoing edge |

Each constructor requires attributes of its own phase. Each container's children
have that same phase. Source and Core attribute records are nominally distinct
even though their fields agree, as are Normalized and Visible. There is no
untyped payload, generic phase cast, or `Done` constructor (the concrete Haskell
`Tree` fills `Done` with uninhabited `Void`). Text and image payloads are separate
constructors; jets carry the closed seven-variant `goo/primitive` sum.

The `attrs` and `children` methods preserve phase types and child order. Only the
three identified phases expose `node_id`; only Semantic exposes `after`. Edges
retain left/right slots and IDs, affinity, optional rule number, provenance, and
owning parent ID/slot. Reference consistency and positive rule-number validation
belong to the codecs and validated results in items 06–07.

`goo/node_id`, `goo/slot`, and `goo/path` are distinct nominal types. Goo paths are
string segments, separate from Foil's aura-tagged native `path`. The absolute-path
parser accepts root and unknown valid ASCII paths, rejects empty/dot/dot-dot
segments and malformed separators, and never silently repairs input.
`goo/path/trusted` reproduces Haskell's permissive `parsePath` normalization for
trusted policy literals. `src/paths.foil` contains the existing vocabulary and
summary default context. Slot aliases and interpretation remain item 08.

`goo/rank` has exactly Required/Compact/Full (0/1/2). `goo/config` preserves all
eight optional fields: grow, maxIdeal, primary, toggle, label, optionLabel, value,
and max. Absence is distinct from a present false, zero, or empty string.
`goo/loc` stores one-based line/column; missing origins use `maybe/none` and its
`make` helper rejects zero coordinates.

`goo/scalar` stores the exact IEEE-754 binary64 bits of a Haskell `Double`.
`from_bits` rejects nonfinite or wider-than-64-bit representations, and preserves
signed zero, subnormals, and negative finite values. This is representation only:
no decimal conversion, arithmetic, or rounding policy is introduced. The numeric
fields of an untrusted config must additionally satisfy the existing nonnegative
constraints in item 06. Raw record constructors, including paths and locations,
are for trusted compiler code; these types do not claim to be validated wire
values. UUID allocation likewise remains item 09.

Run:

```sh
extras/mounts/goo/bin/goo build
extras/mounts/goo/bin/goo test-types  # real positive and negative compiler clients
extras/mounts/goo/bin/goo test       # unit, type, and frozen parse regression suites
extras/mounts/goo/bin/goo fmt --check
```

The type checks compile small clients against the published type artifact through
the production compiler, forcing compilation under `Try`. Positive clients must
compile, while forbidden constructors, fields, phase mixing, and payload types
must produce the expected elaboration diagnostic. Syntax errors or unrelated
runtime failures cannot count as a successful rejection. Compilation tests run
in a disposable snapshot against an empty source root; normal adapter requests
continue to execute precompiled code.
