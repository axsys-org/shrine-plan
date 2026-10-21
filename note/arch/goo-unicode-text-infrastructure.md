# Goo Unicode text infrastructure

Deliver a reusable Unicode text system before building the shared document
editor. Grove applications keep their existing declarative ownership model.
Goo computes layout and editing geometry on the server. Mash paints prepared
glyphs and captures input. This specification supplies the T1–T6 tickets in the
[document workspace plan](goo-document-workspace-plan.md).

The selected implementation uses a persistent native HarfBuzz/ICU service,
a pinned Mash font profile, a checked Foil continuation boundary, and an SVG
glyph-outline painter. These are planned additions, not existing capabilities.

## Ownership

| Layer | Owns | Produces |
| --- | --- | --- |
| Mash profile | Font files, styles, fallback order, feature policy, paint recipe | Content-addressed font/profile bundle |
| ICU inside the text service | Unicode segmentation, break opportunities, bidi analysis | UTF-8-indexed analysis and line-specific visual run order |
| HarfBuzz inside the text service | Shaping a specified run with its chosen font and context | Glyph IDs, clusters, advances, offsets, extents |
| Goo in Foil | Font/run policy, actual line fitting, wrapping, adjacency, baselines, carets, selections | Validated prepared geometry |
| Trusted host | Service lifecycle, bundle verification, request routing and caches | Matching service replies |
| Mash renderer | Paint prepared shapes, capture input, map viewport coordinates | User intents and pixels |

HarfBuzz shapes font runs but does not perform paragraph wrapping or bidi
analysis. ICU supplies boundaries and bidi support. Goo remains responsible
for choosing actual line breaks and using those results.
[HarfBuzz scope](https://harfbuzz.github.io/what-harfbuzz-doesnt-do.html),
[ICU boundaries](https://unicode-org.github.io/icu/userguide/boundaryanalysis/),
[ICU bidi](https://unicode-org.github.io/icu/userguide/transforms/bidi.html)

The service does not accept document mutations, arbitrary file paths, external
font URLs, HTML, or client-provided geometry. It is an internal dependency of
Goo. The browser continues to request prepared Goo content.

## Packaging and font profile

Build a small C++ executable against HarfBuzz and ICU using Nix. Reuse the
repository's locked package set when its APIs satisfy this protocol; otherwise
update that dependency deliberately. T1 records the exact resolved versions,
Unicode data version, build derivation, and hashes. Do not specify a floating
“latest” dependency or use host-installed libraries.

Publish capabilities for the supported macOS/Linux architectures. The
handshake names protocol version, engine revision, ICU data revision, shaping
features, paint capabilities, and the font bundle revision. A mismatch fails
before layout starts.

Mash's version 2 profile contains:

- Full font files and hashes, face indexes, licenses and immutable font IDs.
- Explicit fallback chains by style/script and language policy where relevant.
- Default OpenType features, direction policy, nominal sizes and line-height
  policy.
- Unicode and engine compatibility identifiers.
- Supported coverage, required corpus, and a last-resort missing-glyph recipe.
- Numeric conversion and painter capability versions.

Use full, pinned fonts covering Latin, Hebrew, Arabic, CJK and monochrome emoji.
T1 selects and verifies concrete files; a font family name alone is insufficient.
Preserve the version 1 bundle as a compatibility artifact. Font acquisition and
outline extraction happen in the controlled build/runtime service, never by
browser/system fallback.

Try fallback fonts over an appropriate cluster/run with its shaping context.
Do not split a combining sequence or emoji sequence into independently chosen
font characters merely because their code points have individual glyphs. When
the bundle cannot realize a sequence, keep the original text and prepare a
deterministic missing-glyph marker with a coverage diagnostic. That case does
not count as supported coverage.

## Native service protocol

Use a persistent subprocess with framed UTF-8 JSON messages for the first
implementation. Each frame is a four-byte unsigned big-endian byte length
followed by that many UTF-8 bytes. Allocate request IDs independently of
document IDs. Separate diagnostics from the framed output.

Start with an 8 MiB frame limit, at most 1 MiB of UTF-8 paragraph input, and
explicit analysis/glyph/output budgets. These are configurable resource limits,
not character-set restrictions. Oversized input returns a typed error without
truncation. Later streaming may extend capacity under a new capability.

All requests include protocol, engine/profile revision, request ID and an input
digest. All replies echo those fields. The initial operations are:

| Operation | Request | Response |
| --- | --- | --- |
| `capabilities` | Expected protocol/profile | Actual engine/data/profile and supported operations |
| `analyze` | Paragraph text, explicit locale and base direction | UTF-8/UTF-16/scalar maps, grapheme/word/line-break boundaries, script/bidi information |
| `shape_runs` | Text plus contextual ranges, explicit fonts, size, features, direction and line-boundary flags | Positioned glyph data in logical run records and cluster maps |
| `line_bidi` | Analyzed paragraph identity and Goo-chosen logical line ranges | Visual run order with the required per-line bidi adjustments |
| `glyph_assets` | Font hash/face, glyph IDs and pinned variation settings | Reusable outline paths and extents in font units |

Font selection and line selection are explicit Goo inputs to these operations.
The service may report missing glyphs but cannot choose an unlisted system font
or silently choose different line boundaries.

Validate UTF-8 on input. Map ICU's and browser APIs' indexing conventions to
UTF-8 offsets before returning data. Reject unpaired surrogate input before it
crosses the native boundary. Preserve original scalar sequences and default
ignorables; do not normalize text during analysis. Document ingestion handles
newline normalization. The existing NUL transport restriction stays explicit.

Return typed errors for revision mismatch, invalid offsets, missing assets,
unsupported capabilities, work limits, timeout and worker failure. Cancel
superseded requests; discard their late replies even if the native call finishes.
Restart a failed worker without treating any request as a committed document
operation. There are no document operations in this service.

## Integration into pure Goo preparation

Introduce a pure state-machine boundary:

```text
start(text, style, profile, context)
  -> done(prepared) | need(request, continuation) | error(diagnostic)

resume(continuation, verifiedReply)
  -> done(prepared) | need(request, continuation) | error(diagnostic)
```

The trusted host fulfills `need` and resumes Foil. Replies are accepted only
for the matching request digest, revisions, text ranges and budgets. Pure
geometry validation still checks finite dimensions, indexes, cluster bounds
and consistency. Passing those checks is not evidence that arbitrary client
measurements came from the selected shaper: only the trusted service adapter
can supply production replies.

Use the same adapter from the standalone CLI/worker and the live Explorer
host. This is a new host protocol extension; the existing Rex/UUID bridges do
not already provide arbitrary native calls. Keep intermediate state in the
leased Goo runtime instead of rebuilding the compiler state for each font run.

The pipeline is:

1. Validate and analyze the complete paragraph.
2. Resolve styles, script/direction runs, and the pinned font fallback policy.
3. Shape candidate runs with surrounding context.
4. Have Goo choose line boundaries from candidate breaks and shaped widths.
5. Reshape boundary-sensitive runs and obtain per-line bidi ordering for those
   selected ranges. Refit if changed advances invalidate the proposed break.
6. Produce final boxes, baselines, run positions, carets, selection segments and
   hit regions.

Specify a bounded fitting strategy with deterministic tie breaks. If emergency
wrapping is needed, break at permitted grapheme boundaries and reshape with
context; do not slice a glyph cluster from an old shaping result. The planner's
ordinary box layout consumes the resulting text-block metrics.

Pin the service's font scaling and round shaped pixel geometry once to signed
1/64 CSS-pixel units. Convert those integers exactly into Goo's binary64
coordinates; preserve existing planner arithmetic thereafter. Record this
numeric policy in the profile and verify it across supported hosts. Glyph
outline coordinates remain in font units with explicit transforms.

## Editing geometry

Prepared text retains logical text separately from glyph output. For each
block, publish logical lines, visual runs, glyph references and positions,
cluster ranges, caret stops, selection segments and hit regions.

A Unicode grapheme can involve several glyphs; a ligature can involve several
graphemes. Do not equate either with a shaping cluster. Use font-provided
ligature caret information where available. For missing internal caret
information, define a deterministic subdivision of the cluster's advance at
permitted grapheme boundaries; test and document that fallback.

An offset at a wrap or bidi boundary can have more than one visual position.
Retain affinity and direction in the caret representation. Define visual arrow
movement separately from logical range editing. One logical selection can paint
as multiple visual segments.

Empty paragraphs and terminal newlines get editable line/caret boxes. Tabs use
explicit Goo tab stops. Mark changes cannot split a user-visible grapheme in
ways forbidden by the declared editing policy. Mark and text operations never
infer their offsets from painted DOM spans.

## Painter and accessibility

Use SVG paths and reusable glyph definitions for the first version 2 painter.
Extract outlines through HarfBuzz's glyph drawing interface, cache them by
font hash/face/glyph/variation identity, and place them at Goo's prepared
positions. HarfBuzz exposes a drawing API for extracting glyph shapes.
[Glyph drawing](https://harfbuzz.github.io/harfbuzz-hb-draw.html)

The browser may rasterize paths and apply a viewport transform. It does not
reshape text or choose glyph positions. Do not use SVG `text`, canvas
`fillText`, CSS wrapping, or DOM range geometry as a fallback for version 2.
Bit-identical antialiasing across operating systems is not an acceptance goal;
identical layout inputs and prepared geometry are.

Use a separate semantic text representation for reading and a native capture
control for active editing. Prevent duplicate screen-reader announcements.
Preserve logical content for copy/paste and explicit search; browser find,
native drag selection and accessibility focus need dedicated qualification
because paths do not provide those behaviors automatically.

Place the capture control using prepared caret geometry. Keep it alive through
IME composition, pane changes, and response delays. Render preedit text only
from a matching Goo draft preparation. Native candidate windows may be placed
by the OS, but their geometry does not determine document layout.

The initial required emoji font must have a paint representation supported by
this outline pipeline. Monochrome emoji qualify if sequences and editing work.
Color fonts and arbitrary OpenType paint graphs are a later declared feature,
not a silent omission or an excuse to use system emoji fonts.

## Persistent execution and caching

Keep a bounded pool of service workers and loaded font faces. Use immutable
cache entries keyed by:

- Analysis: exact text, locale, base direction, Unicode/ICU revision.
- Shaping: contextual text/range, font hash/face, size, features, variation
  settings, script, language, direction, line flags, engine/profile revision.
- Outline: font hash/face, glyph ID, variation settings, outline revision.
- Layout: analysis/shape identities, width, scale, styles, wrapping policy.

Do not key caches only by block ID or Unicode string. Bound cache bytes,
evictions and worker work; report cold and warm behavior. Exclude document
mutation from cache operations.

For edits, invalidate the affected paragraph's analysis and shaping context
conservatively. Reuse unaffected paragraphs and glyph assets. For width-only
changes, reuse width-independent analysis and eligible shaping; recompute line
fitting, boundary-sensitive shaping and editing geometry. A changed font or
engine revision invalidates all dependent results.

## Required qualification

The text fixture corpus must be versioned with the profile:

| Case | Required behavior |
| --- | --- |
| `café` and `café` | Preserve distinct source sequences; correct glyphs and grapheme deletion |
| Hebrew mixed with English, digits and punctuation | Correct per-line bidi order, dual-affinity carets and logical copying |
| Arabic with combining marks and joins | Contextual shaping across candidate wraps and correct final-line shaping |
| Chinese/Japanese/Korean text | Font coverage, valid wrapping, input composition and no split graphemes |
| Emoji with modifiers, flags and ZWJ sequences | Supported sequence shaping and grapheme movement/deletion |
| Ligatures and mixed font styles | Logical-to-visual mapping and stable caret policy |
| Empty/trailing-newline/tabbed paragraphs | Explicit editable geometry at narrow and wide widths |
| Missing glyphs and malformed input | Recoverable coverage diagnostics or typed validation errors; no text loss |

Run the official segmentation, bidi and line-break conformance data matching
the pinned Unicode revision, plus these application fixtures. Unicode's
segmentation and line-breaking specifications are the reference for those
boundaries. [UAX 29](https://www.unicode.org/reports/tr29/),
[UAX 14](https://www.unicode.org/reports/tr14/)

Compare native prepared geometry across supported macOS/Linux targets. Test
Chromium, Firefox and WebKit painting at different widths, text scales and
canvas transforms. Check caret/hit round trips and that copy preserves logical
order. Use real OS IME and VoiceOver before declaring the input surface ready.

Retain version 1 geometry tests unchanged. Add version 2 tests that do not
promote arbitrary browser measurements into the expected layout. Cross-check
pure records, rendered path extents and visible fixtures separately.

Use cold/warm 1 KiB, 20 KiB and mixed-script paragraphs, then the document
plan's 100/1,000-block fixtures. The local targets remain p95 50 ms incremental
preparation and 120 ms input-to-matching-paint; report shaping, host transfer,
Foil fitting and painting separately. These are targets to validate.

## Immediate implementation tickets

**T1: reproducible service and profile contract.** Add the native package,
length-framed codec, capability handshake, engine/profile manifest and selected
font assets. Verify clean builds, wrong-revision rejection, frame/work limits,
shutdown and asset hashes. Preserve the existing Goo profile gates. Exit with
actual pinned versions and a machine-readable coverage manifest.

**T2: analysis and shaping.** Implement `analyze`, `shape_runs`, `line_bidi`
and `glyph_assets`, including UTF-8 maps, deterministic fallback inputs and
outline extraction. Run the multilingual corpus directly against the service.
Exit with verified glyph/cluster results, measured cold/warm costs, and no
dependency on browser measurement.

T3 integrates Goo's fitting and geometry. T4 proves painting and real input.
T5 integrates persistent host execution and invalidation. T6 qualifies and
releases the paired infrastructure. The document prototype starts on that
released path; it does not introduce a temporary ASCII text model.
