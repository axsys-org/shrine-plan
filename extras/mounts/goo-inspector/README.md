# Goo inspector

A small server-rendered Goo workspace: a bounded namespace child list and a
synthetic Values pane following the selected child. The layout is authored in
`inspector.grove`. Views provide content; the workspace owns selection and panes.

```sh
WISP=/path/to/wisp python3 x/eden --compiler none --mount goo-inspector --mount srs --port 8178
```

Open `http://127.0.0.1:8178/goo-inspector?path=/0x11/app/srs/cards`.
The address form and Parent/Browse children links perform ordinary navigation.
Select a row to inspect its synthetic values. Local selection never invokes a
domain action. Existing records with at most 64 direct physical children are
supported. Structural roots, larger collections, pagination, matching-view
catalogs, and evidence panels are outside this version. To inspect a leaf,
browse its parent and select it.

The server renders pane wrappers, native content and the child summaries in the
initial HTTP response. The shared browser adapter adopts that DOM, validates the
current source membership, and attaches selection/follow behavior. Following a
selection fetches the existing server-rendered synthetic view. There is no
`index.html` or JavaScript composition builder. The shared `goo_workspace` endpoint
captures dependencies, constructs the receiver, resolves the declaration, and
renders the workspace. `mount.foil` configures that endpoint and supplies the
source limit, rescan capability, and document assets. The title, path form,
Parent/Browse navigation, reload button, and diagnostics are declared in
`inspector.grove`; shared host code renders lists and attaches the controls.
There is no inspector-specific JavaScript.

Edit `inspector.grove` for pane layout and ordinary view content, or `style.css`
for styling, then click **Reload mount assets**. The mount rescans and publishes,
then the page reloads. A failed publication retains the previous definitions and
assets and displays diagnostics. Installed objects are never reset by this
button. A full page reload resets page-local selection.

Changes to Foil handler code or manifest registrations require restarting Eden.
`--compiler none` avoids paying for P6 optimization during development startup.

Shared checks:

```sh
node --test extras/mounts/explorer/tests/*.test.cjs
WISP=/path/to/wisp python3 extras/x/check --mount goo-inspector --jobs 2
```

Verified the Grove-authored host controls with the explorer/web suites, inspector
mount contracts, and 26 JavaScript checks. Browser rehearsal covered path entry,
Parent/Browse navigation, selected-child values, failed publication preserving
the page with expanded diagnostics, and successful publication updating the Goo
text without a restart.
