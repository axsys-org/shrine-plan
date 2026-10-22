# Portable renderer descriptors, version 1

Ported onto main October 19, 2026. These are additive fields on the existing display
and Explorer render contracts. Existing HTML, display version 1, publication
routes, and action admission remain supported. UIKit adoption is separate from
this server contract; a client does not gain support merely by decoding a field.

## Protobuf response transport, wire version 2

The Explorer mount accepts `wire=protobuf-v2` in queries/forms. It returns
`application/x-protobuf` using the named domain messages in
[protocol/goo.proto](protocol/goo.proto). Omission retains legacy JSON. Duplicate,
unknown, and the rejected generic-v1 selector return HTTP 415 before admission.
Transport versions are independent of display/profile versions.

The response oneof carries presentations, layout bundles, source pages,
snapshots, operation receipts, or failures. Geometry is finite binary64. Text,
paint, semantics, bindings and branded run myths have dedicated fields and
messages. The ordinary preparation encoder reads actual typed preparation
objects and scalar bits, without a JSON display or HTML intermediate. BAT
chunks share storage and flatten once at the HTTP boundary. Some existing
server domain APIs (paint tables, binding descriptors, pane/tree descriptions)
still require typed adapters; their arbitrary JSON shape is not the protocol.

Supported response families are `/goo/render` ordinary/native/pane views and
layout bundles, `/goo/source`, `/goo/status`, `/goo/operation-status`, `/goo/act`
and `/goo/edit-value`. Pipeline captures, patch packets, inspection captures and
catalogs retain JSON pending their own domain schemas. Binary pipeline, patch
and inspection requests fail explicitly. Workspace bootstrap uses JSON because
it may contain patch packets. See [protocol/README.md](protocol/README.md) for
implementation boundaries and regeneration instructions.

Requests remain URL-encoded. Freeze the selector with the original invocation;
retry exactly the same ID/body. A malformed successful action reply remains an
unknown outcome. Persisted receipt representation and action admission are
unchanged. Descriptive metadata and skipped unknown fields grant no authority.

The egui decoder bounds responses to 8 MiB, nesting to 64 levels, and total
messages/fields to 250,000. It rejects duplicate singular fields/oneof cases,
missing required fields, malformed wire types, invalid UTF-8, overflowing
integers and nonfinite geometry. Models still validate profile/font identity,
context, node IDs and binding joins before mounting. Ordinary models deserialize
directly; diagnostic JSON is projected on demand from retained protobuf bytes.

## Ordinary paint and meaning

Every `display.nodes[]` entry now has `paint` and `semantics`. Both have
`version: 1`. Coordinates, fonts, lines, payload, config and image `src` retain
their existing definitions in [HTML.md](HTML.md).

`paint` describes the resolved normal appearance:

| Field | Meaning |
|---|---|
| `units: "css-px"` | Logical units, before platform device-scale conversion |
| `colorSpace: "srgb"` | Six-digit `#rrggbb` colors |
| `foreground` | Text and current-color decorations |
| `background` | `{kind:"none"}`, `{kind:"solid",color}`, or `{kind:"linear-gradient",angleDegrees,stops:[{offset,color},…]}` |
| `border` | `{width,color}`; solid border drawn inside the allocated box |
| `corners` | `{kind:"radius",radius}` or `{kind:"ellipse"}` |
| `clip` | Whether the primitive clips its contents to its shape |
| `states` | Optional `highlight` and `focus` outline recipes, each `{width,color,offset}` |
| `marker` | Status text only: `{kind:"circle",diameter,gap,color:"foreground"}` |
| `image` | Images only: `{fit:"cover",clipToCorners:true}` |

Gradient angles use the CSS convention: 0 degrees points up, 90 points right;
angles apply in physical coordinates even in RTL. Stops are fractions of the
gradient line, with equal offsets representing a hard transition. Radii follow
CSS overlap reduction within the supplied box; an ellipse has half-width and
half-height radii. Borders and radii are already in logical pixels and are not
multiplied by `textScale`. The status marker diameter is already scaled. Paint
its first-line marker using the reserved `prefixAdvance`, supplied baseline,
and direction; do not add another gap to the line box.

The state recipes describe appearance only. Focus/highlight ownership stays
local. Focus means the HTML-equivalent visible keyboard focus; its outline
wins over highlight when both apply. A host may provide platform accessibility
focus separately. Image cover cropping uses the center of the source image;
image corner clipping applies even when the primitive itself has `clip:false`.

Paint is generated at build time from the **verified pinned Mash CSS** plus
profile geometry. Fixed recipes are precomputed constants, so runtime rendering
does not repeatedly format their numeric literals. Runtime consumers do not parse CSS. The bounded importer
rejects unsupported selectors, properties and paint values. An ordinary HTML
button currently uses the browser's light-profile black ButtonText baseline;
the portable recipe makes that color explicit. Primary and destructive flags
follow the CSS cascade, including their combination. The normal bar fallback
is the existing 73% fill. Configured bars preserve HTML's multiply-before-divide
arithmetic and default gradient when the multiplication overflows.

The vendored profile and its content hash are unchanged: this is a new lowering
of the existing artifact, not a modified artifact presented under an old hash.
`paint.version` versions that lowering vocabulary. A future profile change
still requires the regular verified import and asset revision update.

`semantics` supplies platform-independent meaning:

| Role | Fields beyond `version`, `role`, `label` |
|---|---|
| `text` | None; includes current static text/code presentations |
| `group` | None; grouping does not require a separate accessibility element |
| `button` | None; activation comes from the control binding |
| `textbox` | `value`, `editable:true`, `multiline:false` |
| `image` | None; covers image, avatar, presence and media presentations |
| `progressbar` | `range:null` when no semantic value exists, otherwise `{minimum:0,maximum,value}` |

Names match the existing HTML intent: inputs and progress bars use the explicit
nonempty config label or slot; image-like primitives use the explicit label,
payload, or kind fallback. Buttons/static text use their payload. Original
strings are retained; HTML parsing normalizes CR/CRLF, and native editing applies
its own single-line/composition behavior. A fallback painted bar does not invent
a semantic progress value. Neither `editable:true` nor a button role grants
action authority. Busy, selection, disabled state, focus and accessibility
notifications derive from the admitted local session state.

## Explorer control bindings

Ordinary surfaces and patch body controls retain their existing flat fields.
`captures` is always present, including `[]`. Each control also has:

```json
{
  "binding": {
    "version": 1,
    "kind": "invoke-and-become",
    "nodeId": "/example/view:3",
    "route": "0.1.2",
    "slot": "/example/next",
    "captures": [{"slot": "/example/about", "selection": "/example/current"}],
    "presented": true
  }
}
```

`kind` is `input`, `invoke`, `become`, `invoke-and-become`, or `none`. `nodeId`
joins the **local display**, while `route` addresses the original declaration
for admission. `slot` keeps its existing meaning: input argument slot or become
destination. An absent slot remains the legacy empty string. Capture references
identify the lexically resolved selection; they are not captured live values.
The client freezes input and selection evidence when it creates an invocation.

Bindings are produced after pane route and patch occurrence ID rewriting.
`presented:false` means source metadata survived but its node is absent from this
prepared display; do not manufacture a widget for it. Width-dependent visibility
can change that flag. Legacy flat fields and the nested binding describe the same
control. Existing `/goo` action checks still decide whether a request is valid.

## Portable patch occurrence content

A patch description adds `contentVersion:1`. Its existing `scene`, `contents`,
`controlsHTML`, and `offerBindings` remain. Each `contents[]` occurrence adds an
ordered `content[]` sequence:

| `kind` | Fields and interpretation |
|---|---|
| `body` | `key` (declaration route), `profile`, `context`, `display`, `controls`; an ordinary prepared body |
| `port` | Scene-local `key`, accessible `label`, `moves:[]` |
| `handle` | Scene-local `key`, accessible `label`, `moves:[{direction,dx,dy,label},…]` |
| `select` | Scene-local `key`, accessible `label`, `moves:[]`; selection only |
| `presentation` | `key`, `label`, absolute `target` and `slot`, `units:"css-px"`, `rect:{x,y,width,height}`; an embedded ordinary presentation reference |
| `label` | Scene-local `key`, recursive `children[]` content |

Static declarations and typed dynamic populations both carry `content[]`. Dynamic
populations remain passive: portable content does not grant domain action authority.
An embedded `presentation` supplies the same validated subject, slot and rectangle
as the browser frame. A supporting client requests and validates that ordinary
presentation separately, in its own owner; it must not parse the HTML or treat the
reference as action authority. Selection affordances never acquire movement deltas.
Unknown content kinds must be diagnosed rather than silently omitted.

Bodies are encoded from the **same checked preparation** used for their HTML.
A patch-node body uses its scene rectangle width when available, matching the
existing HTML path. Body display coordinates are local to that body. Scene
occurrence geometry supplies placement; renderers must not interpret the body
coordinates as scene coordinates. Sibling bodies keep declaration order. Port
and label keys refer to the enclosing occurrence, not globally unique objects.
A handle is a logical move affordance; the host can choose native controls or
accessible actions instead of copying the HTML corner placement.

The four movement descriptors currently carry +/-10 scene-unit X/Y deltas.
HTML movement buttons are generated from those same descriptors. Top-level
`connectionControls` contains `{key,controls:[…]}` groups. Controls are
`{kind:"disconnect",connection,label}` or
`{kind:"reconnect",connection,endpoint,label}`. These also generate the legacy
connection-control HTML.

These affordances do **not** introduce new operations. The scene's offered
operations, occurrence lifetimes, endpoints, candidate constraints and existing
`offerBindings` determine availability and admission. An offer binding's
`control` is the same finalized control emitted for its ordinary operation body;
its `argumentSlot` identifies the ordinary input used for the operation payload.
The client still owns gestures, candidate choice, camera state, previews,
acknowledgement coverage, and reconciliation. Hosted workspace session receivers are
forbidden from exposing domain invocation through patch occurrences just as
through ordinary surfaces.

## Trusted host capabilities

Explorer `/goo/render` results add `host`. It is `null` for ordinary rendering or
a legacy installed receiver without a descriptor. A registered workspace exposes:

```json
{
  "version": 1,
  "kind": "workspace",
  "declaration": "/example/workspace",
  "navigation": {"kind": "workspace-session", "sourceSlot": "/example/source_path"},
  "operations": [
    {"key": "/example/reload", "kind": "mount-rescan", "source": "/example/source"}
  ]
}
```

The endpoint configuration is stored beside its installed receiver and read
from the render's immutable namespace state. Its declaration must match the
registered receiver. Query parameters cannot create or replace it. The existing
HTML `data-operations` and the portable operations array share one generator.

`workspace-session` identifies main's stored-context contract. The receiver is
the allocated `/{self}/goo/ses/{numeric-id}` record, not the requested source.
`sourceSlot` names the path slot in that record. Refresh sends the session address
as `target` with the installed workspace declaration. Browser navigation enters
the configured workspace endpoint with its `path` query; that endpoint validates
the source and allocates a new context before returning the page. Changing the
source is not a `/goo/render` request against an arbitrary subject.

The existing configured workspace endpoint now accepts `GET ?path=...&format=json`.
It uses the same validation and stored-session allocator as HTML entry and returns
`{version:1,target,source,view,host}` as JSON. `target` is the allocated session,
`source` is the admitted requested path, and `view` is the installed declaration.
Only `path` and `format=json` are accepted for JSON entry, with no duplicate keys;
query fields cannot select a different declaration or manufacture capabilities.
The endpoint URL remains explicit host configuration; the descriptor does not
discover endpoints. After entry, send `target`, `view`, and `workspace=view` to
`/goo/render`. Validate the resulting host/declaration and context before mounting.
Navigation stages another entry and preparation before retiring local owners.

The earlier `workspace-subject` descriptor described
the pre-main synthetic receiver and must not be emitted for stored sessions. Operations identify the supported host workflow, not an
arbitrary executable command or URL. `mount-rescan` retains the existing guarded
status/scan/publication workflow. Unknown kinds must remain unavailable. This is
host configuration transport, not renderer capability negotiation or an
authorization token.

## Verification and consumer work

The profile gate compares actual Chromium CSS colors, backgrounds, borders,
corners, clipping, accessibility labels and roles against emitted descriptors,
alongside existing geometry and text checks. Fixtures include combined button
flags, progress values/overflow, images, scaled controls, RTL, role typography,
and whitespace. The SVG witness uses the emitted foreground. Native tests cover
patch body/offer identity joins, movement/connection content, captures, invisible
controls, installed host metadata, and hosted-session admission.

Run:

```sh
python3 extras/mounts/goo/scripts/test-sync-mash-profile.py
WISP=/path/to/locked/wisp python3 extras/mounts/goo/scripts/check-profile.py --mash-root ../mash
WISP=/path/to/locked/wisp python3 extras/x/check --mount explorer --mount patch-demo
node --test extras/mounts/explorer/tests/*.test.cjs
```

Historical validation on the pre-main branch (October 5, 2026) passed with the repository's locked Wisp runtime:
640 native checks, 8 profile integrity tests, 71 browser JavaScript tests,
14 Chromium/SVG fixtures (79 boxes and 48 explicit lines), and the production-P6
application gate (10 scenarios, 99 render responses, one deliberate save). The
live gate checks portable bindings and trusted host metadata as well as existing
editing, composition, delayed-response, topology and hydration behavior.

A UIKit consumer can now replace duplicated palette/shape and label decisions
with these descriptors, build patch bodies without parsing HTML, and discover
configured host operations from JSON. Native painting, accessibility mapping,
IME, focus, gestures and session behavior remain consumer work. Optional fields
allow older servers to be detected explicitly; clients claiming this descriptor
contract should reject unsupported descriptor versions rather than silently
substitute guessed appearance or action semantics.

Main also emits `snapshot.recipePublication` for declaration lifetime, separately
from global `snapshot.publication` used for action admission. Native consumers
that fall back to global publication remain conservative but may unnecessarily
guard a refresh after an unrelated declaration changes. Action invocations must
still freeze the global publication token.

## Main-port verification — October 19, 2026

Ported from the working tree based on `a1a2bb4` onto main `f373423`.
The stored workspace allocator, newer inspection/documentation/tree paths,
patch queries, dynamic populations and presentation frames are retained.
The receiver registry uses `/sys/content`; host descriptors use the new
`workspace-session` navigation kind rather than advertising the obsolete
synthetic-subject behavior. `select` is currently generated by server code;
this port does not add a Grove authoring constructor for it.

Final verification:

- Native mount contracts pass. Final native suite runs pass 905 assertions:
  web 135, Explorer 599, patch demo 4, moodboard 43, playground 124. Explorer was
  rerun after correcting a test that attempted to author `patch_select` in Grove.
- Profile integrity: 8 tests; prepared contract: 15 assertions. Chromium with
  scripts disabled: 14 fixtures, 79 boxes, 48 explicit lines; SVG advances match.
- Explorer JavaScript: 86 tests pass.
- Disposable production browser gate: 10 scenarios, 103 real render responses,
  one deliberate action. Includes stored-session host metadata and native editing.
- Rust/egui: 27 deterministic tests and strict Clippy pass; disposable save/reread,
  dirty resize, two-tab ownership, delayed/unknown outcomes, exact retry and stale
  response integration passes (15.42 seconds). The macOS app also saved and
  displayed the persisted reread from this server and inspected its binding.

### Rendering performance follow-up (2026-10-19)

The earlier 38.06-second port / 12.549-second main observations mixed compiler
cache states. A fresh process is not necessarily a cold compiler: P6 code and
signature memoization persist across processes. The earlier 0.848-second second
render did not reproduce in the matched small-editor fixture.

The paint generator now selects varying recipe fields and constructs the common
JSON envelope once, sharing nested paint values locally. Generated `profile.foil`
shrinks from 38,381 to 21,801 bytes and from 214 to 51 JSON object constructor
sites. The CSS-derived values, profile identity, prepared geometry, semantics,
and control authority are unchanged. Eight complete HTTP response bodies at
640, 420, and 800 CSS px match the original port byte-for-byte.

Matched measurements used the pinned Wisp runtime and P6, the disposable egui
note fixture, `PL_CODECACHE=0`, and fresh namespaces. Startup completed before
requests were timed; measurements ran serially with the other servers idle and
verification jobs finished. Warm values are medians of four identical requests.

| Implementation | First render, shared caches disabled | Warm median |
| --- | ---: | ---: |
| Main `f373423` | 81.124 s | 140 ms |
| Original port `fd7ef90` | 88.036 s | 154 ms |
| Shared paint builder | 82.185 s | 155 ms |

The cold overhead above main falls from 6.912 to 1.062 seconds. Steady-state
throughput is essentially unchanged by this optimization. A separate first-use
probe with the normal development cache took 7.751 seconds; a fresh process
with already cached original-port code took 0.235 seconds. These normal-cache
first-use samples have different cache populations and are not a controlled
before/after speedup claim. The end-to-end benchmark script then measured a
fresh optimized server with the populated cache: 0.198 seconds for its first
HTTP render and a 0.155-second warm median (63.101 seconds of server startup,
measured separately). A separate runtime trace showed long lazy compiler
spans and hit its 150-second read deadline; it is excluded from the timing table.

A completely cold P6 runtime remains slow on main too. The browser gate retains
its 120-second first-read allowance; the egui client retains its 120-second
render deadline and 20-second action/status deadline.

Follow-up verification passes: 9 profile integrity tests, all 36 compiled paint
recipes against the CSS resolver, 15 prepared assertions, Chromium/SVG parity
for 14 fixtures (79 boxes, 48 explicit lines), 777 web/Explorer/moodboard
assertions plus 2 mount-contract checks, and the disposable egui edit/save,
dirty resize, hidden completion, unknown outcome, receipt, exact retry, stale
response, and guarded-removal integration (14.91 seconds).

The egui checkout's `scripts/benchmark-render.py` reproduces the cache-disabled
comparison using disposable fixtures and archived revisions without changing a
checkout. It saves timings and exact received responses, separates startup from
rendering, and offers `--warm-cache` for normal development-cache measurements.


## Read-only portable Values

Writable records' synthetic Values responses retain `display:null` and the existing
browser HTML slot editor. They additionally expose `readOnlyDisplay`, containing
the ordinary version-1 display already prepared by `goo_reflection` from the same
namespace snapshot. Native clients may consume it for `/sys/slot/synthetic` with
an empty controls array. Its geometry, paint, font and semantics require the same
validation as any display. This field grants no edit/action authority. The native
Explorer opens declared ordinary views for edits; it does not parse or reproduce
the HTML slot editor. Read-only records continue to supply ordinary `display`.


## Live preparation inspection (optional)

The Explorer `/goo/render` request accepts `pipeline=1`. Omission keeps the normal response unchanged; unknown nonempty values are rejected. Prepared tree-page requests (`/goo/source`, `presentations=pane-v1`) also propagate this opt-in to their render variants. It never changes action evidence or enables controls.

Each ordinary prepared fragment may include `pipeline: {version: 1, origin: "live-preparation", note, stages}`. Stage records use the existing compiler inspector shape `{name, status, output, diagnostics}`. They are observations of the values used in this same snapshot/preparation, not a later replay. The stage order is parse, read, source, core, normalized, visible, semantic, metrics, layout, trace, prepared, display, bindings, html. Parse/read are `skipped` with null output because publication artifacts are not retained at this boundary (synthetic typed views bypass them). Source is evaluated typed Goo, not the original Grove file. Other successful stages use `ok` and an empty diagnostics array.

Source/core lack component IDs. Normalized/visible/semantic expose `attrs.id`; layout and display use `id`; metrics uses `sizes[id]`; adjacency trace uses `leftId`, `rightId`, and `parent`; bindings use `binding.nodeId`. Consumers must not infer pre-ID joins from text or ordinal. Prepared inspection provides measurement and wrapped-line records; final boxes, baselines, paint, fonts and accessibility semantics live in display. The display and bindings stage outputs are exactly the corresponding fragment fields. For synthetic Values, display corresponds to `readOnlyDisplay`; HTML is the Goo projection of that display, not the optional browser raw-value editor wrapper.

The enclosing response/fragment supplies profile, context and snapshot evidence. Pane native fragments and patch bodies have independent captures; structural host components retain their existing structured contracts. These diagnostics grant no invocation authority. Unknown pipeline versions can be retained as raw data without preventing admission of an otherwise supported ordinary response. No partial failure capture is added by this extension: a failed preparation follows the existing render error path.

### English text runs

Prepared display version 1 has additive text-run fields. `node.textRuns` is the
lossless source payload, encoded as an ordered array:

```json
[{"myth": {}, "lang": {"en": {"txt": "Hello"}}}]
```

`payload` remains its exact concatenated string projection. IR inspection and
normalized/semantic codecs use the same `textRuns` beside `text`; decoding rejects
conflicting projections, duplicate descriptor keys and unsupported languages.
Legacy string-only input is lifted into one English run with an empty descriptor.

Each static `line.runs` contains prepared fragments with `myth`, `lang: "en"`,
`text`, absolute CSS-pixel `box`, `textX`, and `baseline`. Concatenation equals the
line's `text`. Fragments share its text style/paint in the initial profile; their
origins are supplied by Reaver. `prepared.lines[].runLines` retains the wrapped
run sequences. Editable inputs expose source runs but no stale static lines.

The run's RunDescriptor is a Foil `myth` (path-keyed branded pails). The supported
slots and font registry are documented in `TYPES.md`. Metadata is decoded and
resolved on the server before layout. The client consumes prepared styling.

A display containing styled runs has **display version 2**. Unstyled displays
retain version 1 and identical output. Each styled fragment requires `resolved`:

- `version: 1` and `textStyle`: exact font ID/hash, family, weight, style, size,
  line height and tracking. Extra pinned faces are in `run-fonts/fonts.json`.
- `foreground`: resolved sRGB ink.
- Optional `highlight`: `fill`, `stroke`, inside-border `width`, and `radius`,
  applied to that fragment's supplied box. Wrapped links have one box per line.
- Optional `underline`: `color`, stroke `width`, and absolute CSS-pixel `y`.
- `semantics`: `role` (`text` or `link`) and optional structured `target`
  (`{kind:"path",path:...}` or `{kind:"weblink",href:...}`).

Clients validate supported versions, source/fragment metadata joins, typography,
font hashes, paint bounds, and link-target consistency before mounting. Link
semantics are descriptive and supply no action route. The egui implementation
paints the highlight and exposes its target on hover; click navigation is not
implemented. HTML uses non-navigating spans with the same resolved styling.
Display v2 editing remains plain text; styled input requires the v3 contract
below. Unicode shaping and arbitrary downloaded/namespace font resolution remain
unsupported.

## Rich-text editing (display v3)

A prepared input may supply `editing` with `version:1`, `encoding:"goo-text-v1"`,
`maxBytes:65536`, `styles:[{myth,resolved}]`, and `linkStyle`. Its `textRuns` is the
initial structured value, `semantics.value` is its plain projection, and
`semantics.multiline` is true. `lines` remains empty: editing, selection, caret,
scrolling and IME use the platform editor. The supplied input box is fixed by
Reaver. Styling options contain resolved pinned font/paint recipes; consumers
must not invent font choices or a parallel palette. Match a run's metadata to
an option after removing `/sys/link` and canonicalizing modifier order (an empty
modifier list is equivalent to no modifier slot). Use `linkStyle`'s foreground
and highlight for linked editing text; its placeholder target is descriptive
and grants no action authority.

Display v3 is required even for an empty rich value. Older native clients must
reject it rather than flatten it into a plain input. Browser output explicitly
diagnoses the unavailable editor; it does not expose a plain input pretending to
edit structured runs. Ordinary plain inputs and v1/v2 displays are unchanged.

The action input is a serialized Goo run array in the existing `input:<slot>`
form field. The declaration must use a typed action argument decoder; the mount's
`goo_edit/decode` accepts that JSON string or an existing `goo/text/pail`, checks
its shape, metadata, pinned fonts and ASCII repertoire, and returns a typed pail.
It never resolves code or dispatches from metadata. JSON strings are not
automatically promoted by `.poke`: use a declared typed action. Freeze the wire
string alongside the usual receiver, declaration, versions and invocation ID.
A retry must reuse the exact original body. Preserve edits made after activation.

Rich/plain encoding changes and removed formatting support are incompatible
re-preparations: retain dirty owners and stage the change behind the existing
loss-of-work guard. Compatible refresh/resize must retain run metadata, caret,
composition, selection, typing style, undo history and pending invocations.
Current scope is English/ASCII, bundled fonts, inline modifiers and links;
clipboard interchange is plain text. No browser/HTML rich editor or UIKit rich
editor is included.
