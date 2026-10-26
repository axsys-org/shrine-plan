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

## Text runs

Textual IR leaves and primitive labels carry `goo/text = row[goo/runt]` in
source, core, normalized, visible and semantic phases. A `goo/runt` contains
`myth=myth` and `lang=goo/lang`; the initial language variant is
`goo/lang/en { txt=str }`. `goo/text/en` lifts an existing string into a single
English run with an empty descriptor. Image URLs, IDs, paths and wire keys remain
strings. Existing string-valued configuration labels remain compatibility inputs.

The `myth` field is the existing Foil `myth`: `mop[path pail lt_pith]`.
It is the run's RunDescriptor, with typed, branded pail values at path-shaped
slots. It carries metadata, not receiver identity or action authority. Any pail
brand survives compiler passes, slicing and normalization without conversion.

JSON is only a transport adapter: canonical path strings key tagged pail values
(`kind` and `value`). The codec supports `pails/n`, `pails/b`, `pails/t`, `pails/p`,
`pails/modifiers`, and `weblink`. Foreign brands remain diagnostic data and
cannot be decoded as another type. Duplicate slots and noncanonical paths are
rejected. This does not restrict which pails a run can hold in Foil.

Rendering recognizes these typed myth slots:

| Slot | Pail | Meaning |
| --- | --- | --- |
| `/sys/font` | `pails/p` | Path to a pinned font in the current renderer registry |
| `/sys/modifiers` | `pails/modifiers { values=list[modifiers] }` | `italic`, `bold`, `underline` |
| `/sys/link` | `pails/p` or `weblink { href=str }` | Internal target or HTTP(S) target; filled box highlight |

`modifiers` is the closed sum of the three nullary records. `pails/modifiers`
boxes the typed list at the myth's pail boundary. The underlying text remains
`row[goo/runt]`; `goo/text/pail { value=goo/text }` is its namespace-field carrier.
The explorer's ordinary `show`/text formatter preserves this carrier's runs.

Font paths are `/sys/font/sans`, `/sys/font/mono`, or `/sys/font/<fontId>`.
The registry includes the base profile faces and the `run-fonts/fonts.json`
extension. Sans bold uses weight 750; mono bold uses 700. Italic retains the
selected sans weight (400, 520, 550, 620, 650, 750). Mono italic, unknown font
paths, malformed slots, duplicate modifiers, and styled native inputs are
explicitly rejected. Arbitrary namespace font discovery is not implemented.

Measurement and wrapping use each run's selected font advances. Line extents
account for mixed fonts and all fragments share the prepared baseline.
Underlining and link highlights are prepared paint, with no extra text advance.
Links retain structured targets and descriptive semantics; they do not create
Goo controls or authorize navigation/invocations.

Run boundaries are not word or line boundaries. Measurement sees concatenated
text; wrapping slices the original runs and retains their descriptors. CRLF can
cross runs, tabs expand using the rendering profile, and whitespace collapse for
control labels retains the descriptor of the retained whitespace. Current byte
slicing is used only with validated ASCII measurement; it is not a Unicode
shaper. Only `en` is accepted on the wire, with the existing ASCII limitation.
