# Deterministic ASCII measurement

The native Foil measurer implements `text_style`, `natural_width`, `leaf_size`,
`text_lines`, `leaf_height` and recursive ASCII validation. It is available as
`goo_ascii` and through the `ascii` inspection action. Goo's planner consumes
these measurements on the server; the shared `goo_prepared` module resolves
geometry and text for HTML and other renderers. No browser or system-font query
participates in measurement.

## Canonical profile and pinned fonts

Mash's `@mash/goo-profile` package defines the `mash-goo` version-1 profile.
The committed `profile/` bundle is a verified import of that package's
distribution: definition/schema, CSS, fonts, metrics, licenses and asset hashes.
Its content-addressed revision binds all of those inputs. Font fallback is not
part of the measurement model.

`scripts/sync-mash-profile.py` generates `profile.foil`, containing profile
identity, text styles, primitive geometry and font metadata. `ascii.foil`
consumes those values directly. The same authored Mash values generate the CSS.
`scripts/generate-fonts.py` imports `profile/metrics.json` and verifies pinned
font hashes before generating `fonts.foil`: eight faces, 760 glyph advances,
units, weights, names and provenance hashes. The profile also supplies verified
vertical font metrics for the portable display list's explicit baselines.
Runtime measurement uses these compiled constants.

From the Reaver repository root, update and verify with:

```sh
pnpm --dir ../mash run goo:profile
python3 extras/mounts/goo/scripts/sync-mash-profile.py --mash-root ../mash
python3 extras/mounts/goo/scripts/sync-mash-profile.py --check
```

Only an explicit `--mash-root` update replaces the imported assets and generated
tables. Local `--check` verifies the complete inventory, byte hashes, revision
and generated constants without a sibling checkout. Production builds perform
that check and fingerprint the bundle. Existing historical `fonts/` inputs are
retained reference material, not an independent active typography source.

## Numeric and text policy

`binary64.foil` performs finite arithmetic using exact integer fractions followed
by round-to-nearest, ties-to-even binary64 rounding after every operation. The
first profile preserves the original measurement operation order, including
`(line-height ratio * base font size) * scale`, left-to-right glyph sums,
negative tracking and the wrapping comparison with `room + 0.00001`.
Tracking and insets remain unscaled; typography scales, while fixed primitive
sizes retain their existing behavior. Preferred widths use ceiling after the
configured/default cap. The planner applies config grow overrides.

CRLF becomes one newline, bare CR becomes newline, and tabs become four spaces.
Text/code retain spaces and break after the last fitting space, hyphen or slash;
overlong tokens make progress one ASCII character at a time. Empty text and a
terminal newline retain their existing line-count rules. Text status markers
reserve `8 * scale + 5` only on the first paragraph's first line; text errors
gain the `! ` prefix. Buttons use collapsed words for natural width. Role style
uses the slot's first segment, while caps and minimum widths use the exact slot.

Profile version 1 accepts printable ASCII plus tab/CR/LF in measured payloads.
Recursive failures identify the first unsupported node. Image URLs and config
labels are excluded from geometry/ASCII checks. Unicode shaping, fallback fonts
and Unicode bidi are not implemented by this profile. RTL context resolves
physical placement for the supported text; it does not claim broader glyph
coverage. NUL remains excluded by the Foil JSON transport and is rejected before
measurement. Other unsupported controls/text produce an ASCII failure.

## Inspection protocol

```json
{"version":1,"action":"ascii","tree":{"id":"example","kind":"text","slot":"title","after":null,"text":"Hello world"},"textScale":1,"widths":[80,180,320]}
```

A successful response contains `profile` (`id`, `version`, `revision`) and
preorder leaf nodes with IDs, style, natural width, min/pref/grow size and
per-width height/lines. Lines are null for leaves that do not use text/code
wrapping. A malformed semantic tree or invalid scale/width returns a protocol
rejection; an unsupported payload returns an ASCII rejection. Scale must be
finite and in `(0,10]`; widths finite and in `[0,100000]`.

The `fonts` action (`{"version":1,"action":"fonts"}`) returns the same profile
identity plus compiled font metadata, glyph units and numeric advances. All
calculations and validation run in Foil; the host frames the request and
preserves decimal lexemes. For final absolute boxes and baselines, use the
[prepared display contract](HTML.md#public-prepared-contract), not the inspection
action as a second layout implementation.

## Validation

The current acceptance gate verifies the actual profile and prepared renderer:

```sh
WISP=/path/to/the/locked/wisp python3 extras/mounts/goo/scripts/check-profile.py
WISP=/path/to/the/locked/wisp python3 extras/mounts/goo/scripts/check-profile.py --mash-root ../mash
python3 extras/mounts/goo/scripts/test-sync-mash-profile.py
```

Without `--mash-root`, checks remain repository-local and cover bundle integrity
and native preparation. With it, the gate also verifies the paired distribution
and runs Chromium HTML geometry and SVG-consumer checks using Mash's installed
Playwright. Neither consumer imports Goo's planner or remeasures text to choose
line breaks. Native arithmetic assertions remain exact binary64 comparisons;
browser realization checks account for browser coordinate precision.

The older `test-metrics`, `build-ascii-oracle.sh` and
`check-ascii-corpus.py` suites are historical differential comparators requiring
the former top-level `goo/` oracle tree and frozen fixtures. Their 7,920 accuracy
cases, 760 advances and wrap-boundary probes document the earlier ASCII model.
The unchanged Haskell measurer is useful evidence for preserving arithmetic,
but cannot establish conformance to newly versioned profile metadata, CSS or
portable display output. Preserve those frozen references; the current
`check-profile.py` gate defines renderer acceptance.
