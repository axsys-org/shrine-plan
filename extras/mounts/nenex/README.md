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

The `cooperate` mount adds document-local agent runs through the MCP endpoint at
`http://127.0.0.1:8131/mcp`. See the [harness interface and client](../cooperate/README.md)
for captured context, branching traces and reusable results.

The development launcher creates a fresh namespace on each restart. Browser
reloads preserve edits within that running namespace. This is not durable storage
across server restarts.

## Implementation

- `library.grove` declares the library's role, summary and local selection.
  The shared Goo host prepares its views, and the existing topology adapter
  renders and hydrates its members using Mash's profile. Navigation links open
  the formatted page; selecting a library row does not write wiki state.
- `interface.foil` registers `/nenex` and builds a workspace receiver rooted at
  the existing wiki corpus. Its browser responder delegates library construction
  to `goo_workspace`. The reader uses the existing live document fragment,
  backlinks, source form and history scrubber.
- `style.css` styles the surrounding shell and native reader/editor. It does not
  change the measured geometry or typography of Goo's prepared surfaces.
- `interface.js` handles disclosure anchors, active-page decoration, local wiki
  links and the native editor's unsaved-change warning. It submits the existing
  source form with progress and failure feedback, preserving the draft on errors.
  It does not interpret Goo layouts or maintain a second library model.
- `main.foil` retains the wiki domain. The derived `sys/lede` slot feeds the
  Goo summary and is excluded from semidoc's record/source synchronization.

Goo's current inputs are single-line. The source editor deliberately uses a
native textarea, preserving multiline text and the existing `/post` protocol.
The original `/ns/<node>/app/nenex` view remains available.

## Checks

```sh
WISP=/path/to/wisp python3 extras/x/check --mount nenex
```

The wiki checks cover links, search, source/record synchronization, derived
library titles, browser form line endings and duplicate/invalid page names. Browser verification should
cover library navigation, create/search, multiline save, discard, dirty departure,
history, and a narrow viewport against a disposable development namespace.
