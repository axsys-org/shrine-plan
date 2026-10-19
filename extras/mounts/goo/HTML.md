# Server preparation and rendering

Goo owns semantic interpretation, measurement, adjacency, wrapping and layout.
Mash's `mash-goo` version-1 profile supplies pinned fonts, typography, primitive
geometry and matching HTML recipes. Preparation happens on the server. A browser
or another painter consumes the result without reimplementing Goo's layout
semantics or running a client measurement pass.

## Public prepared contract

`goo_prepared/prepare` accepts a semantic tree and one render context: available
width, text scale and direction. It computes a validated native plan, joins each
plan ID to its semantic payload, and stores explicit lines for static text. Empty semantic output
is supported. The HTML entry point `goo_html/prepare` delegates to this shared
module; preparation has no HTML or browser dependency. The standalone development
JSON action defaults to width 752, scale 1, LTR and view path `/full`. Live Explorer
requests require an explicit context.

`goo_prepared/encode` validates a prepared value and returns `maybe[json]`. Its
version-1 display list contains:

- `profile`: the profile `id`, `version` and content-addressed `revision`.
- `context`: the requested `width`, `textScale` and `direction` (`ltr`/`rtl`).
- `coordinates: "absolute-css-px"`, resolved root `width`/`height`, and preorder
  `nodes`. The root width includes Goo's normal layout quantization.
- Each node's `id`, `parentId`, `kind`, semantic `role`, full `slot`, `config`,
  original `payload`, absolute `box`, `textStyle` and explicit `lines`. Images
  additionally retain their `src`. Each node also carries versioned `paint` and
  `semantics` descriptors; see [the portable contract](PORTABLE.md).
- Each text style's pinned font ID/hash, family, weight, style, font size,
  line height, letter spacing and insets. Kerning and ligatures are disabled
  for this profile's deterministic glyph-advance model.
- Each line's `text`, absolute `box`, `textX`, absolute `baseline` and
  `prefixAdvance`. The prefix reserves the first status marker. Baselines come
  from the pinned font's vertical metrics; painters need not infer CSS line-box
  behavior.

Editable `input` nodes have an empty `lines` array. Their original value remains
in `payload`, alongside `config`, the allocated `box` and resolved `textStyle`.
The renderer's native control owns editing and painting that value inside the
server-allocated box, including tabs, caret, selection and composition. The
prepared display does not claim static glyph positions for an editable value.
Static button and avatar labels still carry explicit lines.

Coordinates are physical positions from the surface's top-left, including RTL
placement and the resolved gaps/alignment. Renderers paint those boxes and lines
using the identified fonts. They do not need to interpret flow direction,
adjacency rules, wrapping or the browser DOM. A new width, text scale, direction
or profile revision requires a new preparation; reflowing an existing display
list under a different context is outside the contract.

The legacy record namespace `goo_html_internal` remains for source compatibility.
Its name does not imply that preparation belongs to HTML. Foil record constructors
are not compiler-private, so guarded consumer entry points revalidate the
measurement, dimensions, ID joins, measured summaries, aggregate geometry,
leaf heights, lines and rebuilt render tree. Forged prepared records cannot
bypass those guards. Public painting takes no independent width or scale.

## HTML consumer

`goo_html/fragment` paints the same checked preparation as the portable display
list. It emits a surface, groups and rows, explicit text spans, images, controls
and fixed primitives. Text and attributes use the same escaping builder. Input
value attributes preserve original whitespace; the native control applies its
normal single-line editing behavior. Status marks occur only on the first
explicit status-text line. Row gaps become logical margins and stacked children
select top alignment. The HTML recipes realize the server's resolved geometry;
there is no client text measurement or layout planner.

All dimensions use native binary64 values printed as exact decimal JSON number
tokens valid in CSS. Equivalent numeric spellings are intentional. Bar gradients
retain the existing arithmetic ordering, including overflowing `100 * value`.

`goo_html/document` emits the doctype, metadata, title, profile stylesheet link,
render root and view-path border colors. It includes no scripts or API bootstrap.
`/static/goo-profile.css` and its font URLs resolve to the verified, vendored Mash
bundle. The CSS pins horizontal and vertical font metrics; system fonts are not
a substitute. See the [profile update workflow](README.md#renderer-profile).

The version-1 test/development action `render` accepts `tree`, optional `width`,
`textScale`, `direction` and `viewPath`. `tree` is the checked semantic wire format
or null. Successful responses contain `profile`, the portable `display`, legacy
`prepared` inspection, `html` and `document`. They do not accept externally
supplied plans, rows, lines or prepared records. Source compilation reaches
prepared output and HTML and returns `complete` when all stages succeed.
Recorded-measurement fixtures still stop at geometry: the profile renderer must
not silently paint a plan based on unrelated measurements.

Version 1 supports ASCII measured text plus tab/CR/LF. Unsupported Unicode
produces an explicit measurement failure. Changing the font fallback or letting
the browser rewrap does not extend that coverage. See [ASCII measurement](ASCII.md).

Explorer's production `/goo/render` endpoint adds published-view selection,
namespace snapshots, action controls and pane descriptions to this boundary.
It requires the measured container context and validates the same profile in the
browser. See the [live preparation contract](../explorer/PANES.md#live-preparation-contract)
and [real application gate](../explorer/APPLICATION-INTEGRATION.md).

## Verification

Run the current renderer conformance gate from the repository root:

```sh
WISP=/path/to/the/locked/wisp python3 extras/mounts/goo/scripts/check-profile.py
WISP=/path/to/the/locked/wisp python3 extras/mounts/goo/scripts/check-profile.py --mash-root ../mash
```

Without `--mash-root`, the script verifies the vendored profile and native
preparation under the production P6 compiler, including guard rejection and display fixtures.
`--compiler none` is available for boot-compiler diagnosis. With that argument,
it also verifies the paired Mash distribution and uses Mash's installed
Playwright/Chromium to compare actual HTML geometry with the server's display
list. Page JavaScript is disabled. An SVG consumer independently paints the
display list without importing Goo's planner. `--output DIR` retains native
logs, fixtures and consumer artifacts. These checks use the real profile assets
and are the acceptance contract for current HTML and portable renderers.

The old `test-html` and `goo/scripts/porting/native-browser-*` suites are
historical differential comparators. They require the former top-level `goo/`
tree, its frozen fixtures and the unchanged Haskell oracle, none of which are
runtime dependencies or included by this Extras mount. Their original HTML-tree
comparison and 7,920-case browser evidence document the prior renderer. New
profile metadata, asset links and display output intentionally extend that
contract. Preserve frozen references as historical evidence; do not regenerate
them to make current profile conformance pass.

The browser conformance gate checks boxes and line heights within 0.12 CSS px,
and glyph advances within 0.25 CSS px. Native HTML rounds font metrics and
half-leading, so its baseline allows 1.5 CSS px of rendering variation. The
exported baseline remains fractional and renderer independent; the SVG consumer
uses it directly. These tolerances do not change the server plan or line breaks.
