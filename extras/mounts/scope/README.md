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
