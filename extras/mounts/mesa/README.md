# mesa

Registers the foot at `/<self>/io/mesa`: the one place a world meets other worlds.

- `src/foil/net.foil`: the rules of publication and landing, pure.
- `src/foil/mesa_foot.foil`: the foot's rules, as steps over its state and the world's.
- `src/foil/mesa_wire.foil`: the actor that gives the foot its socket and tells Mesa the cards.
- `src/reaver/mesa.rvr`: the only file that names a call of the Mesa bridge in the runtime.

## Identity is a trusted setup

**Whoever writes a peer's card decides whose key is whose.** A person, a script or a hand writes each card. The
foot hands the card to Mesa and Mesa accepts it. There is no verifier and no first contact, so:

- a world with no card is not heard
- when a peer changes its key, someone has to write the new key on its card, and nothing from that peer lands
  until they do
- a wrong key written at a new life is accepted, and the right key then needs a later life

This is not Groundwire identity. The card stands in for a verifier. When a verifier exists it takes the place of
whoever writes the cards, and no rule here changes.

What Mesa does with the keys: it signs every page the world publishes with the world's key, and checks every
page from a peer against the key it accepted for that peer (`mesa-jael`). The rules of this mount sign nothing
and check no signature. A world's names do not change when its key changes.

## What it does

A world publishes what it writes beneath `/<self>/our/<peer>` to that peer, and what it writes beneath
`/<self>/our/public` to every peer it knows. What goes to one peer is sealed for that peer. What is public is
sent as it is.

A reader holds a publisher's names under the same names, in a store it keeps for that publisher beside its own
(`namespace.peers`): what `A` writes at `/A/our/B/doc`, `B` reads at `/A/our/B/doc`. That store is not part of
the reader's own names, and the reader runs no behaviour and judges no contract in it. What the reader knows
about it is in the reader's own records below the card:

- where each root stands: `/<self>/io/mesa/<publisher>/stand`
- the version and content hash the publisher gave each name: `.../said/...`

A peer is a card with a `key`, a `host` and a `port`, plus a `life` and a `rift` when they are not 1 and 0. The
card is a request to Mesa. Mesa refuses a lower life, and a different key at the same life. A peer whose card
was removed stays blocked until a card with a higher life is written. When Mesa refuses a card, the foot writes
the key and the reason beside the card (`barred` and `cause` on `stand`), and that peer is not a peer of the
foot. The foot reads cards and never writes them.

Packets are UDP datagrams on one socket, on the `port` of the foot's record. A packet from an address that no
card names is dropped.

## Files beside the world

Mesa keeps four files for a world in `io/mesa/`. They are in the world's folder but not in the world's store.
The foot's record, `/<self>/io/mesa`, can name another place for `ring` and `mark`.

- `ring`: the private key. Only the runtime reads it. Each later key gets a file of its own (`ring.2`).
- `ring.manifest`: which key Mesa signs with.
- `ring.authority`: what Mesa accepted for each peer, and each block.
- `mark`: the rift, the highest epoch announced, and the lowest key manifest the world accepts.

A world that has never stated a key gets one from the runtime. A world that has stated a key is never given
another, and stays silent without its key file. A world changes its key when someone writes a later `life` on
its record. Its peers follow when someone writes the new key and that life on their cards.

If one of the four files is damaged or unreadable, or a world that has run before has no mark, the foot does
not start. It says why and overwrites nothing.

## What this mount does not do

- **No proof of a past publication for a third party.** A reader keeps the version and the content hash a
  publisher gave for each name. It keeps no signature: Mesa checks the signature of each page and hands the
  rules only the bytes. The smallest fix is in libmesa: a finished read that also gives the life, the rift,
  the total, the root and the signature of its page. Shrine makes no signatures of its own in their place.
- **No verifier, no first contact.** See the first section.
- **The private key is on the machine.** It is a file only the runtime reads, and it is in the runtime's
  memory. Someone who takes over the host can take it. There is no signer outside the process.
- **The key files travel with the folder.** Restoring only the store (the folder `snap`) leaves them alone, so
  an old key of the world or of a peer does not come back. Restoring the whole folder from a copy rolls them
  back too, and nothing in that folder can prevent it.
- **A full engine is replaced.** An engine holds 64 MiB of bound pages. When it is full the foot makes a new
  engine on the same socket. Reads in progress stop and a later hint starts them again. A name always has the
  same content, so the new engine gives the same page for it. Mesa could instead retire old names
  (`RETIRE_BEFORE`), but that needs page names that sort by version, and page names will change with Mesa's
  native paths.
