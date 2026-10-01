# Goo panes and local selection

The explorer owns a private, page-local semantic session. A selection changes
presentation context; an action captures that context and uses the existing
namespace action adapter. Selection and deck gestures do not call `/goo/act`,
normalize action arguments, sample providers, or write domain receipts.

## Integration map

- `src/foil/grove_views.foil`: validates keyed local constructors and retains
  them alongside ordinary lowered `show` and expanded `present` nodes.
- `goo_panes.foil`: read-only description serialization and initial server HTML. Native fragments still
  pass through `goo_bridge` and Goo v2 normalization, layout and HTML.
- `goo-session.js`: private typed handles, reconciliation, source/member
  validation, tracked selection reads, encounters, guard ordering, capture and
  reflection. Description planning does not create owners.
- `goo-panes.js`: the explorer's native list/deck gestures, retained DOM, actual
  input integration and selection-following subject presentations.
- `goo-actions.js`: shared action adapter for ordinary previews and panes.
- `src/foil/goo_runtime.foil`: bounded namespace source reads, lifetime/data
  evidence validation, normal argument/receiver admission and invocation retry.

There was no earlier pane/session store, list/topos, or draft checkpoint service
in this explorer. The session is the minimal shared primitive for those local
owners; it does not create a privileged `/ui` namespace. Namespace domain state
and its existing observation/versioning mechanisms remain authoritative for
subject data.

## Actual source spelling

```grove
workspace =
  @view
  #on ; %/study
  #for ; /sys/slot/workspace
  study => pane('/workspace) {
    selection('/current, source = '/0x11/app/panes/cards) {
      split {
        pane('/queue) {
          list('/rows, source = '/0x11/app/panes/cards,
            selection = '/current, slot = '/sys/slot/summary)
        }
        pane('/detail) {
          follow('/subject, selection = '/current,
            slot = '/sys/slot/content)
        }
      }
    }
  }
```

Use the single-line calls in `../panes/panes.grove` for the executable specimen.
The spelling adapts the proposed binder/match surface to the existing parser:

| Proposed form | This slice |
| --- | --- |
| `selection(key) { current => ... }` | `selection(key, source = path) { ... }`; ports resolve the selection's literal key lexically |
| `list(study.cards, selection=current) { card => present(card, slot) }` | `list(key, source=path, selection=key, slot=slot)`; a bounded namespace-member presentation |
| `match current.subject ... present(card, slot)` | `follow(key, selection=key, slot=slot)`; a tracked optional selection read and continuing subject encounter |
| Creation-only typed seed | `initial = .member('/0x11/app/panes/cards/a)` names a **membership key** in the advertised source, resolved once from its bounded snapshot |
| Overlapping `stack` | `pane_stack { pane(key) { ... } ... }`; existing vertical `stack` is unchanged |
| Deferred selection operand | `.capture('/current)` in an ordinary group's `myth` |

`pane`, `selection`, `list`, `follow` and `deck` require keys. The key is local,
not a globally executable namespace handle. Use path-literal selection keys for `.capture`. Pane and selection are different
handle kinds. Equal keys in separate workspaces are independent. Groups,
selection scopes, split/deck/stack wrappers are not addressing ancestors.
Duplicate owner/kind/key declarations are diagnosed.

A source is an installed namespace record with at most 64 physical direct child
keys. `/goo/source` returns captured direct-child membership references. Their
source and subject lifetimes use the namespace's **x shape counter**, which
changes on creation/removal but not an ordinary live edit. Subject data version
is separate evidence. No subtree flattening or whole-source lookup occurs.
The initial member must exist in that snapshot; invalid seeds are explicit
local diagnostics. No seed means no selection.

The adapter's port type is `namespace-record`, paired with the exact source
identity and lifetime. The selected recipe's normal published role contract
still decides whether it can present that record. This is not a general typed
collection/query language or a projection correspondence mechanism.

## Continuity and guards

The accepted selection is the only choice authority. A follower derives its
binding from that selection; it has no writable navigation subject. Membership
changes can preserve the encounter when subject bindings are equal. Ordinary
live data revisions preserve encounter and recipe. `become` changes only that
encounter's recipe. Choosing the same member is a no-op.

Pointer activation selects. Arrow keys move list focus; Enter selects. Clear
uses the same local protocol. Nested buttons, inputs and links own their events.
Usable row references remain usable after another member is selected. Intent
sequence is allocated by the session; retrying an old intent cannot undo a later
choice. Handles from another session, retired incarnations and reflected JSON
snapshots cannot execute local operations.

The real Goo text inputs in following panes retain working values separately
from server seed values. A dirty departure shows an inline Stay / Discard and
leave decision. Accepted selection and its usable encounter remain unchanged
while a candidate is pending. All affected followers are guarded. A newer
candidate supersedes an older guard result. Checkpoint callbacks can succeed
without implying that a superseded presentation transition also succeeds.
This repository has no independent draft/checkpoint service; the built-in UI
provides discard/refusal, not a fabricated autosave service.

Composition defers structural reevaluation and refuses destructive departure.
Retirement releases resources only after guards allow it. Full page reload has
no retained UI-session continuity. A refresh explicitly observes domain/source
changes; this slice does not add background watchers.

`split` uses equal flexible columns with a deterministic one-column narrow
fallback. `deck(key)` uses local keyed alternative selection. It seeds the first
child once, preserves an active child across reorder and picks the first
survivor after guarded removal. Empty decks have no active child. Inactive
panes are suspended and removed from keyboard navigation while keeping inputs
and encounters; their subject view is refreshed before reuse. `pane_stack`
overlaps panes in declaration order without history, modality or focus traps.

Asynchronous subject output carries owner incarnation, accepted selection
revision, encounter, recipe generation and member evidence. Stale output cannot
replace the current encounter. Old content is marked loading and made inert
while a newly accepted subject loads. Queue and adjacent pane owners survive
that detail update.

Filtering/unloading a known member is not deletion. Confirmed deletion leaves
an explicit unavailable selection. A recreated record at the same path does not
inherit the old choice. An incompatible source lifetime requires removing and
redeclaring the selection, rather than silent rebinding/reseeding.

## Captures and domain actions

```grove
group(on = study, action = %/archive, myth = {
  %/archived = .capture('/current)
}) {
  action("Remember selected card")
}
```

The binding is deferred. Activation freezes the **accepted** membership and
observation evidence, even if another candidate is pending. Multiple operands
from one owner are captured synchronously; cross-owner atomic capture is
rejected. The invocation retains this immutable payload when retried.

For this single-selection adapter, validated capture normalizes to the existing
**path codec** naming the concrete subject. Source/member identity, lifetime,
data version and accepted local revision accompany it in the invocation
snapshot; they are not a live selection reference passed to the action handler.
An empty/unavailable selection fails. Server-side validation checks membership,
the published lexical selection source, source and subject lifetimes, current data version, existence and application
authority before the existing typed action handler/receiver checks run.

`/goo/act` stores successful invocation identities and exact request payloads in
`/<self>/weft/goo_receipts`. Identical retries return the original response;
changed payloads using the same ID are rejected. Recording the receipt and
exposing the candidate domain state succeed together. This development journal
is bounded to 1024 invocations per namespace; the page capture cache is bounded
to 128. Exhaustion is an explicit error, not silent receipt eviction. Legacy
requests without an invocation ID remain compatible.

Existing grading/provider actions retain their card receiver and normal
admission. Selection gives no additional mutation authority. The specimen's
`archive` action simply stores the captured path on its study object; it is
local fixture authority, not external Shrine integration.

## Inspection and limits

“Inspect local runtime” serializes the actual session owners, keys, lifetimes,
selection ports, read dependencies, accepted/pending choice, focus, encounters,
recipe generation, suspension, input buffers, resources, local outcomes and
captured invocation arguments. These are read-only snapshots of executed state,
not a second inspector model.

Version one is single-select, a finite namespace source, page-local lifetime,
and explicit refresh. No general history, cross-owner transfer, new medium,
arbitrary application JavaScript, rich-text editor, automatic migration or
cross-device persistence is implied. The finite list adapter selects an ordinary Goo subject recipe by slot; it does
not accept a custom repeated body or dynamically nest another local-session
view inside a member recipe. Such nested recipes produce an explicit diagnostic.
Static `present` expansion containing pane declarations remains supported.
A source is bounded to 64 records and a
session to 256 semantic owners. Reflection retains the last 64 local events.

## Run and test

```sh
WISP=/path/to/wisp python3 x/eden --mount panes --port 8172
# Open http://127.0.0.1:8172/views/0x11/app/panes/study
node --test extras/mounts/explorer/tests/*.test.cjs
WISP=/path/to/wisp python3 extras/x/check --mount panes --jobs 2
```

The study is an ordinary record at `/0x11/app/panes/study`, alongside `/cards`.
Do not use the installation root as this action receiver: its pact manifest
replays seed records when changed.

The Node suite uses deterministic deferred guards/render tickets (no sleeps).
The mount tests include real Grove parsing/lowering, source lifetime/capture
validation, invocation retry, the existing Goo action/provider regressions,
explorer reflection, and Goo v2 rendering/layout regressions. Browser rehearsal
must additionally exercise the actual row/button/input/deck DOM; isolated owner
tests alone are not evidence of rendered integration.

See [verification and rehearsal](PANES-VERIFICATION.md) for observed results and coverage boundaries.

## Server rendering and path-valued sources

`selection` and `list` also accept a direct path-typed receiver field, for example
`source = inspector.source_path`. The compiler checks the field type. Rendering
binds its value from the receiver; missing values produce a diagnostic. Action
capture validation resolves the source again from the current receiver, so a
browser cannot substitute a different source. Changing a source requires a new
workspace; incompatible rebinding of an existing owner remains rejected.

`goo_panes/server_body` emits native fragments and pane wrappers with temporary
hydration addresses. Its read-only callback supplies initial list members from
the caller's captured observation. The browser adopts those wrappers and native
content rather than replacing them. It validates live membership before enabling
list interaction and continues to fetch subject presentations through the shared
server renderer. Initial deck activation and local ownership remain browser
responsibilities. This does not add query-backed or paginated sources.

### Hosting a workspace

`goo_workspace` hosts a server-rendered workspace independently of the inspector.
A mount constructs a `goo_workspace/endpoint` with:

- `declaration`: the absolute published workspace declaration path;
- `source_slot`: the path-typed slot used to construct its transient receiver;
- `initial`: the subject path when the request has no `path` query parameter;
- `validate(selected)`: optional source-policy diagnostic;
- `operations`: pairs of local capability key and mount source path for rescan;
- `document(target, content)`: the surrounding HTML document.

Delegate the mount's workspace route to `goo_workspace/request endpoint request
now`. Activate it with `goo_workspace/install endpoint fallback state`, passing
the previous HTTP talk handler as `fallback` (normally `goo_browser/talk`).
Endpoints dispatch by declaration, so hosts can chain handlers for different
workspace declarations. The configuration is fixed by the mount: URL parameters
select the subject, not the declaration or receiver slot.

The host captures the subject subtree and the local cached view catalog, checks
the configured declaration and receiver contract, binds source fields, and emits
the shared pane markup. `document` receives either the server-rendered workspace container
or a diagnostic. Load the shared Goo scripts and attach `GooPanes` to `#workspace`
using its `data-target` and `data-description`. Source limits and document chrome
remain host policy; the generic endpoint imposes no inspector-specific 64-child
limit. Child summaries are rendered by the shared host from the list's source and slot. Only record-bearing children are advertised; `browse` adds ordinary workspace navigation for each member.


### Workspace navigation and operations

These controls belong inside a pane. They do not invoke domain actions or create
nested workspaces inside content views:

```text
navigate('/address, source = inspector.source_path, mode = "input", label = "Inspect path")
navigate('/parent, source = inspector.source_path, mode = "parent", label = "Parent")
operation('/reload, operation = '/mount_reload, label = "Reload mount assets")
operation_status('/publication, operation = '/mount_reload, label = "Mount publication")
```

`navigate` accepts a path-typed receiver field or literal path. `mode = "input"`
emits a GET form; `"parent"` links to its parent; the default links to the source.
Navigation preserves the workspace URL and changes its `path` query parameter.
`list(..., browse = "Browse children")` adds a link for each member without
changing selection. Ordinary clicks use the session's departure guards; links
also support normal browser new-tab behavior.

`operation` names a host-configured capability, not a URL. The first host binding
is mount rescan/publication: `operations = [[key source]]`. The shared
`goo-workspace.js` adapter polls the requested scan, disables duplicates, and
reloads only after successful publication. `operation_status` observes the same
capability and presents pending, success, or expandable failure details. Reload
checks local departure guards, never resets installed instances, and preserves
the current page when publication fails. Labels and control placement are Goo
source; transport and operation state are shared host code.

Load `/static/goo-workspace.js` after the shared session, pane, and action scripts.
It attaches controllers to server-rendered workspace containers automatically.

### Creating an object with an action

A creation group keeps the presenting receiver and names a separate, absent
write destination:

```text
group(make = creator.creation_target, role = %/created_card, myth = {
  '/sys/req = .input("")
  '/sys/res = .input("")
}) {
  input('/sys/req)
  input('/sys/res)
  action("Create card")
}
```

`make` accepts a literal absolute path or a direct path-typed receiver field.
`role` names a published role. `make` is mutually exclusive with `on` and
`action`; the creation itself is the operation. The presenting object must still
exist, match its view, and pass the ordinary freshness checks. The server resolves
the destination from that current receiver, checks application write authority,
validates the supplied initial fields against the creation role, and atomically
installs the record and its contract only if the destination subtree is empty.
An occupied destination never becomes an update. Failed validation leaves the
namespace unchanged; retries with the same invocation identity return the
original successful receipt.

Creation inputs use literal text defaults from their `.input(...)` bindings,
not same-named slots on the presenting object. Other displayed expressions keep
the enclosing receiver. Successful creation uses the existing refresh behavior;
it does not implicitly navigate or select the new object.

`grove-dev/creation.grove` supplies a runnable example at
`/views/0x11/app/demo/creator`, creating `/0x11/app/demo/created`.
