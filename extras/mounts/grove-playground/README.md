# Visual Grove playground

Run from Reaver with the accompanying Mash checkout (including the picker lifetime API):

```sh
pnpm --dir /path/to/mash/packages/shrine-components run build:js
GOO_PATCH_MASH_ROOT=/path/to/mash nix develop .#eden --command python3 x/eden --mount grove-playground --port 8114
```

Open `/grove-playground`. The canvas fills the workspace. **Add / browse** opens
the component library and outline. **Properties**, **Preview**, and **Source**
switch the right-hand panel; **Publish ↗** opens the explicit publication form.
Panels retain their native inputs when closed. Escape dismisses the library and
inspector when focus is outside an input. The initial graph contains a role, sample record,
view, and `show` component. Its slot definition is editable in the library. Select a card (or its outline button) to populate
**Save properties**. Palette buttons prepare **Create node**; submitting that
ordinary Goo action creates the node. Connect a relationship port to a node's
`ref` port, using dragging or click-click. The connection form provides the same
operation without dragging. Relationship buttons populate disconnect, child-order,
and sample-field-value forms. Child indices are zero based. Disconnect references
before deleting a node. View collapse hides its component subtree without deleting
it. `opt` uses its value property for rank 1 or 2.

**Add / browse → Show card kinds** provides a checkbox and count for each
category—role, sample, and **View / pane**—plus **Show all** / **Hide all**.
Slots are definitions only: they have no canvas cards, wires, or connectors and do
not participate in arrangement, routing, or Fit bounds. Create and edit them in
**Add / browse**, and edit their references in **Connections**. Show all never
adds slots to the graph.
All Goo constructors belong to View / pane; they remain individual choices in the
creation palette, but are not separate card categories. Hidden cards and their incident wires are
removed from the server projection and compatibility suggestions; they remain in
the draft and generated source. Showing a kind restores its stable identities and
saved positions. Hiding View / pane hides view declarations and all Goo components together.
View collapse still controls the subtree of one particular view. Preferences survive browser reload within the running namespace and
apply to newly created cards of that kind. Keyboard users can Tab to a checkbox
and press Space. Filtering a selected card closes its inspector without submitting
or discarding buffered native input.


**Arrange** animates a force-directed layout of the currently visible cards, then
saves all positions in one ordinary Goo move action. Use **Fit** to frame the
result in the current pane. **Cancel** or Escape restores
the saved positions before submission. Typing or interacting with the canvas also
cancels the calculation; a newer server projection invalidates it. Hidden cards keep
their saved positions. Arranging does not change generated source or recompile the
preview. With reduced motion enabled it calculates without intermediate animation.

The command loads the pinned `d3-force@3.0.0` ESM bundle from esm.sh on demand.
If it cannot load, the editor remains usable and nothing is saved. Simulation is
bounded to 180 ticks / five seconds, followed by rectangle clearance using supplied
card sizes. This improves spacing; it does not minimize every wire crossing. After the saved
placement arrives, obstacle-avoiding edge routing runs automatically.

Fallback connections use one cubic Bézier with 80-unit handles along the source and target
port normals. The server centers each 96×24 relation-label box at `B(0.5)`; with
these equal opposing handles that equals the endpoint midpoint. Signed control
points are retained at canvas boundaries. Goo's existing cubic rendering, hit
geometry, and endpoint-handle deformation are reused. Label positions settle with
the accepted server projection. Fallback curves do not avoid other cards.

After a graph or placement change, a module worker loads pinned
[`libavoid-js@0.5.0-beta.5`](https://github.com/Aksem/libavoid-js) (LGPL-2.1-or-later)
ESM and WASM assets from jsDelivr. It proposes orthogonal paths around supplied
card rectangles with 12-unit guide clearance. Endpoints stay at the exact Goo port
anchors; shared endpoint nudging is disabled. Interior routing nudges use eight
units. **Route edges** retries a failed calculation; **Cancel routing** or Escape
cancels before submission. Interaction, composition, a newer graph, or starting
Arrange cancels unsent work. Download/calculation has a 20-second timeout.

The existing bound **Save routing** Goo action validates the complete connection
population, topology/lifetimes, current routing basis, coordinates, endpoint
directions, and obstacle clearance. It fits SVG cubic splines on the server: a single broad Bézier where clear,
otherwise an interpolating spline through the obstacle guide with shared
tangent bisectors, capped by local spacing to prevent loops. Conservative de Casteljau subdivision checks the actual curves against
card rectangles and reduces tangent length when necessary. All paths use M/C
commands; very tight corridors can approach straight runs. Labels follow the
curve midpoints, preferring positions clear of cards. Only the derived `board.scene` is
saved; source, semantic revision, preview and publication are unchanged. Reload
restores these routes without recalculating them. Later semantic, placement, or
visibility edits regenerate fallback curves and request fresh routing.

Routing is bounded to 128 cards, 512 wires, 128 points per wire and 8192 total
points, using supplied geometry without DOM measurement. Failure retains usable
fallback curves. This routes around cards; it does not guarantee zero wire
crossings or globally collision-free labels. Overlapping cards can make a valid
route impossible; Arrange can separate them.

Implementation lives in the playground mount, worker and geometry adapter. The
only shared Goo action change exposes the captured invocation ID on an ordinary
bound button (`data-goo-invocation`) for exact receipt correlation. Mash’s existing
scene painter and cubic hit geometry are reused unchanged by this routing feature.

Every accepted semantic edit compiles generated Grove and replaces the isolated
preview. Movement, collapse, and card-kind visibility do not recompile. Invalid drafts remain editable;
the last successful preview is retained. **Publish revision** explicitly installs
the currently compiled draft in the separate `published` instance. Source export
is read-only; it does not modify checkout files. Text is the initial role-field
codec. The preview sample selector switches between compiled sample records. Whole-source import, action authoring, and arbitrary Foil code are excluded.

To extend the example, create a `row`, disconnect the view's existing `child`
relationship, connect the view's `child` to the row's `ref`, and connect the row's
`child` to the existing `show`. Add a `text` component, set its value, and connect
it as another row child. Select either relationship and use **Reorder child** to
change its index. Incomplete intermediate drafts can report diagnostics while
the previous working preview remains visible.

| Record/component | Properties and relationships |
| --- | --- |
| `slot` | Name becomes the Grove slot name. |
| `role` | `field` connections declare text fields. |
| `sample` | `on` selects its role; value supplies field defaults. Optional `field` connections have values editable with **Save sample field**. |
| `view` | `on` selects its receiver role; `for` selects a declared presentation slot. The slot property supplies a path when there is no `for` connection. |
| `group`, `row`, `col`, `or` | Ordered `child` connections; optional presentation slot property. |
| `opt` | Ordered `child` connections; value is rank `1` or `2`. |
| `show`, `text`, `path` | Optional receiver `field` binding and presentation slot. `text` can use a literal value; unbound `path` uses the receiver itself. |
| `present` | `view` selects another view for the same receiver role. |

Click **Inspect a presentation** inside the live preview, then click the compiled
view to inspect its real recipe, subject, and resolved layout.

## Integration

The document is a `playground/draft` pail: stable declaration/component IDs,
identity-bearing relationships, a separate placement row, collapsed view IDs, and
hidden card kinds.
The scene and native card bodies are server-derived projections. The browser never
measures cards/ports/labels or validates program relationships. The optional Arrange
command computes placement proposals from server-supplied geometry; the server
validates and stores accepted positions and prepares the resulting routes.
The 128-node authoring bound is a playground policy, not a patch-component limit.

`goo_patch/population` adds typed passive native occurrences to existing `patch`
preparation. `patch_operation` retains statically published Goo actions and their
captured receiver/evidence. Dynamic content cannot inject new domain controls.
`/goo/patch-query` resolves installed query providers by declaration and target;
compatibility is advisory, and creation choices are revalidated by the bound action.
Reconnect queries include the replaced relationship and endpoint, so the server
checks cardinality after removing that relationship rather than rejecting its own
existing endpoint. This is an additive optional field on the patch query contract.

`grove_draft` registers host-owned compilation destinations. Eden's supervisor
adapter reuses the mounted compiler substrate, Grove backend, publication artifacts,
and installer. The draft, preview definitions/instance, and published definitions/
instance have separate namespace identities. Compilation works on a candidate
namespace; failure retains the previous installation and records a diagnostic.
Declaration markers and component source order associate compiler diagnostics with authoring identities.
The draft adapter checks published recipe lowering results before committing: ordinary
Grove publications may intentionally retain diagnostic views, but a successful
playground preview must have executable recipes.

Drafts survive browser reload within the running namespace. The disposable Eden
launcher does not promise application persistence across server restarts. After
changing the playground implementation itself, restart the development server:
mounted HTTP closures retain the compiler/type versions from activation. This is
separate from editing and compiling playground drafts, which works live.

Card-kind filtering changes only the playground: `model.foil` stores and validates
the preference, `main.grove` exposes an ordinary bound Goo action, `scene.foil`
filters occurrences and wires, and `mount.foil` exposes state and filters query
advice. `app.js` and `style.css` provide the checkbox controls and synchronize the
outline. No shared Goo renderer, patch contract, compiler bridge, or Mash component
changes are required for this feature.

The arrangement integration adds `beginNodeMovePreview` to the shared Mash patch
surface: one captured move binding, transient geometry, cancellation, and a single
submission through existing receipts. Force calculation and the Arrange/Cancel UI
live in this playground's `layout.js` and `app.js`. The only server change for this
feature serves the new module; existing batch movement admission, storage, and
routing are reused unchanged.

## Checks

```sh
WISP=/path/to/wisp python3 extras/x/check --mount grove-playground
node --test extras/mounts/explorer/tests/*.test.cjs
node extras/mounts/grove-playground/check-browser.mjs http://127.0.0.1:8114 /path/to/mash /tmp/grove-playground-browser
node extras/mounts/grove-playground/check-visibility-browser.mjs http://127.0.0.1:8114 /path/to/mash /tmp/grove-visibility-browser
node extras/mounts/grove-playground/check-layout-browser.mjs http://127.0.0.1:8114 /path/to/mash /tmp/grove-layout-browser
curl --fail --location https://esm.sh/d3-force@3.0.0/es2022/d3-force.bundle.mjs --output /tmp/d3-force-3.0.0.bundle.mjs
D3_FORCE_MODULE=/tmp/d3-force-3.0.0.bundle.mjs node --test extras/mounts/grove-playground/test-layout.mjs
```

In the Mash checkout, run the fixture and type checks with:

```sh
BROWSERS=chromium,firefox,webkit pnpm --dir packages/shrine-components exec vitest run src/patch/reconcile.test.ts src/patch/patch.test.ts
pnpm --dir packages/shrine-components run check:types
pnpm --dir packages/shrine-components run build:js
```

The browser gate uses the real namespace, compiler, and Goo actions. Run the Mash
patch fixture harness tests as well for reordered projections, receipts, and
encounter retirement. Automated composition events test lifecycle preservation;
they do not establish manual operating-system IME or screen-reader coverage.

The compiler bridge runs inside Eden's namespace supervisor. Its compile/install
transaction is serialized with edits, so an older result cannot overtake a newer
committed revision. Publication checks the selected draft revision, and uses the
existing artifact and installation case checks. It never installs into an unrelated
application target. Global catalogue evidence still guards actions; the specific
recipe publication now controls editable presentation lifetime, so compiling a
preview does not retire an unchanged editor.

Current scope: the existing Goo text profile supports ASCII text; graph captions
substitute unsupported bytes with `?`. Draft values and exported source remain
unchanged. Richer font/shaping coverage remains upstream work. There is no source
import, arbitrary Foil, action authoring, manual IME certification, or promise that
the disposable launcher restores its namespace after a server restart.

## Verification record — 2026-10-05

The real editing-and-publication gate passed against the local Eden server, using
the matching local Mash build. No domain responses were mocked or intercepted.

| Browser engine (headless) | Version | Live workflow checks |
| --- | --- | --- |
| firefox | 153.0 | 15 passed |
| webkit | 26.5 | 15 passed |
| chromium | 151.0.7922.34 | 15 passed |

Each engine exercised real compilation/installation, automatic preview updates,
presentation inspection, duplicate submissions, failed-build preservation and
component diagnostics, identity-preserving renames, explicit publication and
stale-publication rejection, server compatibility and stale-query rejection,
creation/configuration/order/collapse, reconnection, dirty input/caret and synthetic
composition preservation, source export, browser reload, and atomic creation-picker
submission. Instrumentation observed no node/port/label geometry reads; a source
audit also confirmed that patch measurements are confined to the root viewport.

Additional passing checks:

- 41 native playground checks, including a program built from an empty draft and
  compiled, the full constructor palette, validation, and deleted/recreated IDs.
- 649 shared native checks (135 web and 514 explorer), plus mount-contract compilation.
- 81 explorer JavaScript tests.
- 132 Mash patch fixture tests across Chromium, Firefox, and WebKit, covering
  reordered projections/receipts, retirement, stale compatibility, and composition.
- Mash TypeScript checks and JavaScript build; repository whitespace checks.

These results include synthetic composition events, not manual operating-system
IME coverage. They do not certify screen readers or persistence across an Eden
launcher restart. The Reaver mount currently requires the accompanying local Mash
changes; dependency pins were not advanced by this implementation.

## Visual refresh — 2026-10-06

The workspace uses a dark canvas, compact navigation, readable server-authored
cards, and on-demand library/inspector/output panels. Card selection uses the
existing Goo selection binding. The embedded preview retains the compiled view
and presentation inspection while hiding the namespace browser scaffolding.
Panel switching does not replace native form controls. Server geometry remains
authoritative; the refresh adds no card, port, or label measurement.

Verified with 42 native playground checks, 649 shared native checks, mount-contract
compilation, 81 shared JavaScript tests, and 135 patch fixture checks across
Chromium, Firefox, and WebKit. Type checking and the Mash JavaScript build pass.
Desktop and narrow layouts were also checked in the in-app browser, including
panel switching with unsaved input and absence of horizontal page overflow.
Composition coverage remains synthetic, not manual OS IME coverage.

The refreshed UI passed all 15 live workflow checks in Chromium 151.0.7922.34,
including card-to-form prefill, compiled preview inspection, publication, stale
publication rejection, relationship editing, input preservation, export, and reload.
That run used checkout assets over the real Eden mount; no domain responses were
mocked. Firefox and WebKit were rerun for the patch fixtures, not the complete
live workflow in this visual-refresh pass. Hidden authoring and output panels
retain their pane allocation so Goo can prepare layouts and keep bindings current.
The final mounted build was also exercised in the in-app browser: select a card,
edit its sample text with preview closed, reopen the correctly sized compiled
preview, and explicitly publish revision 2. Desktop and compact layouts were
visually checked after that final sizing change.

## Card visibility verification — 2026-10-06

59 playground native checks (17 new), 649 shared native checks, mount contracts,
and six profile Python checks pass. The focused real-server visibility gate passes
seven checks each in Chromium 151.0.7922.34, Firefox 153.0, and WebKit 26.5.
It covers keyboard toggles, actual scene/wire/hit-region removal, selected-card
inspection cleanup, buffered input and caret preservation, unchanged source and
preview/publication revisions, filtered compatibility advice, reload restoration,
and bulk hide/show with identical identities and positions. No card/port/label
measurements or page errors were observed. Composition events are synthetic:
Goo defers the projection until composition ends; this is not manual OS IME coverage.
The full editing/publication gate and shared patch fixture harness were not rerun
for this playground-only feature.

The subsequent category correction groups all Goo constructors and view declarations
under **View / pane**, including card badges, colors, outline labels, and visibility.
The server supplies category metadata separately from the constructor palette.
62 playground native checks pass, together with the 649 shared checks and mount
contracts. The updated eight-check visibility browser gate passes in Chromium
151.0.7922.34, including grouped hide/restore with the full creation palette retained.
Firefox and WebKit were not rerun for this category correction.

The full-page playground disables horizontal browser overscroll navigation with
`overscroll-behavior-x: none` on its root `html` element, scoped to
`body.playground-app`. Vertical overscroll remains `auto`. Canvas-owned wheel
cancellation, native editor scrolling, and Ctrl/Command-wheel behavior are unchanged.
Verified the applied root policy and automated Chrome horizontal scrolling over
canvas background and a port control; physical macOS trackpad gestures were not
manually tested. This correction changes only playground CSS.

## Animated arrangement verification — 2026-10-06

The focused real-server layout gate passes all six checks in Chromium
151.0.7922.34, Firefox 153.0, and WebKit 26.5 (headless). It exercises the actual
CDN D3 engine and ordinary Goo batch move admission: animation, Cancel, keyboard
activation, one submission, nonoverlapping final cards, unsaved input/caret
preservation, unchanged semantic/preview/publication revisions, duplicate
submission, reload restoration, cancellation by a newer visibility projection,
reduced motion, and retention of hidden-card positions. No forbidden geometry
reads or page errors were observed. Only the optional CDN request is intercepted
to exercise failure and a delayed download; domain responses are not mocked.

Six solver tests pass, including 128 initially overlapping variable-size cards,
deterministic results, and immutable scene inputs. The shared patch fixture gate
passes 153 tests across the same three engines, including move-preview rejection,
unknown outcomes, both receipt/projection orders, invalid batches, deleted/recreated
lifetimes, retirement, Escape, and synthetic composition. Type checking, the Mash
JavaScript build, and Eden mount compilation pass. The complete editing/publication
gate and native domain suites were not rerun for this placement feature. Composition
coverage is synthetic; manual operating-system IME coverage is not claimed.

## Cubic connections verification — 2026-10-06

70 playground native checks pass, including cubic commands, endpoint alignment,
80-unit outward handles, signed boundary control points, and centered label boxes.
The 649 dependency checks, mount contracts, and six profile Python checks also pass.
The real layout browser gate passes seven checks each in Chromium 151.0.7922.34,
Firefox 153.0, and WebKit 26.5. It now validates server curve geometry and actual
SVG cubic output before and after arrangement and reload, alongside the existing
receipt, cancellation, input preservation, filtering, and reduced-motion cases.
No forbidden node/port/label measurements or browser errors were observed.
This change uses the existing shared Goo cubic implementation; the shared fixture
suite was not rerun. No manual OS IME coverage is claimed.


Routing checks (actual pinned WASM package installed separately):

```sh
LIBAVOID_MODULE=/path/to/libavoid-js/dist/index-node.mjs \
LIBAVOID_WASM=/path/to/libavoid-js/dist/libavoid.wasm \
  node --test extras/mounts/grove-playground/test-routing.mjs
node extras/mounts/grove-playground/check-routing-browser.mjs \
  http://127.0.0.1:8122 /path/to/mash /tmp/grove-routing-browser
```

## Obstacle-routing verification — 2026-10-06

85 native playground checks pass (15 new routing checks), including server
admission, rounded path generation, stable topology, stale basis rejection,
missing populations, endpoint changes, diagonals, card crossings, wrong port
directions, malformed/out-of-range coordinates, duplicate vertices and basis
invalidation by movement/visibility. The 649 dependency checks, mount contracts
and six profile Python checks pass. Six geometry adapter tests use the actual
pinned libavoid WASM, including reversed connections, shared sockets, obstacle
detours, signed coordinates, immutable inputs, determinism and cleanup. All 18
shared Goo action tests pass, including invocation correlation.

The existing seven-check arrangement regression gate passes in Chromium with
routing enabled. The full editing/publication gate and shared patch fixture
suite were not rerun for this routing feature. Composition coverage is synthetic;
manual operating-system IME coverage is not claimed. Browser reload restoration
is tested within the running Eden namespace; launcher-restart persistence is not
claimed.

The focused eight-check routing browser gate passes in Chromium 151.0.7922.34,
Firefox 153.0 and WebKit 26.5, using the final mounted build and real CDN WASM.
It covers rounded path clearance and exact endpoints; keyboard Arrange followed
by one route save; unchanged source/preview/publication; dirty input and caret
preservation; duplicate receipt and reload restoration; stale route rejection;
hide/show projections; cancellation during a worker download; CDN failure and
keyboard retry after synthetic composition; and absence of node/port/label DOM
measurements or browser errors. Only optional CDN requests are intercepted for
failure/cancellation tests; Goo admission and scene responses are real.

## Flowing spline presentation — 2026-10-06

The short corner fillets have been replaced with full cubic splines. A clear
source/target pair gets one broad Bézier. Obstructed pairs use interpolating
cubics with shared tangent bisectors and handles bounded by adjacent knot spacing;
this prevents loops where short port stubs meet long guide segments. Conservative
subdivision checks the actual curves, reducing tangent lengths when necessary.
Labels follow curve midpoints. Fit includes the complete control hull. The route
revision suffix is `:spline-v2`; the client can upgrade saved `:avoid-v1` guides.
No shared Goo renderer or Mash changes are needed for this presentation change.

90 native playground checks and seven actual-WASM adapter tests pass. The complete
eight-check routing workflow passed in Chromium, Firefox and WebKit before the
final handle-spacing and Fit refinement. The final geometry gate additionally
checks exact ports, continuous tangents, monotonic controls on guide legs (no
local loops), actual curve/card clearance, input preservation, saved geometry
through reload, full Fit bounds and no node/port/label DOM measurement. Run it with:

```sh
GEOMETRY_ONLY=1 node extras/mounts/grove-playground/check-routing-browser.mjs \
  http://127.0.0.1:8128 /path/to/mash /tmp/grove-spline-browser
```

The final three-check geometry gate passes in Chromium 151.0.7922.34,
Firefox 153.0 and WebKit 26.5 against the mounted 8128 build, including the
locally bounded tangent and Fit refinements. Visual review confirms broad curves
without the earlier short-stub curls. No manual OS IME coverage is claimed.

## Whole-cable fitting — 2026-10-06

The previous interpolating spline preserved too much of the orthogonal router's
shape. The server now tries a single clear cubic, then a two-span sweep on the
side selected by the obstacle guide. The sweep crest can move outside the guide
envelope and toward either endpoint, so rectangular detours no longer dictate
the curve's knots. Each port
handle is limited independently by the next card in its departure direction.
All candidates still pass conservative subdivision against actual card boxes.
Subdivision uses directed integer intervals, preserving exact port endpoints
without introducing false intersections through a blanket rounding allowance.

For more complicated obstructions, a bounded dynamic program selects the fewest
clear cubic spans through a subset of guide knots with shared tangent handles.
Guides over 32 points use the linear fitter; tight corridors retain the existing
safe fallback. This is a bounded geometric heuristic, not a global minimum-bend
or crossing-free graph router. Different wires may still cross one another.

Saved scenes use `:spline-v3`. The client recognizes prior `:avoid-v1` and
`:spline-v2` revisions and submits their replacement through the same bound Goo
routing action and receipt path. This change is in playground server geometry
and route-version handling; the shared Goo/Mash renderer is unchanged. No node,
port, or label DOM measurement is introduced.

The native suite now includes reduced span counts, a crest outside the guide
envelope, exact continuous tangents, whole-curve/card clearance, independent
port reach, redundant-knot removal, a blocked-sweep rejection, and short straight
connections that cannot double back. 96 native playground checks and seven
actual-WASM adapter checks pass.

Run the full browser routing workflow with:

```sh
node extras/mounts/grove-playground/check-routing-browser.mjs \
  http://127.0.0.1:8131 /path/to/mash /tmp/grove-cables-browser
```

The complete eight-check routing workflow passes on the mounted 8131 build in
Chromium 151.0.7922.34, Firefox 153.0, and WebKit 26.5. Checks cover exact ports,
continuous tangents, sampled card clearance and self-crossing rejection, full
Fit bounds, fewer curve spans, keyboard Arrange, one routing save, unchanged
semantics, input/caret preservation, duplicate receipts, reload restoration,
stale rejection, visibility changes, cancellation, CDN failure/retry, and no
node/port/label DOM measurements or browser errors. The Chromium arrangement
reduces 25 guide legs to 12 cubic spans. Composition coverage is synthetic; no
manual operating-system IME coverage is claimed. The broader publication flow
and shared Mash fixture suite were not rerun for this geometry-only change.

## Card dragging

Drag the card body to move it; a click still selects it. Ports, the explicit Move
control, and keyboard move buttons keep their existing actions. Escape cancels
an unsent drag. A completed drag uses the existing Goo `move-nodes` action;
accepted placement changes are saved separately from program meaning and trigger
edge rerouting.

The shared Mash gesture layer recognizes node selection chrome as a drag starter;
the playground only supplies the grab/grabbing cursors. When developing against
`GOO_PATCH_MASH_ROOT`, rebuild Mash with `pnpm --filter @mash/shrine run build:js`
before starting Eden: the mount bundles the built package JavaScript.

The mounted integration check uses real mouse input and server actions:

```sh
node extras/mounts/grove-playground/check-drag-browser.mjs \
  http://127.0.0.1:8132 /path/to/mash /tmp/grove-drag-browser
```

Verified with 54 shared patch fixture checks per engine (162 total), including
reordered receipts, native input ownership and Escape with external keyboard
focus. The four mounted drag checks pass in Chromium 151.0.7922.34, Firefox
153.0 and WebKit 26.5: real card-body click/drag, one saved move and rerouting,
input/caret and semantic revision preservation, Escape cancellation, reload
restoration, keyboard movement, and no node/port/label geometry measurements.
Type checking and the shared component JavaScript build pass. This run used
mouse input; manual touch and operating-system IME testing are not claimed.

## Slot-free canvas verification — 2026-10-06

Slots remain typed draft declarations and ordinary library/form targets. The
server projection excludes their cards, incident wires, slot-only ports, and
positions from canvas bounds. Compatibility candidates use the same projected
ports. Roles, samples, and View / pane are the three canvas visibility categories;
Show all never restores slots. Arrangement and routing consume this smaller scene.
No shared Goo renderer or gesture implementation changed.

104 native playground checks pass, including real Grove compilation, slot
exclusion after creation/show-all, compatibility ports, Fit bounds, and routing
validation using a view-to-role fixture. Mount contracts and 649 dependency checks
also pass. The updated nine-check visibility gate passes against the real Eden
server in Chromium 151.0.7922.34, Firefox 153.0, and WebKit 26.5. It covers the
retained slot library/palette, actual scene and hit-region filtering, keyboard
controls, unchanged compiler/source state, reload, and dirty input/caret
preservation. The harness waits for routing and admitted form bindings before
interaction. Composition coverage is synthetic; manual OS IME was not run.

## Signed card placement — 2026-10-06

Cards can cross either world-coordinate zero axis. Move admission, subsequent
base-origin checks, creation-picker placement, fallback curves, labels, Fit
bounds, and routing obstacles all retain the signed position. Placement uses
explicit `bx`/`by` fields with the routing system's 100000 offset; wire coordinates
remain ordinary signed JSON numbers. Seed and automatic placements convert at
the boundary. Positions are bounded to [-100000, 100000] and rounded using the
existing exact decimal rounding. Old running demo namespaces are left intact;
this schema is installed in the rebuilt demo.

Ordinary edit actions now forward the model's actual rejection message through
the existing Goo receipt/error path instead of replacing it with “Invalid or
stale playground edit.” No shared Mash component changes are needed.

124 native checks and eight actual libavoid WASM checks pass. The drag browser
gate has additional cases for crossing both axes, moving again from a negative
base, returning to positive coordinates, reload, unchanged compilation state,
Fit bounds, and the actual stale-move rejection message. Those new browser cases
have not yet been run: browser access is awaiting explicit permission after an
automatic approval rejection. Existing browser results above predate this fix.
