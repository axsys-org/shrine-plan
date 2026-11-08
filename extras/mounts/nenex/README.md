# Nenex

See the [shared harness ownership map](../../HARNESS.md) for responsibilities
and integration boundaries.

Nenex presents existing namespace documents as a continuous Grove/Goo page tree:

```sh
x/eden --mount nenex --mount cooperate --compiler none --port 8131
```

Open [Nenex](http://127.0.0.1:8131/nenex). The library opens its native page
frontier; pages prepare their existing block controls as they enter the viewport.
Expand a page's **Child pages** disclosure to open its next native frontier.
**Load more pages** follows the native child cursor. Opening the library does not
walk every page, work attempt or capture in the world. Accepted page actions
refresh their existing native frontiers, keeping unchanged open pages and drafts.

Each page's **Page actions** offers Semidoc source editing, page/block questions,
and creation. The library also offers creation and native search; its record
inspector exposes the retained query and result paths. Page names begin with a
letter or underscore and contain letters, digits, underscores or hyphens;
creating an existing name never overwrites it.

Named child documents can be opened through `?path=` and linked from their parent.
Numbered prose children remain part of the containing page. The
[Semidoc flow harness](../flows/README.md) uses this to build a handbook with
concept documents from editorial briefs and captured source material:

```sh
x/eden --mount flow-examples --mount codex --compiler none --port 8300
```

Open Nenex's example catalogue, create the **handbook** example, publish its
saved definition and attach maintenance. An existing `handbook_flow` page is not
assumed. Nenex and its native cell surfaces run in the same world; add the
optional `inspector` mount if you also want the standalone `/live` view.
Eden captures repository evidence;
the native filesystem foot notices stable changes and existing hands maintain
the handbook. No standalone observer or Python work runner is needed.

With `flows` mounted, its declared page-tool views author and publish Semidoc
flows and attach the shared native maintenance hand. These views invoke the same
native operations as reflected/headless clients. Optional examples come from the
separate `flow-examples` mount; Nenex does not assume any flow recipe or provider.

An authored embed retains its reference and descriptor on the original Semidoc
block. A descriptor can explicitly name a published Goo view through
`/goo/view`; the view receives the referenced native object. Optional
`/goo/cells` path rows select relative native cells for read-only inspection.
Repeated occurrences share their receiver, while each occurrence keeps its own
block address and local presentation. An unavailable or incompatible descriptor
leaves its reference inspectable and its source intact.

Question controls bind the native question controller. Current answer text comes
from its reactive `/x/<controller>/answer` cell, so changed or missing evidence
does not expose a retained answer as current. A conflicted current output remains
inspectable with its native error. Native cells, context, holes, connections and
history are lazy related views over their real namespace paths. They use the
shared Goo host and `/ns` inspector; the optional standalone `/live` viewer is
not required.

The `cooperate` mount adds document-local agent runs through the MCP endpoint at
`http://127.0.0.1:8131/mcp`. See the [harness interface and client](../cooperate/README.md)
for captured context, branching traces and reusable results.

An explicit Eden snapshot restores the namespace across server restarts. Page sources, cells,
holes, frozen work and namespace history are saved together before a write is
acknowledged. Use `--snapshot PATH` and repeat the mount selection to resume it;
without this option the invocation is disposable. This uses the runtime's
existing snapshot store, with no Nenex save format.

## Implementation

- `main.foil` owns wiki source expansion, reconciliation, links and search.
- `editor.foil` and `editor.grove` expose native per-block operations. Source
  and rich editing update those same records through normal admission.
- `tools.foil` and `tools.grove` declare page/library, answering and hole controls.
  The adapters hold no work, document, retry or watcher state.
- `editor_http.foil` exposes one ephemeral manifest per page and a paged native
  `.y` frontier. The shared `explorer/goo-document.js` keeps only local prepared
  controls, input drafts and focus. Refreshing one page fetches only that page's
  manifest; each page retains its own epoch and structural-edit scope.
- `interface.foil` routes `/nenex` and `/nenex/edit` to this same document surface.
  The former reader application script, stylesheet and handwritten forms are
  removed. The original native Weft face remains available through `/ns`; it is
  not a second primary Nenex route.

Mounts contribute optional tools at `/gov/nenex_ui/tools/<name>` with an explicit
`/goo/view` path, optional `/goo/target` receiver (default: current page), and
`/sys/lede` label. Tool views prepare when opened, rather than mounting every
form for every page. Page children, source blocks, work and cells remain native
namespace ownership boundaries.

Document expansion retains the normalized source projection in native system
metadata. Synchronization reuses that projection while the source is unchanged,
so changes to named work or inputs do not repeatedly parse large evidence
documents. Source edits replace it in the expansion transaction; direct edits to
numbered prose still regenerate canonical source. The retained projection is
excluded from document content and Semidoc export.

Semidoc attributes retain their cardinality and value types in those same native
records. A single word or reference uses the existing text/path pail. Repeated,
multi-value and valueless attributes use `semidoc/sattr/occurrences` in the
predicate's slot, preserving occurrence order, value boundaries and references.
Predicate order is canonicalized; lexical aliases remain expanded paths.
Source and Goo edits therefore preserve authored flow bindings and relationships.
Native record edits apply their changed slots against the existing captured
projection and authored source, so an older, less expressive projection cannot
erase untouched declarations. This uses the existing source and image; it adds
no document record, history format or migration pass. This is slot reconciliation,
not a general concurrent merge: source and Goo edits retain their native version
guards, and block reordering refuses named descendants attached below prose.

`/nenex?path=<namespace path>` and `/nenex/edit?path=<namespace path>` open
the same native editor. The whole document is a continuous sequence of native Grove/Goo block views.
Each field still belongs to its original `text`, `title`, `lead` or `body` slot.
Select text for the formatting toolbar; type `/` for Text, Heading, Bullet list,
Quote and Code. Enter splits a block (inside code it inserts a newline), and
Shift+Enter inserts a soft newline. Backspace at the start joins compatible
siblings. The focused block exposes Save, insert-after, move-up/down and Delete.
Blur saves that block; Ctrl/Cmd+S saves dirty blocks in order. References retain their original targets and explicit embed descriptors;
compatible declared Goo embeds are interactive. The shell adds no handwritten CSS.

The slash menu changes real Semidoc node kinds. Heading Enter creates its first
paragraph child. Moving a container carries its children; deleting a container
or converting it to a leaf refuses while it has children. Structural edits
refuse when numbered content contains named descendants, so renumbering cannot
silently destroy attached work. Named root subtrees (`inputs`, `cells`, `work`,
named child documents) are excluded from editing and survive every operation.
Numbered addresses remain positional, as in Semidoc source editing.

The shared `goo-document.js` host keeps only local input drafts, prepared control
evidence and focus. It reads an ephemeral path manifest and activates published
Grove controls through `GooActions`; it does not parse Semidoc or store a second
document model. Structural writes flush other drafts first, freeze editing while
in flight, and compare authored content against the captured native epoch.
The declared source action uses the same guard and native admission. Work, cell and hole
updates do not invalidate an otherwise unchanged document; changed source or
numbered document records do, even when a reconciliation conflict retains the
same source text.
Refusals retain the draft. If a reply or the subsequent refresh is lost,
Ctrl/Cmd+S resumes the captured change with the same invocation. Structural
editing stays frozen until it settles. The
rich-block viewport uses native Goo typography and expands locally with text.

`editor.grove` publishes a native namespace operation from `editor.foil` in
each block action's metadata, so reloads retain the domain commit path.
The shared Goo runtime checks the presented receiver, revision, publication and
bound inputs before invoking it. The operation regenerates source from the
current page subtree and commits through Nenex's existing expansion transaction.
There is no editor document record or flattened copy of the page. Named children
such as `inputs`, `cells`, `work` and nested named documents are outside that
projection and remain intact.

A retained source projection from an unknown publication is never treated as
proof of an intentional native deletion. Faithful unchanged content remains
readable; a disagreement preserves source and records and requires explicit
resolution through a fresh source edit.

The retained source projection is a reconciliation baseline, not a concurrent
merge engine. With a faithful baseline, native edits remain authoritative.
When an older projection omitted authored relationships, automatic recovery
accepts only one text-field change at an unchanged position. Structural changes,
relationship edits, or conflicting source text retain both sides and report a
conflict instead of transferring hidden bindings to a different block. Goo
serialization refuses that conflict; submitting a fresh source edit explicitly
selects the source to expand. Old records and their x/y/z cases remain available.
Reverting the conflicting native edit also clears the reconciliation error.
For numbered blocks with named work beneath them, source editing also refuses
changes beyond a single text edit: positional source cannot safely identify
which work should follow a moved block. Root-level named children are unaffected.

Rich fields contain the shared `goo/text/pail` value. Semidoc export carries the
same run value in a reserved `;@ /doc/rich` hexadecimal JSON attribute on that
node, with its readable text encoded as a JSON string. This preserves blank
paragraphs, whitespace, newlines and text beginning with Semidoc block markers.
Import checks the text against the run payload before accepting the source.
To replace a formatted field manually with plain Semidoc, remove its `/doc/rich`
attribute and author ordinary text. Inconsistent metadata rejects the source
transaction and keeps the previous document.

The browser maintains only local rich-input drafts and selection; native Foil
owns formatting commands and commits. The current editor bounds a document to
256 numbered nodes and 192 KiB of source, and uses Goo's current ASCII input
contract. A block outside that contract displays a diagnostic while the remaining
blocks stay editable; its source is unchanged. The original `/ns/<node>/app/nenex` view remains available.

## Checks

```sh
WISP=/path/to/wisp python3 extras/x/check --mount nenex
```

Native checks cover links, repeated relationship occurrences, search,
source/record synchronization, retained image ownership, source and Goo guards,
named attachments and prior x/y/z history. The `nenex-document-tests` gate
compiles the production Grove source and block editors, invokes their actual
controls for source, block editing, creation, questions and holes, and checks
native frontier continuation and independent page manifests. The shared document
host tests cover page-local drafts/epochs, native embed receivers, lazy tools and
same-invocation recovery after a lost response.

## Page and block questions

Choose **Page actions → Ask about a page or block**. Supply a question name,
question, `page` or a numbered block path, and optional additional evidence paths
(one per line). With Codex mounted, its native work provider is the default.
The declared action invokes shared answering; its hand owns captured attempts,
missing-evidence holes and re-answering. Question controls pause/resume and
explicitly rebind the quoted selection. Hole controls resolve the exact current
attempt and generation. Current answer output and retained attempts stay separate.

The primary lens projects authored page source, excluding backlinks, work and
answer metadata to prevent self-triggering. Block questions keep their original
quote and original location under the page's named work/cell subtrees. Numbered
block paths are positional: reordering or deleting prose cannot silently change
that quote. **Bind current page or block selection** explicitly rebinds it; prior attempts
remain frozen. The current page stays live in either scope.

The answering provider receives only the bound, bounded context. It does not
browse or crawl automatically. A fetcher can publish evidence records or cells
and bind them through the same interface; native answering does not require a
separate web or Python scheduling loop. Questions, captured evidence and unresolved
holes share the same native world persistence as the rest of the page.

Related native cell views are read-only inspection surfaces. Flow occurrence
controls come from the flow's declared view and operate on its existing work
controller. Reading a cell or opening a document does not invoke a flow.
