# Native block document

```sh
python3 x/eden --mount block-document --mount mcp --port 8137
```

Open http://127.0.0.1:8137/block-document. The document is
`/0x11/app/block_document/document`; declarations live under
`/0x11/gov/block_document`.

Click the document to type. Enter creates a paragraph; Backspace joins at its
start. Type `/` at the start of a paragraph for Text, Heading, Bullet list or
Code. The menu supports arrow keys, Enter and Escape. Select text for the
floating bold/italic/underline/clear toolbar; Ctrl/Cmd-B, I and U also work.
Ctrl/Cmd-Z and Shift-Z (or Ctrl-Y) traverse the local editing history. Paste and
cut use plain text. **Save document** invokes the declared Grove action and
validates the structured input through `goo_edit/decode` before updating Foil
state. Local changes remain drafts until saved.

The complete notebook shell is the `editor` view in `main.grove`: its title,
guidance, rich input, Save control and revision. `/block-document` is an empty
host that mounts this prepared view directly. It loads only the generated Goo
profile and font stylesheets, with no application stylesheet or Explorer pane
chrome. Popup surfaces use the exported Goo overlay canvas paint. Input insets
and viewport dimensions come from native preparation. Runtime feedback is
prepared as Goo text through `/goo/feedback`.

`main.grove` authors the rich input, its typed save action, and ordinary Grove
views for the formatting toolbar and slash menu. Goo prepares those views with
its own layout, fonts and button rendering. `goo/text_edit.foil` implements the
pure draft commands: formatting, paragraph breaks and block styles.
`document.foil` owns the bounded block model, identity allocation and saved
history. The shared Explorer adapter `goo-rich-input.js` mounts the prepared
controls, anchors them to the selection, and sends commands to
`POST /goo/text-command`. That endpoint transforms a submitted draft; it cannot
read or write namespace objects. Save remains the declared Grove action.

The mount contains no application JavaScript. The shared browser adapter still
owns platform typing, selection, clipboard, draft storage and local history;
this is not a JavaScript-free editor. Local insertion/deletion and undo/redo
still live in that adapter; moving them into a Foil hand is separate work.
It consumes display v3's input
value and resolved style palette. Rich input drafts, selection,
typing style and local history survive compatible repreparation. Incompatible
encoding or palette changes use the existing departure guard. Invocation retries
retain the original structured wire value; edits made while saving remain dirty.

The small document uses a defined interchange convention within `goo/text`:
newlines separate blocks, `/sys/font/sans750` marks heading text, and a `- `
prefix represents a bullet. The Foil save operation reconstructs blocks,
retaining the identities of an unchanged prefix/suffix and the first edited
block; additional changed blocks receive fresh identities. This is a flat
paragraph editor, not nested lists, drag-reordering or collaborative selection
transforms. Heading styling currently uses the contract's supplied heavy face
at the input's text size. Code uses the supplied monospace face.

Current contract coverage is English/ASCII and bundled fonts. Unsupported input
is refused visibly. Structured link metadata survives editing; link navigation
and embeds are not part of this input. Limits are 64 KiB serialized input, 100
blocks, 64 runs per block, 4096 characters per run, 50 saved checkpoints and 100
local editing checkpoints. Saved edits use the launcher's native world storage;
`--ephemeral` discards that world when the launcher exits. Unsaved drafts and
local undo history live only in the current browser page.

Checks:

```sh
node --test extras/mounts/explorer/tests/*.test.cjs
WISP=/path/to/locked/wisp python3 extras/x/check --mount block-document --jobs 2
```
