# Native block document

Run from the repository root:

```sh
python3 x/eden --mount block-document --mount mcp --port 8137
```

Open http://127.0.0.1:8137/block-document . The installed document is
`/0x11/app/block_document/document`; declarations live under
`/0x11/gov/block_document`.

The page is prepared from real `goo/text` runs. Grove forms invoke native Foil
operations on one typed document record. There is no application JavaScript or
independent browser document store.

Select a bracketed block number and a zero-based run number. Apply text and a
style (`plain`, `bold`, `italic`, `underline`, or space-separated combinations).
Append a run to add differently formatted text. Split at an offset within the
selected run; merge combines matching adjacent block kinds. Insert, remove,
move up/down, change kind, undo and redo use the same document authority.

This first editor uses the renderer's printable ASCII coverage and explicit
single-line run forms. The structured reference is a read-only displayed link,
not an actionable embedded presentation. Up to 100 blocks, 64 runs per block,
4096 characters per run, and 50 undo checkpoints. Accepted edits last for the
running sovereign; restarting the development launcher creates a fresh world.
