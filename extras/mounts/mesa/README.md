# mesa

Registers the foot at `/<self>/io/mesa`: the one place a world meets other worlds.

- `src/foil/net.foil`: the rules of publication and landing, pure.
- `src/foil/mesa_foot.foil`: the foot's rules as steps over its state and the world's.
- `src/foil/mesa_wire.foil`: the actor that gives the foot its socket, and that tells Mesa the cards.
- `src/reaver/mesa.rvr`: the only file that names a call of the Mesa bridge in the runtime.

A name of a peer is a name that the system already authenticated. Mesa holds the key of the world and signs
each page that the world publishes. Mesa (`mesa-jael`) holds the key that it accepted for each peer, and
examines each page that a peer publishes. No rule of this mount holds a key or examines a signature, and no
application that uses a name of a peer thinks about keys. A change of key changes no name.

What is published to one peer is sealed for that peer; what is public is sent as it is. A world publishes what
it writes beneath `/<self>/our/<peer>` to that peer and beneath `/<self>/our/public` to everyone it knows. A
reader holds a publisher's names under those same names, in a store that it keeps for that publisher beside
its own (`namespace.peers`): what `A` writes at `/A/our/B/doc`, `B` reads at `/A/our/B/doc`. That store is not
part of the reader's names, and the reader runs no behaviour and judges no contract in it. What the reader
knows about it is in the reader's own records below the card: where each root stands
(`/<self>/io/mesa/<publisher>/stand`) and the version and content hash that the publisher gave each name
(`.../said/...`).

A peer is a card with a `key`, a `host` and a `port` (and a `life` and a `rift` when they are not 1 and 0). The
card is a request: it names the key that this world wants Mesa to accept for the peer. Mesa decides. It does
not accept a lower life, or a different key at the same life, and it keeps a peer whose card was removed
blocked until a card with a higher life comes. When Mesa does not accept a card, the foot writes the key and
the reason beside the card (`barred` and `cause` on `stand`), and the peer is not a peer of the foot. The foot
reads the card and does not write it. Until a verifier for the domain exists, the one that writes a card is
the one that says whose key is whose: this is a trusted setup.

Nothing outside tells a world anything. Mesa keeps four files for a world, in `io/mesa/` under the world's
file root, outside the world's records: `ring` (the key; only the runtime reads it, and a later key has a file
of its own, `ring.2`), `ring.manifest` (which key Mesa signs with), `ring.authority` (what Mesa accepted for
each peer) and `mark` (the rift, the highest epoch announced, and the lowest manifest that the world
accepts). A restore of the world does not take them back. The foot's record, `/<self>/io/mesa`, can name the
`ring` and the `mark` elsewhere. A world that has never stated a key gets one from the runtime; a world that
has stated a key is never given another, and stays silent without its key file. A world changes its key when
its record names a later `life`.

Packets are UDP datagrams on one socket. The foot makes its socket on the `port` of its record. A packet from
an address that no card names is discarded.

## What this mount does not do

- **No proof of a past publication to a third party.** A reader keeps the version and the content hash that a
  publisher gave for each name. It keeps no signature: Mesa examines the signature of each page and gives the
  rules the bytes only. So a reader cannot show a third party later what a publisher said. The smallest
  addition that restores this is in libmesa: a finished read that also gives the life, the rift, the total, the
  root and the signature of its page. Shrine makes no signatures of its own in their place.
- **A card is trusted.** Until a verifier for the domain exists, the one that writes a card is the one that says
  whose key is whose. A wrong key at a new life is accepted, and the right key then needs a later life.
- **The key is on the machine.** The seed is a file that only the runtime reads, and it is in the memory of the
  runtime. A host that is taken over can take it. A signer outside the process is not in this mount.
- **Mesa's files are in the world's folder.** A restore of the store alone (the folder `snap`) keeps them, and
  then an old key of the world or of a peer does not come back. A restore of the whole folder from a copy takes
  them back with it; nothing in that folder can prevent this.
- Not here: first contact with a world that has no card, a verifier of identities, an outside signer, and
  proofs of history.
