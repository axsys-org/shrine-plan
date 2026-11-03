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

## Publications (phase 1)

What a world exposes is a record under its own root, written by the owner or an agent on the
owner's behalf, never by the sidecar:

```
/<self>/net/publications/<name>   one name this world exposes; <name> is one lowercase segment
   path    required, text         the local path whose revisions are exposed, e.g. /0x11/pub/aluminum
   to      required, text         "public", or the node id of one peer such as 0x12
   slots   optional, text         the slot names to expose, space-separated; absent means every slot
   note    optional, text
```

The sidecar lists `/<self>/net/publications` (care `y`), reads each child, and watches the record
at `path`: every new case is bound under the Mesa name `<name>@<case>` and announced to the peers
`to` names (every configured peer for `public`). Nothing not listed here is ever bound. Visibility
at this libmesa commit is traffic policy, not authentication: every bind is `Access::Public`, and
`to` decides only who is told.

The role's contract is judged on every update: a poke or remake that leaves a publication without
`path` or `to`, or with either not text, is refused (`curb_need`, `curb_type`). The first write of a
record under the tree is not judged: the tree stamps the contract onto the record in that same write,
and the kernel treats a new contract as adopted over the record it arrives with (`guard_diffs` in
`lain_poke.foil`). The sidecar therefore skips a publication that lacks `path` or `to` and says so in
its log; the next complete poke makes it a publication.

On the acquiring side `/net/names/<publisher>/<name>/current` is written once per acquired
revision: a sidecar that restarts, or a notice delivered twice, compares `remote_case` with what
the world already holds and writes nothing for a revision already acquired.

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

## Phase 0, measured (2026-11-02)

`demo/phase0.py` boots two worlds from this checkout (A `0x11` with `mcp probe`, B `0x12` with
`net mcp probe`), starts the shrine-mesa publisher beside A and the reader beside B
(`/Users/ianchanner/shrine-mesa`, commit 462745f, libmesa 2e94a13), and asserts the loop:

| what | measured |
|---|---|
| A's revision acquired in B (flow notice, signed named read, world write) | 0.16 s (revision 1), 0.11 s (revision 2) |
| `/x/0x12/net/stale` listing the name after A's next revision | 0.14 s after the write in A |
| `kill -9` of B's runtime, restart, overlay unchanged | 2.6 s |
| re-judging at the new case | the overlay empties |
| runtime footprint after the run | A 69 MB, B 197 MB |

What is real: the acquisition is a publisher-signed Mesa read verified by the reader's engine, the
notice a durable flow with receipts, the overlay a kernel lens over records, persistence the
world's own. What is not yet: the bind is `Access::Public` (libmesa's signed-public profile refuses
any other access at this commit), there is no requester authentication or encryption, the sockets
are loopback, and the publisher keys are local seed files.
