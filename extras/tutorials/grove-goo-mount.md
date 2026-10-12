# Making a Grove and Goo mount


> For a workspace that only needs a path receiver and the standard page shell,
> the [declarative workspace registration](../../MOUNTS.md#declarative-goo-workspaces)
> now replaces the manual host shown below. This tutorial keeps the explicit
> Foil path to explain the interfaces and support custom data and operations.

Build a small notes application with two seeded records, a selectable list, a
reader, and an editor. The application will run at `/hello-grove`, use ordinary
Goo selection and action bindings, and save edits into the running Shrine
namespace. It needs no application JavaScript.

This tutorial uses the host interface implemented in this checkout. The declarative
workspace registration is available, but this example uses a custom host.
The Foil glue is included in full, including publication-to-instance installation
and the HTTP route.

The complete example is in [hello-grove](../mounts/hello-grove/). You can run it
first, then read the construction steps. If you want to build it yourself, use
those files as checkpoints; the code blocks below assemble the same four runtime
files. Run shell commands from the repository root.

## Run the finished example

You need this Reaver checkout, Nix with flakes support, and the toolchain used by
Eden and the Explorer mount. The launcher enters its Nix environment; Explorer's
host hook prepares the shared browser assets. The first run may build or fetch
those dependencies.

```sh
python3 x/eden --list-mounts
python3 x/eden --compiler none --mount hello-grove --port 8137
```

`--compiler none` uses the boot compiler instead of installing an optimizing
compiler tier. Grove and Foil still compile. If port 8137 is occupied, choose a
free port and use it in the browser URL too.

Wait for the `Eden: http://127.0.0.1:8137` line, then open
[Hello Grove](http://127.0.0.1:8137/hello-grove).

1. Select **First note** in the list.
2. Read **Hello from Grove.** in the reader.
3. Choose **Edit** and change the note's body.
4. Choose **Save and read**.
5. Reload the browser and select **First note** again. The saved body remains.

A browser reload does not restart the namespace. This development launcher stages
a fresh namespace for each new server run: stopping and restarting it restores
the seeds. It is not a production persistence configuration. Selection is local
to the page, so reselect the note after a reload.

For development against a sibling Mash checkout, the existing asset build hook
also accepts `GOO_PATCH_MASH_ROOT=/path/to/mash`. The ordinary launch command uses
the configured dependencies; you do not need to add a frontend package to this
mount.

## Understand the four layers

A mount is a package of source definitions, optional assets, and entrypoints.
Eden loads it and its dependencies. Grove declares records, roles, views, and
pane structure. Goo executes the presentation and interaction model. A small
Foil host connects a browser route to an installed workspace.

| Layer | In this example | Responsibility |
| --- | --- | --- |
| Packaging | `mount.json` | Name, dependencies, source mapping, publication roots, assets, and hooks |
| Application | `main.grove` | Note role, seed records, views, selection, panes, and edit binding |
| Hosting | `mount.foil` | Instantiate the template, construct the workspace receiver, and serve the page |
| Appearance | `style.css` | Page framing and responsive pane proportions |

A **slot** identifies a property in a record. A **role** describes which slots and
types a record must satisfy. A **view** presents a matching record for a named
presentation purpose. A **pane** composes local interaction structures such as
selections and followers. A **topos** presents the members of a source: here it
is a list. The selection owner records the user's choice, and the follower
presents that chosen subject.

Keep these three namespace locations distinct. With the default node `0x11`:

| Location | Meaning |
| --- | --- |
| `/0x11/io/fs/hello-grove` | Mount source and publication control record |
| `/0x11/gov/hello_grove` | Published Grove declarations and installable template |
| `/0x11/app/hello_grove` | Installed application data |

For example, `.../gov/hello_grove/note` is the role declaration;
`.../app/hello_grove/notes/first` is a note you can edit. Publishing a template and
instantiating its records are separate operations.

## Create the source bag

The checked-in example has this runtime layout:

```text
extras/mounts/hello-grove/
  mount.json
  main.grove
  mount.foil
  style.css
```

The README and browser check beside them are supporting material. Mount source
bags use flat filenames. A logical module name may contain slashes, but its
manifest mapping must point to a filename directly inside the bag.

Create `mount.json`:

```json
{
  "version": 1,
  "name": "hello-grove",
  "dependencies": [
    "explorer",
    "codecs"
  ],
  "modules": {
    "hello_grove_mount": "mount.foil"
  },
  "grove": [
    {
      "root": [
        "gov",
        "hello_grove"
      ],
      "files": [
        "main.grove"
      ]
    }
  ],
  "assets": {
    "/hello-grove/style.css": "style.css"
  },
  "files": {},
  "roots": [
    [
      "lib",
      "hello_grove_mount"
    ],
    [
      "gov",
      "hello_grove"
    ]
  ],
  "tests": {},
  "activate": {
    "module": "hello_grove_mount",
    "entry": [
      "hello_grove_mount",
      "install"
    ]
  },
  "http": {
    "module": "hello_grove_mount",
    "entry": [
      "hello_grove_mount",
      "http"
    ]
  },
  "routes": [
    "/hello-grove"
  ]
}
```

The mount name matches its directory. `modules` maps the logical Foil module
`hello_grove_mount` to `mount.foil`. The `grove` entry publishes `main.grove` under
`gov/hello_grove`; Eden supplies the node prefix. `roots` must agree with the
outputs declared by the Foil and Grove mappings. They describe publication
ownership, not the application's installed data root.

The Explorer dependency supplies the shared Goo browser host, assets, and
render/action endpoints. This example follows the existing workspace mounts by
also declaring `codecs`. The manifest does not need to list each transitive
dependency individually.

`activate` and `http` name actual exported Foil entrypoints. A `routes` claim alone
does not implement a handler. `assets` makes the stylesheet a required published
asset. The empty `tests` and `files` mappings contain no runtime logic; the former
can later register native test modules, and the latter is migration inventory.
There is no Python `host` hook or post-start driver in this mount.

## Define the records and workspace input

Start `main.grove` with:

```plaintext
#import text=lib/grove/types/text
#import path_type=lib/grove/types/path
#import lede=sys/lede
#import content=sys/content

source_path =
  @slot

context =
  @role
  %/source_path: path_type

note =
  @role
  lede: text
  content: text
```

`#import` gives a local name to an existing declaration. `lede` and `content` are
shared data slots; `text` and `path_type` are existing Grove type declarations.

The note role requires both text fields. It does not create any note instances.
The separate `context` role is the workspace's input contract: its `source_path`
field tells the list which collection to browse.

`%/source_path` resolves within this Grove publication. After publication its
identity is `/0x11/gov/hello_grove/source_path`. The host uses that exact slot to
construct the receiver. The list and reader eventually operate on the actual
note records, not on that temporary context record.

Some syntax to recognize before proceeding:

- `@role`, `@view`, `@pane`, and `@tree` identify declaration kinds.
- `#on ;` identifies the receiver role of a presentation.
- `#for ;` identifies the purpose, or presentation slot, that the view serves.
- `%/name` refers to a declaration in the current Grove unit.
- `'/sys/slot/label` is a path literal used as a constructor argument.
- `record => { ... }` names the presentation's receiver and defines its body.

These are namespace references. A quoted path such as `'/current` inside a
selection is a local interaction key, not a request to create a namespace record
at `/current`.

## Add summary and detail views

Append:

```plaintext
summary =
  @view
  #on ; %/note
  #for ; /sys/slot/hello_note_summary
  note => { show(note.lede, '/sys/slot/label) }

detail =
  @view
  #on ; %/note
  #for ; /sys/slot/hello_note_detail
  note => {
    show(note.lede, '/sys/slot/title)
    show(note.content, '/sys/slot/content)
    action("Edit", become = '/sys/slot/hello_note_edit)
  }
```

Both views accept the note role, but serve different presentation slots. The list
will request `hello_note_summary`; the follower will request `hello_note_detail`.
The distinctive names keep this example's recipes separate from recipes using
common slots elsewhere in the application.

Inside a view, `show` presents a value using the indicated Goo presentation slot.
Here the note's `lede` is a compact label in the list and a title in the reader.
The body is shown as content.

The **Edit** button uses `become` to ask the current presentation encounter to use
the edit recipe. Pressing it alone does not write a domain record. The selected
subject remains the same note.

The server resolves the view and prepares its content and dimensions. This mount
uses the existing browser renderer and does not measure its text or implement its
own layout engine.

## Add the editor

Append:

```plaintext
edit =
  @view
  #on ; %/note
  #for ; /sys/slot/hello_note_edit
  note => group(on = note, action = .poke, myth = {
    '/sys/lede = .input(note.lede)
    '/sys/content = .input(note.content)
  }) {
    input('/sys/lede)
    input('/sys/content)
    action("Save and read", become = '/sys/slot/hello_note_detail)
  }
```

The group establishes the action binding for its children. `on = note` identifies
the writable receiver; `.poke` uses the existing record update action. The `myth`
map associates the two real namespace slots with captured input values.

`.input(note.lede)` and `.input(note.content)` initialize editable fields from the
receiver. The corresponding `input` constructors render those bound controls.
**Save and read** submits the action and requests the detail recipe after a
successful save.

This is enough for ordinary field editing. You do not need to handwrite a fetch
handler, mutate browser data and later synchronize it, or define a custom action
for this example. The existing action boundary checks the binding and current
version evidence. A stale or rejected edit must not be treated as a successful
save. Goo also owns dirty-input and composition handling during refreshes.

Use a declared domain action when an operation has additional business meaning,
validation, or a multi-record effect. Keep that operation on the server and bind
it through Goo rather than adding an unrelated client write path.

## Connect the list and reader

Append the workspace and two child panes:

```plaintext
workspace =
  @pane
  #on ; %/context
  #for ; /sys/slot/hello_workspace
  context => selection('/current, source = context.source_path) {
    split {
      pane(%/Notes, ports = { '/current = '/current })
      pane(%/Reader, ports = { '/current = '/current })
    }
  }

Notes =
  @pane
  #on ; %/context
  #for ; /sys/slot/pane/HelloNotes
  #port ; /current
  context => {
    list('/notes, source = context.source_path, selection = '/current, slot = '/sys/slot/hello_note_summary)
  }

Reader =
  @pane
  #on ; %/context
  #for ; /sys/slot/pane/HelloReader
  #port ; /current
  context => {
    follow('/note, selection = '/current, slot = '/sys/slot/hello_note_detail)
  }
```

There are two different inputs here. `context.source_path` is a namespace path
supplied by the host. `'/current` is a local selection channel shared by the list
and follower.

The entry pane creates the selection owner. Its source is the notes collection.
Each child pane declares an external `#port` for that selection, and the parent
connects it with `ports = { '/current = '/current }`. The pane bodies use the
context receiver to locate data and the port to share the current choice.

The `list` projects members and renders each with the summary recipe. `follow`
uses the accepted selected member as its subject and requests the detail recipe.
The entry pane itself has no unconnected external ports, so the workspace host
can instantiate it.

No initial selection is specified. The reader starts by asking you to choose a
member. Selection belongs to this page's local session, while saved text belongs
to the namespace.

This simple flat list uses the shared finite-source limit of 64 members. For a
large hierarchical namespace, use `topology = "tree"` on the selection and
`list_tree` as the projection, as the documentation mount does. Its shared loader
pages children on expansion. That is a deliberate extension; do not assume this
flat example provides unlimited loading.

## Seed two notes

Finish `main.grove` with:

```plaintext
"/" =
  @tree

"/notes" =
  @tree
  lede: "Tutorial notes"

"/notes/first" =
  @tree
  lede: "First note"
  content: "Hello from Grove."

"/notes/second" =
  @tree
  lede: "Second note"
  content: "Selection connects the list to the reader."
```

The quoted paths are installation paths relative to the instance root. Installing
at `/0x11/app/hello_grove` creates `notes/first` and `notes/second` below it. Their
values satisfy the note role because both required slots contain text.

The `/notes` parent supplies a collection label. The flat list shows its children,
so that parent does not need to satisfy the note role.

Seeds describe initial installed content. Editing a note does not rewrite this
Grove file. Conversely, changing these strings in the source does not migrate an
already installed note. Keep that distinction in mind when testing source changes.

## Write the small Foil host

Create `mount.foil` beginning with:

```plaintext
- explorer_mount
- goo_workspace

+ hello_grove_mount
```

Append each of the following blocks under that top-level declaration. The two-space
indentation is significant. The complete assembled file is also available in
[the companion mount](../mounts/hello-grove/mount.foil).

Foil conventions used below are `\` for a function, `^` for its return type, `=`
for local bindings, and `|` for application. `?>` pattern-matches a value with a
fallback when it does not match. The host uses existing typed functions, so their
signatures define the integration boundary.

### Configure the endpoint

```plaintext
  + endpoint
    \ self=iota
    ^ goo_workspace/endpoint
    | goo_workspace/endpoint [self 'gov 'hello_grove 'workspace]
        [self 'gov 'hello_grove 'source_path] [self 'app 'hello_grove 'notes]
        hello_grove_mount/validate [] (hello_grove_mount/page self)
  + validate
    \ selected=axal[myth]
    ^ maybe[str]
    ? selected.wyt .none
    | ./some "Choose an existing collection of notes."
```

`goo_workspace/endpoint` takes six arguments, in order:

| Argument | Value supplied here |
| --- | --- |
| Entry pane | The published `workspace` declaration |
| Receiver slot | The published `source_path` slot |
| Default subject | The installed notes collection |
| Subject validator | Require an existing namespace location |
| Host operations | Empty list |
| Document function | The page shell below |

`self` is the running node identity. Using it here lets the mount run under a
node other than `0x11`. The validator checks existence; it is not a proof that all
children satisfy the note role. This workspace is intended for collections of
notes. A broader browser needs broader member views or explicit fallback recipes.

### Parse the URL and register its handler

```plaintext
  + query_valid
    \ target=str
    ^ bool
    = parts (http_foot/split 63 target)
    ? (gt parts.len 2) .false
    = query=str (? (eq parts.len 2) parts.at(1) "")
    ? (eq query.len 0) .true
    ?> (./ok fields) (Try[str row[[str str]]] http_foot/fields query) .false
    ? !(eq fields.len 1) .false
    = [key value] fields.at(0)
    | and (eq key "path") (maybe/is_some (browser_routes/value_path value))
  + http
    \ files=row[[str nat]] state=namespace
    ^ http_foot/config
    = plan
        \ request=http_foot/request now=nat
        ^ http_foot/action
        ? !(eq request.method "GET") (./reply (http_driver/response 405 "GET required"))
        = url (http_foot/split 63 request.target).at(0)
        ? ((eq url "/hello-grove") || (eq url "/hello-grove/"))
          ? !(hello_grove_mount/query_valid request.target)
            | ./reply (http_driver/response 400 "Use one canonical absolute namespace path.")
          | goo_workspace/request (hello_grove_mount/endpoint state.self) request now
        ? !(eq url "/hello-grove/style.css") (./reply (http_driver/response 404 "Not found"))
        = found (files.keep((\ [key bytes] (eq key "style.css"))))
        ? !(found.len) (./reply (http_driver/response 404 "Not found"))
        = [name bytes] found.at(0)
        | ./bytes 200 bytes "text/css"
    | http_foot/add_routes [(http_foot/route "/hello-grove" plan)] http_foot/empty
```

The route accepts GET and an optional single canonical `path` query parameter.
For example, with the default node:

```text
http://127.0.0.1:8137/hello-grove?path=%2F0x11%2Fapp%2Fhello_grove%2Fnotes
```

Malformed, duplicate, and unknown query fields are rejected. The URL selects the
subject collection; the host fixes the entry pane and receiver slot.

`goo_workspace/request` asks the existing namespace/HTTP machinery for the subject
and view catalog needed to render the workspace. This function returns an HTTP
action; it does not implement a second request server. The stylesheet is also
declared in the manifest and participates in the existing asset publication path.

The mutation endpoint is already supplied by Explorer. Saving a note does not
POST to `/hello-grove`; the shared action adapter sends the bound operation to
the existing Goo action boundary.

### Wrap the workspace in a page

```plaintext
  + page
    \ self=iota target=path content=row[weft/node]
    ^ nat
    = assets (goo_browser/presentation_assets).snoc((weft/el "script" [(weft/att "src" "/static/goo-workspace.js") (weft/att "defer" "defer")] []))
      assets assets.snoc((weft/el "link" [(weft/att "rel" "stylesheet") (weft/href "/hello-grove/style.css")] []))
    | weft/page_with_assets "Hello Grove" assets
      [(weft/el "header" [] [(weft/leaf "h1" [] "Hello Grove")
         (weft/leaf "p" [] "Select a note, read it, and edit its text.")])
       (weft/el "main" [] content)]
```

`goo_browser/presentation_assets` supplies the shared Goo assets. The additional
workspace script mounts the server-provided workspace description. The final link
adds the application's stylesheet.

`content` already contains the shared workspace wrappers and initial server HTML.
Keep those wrappers: they carry the declaration, subject, description, and local
session boundary that the browser needs. The shell supplies the surrounding
header and document, not another copy of the selection or application state.

### Install the data and workspace host

```plaintext
  + install
    \ state=namespace
    ^ either[pail namespace]
    = source=path [state.self 'gov 'hello_grove]
      target=path [state.self 'app 'hello_grove]
    ?> (./some version) state.case(.x source) (./err (pails/t "Hello Grove publication is missing."))
    ?> (./ok next) (grove_install/instantiate source version target state)
      | ./err (pails/t "Hello Grove instance could not be installed." )
    | goo_workspace/install (hello_grove_mount/endpoint state.self) goo_browser/talk next
```

Eden calls the activation hook after publishing the selected mounts. The source
path identifies the published template. Its current version is passed explicitly
to `grove_install/instantiate`, which creates the instance at the chosen target.
The operation is fallible; this example reports a startup failure instead of
continuing with an empty application.

Then `goo_workspace/install` registers the hosted receiver and connects the
workspace response handling to the existing browser host. It receives `next`, the
namespace returned by installation, so the newly created notes are present.

This activation hook is intended for the launcher's fresh namespace. It does not
overwrite an occupied instance or implement migration. A production startup path
that reopens an existing namespace must decide explicitly whether to reuse,
install, or migrate its application data.

## Add a little styling

Create `style.css`:

```css
body { margin: 0; color: #24352a; background: #f6f8f2; font: 15px/1.6 system-ui, sans-serif; }
header, main { max-width: 1100px; margin: auto; padding: 20px; }
header h1 { margin-bottom: 0; font-family: Georgia, serif; }
header p { color: #657467; }
.goo-split { grid-template-columns: minmax(220px, 1fr) minmax(0, 2fr); gap: 20px; }
.goo-pane { min-width: 0; }
.preview > h2, .preview > .meta { display: none; }
@media (max-width: 720px) { .goo-split { grid-template-columns: 1fr; } }
```

These rules style the outer document and allocate space between panes. Goo retains
ownership of prepared view content and control behavior. The two columns stack
at narrow widths; the shared render boundary selects the applicable pane-width
layout.

You now have all four runtime files. Start the mount with the command at the top
and perform the read/edit/save/reload walkthrough.

## Follow one interaction through the system

On startup, Eden captures mount source files, compiles and publishes the Grove,
then calls `install` to instantiate the notes and register the workspace host.

On GET `/hello-grove`, the endpoint chooses the default collection. The shared
host supplies a context record containing its path, validates the workspace
contract, prepares its pane description, and produces the initial wrappers. The
shared browser code hydrates the local session and obtains the member
presentations through the existing render boundary.

Selecting **First note** delivers a member reference to `'/current`. The session
admits that reference against its source. The follower renders the selected
namespace subject with the detail recipe. Choosing **Edit** changes the encounter's
recipe. Saving captures input values and submits the admitted action against that
same subject. The accepted update changes the namespace and refreshes the
presentation through the existing runtime.

The list, follower, and editor never need an independent JavaScript notes array.
The server remains the authority for the record and the action result.

## Change and verify the example

For a straightforward first experiment, change the second note's seeded content,
stop this disposable demo, and start it again. The new instance will contain the
new seed. Do not use restart as a persistence strategy for real application data.

Source rescan is a separate tool: it publishes a successful candidate or retains
the previous successful publication on failure. It does not rerun activation,
reset existing instances, or replace captured HTTP handler code. Changes to host
Foil or route contracts require restarting this host. See
[the mount lifecycle](../../MOUNTS.md#explicit-rescan) before adding a rescan or
reset control to a real application.

To check activation and HTTP types, use the core development environment or set
`WISP` to a working runtime, then run:

```sh
WISP=/path/to/wisp python3 extras/x/check --mount hello-grove --contracts-only
```

This validates hooks; it does not exercise the UI. The companion browser check
performs the real edit/save/reload flow against a running instance:

```sh
node extras/mounts/hello-grove/check-browser.mjs \
  http://127.0.0.1:8137 /path/to/mash /tmp/hello-grove-browser
```

It uses the Playwright installation from Mash's integration-test dependencies.
Its edits target only this tutorial's first note and restore the original text.
The test server should be a disposable tutorial instance. Verification results
for this example are recorded in its [README](../mounts/hello-grove/README.md).

Useful next exercises are adding a third seed, changing the detail layout with
`row` and `col`, and adding a second follower that uses
`'/sys/slot/synthetic` to inspect the same selected note. A follower within the
same selection scope can use the existing channel; a separate child pane needs
a declared and connected port.

## Diagnose common mistakes

| Symptom | What to inspect |
| --- | --- |
| Mount is absent from `--list-mounts` | Directory, manifest name/version, and the selected extras root |
| Startup rejects publication ownership | `roots` must match the declared Foil and Grove outputs |
| Definitions exist but notes do not | The activation hook must instantiate the template under `/app` |
| Workspace reports a receiver mismatch | Its role slot and the host's `source_slot` must identify the same declaration |
| Reader stays empty | Select a member and check that both child ports connect to the same selection owner |
| View is unavailable or ambiguous | Check required role fields, presentation slot, and competing matching views |
| Only the outer HTML appears | Confirm the shared asset URLs and workspace script load successfully |
| Save is rejected | Inspect action/version evidence; do not bypass admission with a direct client write |
| Changed seed text does not appear | Existing instances keep their records; rescan does not reinstall seeds |
| Edits disappear after server restart | This launcher creates a new staged namespace on each run |

Eden prints the path to its native log during startup. Use that log for compiler
and publication errors. Browser network responses and **Inspect a presentation**
help distinguish a bad recipe, a receiver mismatch, and a stale interaction.

For further detail, read [the pane interface](../mounts/explorer/PANES.md),
[application integration](../mounts/explorer/APPLICATION-INTEGRATION.md), and
[the documentation mount](../mounts/goo-documentation/README.md).
