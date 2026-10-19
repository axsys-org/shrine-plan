# Portable renderer descriptors, version 1

Ported onto main October 19, 2026. These are additive fields on the existing display
and Explorer render contracts. Existing HTML, display version 1, publication
routes, and action admission remain supported. UIKit adoption is separate from
this server contract; a client does not gain support merely by decoding a field.

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

This descriptor does not add a JSON session-allocation endpoint or an endpoint URL.
Native host support must supply an explicit entry adapter; until then it must
reject this navigation kind. The earlier `workspace-subject` descriptor described
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

Cold HTTP rendering exceeded the old 20/30-second test deadlines. A diagnostic
run measured 38.06 seconds for the first ported render and 0.848 seconds for the
next; an unmodified-main baseline measured 12.549 and 0.132 seconds. These are
local observations, not controlled benchmarks. The browser gate permits 120
seconds only for its first read. The egui client allows 120 seconds for render
requests, retaining its 20-second save/status deadline and exact-retry behavior.
Cold-start cost and the observed warm-render overhead remain performance work.
