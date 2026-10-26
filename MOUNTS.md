# Eden source mounts

For a complete notes application using the existing workspace host, see
[Making a Grove and Goo mount](extras/tutorials/grove-goo-mount.md).

`x/eden` boots Shrine's namespace, Pact, supervisor, filesystem driver and HTTP
transport. It does not install a browser application or build browser assets.
Unregistered HTTP routes return 404.

```sh
x/eden
x/eden --list-mounts
x/eden --mount debugger --mount srs
x/eden --extras-root ../shrine-extras --mount explorer --mount codex
```

Native publication appends new definitions; it does not rewrite historical laws
or infer type identity from unchanged declarations. A mount can list owned
`pinned_modules` in its descriptor. First publication compiles missing artifacts;
subsequent scans import those exact artifacts from the mount's existing native
image record, including their original dependency graphs. Their source files are
bootstrap inputs, not refresh inputs once pinned. To change a contract, publish a
new explicitly selected module/version and handle compatibility at activation.

The mount descriptor and compiler belong to the saved service. These changes
govern newly compiled services, not an automatic upgrade of a running saved world.

Native command admission uses one budget of 128 reaction rounds after the
submitted event. Supervisor writes, guarded operations and Grove installation
share this policy. A quiescent candidate can commit; exhaustion, reaction failure
or unsupported outbound effects discard the candidate and its dependency index.
The budget limits reaction rounds, not execution time inside an individual hand.

The default mount sources are this checkout's `extras/` directory.
`--extras-root` selects another source directory, including its Nix configuration.
Dependencies are loaded once, before their consumers. Only selected
mounts and their dependencies prepare host tools or assets. Mash and Node belong
to the debugger's extras environment, not the core Eden shell.

Each flat bag has a version-1 `mount.json`. It maps logical Foil module names to
filenames, declares ordered Grove units and their publication roots, and declares
assets, dependencies and optional activation, HTTP and host entrypoints. See the
[extras guide](extras/README.md) for the schema and application checks.
Core rejects unknown names, cycles, core-module overrides,
overlapping publication ownership and duplicate route claims. HTTP dispatch uses
the longest matching path prefix, with segment boundaries.

## Declarative Goo workspaces

An ordinary workspace can use the shared Explorer host instead of writing a
Foil endpoint, HTTP dispatcher, installation hook, query parser, and page shell.
Declare `explorer` as a dependency and add `workspaces` to `mount.json`:

```json
{
  "version": 1,
  "name": "reader",
  "dependencies": ["explorer"],
  "modules": {},
  "grove": [{"root": ["gov", "reader"], "files": ["reader.grove"]}],
  "assets": {"/reader/style.css": "style.css"},
  "workspaces": [{
    "name": "main",
    "route": "/reader",
    "entry": ["gov", "reader", "workspace"],
    "receiver": {
      "slot": ["gov", "reader", "source_path"],
      "initial": ["lib"],
      "admission": "namespace"
    },
    "shell": {
      "title": "Namespace reader",
      "brand": "goo / reader",
      "subtitle": "Explore the namespace",
      "stylesheet": "/reader/style.css",
      "breadcrumbs": true,
      "navigation": [["Library", ["lib"]], ["System", ["sys"]]]
    }
  }]
}
```

The Grove source declares `source_path = @slot`, a context role with a required
path-valued field at that slot, and a `workspace = @pane` whose `#on` names that
role. The entry pane has no external selection ports; it can declare selections
and supply ports to its child panes. See
[`documentation.grove`](extras/mounts/goo-documentation/documentation.grove)
for a complete example.

Paths in registrations are arrays of symbolic namespace names. Eden prefixes
them with the current node, except paths starting with `sys`, which are absolute.
An empty `initial` or navigation path denotes the node root. `entry` and the
receiver slot must be within this mount's declared Grove roots. The route is a
canonical non-root HTTP path. Names and entry panes must be unique within the
mount. The loader rejects duplicate route claims across selected mounts.

`receiver.admission` defaults to `namespace`, allowing structural namespace nodes
with children; `record` requires a record at the selected path. This is subject
validation, not an authentication policy. Requests may supply only one canonical
absolute `?path=…`; they cannot choose a different pane or receiver slot. The
initial subject need not exist when definitions are published, allowing an
activation hook to create it; admission runs when it is requested.

`shell` is optional. Its text fields are escaped. It supplies `title`, `brand`,
`subtitle`, `footer`, `breadcrumbs` (default false), `navigation` (default empty),
and a `stylesheet` URL from this mount's assets. Standard Goo scripts and styles
come from Explorer. The header/brand/breadcrumb classes are
`goo-workspace-header`, `goo-workspace-brand`, and `goo-workspace-breadcrumbs`.
No application-specific JavaScript is needed for normal panes, navigation,
selection, or rendering.

Workspace page routes and all assets on a declarative mount are claimed
implicitly. Do not repeat them in `routes`. Additional custom `http` routes must
still be declared in `routes`. Existing manual `activate` and `http` hooks remain
supported, including on mounts that also declare workspaces; shared installation
runs after activation. A workspace's stylesheet comes from the last successful
source publication, through the same asset service as other mount assets.

The importer creates a typed `goo_workspace_mount/bundle` at the mount control
record, under the `source_mount/slot 'workspaces` slot. It contains registrations
and the candidate namespace version at validation. This is inspectable,
versioned namespace data; it is not a new evaluator or a second browser runtime.
Each candidate publication validates the actual compiled entry pane, its lack of
external ports, the path receiver's role match, and its pane description. Failure
rejects the candidate and retains the previous published definitions, registration,
and assets. Installation reuses `goo_workspace/install` and hosted receivers;
HTTP and hydration continue through the existing Goo boundaries.

Mount descriptor changes (including shell and receiver settings) require a service
built with those registrations; restarting a saved service retains its descriptor. Grove and asset rescans retain the existing atomic
publication behavior. Custom receiver constructors, guards beyond the two
admission policies, host operation mappings, and custom page shells still use
the manual Foil endpoint interface. Documentation's compiler-metadata reader is
an independent capability and is not part of this registration format.

## Source, definition and instance identities

For node `0x11` and mount `srs`:

- `/0x11/io/fs/srs` is the mount control record.
- `/0x11/io/fs/srs/source/<filename>` contains imported bytes.
- The `apps/srs/main` Foil module retains its compiler identity beneath the
  publisher's `/lib` root.
- `/0x11/gov/srs` is the published Grove template.
- `/0x11/app/srs` is one possible installed instance.

A compiler custom reader reads only the captured source records, plus declared
dependency artifacts and core sources. Extras are never overlaid into core's Foil
source directory. The runtime prohibits symlinks outside its file root, so a
private scanner captures each requested bag into a separate `mounts/` directory
before importing it. Every request reads the current checkout. Missing files in
old namespace history are excluded from the compiler snapshot.

## Explicit rescan

Warp the mount control record with its `op/rescan` operation. With explorer
mounted, this is also available through the ordinary operation UI, or:

```sh
curl --data-urlencode 'op=/0x11/io/fs/srs/op/rescan' \
  http://127.0.0.1:8130/op/0x11/io/fs/srs
```

The control record's publisher-owned `fs/source/status` slot reports the scan
epoch, readiness, message and last successful publication. `fs/source/diagnostic`
contains the publication failure, if any. The filesystem `res` report records
known and missing files. Read failures, missing inputs and compilation failures
retain the previous successful definitions. Obsolete scan completions are ignored.
Unchanged captured bytes do not compile or publish again.

Each mount is compiled against one captured namespace state. Its complete candidate
is installed only after all Foil modules, Grove units and required assets validate.
Activation runs on initial selection. Existing instances and feet retain their
captured code and state; rescan does not rerun activation, replace drivers or
migrate instances. New installations can use the newer definitions. Route handlers
remain captured by the running HTTP foot. Declared asset URLs read bytes from
the latest successful mount publication, so rescan followed by browser reload
picks up HTML, CSS and JavaScript changes. Failed publication retains the previous
assets. Restart can select explicitly published handlers from retained mount images
under the saved service's existing registrations. New mounts, descriptor contracts
(including asset URL mappings), or core driver code require a service built with
those registrations and implementations; restarting the saved service does not
change them.

Watching, persistence and automatic instance migration are outside this interface.

## Cached overlays

Import `overlay_cache` to materialize an existing `/o` application in an ordinary
namespace record. `overlay_cache/path version transform input` constructs its
source path, with a pinned transform version and live input. Then
`overlay_cache/install target source state` returns `either[iota namespace]`,
priming the result before it returns. Place the target outside the overlay's input
subtree; installation rejects targets covered by the resolved source dependencies.

Consumers watch the cache record with `.x` care and decode its result with
`overlay_cache/value record`, which returns `axal[myth]`. Existing `/o` dependency
rules refresh the materialization on relevant changes, including nested overlays,
input deletion and successful source publication. Poking the cache's
`/sys/from` path slot rebinds and refreshes it. The transform remains
pinned until that source path selects a different version. Callers committing
prepared namespace batches outside dispatch must run `sovereign_reconcile` against
the before/after states; source-mount publication already does this.

Explorer's view catalog is a `felt` overlay over the node's `/gov` subtree,
materialized at `/weft/view_catalog_cache`. Page requests read that record instead
of rescanning published definitions. HTTP and journal writes are outside `/gov`
and do not invalidate the catalog. The cached catalog includes an inverted index
of required slots: an object supplies candidate view ranks through its current
slot keys, then the normal contract check validates those candidates. Views with
no required slots remain candidates for every object; alternatives are deduplicated
and original catalog order is preserved. Changing a published contract rebuilds
the index through the same overlay invalidation, while object edits use their new
slots immediately without retaining per-object cache entries.

## Checks

```sh
python3 x/eden-mounts-test.py
python3 x/test_runner_tests.py
x/check foil:tests/source_mount foil:tests/fs_reconcile foil:tests/http_foot foil:tests/inspect_read
x/eden --check
x/eden --extras-root ../shrine-extras --mount debugger --mount srs --mount codex --check
```

Application suites live in extras. Core Grove compiler tests use independent
fixtures in `src/grove/fixtures`; they do not read SRS or debugger sources.

## Live Grove development

Start a small, editable Grove with both the explorer and compiler inspector:

can
```

Open `http://127.0.0.1:8144/grove/dev?selected=/0x11/app/demo/notes/welcome`.
The **Develop this Grove** link in object and view pages opens the same panel for
an existing installation. The Grove selector lists the selected mounts' published
units; source filenames, published version, installed version, and instance
revision stay visible. **Objects**, **Views**, and **Internals** open the existing
slot inspector, Goo preview, and debugger. The published-template link exposes
Grove declarations and their compiled records; follow `note` and its role constraints in the
demo to inspect its role. Goo presentation is provided by `goo-inspector`;
the development mount itself no longer declares views.

Domain development rehearsal:

1. Open `extras/mounts/grove-dev/demo.grove` in your editor. Change the welcome
   content; save.
2. Click **Rebuild · reset to seeds**. The panel requests a fresh scan, waits for
   that scan's publication, and atomically replaces the instance. No Eden restart
   is needed. Runtime edits are reset. If the selected object was removed, the
   panel returns to the instance root.
3. Add a child tree, remove another, and rebuild. Inspect their slots.
4. Introduce a syntax error and rebuild. Diagnostics remain visible and the old
   instance remains installed. Fix the file and rebuild again.
5. Click **Delete instance subtree**, then **Install latest**. Deletion retains
   the published template and panel context, so reinstall works without a restart.

Rebuild is explicit: saving alone does not publish or reset anything. Compilation
failure prevents replacement. If publication succeeds but installation fails, the
old instance is retained and the differing published/installed versions remain
visible. A concurrent instance edit or newer publication rejects a stale request.
The management controls operate on independent Grove installations below `/app`;
they cannot remove publication roots or unrelated occupied roots. Core/Foil driver
changes require a service built with that code; restarting retains the saved service. Browser assets reload through mount rescan;
the Goo inspector provides a **Reload mount assets** button.

For an automated rehearsal against a disposable demo instance:

```sh
python3 extras/mounts/grove-dev/rehearse.py --url http://127.0.0.1:8144
node extras/mounts/explorer/test_grove_dev.mjs
```

The rehearsal temporarily edits the demo source, checks successful and failed
publication, replacement rollback guards, independent instances, deletion,
reinstallation, and debugger pages, then restores the source and live seed data.
On the local native runtime with `grove-dev` and `debugger` selected, the
rehearsal measured 1.9–4.9 seconds from rescan through atomic replacement
(1.1–4.0 seconds for publication); rejecting the syntax error took 1.9 seconds.
These are small-fixture measurements, excluding cold server startup.

The `/grove/dev/status` endpoint is read-only; management requests use POST and
carry the template version, instance subtree revision, and scan epoch observed by
the panel. Epochs and versions are decimal strings in JSON to avoid integer loss.

### Date and duration literals

Grove tree slots accept quoted temporal literals directly:

```grove
"/example" =
  @tree
  stamp: '@2026.9.30..12.0.0
  precise: '@@1969.7.21..2.56.15
  elapsed: '@h1.m30
```

The compiler stores these as `pails/dm`, `pails/ds`, and `pails/dr`, retaining
which timestamp precision or duration unit was supplied. Published `time` and
`duration` codecs accept these wrappers as well as their existing `pails/n`
values. Their numeric read/write APIs still expose the payload without unit
conversion; arithmetic must use the appropriate units.

Goo `show` on a `time` or `duration` field renders UTC timestamps and readable
unit groups. Tagged values also format through `text` and the object inspector.
Timestamp fractions retain their exact binary precision. Existing untagged
numeric `time` values render as `dm` (1,024 ticks/second from Apollo zero), and
numeric durations as milliseconds. Ordinary `number` values remain decimal.
The leading apostrophe and full date/time are required; date-only literals are
not supported.

The development mount includes `dates.grove`; open
`/grove/dev?selected=/0x11/app/demo/dates/example` for the live example.

## Goo inspector

`goo-inspector` is a small server-rendered Goo workspace with a bounded child
list and a synthetic Values pane. The shared browser adapter adopts the initial
HTML and attaches local selection/follow behavior. Its layout lives in
`extras/mounts/goo-inspector/inspector.grove`, using a path-typed receiver field
for the namespace source.

```sh
WISP=/path/to/wisp python3 x/eden --compiler none --mount goo-inspector --mount srs --port 8176
```

Open `/goo-inspector?path=/0x11/app/srs/cards` and select a child. Address changes,
Parent and Browse children links navigate to a new server-rendered workspace.
This version supports existing source records with at most 64 physical children;
matching-view catalogs, evidence, structural roots and pagination are deferred.
Edit the Grove layout or CSS, then use **Reload mount assets**. See
[the mount README](extras/mounts/goo-inspector/README.md) for details.

## Visual Grove playground

`grove-playground` provides a combined declaration/component patch canvas, ordinary
Goo editing forms, generated source export, and an isolated compiled preview at
`/grove-playground`. Semantic edits compile through Eden's namespace draft adapter;
publication into the separate `published` instance is explicit. The mount depends
on `explorer` and `codecs`. See [the playground README](extras/mounts/grove-playground/README.md)
for the matching Mash build, launch command, supported authoring model, and checks.

### Goo moodboard

`python3 x/eden --mount goo-moodboard --port 8135` serves `/goo-moodboard`:
notes, image references, and real live Goo subject presentations on the existing
patch canvas. Positions and card content are typed namespace data, with ordinary
Goo create/edit/delete forms and bound movement receipts. The default seed includes
an editable project brief. See `extras/mounts/goo-moodboard/README.md` for the shared
rendering boundaries, verification commands, and current limits.

### Goo documentation

`--mount goo-documentation` serves `/goo-documentation`: a Grove-authored namespace
outline with Documentation and Values tabs. It reads actual lore, source, and
reflected types through the shared Goo rendering and selection boundaries.
See [usage and integration](extras/mounts/goo-documentation/README.md).
