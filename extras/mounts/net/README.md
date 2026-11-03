# net: networked names

The generic substrate for one world observing another's published names. It knows
publishers, names, revisions and whether a judgment has fallen behind a revision.
It knows nothing about any business.

## Records

```
/<self>/net/names/<publisher>/<name>/current   written only by the shrine-mesa sidecar: the viewed slots of
                                                the acquired revision, plus remote_case, publisher, source (name@case)
/<self>/net/names/<publisher>/<name>/seen      written by whoever judged against a revision: remote_case is the
                                                revision the judgment relied on
/<self>/net/stale                               a cell over the whole names subtree (z care); never stored
```

`<publisher>` is the publisher's node id (a hex segment such as `0x11`); `<name>` is one path
segment the publisher chose. The acquired revision is source-attributed, not verified: the
remote epoch and case are recorded, and until Mesa and Groundwire the signature is the
sidecar's to check.

## Reading the overlay

Over MCP, with the node spelled: `mcp/read path=/x/<self>/net/stale care=y`. Each child is
`/<publisher>/<name>` with `current` (the acquired revision), `seen` (the judged one),
`publisher` and `name`. A name with no `seen` was never judged and is not listed; a name
whose `seen` equals `current` is not listed. `/c/x/<self>/net/stale` shows the cell's context,
including `/sys/tack/case`, the input subtree's current case.

## Why the cell is written from activation

A Grove `@tree` seed accepts only a y-care tack, and the names subtree is three deep. The
`@sewn` declaration `stale` is published with the Grove template at `/<self>/gov/net/stale`;
`activation.foil` instantiates the template at `/<self>/net` and then writes the cell record
`{sys/weft: (safe 1 .x /gov/net/stale), sys/tack: (safe 0 .z /net/names)}` through
`grove_install/change`.

## Running it

```
python3 x/eden --node 0x12 --mount net --mount mcp --mount probe --port 8302 --world <dir>
```

`mount.json` depends on `codecs` for the Grove `text` type.
