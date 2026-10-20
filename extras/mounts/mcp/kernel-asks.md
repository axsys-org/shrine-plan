# Kernel asks: grants and assigns

The network is five writes on things, never on agents: own (you wrote it), grant (a capability on a thing to a resident, read or write, no obligation), assign (ownership moves, and the assignee watches it by default), ask (a hole or a record placed at the thing), answer (the owner or an assignee writes at the thing). Ask and answer need nothing new. Own is the journal's `who`. The two derived views (per resident: owns, cans, watches, waiting; per thing: owner, assignees, grants, open questions) are built in the mcp mount from the journal and the records, on ic-hands. Grant and assign need the kernel, and this is the ask.

## Grant

A grant is a record on the thing: `<thing>/grants/<name> {read: true, write: true}` (either may be false or absent), written by the thing's owner. It is permission, not obligation: it says nothing about whether the grantee looks.

What the kernel must do: honour it. Today every resident may read and write everything; with per-folder access, a write under `<thing>` by `who` is admitted when `who` is the owner, an assignee, or holds a grant with `write: true` on `<thing>` or a folder above it; a read likewise with `read`. The refusal names the thing and the missing capability, like `if_case` names the case. The mount's residents view then reads `can` from the grants instead of answering `all`.

## Assign

An assign is one write that does three things, admitted whole or refused whole:

1. ownership moves: `<thing>/sys/owner` becomes the assignee's name (the journal keeps who wrote it before);
2. a grant: `<thing>/grants/<assignee> {read: true, write: true}`;
3. the assignee's watch: `/agent/<assignee>/watch` gains the thing's path, so it is in their bindings and they see it move.

Only the owner (or an assignee) may assign. The thing view's `assignees` are the names `/sys/owner` has held, newest first; `owner` is the current one.

## What the views answer today, without the kernel work

- per resident (`read path=/agent` or `/agent/<name>`): `owns` the folders written with the name (from the journal, 400 events back), `watches` what the cells under the place point at plus `/agent/<name>/watch`, `waiting` the inputs of its cells that nobody wrote and its asks with no answer plus `/agent/<name>/waiting`, `present` a stream open under the name, `last` the newest event with the name, `can` read all, write all, and what `/agent/<name>/can` declares it computes.
- per thing (`read path=<thing> thing=true`): `owner` (`/sys/owner`, else the oldest writer the journal walk finds), `last_writer`, `grants` (the records under `<thing>/grants`), `assignees` (the names `/sys/owner` has held), `questions` (records under the thing with a `question` slot and no `answer`).

Until the kernel honours grants, `can` is informational and every write is admitted; the views are true to the records either way.
