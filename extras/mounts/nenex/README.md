# Nenex

A personal wiki with a Goo page library, Mash's pinned renderer profile, and a
formatted semidoc reader. Run from the repository root:

```sh
x/eden --mount nenex --mount cooperate --compiler none --port 8131
```

Open [Nenex](http://127.0.0.1:8131/nenex). Use **Read page** in the library,
**Edit source** to edit multiline semidoc, and **Save page** to commit a revision.
Search and creation use the corpus's existing actions. Page names begin with a
letter or underscore and contain letters, digits, underscores or hyphens;
creating an existing name never overwrites that page.

Named child documents can be opened through `?path=` and linked from their parent.
Numbered prose children remain part of the containing page. The
[Semidoc flow harness](../flows/README.md) uses this to build a handbook with
concept documents from editorial briefs and captured source material:

```sh
x/eden --mount flows --mount codex --compiler none --port 8300
```

Open `/nenex?path=/0x11/app/nenex/w/handbook_flow` and attach maintenance.
Nenex and `/live` Cells run in the same world. Eden captures repository evidence;
the native filesystem foot notices stable changes and existing hands maintain
the handbook. No standalone observer or Python work runner is needed.

With `flows` mounted, **Page tools → Flows** creates a Semidoc authoring page,
publishes its saved definitions and attaches the shared native maintenance hand.
Input fields come from the published definition. Status and links expose the
output, revision drafts and working overlay; pause/resume use the same native
operations as other clients. See the flow harness's authoring contract for the
source syntax and evidence shape. No command-line client is required for these
actions. Page tools are typed mount contributions, so Nenex itself remains
independent of a particular flow recipe or provider.

The `cooperate` mount adds document-local agent runs through the MCP endpoint at
`http://127.0.0.1:8131/mcp`. See the [harness interface and client](../cooperate/README.md)
for captured context, branching traces and reusable results.

Eden restores the same native world across server restarts. Page sources, cells,
holes, frozen work and namespace history are saved together before a write is
acknowledged. `--world PATH` selects a world; `--ephemeral` creates a disposable
one. This uses the runtime's existing snapshot store, with no Nenex save format.

## Implementation

- `library.grove` declares the library's role, summary and local selection.
  The shared Goo host prepares its views, and the existing topology adapter
  renders and hydrates its members using Mash's profile. Navigation links open
  the formatted page; selecting a library row does not write wiki state.
- `interface.foil` registers `/nenex` and builds a workspace receiver rooted at
  the existing wiki corpus. Its browser responder delegates library construction
  to `goo_workspace`. The reader uses the existing live document fragment,
  backlinks, source form and history scrubber.
- `style.css` styles the reader shell and Semidoc source form. It does not
  change the measured geometry or typography of Goo's prepared surfaces.
- `interface.js` handles disclosure anchors, active-page decoration, local wiki
  links and the source form's unsaved-change warning. It submits the existing
  source form with progress and failure feedback, preserving the draft on errors.
  It does not interpret Goo layouts or maintain a second library model.
- `main.foil` retains the wiki domain. The derived `sys/lede` slot feeds the
  Goo summary and is excluded from semidoc's record/source synchronization.

Document expansion retains the normalized source projection in native system
metadata. Synchronization reuses that projection while the source is unchanged,
so changes to named work or inputs do not repeatedly parse large evidence
documents. Source edits replace it in the expansion transaction; direct edits to
numbered prose still regenerate canonical source. The retained projection is
excluded from document content and Semidoc export.

The reader's **Edit with Goo** link opens `/nenex/edit?path=<namespace path>`.
The whole document is a continuous sequence of native Grove/Goo block views.
Each field still belongs to its original `text`, `title`, `lead` or `body` slot.
Select text for the formatting toolbar; type `/` for Text, Heading, Bullet list,
Quote and Code. Enter splits a block (inside code it inserts a newline), and
Shift+Enter inserts a soft newline. Backspace at the start joins compatible
siblings. The focused block exposes Save, insert-after, move-up/down and Delete.
Blur saves that block; Ctrl/Cmd+S saves dirty blocks in order. References remain
links, including their embed descriptors. The shell adds no handwritten CSS.

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
The source form uses the same guard and native admission. Work, cell and hole
updates do not invalidate an otherwise unchanged document; changed source does.
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

The wiki checks cover links, search, source/record synchronization, derived
library titles, browser form line endings and duplicate/invalid page names. Browser verification should
cover library navigation, create/search, multiline save, discard, dirty departure,
history, and a narrow viewport against a disposable development namespace.

## Page and block questions

The reader's **Ask** link opens **Questions**. Ask about the page or select a
block quotation; optionally bind additional namespace paths or `/x/...` cell
results. With Codex mounted, its existing native work provider is preselected.
The form submits one native operation. A shared answering hand owns dispatch,
captured attempts, missing-evidence holes and re-answering when context changes.
The answer is an ordinary cell and a live reader fragment, with inspection links
for the context and attempts. Pause/resume uses the same native operation.

The primary lens projects authored page source, excluding backlinks, work and
answer metadata to prevent self-triggering. Block questions keep their original
quote and original location under the page's named work/cell subtrees. Numbered
block paths are positional: reordering or deleting prose cannot silently change
that quote. **Change the quoted selection** explicitly rebinds it; prior attempts
remain frozen. The current page stays live in either scope.

The answering provider receives only the bound, bounded context. It does not
browse or crawl automatically. A fetcher can publish evidence records or cells
and bind them through the same interface; native answering does not require a
separate web or Python scheduling loop. Questions, captured evidence and unresolved
holes share the same native world persistence as the rest of the page.

The **Cells** section embeds the existing live Cells renderer over native cells.
Flow outputs expose their maintenance work here, with status, concept drafts,
evidence bindings and persistent holes. Opening a draft exposes its working
overlay and **Accept saved draft**, which calls the same guarded native revision
operation used by providers. Reading or navigating cells never executes work.
The reader subscribes only to the corpus root for search state, avoiding a
subscription to every capture and attempt in the wiki.
