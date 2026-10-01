# Goo implementation

Backend, IR, and runtime implementation notes for Goo. For constructors,
source syntax, and author-visible behavior, see the [Goo reference](GOO.md).

## Declaration boundary

Grove parses distinct `@view` and `@pane` tags. The shared `goo/view` IR retains
an `is_pane` discriminator through publication. Both currently share the published
presentation slot and catalog storage; this is not permission to interchange them.
Compiler view selection and runtime slot matching exclude panes. Workspace
endpoints require the pane discriminator. Explorer previews carry declaration-kind
metadata, and browser view selection also excludes panes.

Lowering checks every node against its own declaration kind before expansion.
Views reject keyed/session constructors and selection capture operands
nested in argument expressions. A pane presenting a view does not grant pane
capabilities to that view. Object-local actions, creation, and `become` remain
valid in views.

## Pipeline and IR

The pipeline is Grove parsing and reference resolution → typed Goo view IR →
runtime binding to native source IR → normalization → visibility → adjacency →
measurement/layout → prepared HTML. Pane ownership and local interactions use
the shared session/controller around native fragments.

`show` resolves a field's declared type, including inherited and optional role
fields, and replaces itself with a registered native constructor. The default
registry maps text to `text`, path to `link`, time to `time`, and duration to
`duration`. Text literals lower to `text`; absolute path literals lower to `link`.
Renderers are registered by canonical type identity, not by the final segment
of a type name.

`present` resolves the unique declared view for the receiver role and view slot,
substitutes its receiver binding, and attaches the expanded children in the IR.
Missing views, competing matches, and cycles produce diagnostics. Nested receiver
evaluation is not implemented by the bridge even where the frontend can describe
the expression's type. The explorer's synthetic reflection view is a separate
runtime facility, not a compile-time `present` fallback.

## Native adaptation and rendering

The Grove bridge maps bound values and constructors into native source IR.
It wraps multiple top-level native nodes in a column. `group` leaves arrangement
to semantic normalization; explicit flow constructors retain their direction.
Visibility prunes optional content before adjacency and layout.

The native default visibility budget is required-only for `/sys/slots/scar` and
`/sys/slots/label`, compact for `/sys/slots/summary`, and full otherwise. The bridge
adapts the corresponding singular scar/label/summary view paths to those contexts.
Presentation-slot aliases are listed in the language reference because they
affect authored layouts; they do not rename data slots.

The native measurement path is ASCII-oriented. An accepted type or expression
does not guarantee that its text can be measured. `icon` and `divider` are
recognized by the Grove frontend but lack native bridge implementations.

Native configuration is decoded separately from control binding. The latter
expects an interactive `action` or bound `input` to have its ordinary first
argument, so a leading native config record is not supported for those controls.
The Grove bridge does not apply `[slot]` and `[optional]` config attributes;
standalone reading does. Unknown keys are rejected by the standalone reader but
are not consistently diagnosed through the Grove path.

## Invocation and creation

Declared actions transform the current object through the Grove action adapter.
`.poke` merges supplied slots and validates the result against the view's role
contract. Inputs supply text; providers and captures are resolved through the
runtime rather than a general expression evaluator.

Domain invocations validate publication/receiver freshness and authority.
Retries with the same invocation identity and payload reuse their receipt.
A new invocation targeting an occupied creation destination fails.

Creation validates the destination and role contract, then performs an atomic
create-only mutation. It produces a normal record with supplied slots and its
role contract, not a Grove installation. The presenting object remains the
invocation anchor. Creation input rendering uses literal `.input(...)` defaults
rather than reading the presenting object's slots.

Capture validates source membership and subject lifetime evidence on the server.
Multiple captures from one owner share its snapshot; there is no atomic
cross-owner capture facility. Ordinary data edits preserve member identity;
removal/recreation changes its lifetime.

## Workspace integration

The shared pane session maintains ownership, accepted selections, encounters,
and departure guards around native presentations. State is private to the page,
not stored in a UI namespace. Source reads are bounded to 64 direct physical
child keys of an existing namespace record.

Workspace navigation uses the current endpoint and its `path` query parameter.
Host operation keys resolve through configured bindings; the current operation
adapter implements mount rescan/publication. Its controller requests a scan,
waits for that exact scan's publication, detects supersession, and exposes
diagnostics. Successful publication reloads the page; failure retains it.
This does not replace or reset an installed Grove instance.

## Standalone reader and wire codecs

The standalone literal reader and Grove-embedded Goo share native layout
machinery but have different source languages. Their supported syntax is listed
in the language reference.

Native JSON IR codecs are a separate programmatic interface, not another Goo
source spelling. The source numeric reader accepts Haskell-style numeric
spellings, including hexadecimal, octal, and leading zeros; JSON wire numbers
use the separate strict JSON grammar.

## Publication, diagnostics, and inspection

The frontend retains source spans on views/nodes. Unknown fields, missing or
competing type renderers, missing/competing presentations, cycles, and malformed
local controls produce diagnostics. Published views retain compiled artifacts or
located diagnostics. Some failures only appear during binding or rendering;
compiling a view does not imply that every native payload will render.

The explorer's catalog and matches use cached/indexed overlays. The object page
shows matching declared views and the synthetic reflection view. Debugger
inspection can expose published role contracts, view IR, and declaration provenance.

## Source map

| Responsibility | Source |
| --- | --- |
| Embedded parser and Goo IR | [goo.foil](../foil/goo.foil) |
| Type resolution, constructor validation, lowering | [grove_views.foil](../foil/grove_views.foil) |
| Invocation, creation, providers, source evidence | [goo_runtime.foil](../foil/goo_runtime.foil) |
| Runtime values and native constructor mapping | [goo_bridge.foil](../../extras/mounts/explorer/goo_bridge.foil) |
| Pane serialization and initial HTML | [goo_panes.foil](../../extras/mounts/explorer/goo_panes.foil) |
| Local identity, selection, encounters, captures | [goo-session.js](../../extras/mounts/explorer/goo-session.js) |
| Browser gestures and actions | [goo-panes.js](../../extras/mounts/explorer/goo-panes.js), [goo-actions.js](../../extras/mounts/explorer/goo-actions.js) |
| Workspace host integration | [goo_workspace.foil](../../extras/mounts/explorer/goo_workspace.foil) |
| Standalone literal syntax | [read.foil](../../extras/mounts/goo/read.foil) |
| Native config and JSON codecs | [codecs.foil](../../extras/mounts/goo/codecs.foil) |
| Native adjacency and layout | [rules.foil](../../extras/mounts/goo/rules.foil), [layout.foil](../../extras/mounts/goo/layout.foil) |
| Native HTML primitives | [html.foil](../../extras/mounts/goo/html.foil) |

For lifecycle design details see [Panes](../../extras/mounts/explorer/PANES.md).
