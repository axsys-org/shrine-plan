# Native prepared rendering (items 25–28)

`goo_html/prepare` accepts a semantic tree and one render context: available width,
text scale, and direction. It computes a validated native ASCII plan, joins each
plan ID to its semantic payload, and stores explicit lines with the plan. Empty
semantic output is supported. Defaults at the JSON boundary are width 752, scale
1, LTR, and view path `/full`.

The prepared representation lives in `goo_html_internal`. Foil record constructors
are not compiler-private, so this is an internal namespace convention reinforced
by a runtime guard, not a claim of language-enforced opacity. The public fragment
painter validates the measurement, dimensions, ID joins, measured summaries,
leaf heights, lines, and complete rebuilt render tree before painting. A forged
record cannot bypass this guard through the public fragment/document entry points.
Their signatures accept no independent width or scale. Internal painting helpers
are implementation details; callers must use the guarded entry points.

`goo_html/fragment` emits the surface, groups and rows, explicit text spans,
images, controls, and fixed primitives. Text and attributes use the same escaping
builder. Input values preserve original whitespace; status marks occur only on
the first explicit status-text line. Row gaps become logical margins; stacked
children select top alignment. All dimensions use native binary64 values, printed
as exact decimal JSON number tokens valid in CSS. Equivalent numeric spellings
are intentional. Bar gradients retain the original arithmetic ordering, including
its overflowing `100 * value` behavior.

`goo_html/document` emits the original doctype, metadata, title, stylesheet links,
render root, and view-path border colors. It includes no scripts or API bootstrap.
CSS and fonts remain the frozen shared assets.

The version-1 test/development action `render` accepts `tree`, optional `width`,
`textScale`, `direction` (`ltr`/`rtl`), and `viewPath`. `tree` is the checked semantic
wire format or null. The response contains `prepared`, `html`, and `document`.
It does not accept externally supplied plans, rows, lines, or prepared records.
Source compilation now reaches prepared output and HTML and returns `complete`
when all stages succeed. Recorded-measurement fixtures still stop at geometry:
the ASCII renderer must not silently paint a plan based on unrelated measurements.

## Verification

`test-html` compares all frozen source envelopes through HTML and direct renders
against `test/HtmlOracle.hs`, a test-only adapter around the unchanged Haskell
renderer and document producer. HTML is parsed into a tree. Text, element order,
IDs, classes, direction and nonnumeric attributes compare exactly. Attribute and
CSS property order, entity spelling, and equivalent numeric CSS/ARIA spellings
are ignored; only numeric style/ARIA values use the established layout tolerance.
Mutation checks prove that payload, class, ID, direction, width, and structure
changes are reported at precise paths.

Additional cases exercise hostile markup, labels, empty payloads, whitespace,
all primitives, image wrappers, progress values, nested flows/stacks, both
directions, fractional/narrow widths, scale changes, all debug borders, defaults,
and invalid protocol inputs. Native unit tests exercise the prepared guard and
missing-ID lookup. Compiler clients reject phase/plan confusion and a separate
width argument at painting time.

```sh
goo/scripts/porting/build-html-oracle.sh
extras/mounts/goo/bin/goo build
extras/mounts/goo/bin/goo test-html
python3 goo/scripts/porting/native-browser-cases.py
python3 goo/scripts/porting/native-browser-server.py
# Open http://localhost:8793/static/inspector/ascii-check.html
```

Browser generation reads frozen cases and replaces only their two HTML fields in
`.build/native-browser-cases.json`; it also checks each fragment's parsed parity.
The isolated server overlays that file while serving the unchanged checker,
styles and fonts. All 7,920 frozen expected dimensions and the 3% ceiling remain
unchanged. The original fixture is hashed before and after generation.

Use the baseline hostname `localhost` at normal page zoom for browser acceptance.
Origin-specific saved zoom can affect pixel-snapped borders: the 90% zoom found
on `127.0.0.1` produced identical failures for native and Haskell HTML. See the
retained control run in `porting/gate-h/browser-initial-scale.json`.
