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
and a `port`. See `host.py` for the files and the configuration.
