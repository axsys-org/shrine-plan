# Goo explorer

An independent copy of `goo-inspector`, with its own routes, publication root,
and source files. Both mounts can be selected together.

A small server-rendered Goo workspace: a bounded namespace child list and a
synthetic Values pane following the selected child. The layout is authored in
`explorer.grove`. Views provide content; the workspace owns selection and panes.

```sh
WISP=/path/to/wisp python3 x/eden --compiler none --mount goo-explorer --mount srs --port 8178
```

Open `http://127.0.0.1:8178/goo-explorer?path=/0x11/app/srs/cards`.
The address form and Parent/Browse children links perform ordinary navigation.
Select a row to inspect its synthetic values. Local selection never invokes a
domain action. Existing records with at most 64 direct physical children are
supported. Structural roots, larger collections, pagination, matching-view
catalogs, and evidence panels are outside this version. To inspect a leaf,
browse its parent and select it.

The workspace, Namespace, and Values panes are separate `@pane` declarations.
The workspace owns `/object` and connects it to each child's required `#port`
with `pane(%/Namespace, ports = { '/object = '/object })` (and likewise for
Values). The declaration path supplies each pane's identity; layout wrappers do
not. Selection sharing is explicit at these call sites.

The server renders pane wrappers, native content and the child summaries in the
initial HTTP response. The shared browser adapter adopts that DOM, validates the
current source membership, and attaches selection/follow behavior. Following a
selection fetches the existing server-rendered synthetic view. There is no
`index.html` or JavaScript composition builder. The shared `goo_workspace` endpoint
captures dependencies, constructs the receiver, resolves the declaration, and
renders the workspace. `mount.foil` configures that endpoint and supplies the
source limit, rescan capability, and document assets. The title, path form,
Parent/Browse navigation, reload button, and diagnostics are declared in
`explorer.grove`; shared host code renders lists and attaches the controls.
There is no explorer-specific JavaScript.

Edit `explorer.grove` for pane layout and ordinary view content, or `style.css`
for styling, then click **Reload mount assets**. The mount rescans and publishes,
then the page reloads. A failed publication retains the previous definitions and
assets and displays diagnostics. Installed objects are never reset by this
button. A full page reload resets page-local selection.

Changes to Foil handler code or manifest registrations require restarting Eden.
`--compiler none` avoids paying for P6 optimization during development startup.

Shared checks:

```sh
node --test extras/mounts/explorer/tests/*.test.cjs
WISP=/path/to/wisp python3 extras/x/check --mount goo-explorer --jobs 2
```
