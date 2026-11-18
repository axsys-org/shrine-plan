# scope

Registers the foot at `/<self>/io/scope`, which runs a scope's rules whenever the world moves.

- `src/foil/scope.foil`: the rules, pure: a place is opened, filled and listed; the catalog is told to each
  member; a member meets the worlds a scope lists.
- `src/foil/scope_foot.foil`: the foot. It is told each commit, reads the world as it stands and asks for the
  writes the rules answer. The rules settle.
- `src/foil/desk.foil`: the signing desk of the foot at `/<self>/io/mesa`. A place's invitation is minted there
  when the place asks.

A record beneath `/<self>/io/scope` says what the foot tends. One with a reference in `root` is a scope this
world keeps: a place is any record beneath the root that holds an invitation's number in `invite`, wherever a
pack puts it, and the catalog is `<root>/catalog/<world>`. One with
a number in `scope` is a scope this world is listed in: the worlds it lists become cards of this world's own,
each checked against its name.

A record with a number in `to` is a joining: what the door wrote when it was handed a link. Once the claim it
asked for is made, the scope the link named is met, the record takes `maker`, `scope` and `side`, and the world
asks to be brought before the scope.

## The door's two routes

- `POST /scope/link/<number>`, from someone this world let in: the link to the invitation minted under that
  number, with its secret after it, as one line of text. The first request answers 202 while the foot leaves
  the secret; a later one answers 200 with the link, once, and the file is emptied.
- `POST /scope/join`, with a link as the body: this world claims the link's name and joins. Someone this world
  let in may hand over any link. Nobody may hand over only the link to this world's own name, while the world
  has let nobody in: that is a world prepared for the place. The session such a request showed
  (`Authorization: Bearer <secret>`) is the one the claim lets in.

A secret passes between a request and a file of the foot's (`io/mesa/out/<number>`, `io/mesa/in/<name>`) and is
in no record.
