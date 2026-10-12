# Goo reference

This is the authoring reference for Goo: Grove views, presentation constructors,
actions, panes, and host controls, including current syntax limitations.

There are two source languages: **Grove-embedded Goo**, described first, and
**standalone literal Goo**, described at the end. Backend architecture, IR,
and runtime internals are covered in [Goo implementation](GOO-IMPLEMENTATION.md).

## Contents

- [Declaring a view and writing expressions](#declaring-a-view-and-writing-expressions)
- [Constructor index](#constructor-index)
- [Presentation and native layout](#presentation-and-native-layout)
- [Native configuration](#native-configuration)
- [Actions, inputs, and creation](#actions-inputs-and-creation)
- [Panes and local selection](#panes-and-local-selection)
- [Workspace navigation and operations](#workspace-navigation-and-operations)
- [Standalone literal Goo](#standalone-literal-goo)

## Declaring a view and writing expressions

```grove
#import text=lib/grove/types/text
#import req=sys/req

card =
  @role
  req: text

card_label =
  @view
  #on ; %/card
  #for ; /sys/slot/label
  ! goo
  card => {
    show(card.req, '/sys/slot/title)
  }
```

`#on` specifies the receiver role. `#for` specifies the view-selection slot.
`card =>` only binds a name to the receiver; it does not specify a type.
`! goo` is optional. A body can be a block of constructors, as above, or a single
constructor with a body: `card => group { ... }`.

### Views and panes

`@view` declares an object projection. It supports presentation, layout, and
object-local `input`/`action` controls, including `.poke`, declared actions, and
`make`. It does not own a selection, routing state, or keyed workspace controls.

`@pane` opts into those features. It uses the same `#on`, `#for`, and receiver
binding syntax:

```grove
workspace =
  @pane
  #on ; %/study
  #for ; /sys/slot/workspace
  study => {
    present(study, '/sys/slot/summary)
  }
```

Only `@pane` bodies may use `pane`, `selection`, `list`, `follow`, `split`,
`deck`, `pane_stack`, `navigate`, `operation`, and `operation_status`.
`.capture(...)` is also pane-only. Ordinary layout, object-local actions, and
`become` are available in both declaration kinds. `become` changes the current
object's presentation recipe; it does not require pane routing or keyed state.

A pane may contain nested panes and present views. A view cannot contain pane
features, even indirectly. `present` and list/follower slot selection resolve
only `@view` declarations; a pane is not a candidate. Workspace endpoints require
an `@pane` declaration. The explorer lists panes separately from view matching,
with their declaration kind shown beside the slot.

Both kinds currently require `#on` and `#for`. Each `@pane` declaration creates
its own local owner. Mount a child with `pane(%/child)`; inline pane bodies are
not supported. `present` still selects views, never panes.

### Calls and expressions

Calls use parentheses and comma-separated arguments. Named arguments use `=`.
Children follow the call in a curly block. A constructor with no arguments can
omit parentheses: `group { ... }`. Braces and calls can span lines; use explicit
braces for child blocks rather than expecting indentation alone to make a body.
The underlying reader is Rex, not JavaScript.

| Spelling | Meaning |
| --- | --- |
| `"Hello"` | Text literal. Double an embedded quote: `"Say ""hello"""`. |
| `card.req` | A field of the bound receiver, resolved against its declared role. |
| `'/sys/slot/title` | Absolute path literal. The leading apostrophe has **no closing apostrophe**. |
| `/sys/slot/title` | Bare absolute path also accepted in path positions, as in `#for` and `present`. Quoted paths are the consistent spelling in bodies. |
| `%/card`, `%/finish`, `%/grade/good` | Grove-relative declaration references, resolved during compilation. These are not arbitrary string interpolation. |
| `name = expression` | A named argument, such as `become = '/sys/slot/res`. |
| `{ '/sys/req = .input(card.req) }` | An action argument record, used by `myth`. |
| `{[grow]: 1, [maxIdeal]: 320}` | Native configuration record; a different syntax from `myth`. |
| `' A comment` | Rex comment line. |

The runtime expression language is deliberately small. Rendering supports text
literals, absolute path literals, and direct receiver fields. There is no general
JavaScript/Foil expression evaluator, arithmetic, interpolation, loop, or lambda
inside Goo. Nested field expressions such as `card.owner.name` are not supported
for rendering. Likewise, numeric,
boolean, and date data are normally supplied through typed receiver fields;
native constructor names do not introduce a new literal language for those values.
Grove data/seed syntax remains the responsibility of Grove and its value codecs.

Three kinds of path must be kept separate:

- A **data slot**, such as `/sys/req`, identifies a property on a record.
- A **view slot**, such as `/sys/slot/edit`, selects a presentation recipe.
- A **native presentation slot**, such as `/sys/slot/title`, gives a rendered
  node a semantic identity for styling and adjacency.

Local pane/selection keys also use path spelling, but are local identities,
not addresses of objects in the namespace.

## Constructor index

In the signatures below, `[...]` means an optional argument; it is not literal
Goo syntax. `value` is a renderable expression, `slot` a presentation path,
`key` a stable local literal, and `source` an absolute path or direct path-typed
receiver field. Details and restrictions follow the table. All keyed constructors and the
`split`/`pane_stack` containers require an `@pane` declaration.

| Constructor | Shape and purpose |
| --- | --- |
| `show` | `show(value, slot)` — choose a native constructor by declared type. |
| `present` | `present(receiver, view_slot)` — expand a matching declared view. |
| `or` | `or { ... }` — first child that produces a native node. |
| `group` | `group([slot]) { ... }` — semantic grouping; also carries action scope. |
| `row`, `flow` | `row([slot]) { ... }` — horizontal flow aliases. |
| `col`, `stack` | `col([slot]) { ... }` — vertical layout aliases. |
| `opt` | `opt([rank]) { ... }` — optional content, rank `1` or `2`. |
| `text` | `text(value[, slot])` — text. |
| `path` | `path(receiver_or_path[, slot])` — display the receiver’s namespace path or a typed path value. |
| `link` | `link(value[, slot])` — currently text formatting, **not a hyperlink**. |
| `number` | `number(value[, slot])` — scalar text formatting. |
| `time` | `time(value[, slot])` — temporal text formatting. |
| `duration` | `duration(value[, slot])` — duration text formatting. |
| `boolean` | `boolean(value[, slot])` — scalar text formatting. |
| `image` | `image(value[, slot])` — image URL. |
| `button` | `button(value[, slot])` — native visual button; no domain invocation by itself. |
| `input` | `input(data_slot[, slot])` — text input; see action binding below. |
| `code` | `code(value[, slot])` — code-styled text. |
| `avatar` | `avatar(value[, slot])` — reference avatar primitive. |
| `presence` | `presence(value[, slot])` — reference presence primitive. |
| `media` | `media(value[, slot])` — reference media primitive. |
| `bar` | `bar(value[, slot])` — reference progress primitive, with numeric config. |
| `action` | `action(label[, become=path][, argument=value, ...])` — invoke enclosing action and/or change recipe. |
| `pane` | `pane(declaration[, key=local_key][, ports={...}][, on=receiver])` — mount a declared pane. |
| `selection` | `selection(key, source=source[, initial=.member(path)]) { ... }` — lexical selection port. |
| `list`, `diagram_tree`, `list_tree` | `list(key, source=source, selection=key[, slot=view_slot][, browse=text])` — selectable namespace members. |
| `follow` | `follow(key, selection=key[, slot=view_slot])` — present the accepted selection. |
| `split` | `split { ... }` — side-by-side panes. |
| `deck` | `deck(key) { ... }` — local tabs over child panes. |
| `pane_stack` | `pane_stack { ... }` — overlapping panes in declaration order. |
| `navigate` | `navigate(key, source=source[, mode=text][, label=text])` — workspace navigation. |
| `operation` | `operation(key, operation=key[, label=text])` — invoke a host-bound operation. |
| `operation_status` | `operation_status(key, operation=key[, label=text])` — show that operation's status. |
| `icon`, `divider` | Reserved but **not currently renderable**. Using them produces a diagnostic. |

`show` and `present` take exactly two arguments and no authored child block.
`pane`, `list`, `follow`, `navigate`, `operation`, and `operation_status` have no child
block. Unknown constructors are rejected. Parser acceptance is not a promise
that every arbitrary named argument has runtime meaning.

## Presentation and native layout

### `show` and `present`

```goo
card => {
  present(card, '/sys/slot/label)
  show(card.res, '/sys/slot/content)
}
```

`show` displays a value according to its declared type, including inherited and
optional role fields. Text uses `text`, paths use `link`, times use `time`, and
durations use `duration`. Text and absolute path literals are also supported.

`present` displays the unique declared view for the receiver role and view slot.
Missing views, competing matches, and recursive presentation cycles are errors.
Use the current receiver; nested receiver expressions are not supported.

The explorer additionally offers a reflection view at `/sys/slot/synthetic` for
records. It is read-only and bounded, and can be requested by `follow`. It is
**not** an implicit fallback for a failed compile-time `present`.

### `path`

```goo
record => {
  or {
    show(record.lede, '/sys/slot/label)
    path(record, '/sys/slot/label)
  }
}
```

`path(record, slot)` displays the bound receiver's canonical namespace path.
The host supplies its displayed identity during SSR and live rendering; a
projection therefore shows its own path, even when actions resolve to a
different writable receiver. No synthetic data slot is added to the record.

`path(record.about, slot)` accepts a direct field declared with the path type;
`path('/sys/req, slot)` accepts a path literal. Current Grove compilation rejects
the root-only literal `'/` in an authored expression; a typed root path field
or the root receiver still displays `/`. Missing optional fields emit no
node, so they participate in `or` normally. Text values, foreign receivers and
child blocks are rejected. The presentation slot is optional and defaults to
body text. `path` does not take a configuration record.

This constructor formats a leaf through Goo's existing server text layout; it
adds no navigation or client measurement. Synthetic slot headings use the same
formatter. Non-ASCII or control bytes use visible `\xNN` escapes under the
current ASCII measurement contract, without changing the namespace identity.

### Missing values and `or`

```goo
or {
  show(card.req, '/sys/slot/title)
  show(card.about, '/sys/slot/title)
}
```

An absent optional field contributes no native node. `or` picks the first child
that contributes a node. This is presence-based selection, not boolean truthiness:
an empty text value still makes a text node. There is no general `if` constructor.

### Groups and optional content

```goo
col {
  row {
    text("Name", '/sys/slot/label)
    text("Ada", '/sys/slot/title)
  }
  opt(1) { text("A compact detail", '/sys/slot/summary) }
  opt(2) { text("An extended detail", '/sys/slot/content) }
}
```

`group` lets Goo choose the arrangement. `row`/`flow` request horizontal flow;
`col`/`stack` request vertical flow. `stack` does not mean overlap: use `pane_stack`
for that. Multiple top-level presentations are arranged vertically.

`opt` defaults to rank `1`; only ranks `1` and `2` are accepted. These are visibility
levels, not CSS breakpoints. By default, scar and label views show required content
only, summary views include compact content (rank `1`), and other views include
full content (rank `2`). This applies to the corresponding `/sys/slot/...` and
`/sys/slots/...` scar, label, and summary paths.

Native slots drive the adjacency/layout rules, not arbitrary CSS declarations.
These aliases are recognized; other slots retain their exact identities:

| Paths | Native slot |
| --- | --- |
| `/sys/slot/title`, `/sys/slots/lede` | `title` |
| `/sys/slot/content` | `body` |
| `/sys/slot/label`, `/sys/slots/label` | `label` |
| `/sys/slot/summary`, `/sys/slots/summary` | `summary` |
| `/sys/slot/caption`, `/sys/slots/caption` | `caption` |
| `/sys/slot/icon`, `/sys/slots/icon` | `icon` |
| `/sys/slots/code` | `code` |
| `/sys/containers/row`, `/sys/containers/col`, `/sys/containers/card` | `row`, `col`, `card` |

These are presentation aliases only. `input('/sys/req)` does not become
`input('/sys/slot/req)`. Singular and plural view paths are not universally
interchangeable.

### Native leaves

Native leaves display decoded text, number, path, boolean, and temporal values
as appropriate. Tagged temporal values retain their formatting; `time` and
`duration` also interpret the supported numeric representation in those roles.
`image` consumes URL text. The reference primitives are a small design system,
not generic HTML tags; there is no arbitrary `div`, `href`, `class`, or style map.
Rendering currently supports ASCII text; unsupported text can produce a diagnostic.

## Native configuration

For native display constructors and layout groups, put a config record first:

```goo
text({[maxIdeal]: 240}, "A bounded label", '/sys/slot/title)
button({[primary]: true, [label]: "Continue"}, "Continue")
bar({[value]: 3, [max]: 10, [label]: "Progress"}, "3 of 10")
row({[grow]: 1}) { text("Expands") }
```

| Config key | Accepted value | Meaning |
| --- | --- | --- |
| `grow` | `0` or `1` | Whether layout may allocate extra width. Not a boolean literal. |
| `maxIdeal` | Nonnegative finite number | Bound on ideal sizing. |
| `primary` | `true` or `false` | Primary button treatment. |
| `label` | Text | Accessible label; also image alternative text where applicable. |
| `toggle` | Boolean | Preserved primitive config; no generic interactive toggle binding is provided. |
| `optionLabel` | Text | Preserved primitive config; no selection/options constructor is provided. |
| `value` | Nonnegative finite number | Progress value. |
| `max` | Nonnegative finite number | Progress maximum. If `value` is supplied, `max` must be positive and at least `value`. |

Leading config records are not supported on interactive `action` or bound `input`
controls. A native visual `button` is separate from an `action`.

The standalone reader additionally applies `[slot]` and `[optional]` attributes.
Grove views currently do not apply those two config attributes: use the
positional slot and an `opt` wrapper. Unknown config keys are not extension
points; the standalone reader rejects them, while the Grove path does not
consistently diagnose them.

## Actions, inputs, and creation

### Edit the receiver

```goo
card => group(on = card, action = .poke, myth = {
  '/sys/req = .input(card.req)
  '/sys/res = .input(card.res)
}) {
  input('/sys/req)
  input('/sys/res)
  action("Save")
}
```

`group` establishes the target, action, and argument scope. Nested groups inherit
that scope; nested `myth` entries add/override argument bindings. `on` currently
means the presenting receiver. `.poke` merges supplied slots into that receiver
and validates the resulting record against the view's role contract.

`input('/sys/req)` edits that exact slot and initially displays its current text
(or empty text when absent). `.input(...)` marks an argument to collect from the
browser at invocation time. Inputs currently supply text values, not automatic
number/date/boolean conversion. Literal text can also render an input preview,
but use a data-slot path to bind an actual editable argument.

### Invoke a declared action

```goo
group(on = card, action = %/finish, myth = {
  '/sys/now = .provider
}) {
  action("Again", %/grade = %/grade/again)
  action("Good", %/grade = %/grade/good)
}
```

`%/finish` refers to a Grove `@action`. The group supplies common arguments;
individual buttons supply additional arguments. Declaration references such as
`%/grade/good` resolve registered constants of the action's argument type.
A declared action transforms the current object. Goo does not execute arbitrary
code in a button expression.

| Argument form | Behavior |
| --- | --- |
| Text literal | Literal text argument. |
| Declared constant reference | Resolve a published action argument constant. |
| `.input(expression)` | Collect the corresponding input slot's text. |
| `.provider` | Server-supplied value; currently implemented for `/sys/now`. |
| `.capture('/selection_key)` | Pane-only: capture the accepted selected member as a path value. |

Do not treat a quoted path in an action argument as a general arbitrary path
value constructor: the constant resolution path and capture mechanism have
specific semantics. Arbitrary receiver calculations are not action expressions.

### Change the displayed recipe

```goo
action("Show answer", become = '/sys/slot/res)
```

`become` changes the view recipe in the current presentation encounter, without
changing the object. An action can both invoke an enclosing domain action and
then become another recipe after success. Without an enclosing invocation,
`become` alone is presentation-only. An unbound `action("Save")` does not invent
a domain operation. Dirty inputs are guarded before departing their encounter.

### Create an object at an absent path

```goo
creator => group(make = creator.creation_target, role = %/created_card, myth = {
  '/sys/req = .input("")
  '/sys/res = .input("")
}) {
  input('/sys/req)
  input('/sys/res)
  action("Create card")
}
```

`make` accepts an absolute path literal or a direct path-typed receiver field.
`role` names the role contract for the new object. `make` is a group argument,
not a constructor, and cannot coexist with `on`/`action` in the effective scope.
Creation forms use literal text `.input(...)` defaults rather than prefilling
from the presenting object's slots.

The presenting object must still exist. Creation produces a normal record with
the supplied slots and role contract; it does not create a Grove installation.
The destination must be empty, including its subtree, and inside the allowed
application namespace. Validation and mutation are atomic. An occupied target
fails without changing it or the presenting object. No navigation or selection
change is implicit after creation.

See the executable [creation fixture](../../extras/mounts/grove-dev/creation.grove)
and [SRS action examples](../../extras/mounts/srs/srs.grove).

## Panes and local selection

```grove
workspace =
  @pane
  #on ; %/study
  #for ; /sys/slot/workspace
  study => selection('/current, source = study.cards) {
    split {
      pane(%/queue, ports = { '/chosen = '/current })
      pane(%/detail, ports = { '/chosen = '/current })
    }
  }

queue =
  @pane
  #on ; %/study
  #for ; /sys/slot/queue
  #port ; /chosen
  study => list('/rows, source = study.cards, selection = '/chosen, slot = '/sys/slot/summary)

detail =
  @pane
  #on ; %/study
  #for ; /sys/slot/detail
  #port ; /chosen
  study => follow('/subject, selection = '/chosen, slot = '/sys/slot/content)
```

Every pane has a declaration. Its body belongs directly to that pane; no outer
`pane(...) { ... }` wrapper is needed. It can mount child declarations and present
ordinary views. A followed member's `@view` cannot introduce pane features.

### Pane identity and explicit ports

`pane(%/detail)` uses the declaration's canonical path as its stable identity,
scoped under the owning pane. Reordering it or placing it in another layout
wrapper preserves that identity. Changing its `#on` or `#for` does not rename it.

Mounting the same declaration twice under one owner requires distinct keys:

```goo
pane(%/detail, key = '/left, ports = { '/chosen = '/current })
pane(%/detail, key = '/right, ports = { '/chosen = '/current })
```

The instance identity includes both the declaration and the explicit key. Changing
the key or the declaration creates a different instance. A duplicate unkeyed
mount is a compile error. Layout groups, selection scopes, splits and decks do
not introduce an owning pane.

`#port ; /chosen` declares a required selection input. `ports` connects each
callee port (left side) to a selection in the caller's scope (right side). Supply
all ports, with no duplicate or unknown names. Use commas between multiple
bindings. A child cannot implicitly use a selection from its parent's body;
forward it explicitly, including through intermediate pane declarations.
The port works with `list`, `follow`, and `.capture(...)`. Local selections can
shadow port names without changing the parent's selection.

Pane composition currently resolves declarations in the same Grove document.
`on` defaults to the current receiver. The current implementation permits only
that receiver, with the same declared role as the child. It does not construct
or evaluate another receiver for the child. Composition cycles are rejected.
Panes requiring ports are reusable components, not standalone explorer previews
or workspace entry points.

### Topoi: lists and trees

A **topos** presents a collection's members and connects gestures to a selection
port. Its member content is still an ordinary slot-selected `@view`. The three
constructors share the same arguments and ownership semantics:

```goo
list('/items, source = study.cards, selection = '/chosen, slot = '/sys/slot/summary)
diagram_tree('/items, source = study.cards, selection = '/chosen, slot = '/sys/slot/summary)
list_tree('/items, source = study.cards, selection = '/chosen, slot = '/sys/slot/summary)
```

`list` is flat, `diagram_tree` lays out the parent relation spatially with pan/zoom,
and `list_tree` is an expandable outline with keyboard traversal. Switching the
constructor while keeping the key and owning pane preserves the topos's identity,
focus reference, and shared selection. Simultaneous topoi need distinct keys.
Disclosure and the diagram camera are presentation state; they do not invoke
object actions. Buttons, links, and inputs in a member view keep their own behavior.

The source defaults to direct children on `z`. Request namespace-tree
membership on the **selection** to share it across all three renderers:

```goo
selection('/chosen, source = study.cards, topology = "tree") {
  list('/flat, source = study.cards, selection = '/chosen, slot = '/sys/slot/summary)
  list_tree('/outline, source = study.cards, selection = '/chosen, slot = '/sys/slot/summary)
  diagram_tree('/diagram, source = study.cards, selection = '/chosen, slot = '/sys/slot/summary)
  follow('/detail, selection = '/chosen, slot = '/sys/slot/content)
}
```

Choose the namespace projection on the selection: `axis = "x"`, `"y"`, or `"z"`
(default `"z"`). All connected topoi inherit it.

- `x`: the root record only; a children selection is empty.
- `y`: the root and nearest live descendant records, retaining structural paths
  between them. Traversal stops at those records.
- `z`: the full subtree, including nested records.

For example, `selection('/chosen, source = '/0x11/app, topology = "tree", axis = "y")`
provides a frontier tree. Virtual namespace paths such as `/o/...` and `/h/...`
use the same namespace projection machinery. Their views can be inspected;
projection does not confer write authority. Actions still require a validated
writable source, and captures retain server-side application authority checks.

Tree membership includes the source root and its projected descendants. Each member
has an explicit parent reference; the root has none. Structural nodes can connect
the hierarchy but cannot be selected as objects. Both source forms are bounded at
64 nodes; a larger source reports an error instead of silently truncating it.
There is no lazy subtree loading in this first version. Trees require a single
root and reject missing parents, duplicate members, and cycles. Use `topology =
"tree"` with tree renderers; `"children"` is the default.

Selection capture works for tree descendants as well as direct children. The
server checks the published selection's topology, bounded membership, and source
and object lifetimes before admitting the action. A renderer cannot enlarge the
selection's authority.

The `panes` mount's `topoi_demo` declaration demonstrates all three on the same
namespace tree, followed detail, editing, and a capture action.

### Other keys, sources, and initial selection

`selection`, `list`, `follow`, `deck`, `navigate`, `operation`, and
`operation_status` still take local path or text literal keys. Identity combines
the owning pane, handle kind, and key. Equal keys in different owners can coexist;
duplicates of the same kind within an owner are diagnosed. Use path literals for
selection ports and capture operands.

A source is a namespace path projected on the selected axis, bounded to **64
nodes**. It can be a literal path or a direct path-typed field. Choose direct
children or recursive tree topology; arbitrary queries and pagination are not
supported.
Member presentations must satisfy the selected view's role contract.

```goo
selection('/current, source = study.cards, initial = .member('/0x11/app/panes/cards/a)) {
  follow('/detail, selection = '/current, slot = '/sys/slot/synthetic)
}
```

The seed is a membership key in the advertised source, resolved once when the
selection is created. Without a seed there is no initial selection. Invalid
seeds produce diagnostics; they are not silently replaced with the first item.
`list` and `follow` default their view slot to `/sys/slot/content`.

`list(..., browse = "Browse children")` adds a navigation link for each member,
separate from accepting that member as the selection.

### Layout containers

```goo
deck('/tabs) {
  pane(%/summary_pane)
  pane(%/details_pane)
}
pane_stack {
  pane(%/back)
  pane(%/front)
}
```

`split` arranges panes in columns, collapsing on narrow screens according to the
host stylesheet. `deck` selects the first pane initially, retains selection by
key across reordering, and suspends inactive panes. `pane_stack` overlaps panes
in declaration order; it does not provide modality, focus trapping, or history.

### Selection and action continuity

Click selects; list keyboard interaction moves focus with arrows and accepts
with Enter. Nested interactive controls do not accidentally select their row.
Dirty input departure is guarded with Stay/Discard behavior. Composition delays
departure. A pending choice is not the accepted selection.

```goo
group(on = study, action = %/choose, myth = {
  %/chosen = .capture('/current)
}) {
  action("Use selected object")
}
```

Capture reads the accepted member, not a highlighted/pending choice. Missing or
unavailable selection fails. Multiple captures from one owner observe the same
selection state; atomic capture across different owners is not supported.

Ordinary data edits preserve member identity; removal/recreation changes its
lifetime. A vanished selection becomes unavailable rather than silently choosing
a replacement. State is page-local: there is no persistent UI namespace, automatic
watcher, or durable selection across a full-page reload.

## Workspace navigation and operations

These controls require an `@pane` declaration, a local pane owner, and the
generic workspace host integration. Labels,
mode, browse text, and operation keys are authored literals, not dynamic templates.

```goo
inspector => {
  navigate('/address, source = inspector.source_path, mode = "input", label = "Inspect path")
  navigate('/parent, source = inspector.source_path, mode = "parent", label = "Parent")
  operation('/reload, operation = '/mount_reload, label = "Reload mount assets")
  operation_status('/reload_status, operation = '/mount_reload, label = "Mount publication")
}
```

| Navigation mode | Behavior |
| --- | --- |
| `"input"` | Editable absolute-path navigation form. |
| `"parent"` | Navigate to the source's parent. |
| Omitted/default | Navigate to the source itself. |

Navigation stays in the current workspace. Ordinary local navigation runs
departure guards; modified clicks retain normal browser link behavior.

`operation` looks up its operation key in the host's configured bindings.
`operation_status` observes the same key; its own local key is independent.
Currently the host operation adapter implements **mount rescan/publication**,
not arbitrary domain actions or arbitrary HTTP requests.

Status is browser-local per workspace: idle, pending, success, or error. Duplicate
submissions are disabled while pending. Publication errors are shown in the status.
Success reloads the page; failure retains it. This operation does not reset an
installed Grove instance. Use `action` for domain mutations and the Grove dev
panel for rebuild/replacement.

## Standalone literal Goo

The `goo` mount's literal reader accepts one native root, without `@view`, a
receiver binding, role lookup, or action/pane execution:

```goo
col(%card) {
  text("Ada", %title)
  text({[optional]: 1}, "Engineer", %summary)
  row {
    button({[primary]: true}, "Continue")
    bar({[value]: 3, [max]: 10}, "3 of 10")
  }
}
```

Its complete constructor vocabulary is:

```text
group row col flow stack opt
text image button input code avatar presence media bar
```

Its native constructor rules differ from embedded Grove Goo:

- Groups take an optional leading config record and an optional slot, followed
  by a required curly body. Default slot is the constructor name.
- Leaves take an optional leading config, optional text payload, and optional
  slot, in that order. Omitted payload is empty text; default slot is the name.
- `opt`, `opt(1)`, and `opt(2)` wrap a required body.
- Slots can be `%title`, an absolute path such as `/sys/slots/lede`, or text such
  as `"title"`. `%title` is standalone slot shorthand, not a Grove declaration.
- Text accepts the Rex text forms (cord, tape, page, span, slug) and
  `escaped("...")` for JSON escape decoding. Ordinary quoted Rex strings double
  embedded quotes; they are not JavaScript string literals.
- Config uses bracketed keys and colon values. Duplicate/unknown keys are
  rejected. Scalars are finite numbers, booleans, or text; `null` is not accepted.
  The source numeric reader also accepts its Haskell-style numeric spellings,
  including hexadecimal, octal, and leading zeros.
- In addition to the config table above, `[slot]: "title"` overrides the positional
  slot, and `[optional]: 0`, `1`, or `2` sets the visibility rank.
- There is no `show`, `present`, `or`, typed scalar alias, `action`, `make`, pane,
  selection, host operation, or receiver-field evaluation in this reader.

Historical examples or proposals can contain forms that neither current source
language accepts.

For a complete authored workspace see the
[inspector Grove](../../extras/mounts/goo-inspector/inspector.grove).
