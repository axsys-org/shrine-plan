# Goo views

A Grove view selects a role with `#on` and a presentation slot with `#for`.
The identifier before `=>` binds the receiver; it does not name its type.
`! goo` is optional on views. Goo uses the existing Rex parser, including
multiline braces, calls, named arguments, and quoted paths.

```grove
#import text=lib/grove/types/text
#import req=sys/req

card =
  @role
  req: text

label =
  @view
  #on ; %/card
  #for ; /sys/slot/label
  ! goo
  c => {
    show(c.req, '/sys/slot/title)
  }

front =
  @view
  #on ; %/card
  #for ; /sys/slot/req
  item => {
    present(item, '/sys/slot/label)
    action("Show", become = '/sys/slot/res)
  }
```

The frontend produces the equivalent of:

```goo
item => {
  present(item, '/sys/slot/label) {
    text(item.req, '/sys/slot/title)
  }
  action("Show", become = '/sys/slot/res)
}
```

## Frontend API

Import `grove_views` and call:

```foil
< document (grove/parse source)
| grove_views/compile root document lookup imported_roles renderers "front"
```

The result is `either[grove/error goo/view]`. The inputs are:

- `root`: canonical namespace path of the Grove document.
- `lookup`: the existing Grove namespace lookup, used when resolving imported
  publication locations.
- `imported_roles`: `row[goo/role]`, with canonical role identities and typed
  field descriptions for externally supplied roles. Use `[]` for local roles.
- `renderers`: `row[goo/renderer]`, mapping canonical type paths to native
  constructor names. `goo/html_types codec_root` supplies `text → text`,
  `path → link`, `time → time`, and `duration → duration` for the value codecs
  under that canonical root. This is an explicit type registry, not a match
  on the last segment of a type name.
- The last argument names the entry view in this document.

For the example above, an uninstalled document can use root `['demo]`,
`lookup` returning `.none`, no imported roles, and
`goo/html_types ['lib 'grove 'types]`.

`grove_views/index` reads all view declarations without expanding them.
`goo/parse` reads an embedded Rex body independently of Grove name resolution.

## IR and lowering

`goo/view` records the declaration's source span, canonical name, role and
slot, receiver binding, and children. Each `goo/node` records its source span,
constructor name, argument expressions, and children. Argument expressions
are normalized Rex; styles and action/input expressions retain their values.

`show(value, style)` resolves a role field's declared type, including inherited
and optional fields, and replaces `show` with the registered native constructor.
String literals lower to `text`, and absolute path literals lower to `link`.
The style is checked as a path and retained as an argument. Optional field
presence and the `or` node remain runtime concerns.

`present(value, slot)` finds the unique view with that receiver role and slot,
recursively lowers it, substitutes its receiver binding, and attaches its nodes
as children of the original `present`. Substitution changes expression bindings,
not member names, namespace paths, strings, or named-argument keys.

The initial explicit vocabulary is `group`, `or`, `action`, `input`, `text`,
`link`, `number`, `time`, `duration`, `boolean`, `image`, `icon`, and `divider`.
Type renderer registrations can produce additional design-system constructors.
Goo does not execute action arguments, providers, or input expressions.

Only the requested entry view and its reachable presentations are lowered.
Missing views, competing views, presentation cycles, unknown fields, and missing
or competing native type renderers produce located errors. Reflection-based
fallback UI and competing-view precedence are deliberately deferred.

The Grove backend publishes each view as a `goo/published` record under the
publisher-owned `grove/view` slot. It includes the receiver fields and role
contract, plus either lowered IR or its diagnostic. A missing presentation
therefore does not prevent the other views in the document from publishing.
Malformed view declarations and invalid receiver roles still fail publication.

The explorer mount serves a small browser at `/views`. Navigate through the
namespace in the sidebar; the detail pane displays every published view whose
role contract admits the selected record. The initial catalog scans the local
publisher's namespace on each request. It has no indexing or pagination yet.

The browser binds the symbolic template into Goo v2's `goo/source` IR, then
uses its normalization, visibility, adjacency, measurement, layout, and prepared
HTML renderer. Actions and inputs remain disabled previews. See
[the integration and mismatch report](../../extras/mounts/explorer/GOO-V2.md)
for the exact constructor, slot, expression, and identity adaptations.

Run `x/eden --mount srs`, then open
`http://127.0.0.1:8130/views/0x11/app/srs/cards/demo` for the sample card.
