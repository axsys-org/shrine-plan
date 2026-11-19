# mesa

Registers the foot at `/<self>/io/mesa`: the one place a world meets other worlds.

- `src/foil/net.foil`: the rules of publication and landing, pure.
- `src/foil/pass.foil`: a name, its custody and its log, pure.
- `src/foil/mesa_foot.foil`: the foot's rules as steps over its state and the world's.
- `src/foil/mesa_wire.foil`: the actors that give the foot a socket and a clock.
- `src/reaver/mesa.rvr`: the only file that names a call of the Mesa bridge in the runtime.

What is published to one peer is sealed for that peer; what is public is sent as it is; every page is signed.
A world publishes what it writes beneath `/<self>/our/<peer>` to that peer and beneath `/<self>/our/public` to
everyone it knows. A reader holds a publisher's names at `/<self>/her/<publisher>`, exactly as published, and
keeps how each mount stands on the card `/<self>/io/mesa/<publisher>`. A peer is a card with a `key`, a `host`
and a `port`.

Nothing outside tells a world anything. The foot's record, `/<self>/io/mesa`, says where its two files are
kept (`ring`, the seed; `mark`, the rift and the highest epoch it announced; both in `io/mesa/` under the
world's file root unless the record says otherwise). A world that has never stated a key and has no ring makes
one from the runtime's entropy; a world that has stated a key is never given another, and stays silent
without its ring. The foot listens when its record holds a `port`, and hears whoever it holds a card for.

A sender with no card that is a route is not heard. Two words are taken from one, each its own proof: a
statement that follows a log kept under the sender's name, and an introduction of the sender vouched for by a
name this world keeps a log for (`pass/welcome`). Only an introduction that holds gives a card its address.
