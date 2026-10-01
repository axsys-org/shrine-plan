# Tree and config codecs

`src/codecs.foil` owns the public tree boundary. A `goo_wire/node` contains JSON
fields; the decoders construct the nominal `goo/normalized` or `goo/semantic`
IR from item 04. JSON values never become internal nodes by casting. The checked
entry points are `decode_normalized` and `decode_semantic`; lower-level node
parsers perform local field validation and the checked entry points also validate
the complete graph. As with other Foil IR records, internal constructors remain
available to trusted code.

Run `extras/mounts/goo/bin/goo adapter` with:

```json
{"version":1,"action":"codec","phase":"semantic","tree":{"id":"n","slot":"custom","kind":"text","after":null,"text":"Hello"}}
```

Use `phase: "normalized"` for fixtures before visibility/adjacency. The response
is `{version:1,ok:true,tree:...}` with canonical wire defaults, or a codec failure.
The `codec` action is an inspection/transport entry point, not the full `fixture`
pipeline. Source compilation still stops after Rex parsing. Measurement, layout,
metric and trace DTOs are item 07 and subsequent work.

## Preserved behavior

- IDs are nonempty strings, not necessarily UUIDs. Slots are open strings.
- Missing/null optional rank means required; missing/null origin/config fields
  mean absent. Present values retain strict primitive types. Grow is integer
  0/1, primary/toggle are booleans, labels are strings, and numeric config values
  must round to finite nonnegative binary64. Integral decimal/exponent spellings
  are accepted for Haskell `Int` fields within its signed 64-bit range.
- Absent config fields are omitted on encoding; slot, optional, origin, and ID
  are emitted. Semantic nodes additionally require and emit `after`, even null.
- Leaves reject any children key, including null. Text defaults to empty. Only
  avatar/media with a non-null string src decode to an image; without src those
  names describe primitives. Image output uses avatar for slots `icon`/`avatar`,
  otherwise media, and clears text. Groups require flow/stack and children,
  while ignoring extraneous leaf payloads. Unknown fields are ignored.
- A bar with a value requires positive max and value <= max. Without a value,
  max may be absent or zero.
- Edges require every field, including nullable rule. Positive rule is required
  for exact and forbidden for fallback; uniform requires normal affinity but
  permits a positive rule. Graph validation rejects duplicate IDs, empty semantic
  groups, root/final-child edges, missing sibling edges, and wrong endpoint IDs,
  slots, ordering or parent ownership. Empty normalized groups are permitted;
  normalized decoding ignores after and still rejects duplicate IDs.

## Numeric boundary

`src/numbers.foil` parses decimal syntax and converts exact rational values to
binary64 with round-to-nearest/ties-to-even, including subnormals, carry and
finite-overflow rejection. IR stores binary64 bits. As in Aeson, an explicitly written negative zero
is canonicalized to zero on decoding; tiny negative numbers may first underflow
to negative zero. Encoding emits an exact
finite decimal expansion; JSON numeric values agree with Haskell, although the
textual spelling can be longer. The host preserves incoming decimal lexemes until
Foil converts them. It does not validate Goo config or perform numeric conversion.
The outer host handles strict JSON framing; the Foil DTO entry assumes that
framing. Unicode and embedded NUL support are outside the agreed scope.

## Validation

Build the package and the **test-only** production Haskell codec oracle:

```sh
extras/mounts/goo/bin/goo build
goo/scripts/porting/build-codec-oracle.sh
extras/mounts/goo/bin/goo test
```

The oracle imports `Goo.Codec` and `Goo.Measurement.validateSemantic` under Goo's
locked Nix environment. It is never linked into or invoked by the production
adapter. `host/codec_checks.py` compares exact binary64 bits for the three floating config fields, every other
structural field exactly, and rejection
behavior using all available frozen normalized/semantic outputs, adversarial
field/edge cases and deterministic binary64 probes. Every accepted output is
reparsed/re-encoded. Diagnostic wording is deliberately not a Haskell/Aeson
compatibility surface; rejection currently reports a generic codec error.
