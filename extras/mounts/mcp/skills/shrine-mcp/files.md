# Your world as files

Your world is a folder of markdown pages. Where you run beside the world, that folder is on disk (a git
repository, one file per page: `docs/brackets.md`), and you use your own Read, Edit, Write, Grep and Glob on it;
`git log -p` is its history, each change in its writer's name. Over MCP the same files are these tools:

| Tool | Use it to |
|---|---|
| `read` `/docs/brackets.md` | see a page: its blocks, values, blanks, sources, references and embeds |
| `edit` `/docs/brackets.md`, old → new | change one exact snippet; it fails if the snippet is not there once (someone changed the page: read it again) |
| `write` `/docs/new.md` | write a whole page; pass `if_case` (the case you read) and a page that changed since keeps both writers' changes |
| `glob` `/docs/*.md`, `grep` `Keystone` | find pages and lines |
| `history` `/docs/brackets.md` | see who changed a page and when |
| `send` | ask someone for a page's open blanks: writes the ask file below for you |

The raw `mcp/read`, `mcp/write` and `mcp/history` are still there for the rare exact read; prefer the files.

## How a page is spelled

The full grammar is `note/markdown-grammar.md`; the parts you use every day:

- Every block ends with its anchor (`<!-- b:p3k -->`). Keep anchors when you edit: they are each block's identity.
  A block you add needs none; it is named when written.
- `[[/suppliers/keystone]]` or `[[Keystone Widgets]]` is a reference to a real name. Only `[[…]]` binds; a bare
  `/path` in prose is text. Search before you write a name, so you link instead of duplicating.
- `{{ceiling: $40}}` is a value on that slot; `{{$37 ^[quote p.1]}}` a value with its source. Write the source of
  every fact that is not the owner's own word.
- `{{lead_time: ? days}}` is a blank. Once asked, it reads `{{lead_time: ? days ← /her/keystone/answer/q42}}`:
  bound to where the answer will appear, then `{{lead_time: ? days = 9 days ^[keystone] ← …}}` when it has come.
  The binding is the ask's, shown on the page and never stored there: never write a `←` yourself, and never
  replace a bound blank with a value; the answer fills it.
- A table is a collection: each row a record named by its first cell, each column a slot.
- `> …` with `— [[/her/…]]` is someone else's words, quoted; never the owner's fact.
- An embed (`[[/her/acme/widgets @x]]` alone on a line) draws that record beneath it; what is drawn is not yours to
  edit when it is someone else's (`/her/…`).

## Lines are prose

A line like `@Keystone lead time for 500 a month?` or `when the answer comes, compare with Acme` means what it says
to whoever reads it; the page binds only blocks, references and slots. Acting on such a line is yours: write the
ask (below), fetch, or, for something that must wait, write a hand (`hands.md`).

## Saving

Write in pieces when you like: save what you have, read and search, then edit or write again. Nothing is lost to
a race: the world applies one write at a time, and a write planned on an older case (pass the `if_case` you read)
is replayed onto the page as it is, block by block; only a block you and someone else both changed is refused, by
name, with the page as it is now.

A write is one write of the whole page. If the world refuses it (malformed syntax, an ask to someone who opted out
or already asked the same), nothing is written and the answer says why: fix it and write again. Half-typed syntax
is text, so a draft never fails; only finished constructs bind. Pages under `/her/` are other worlds'
publications: read-only; quote them, or ask them.

## Asking

Asking is writing one file in your own world, `our/<them>/ask/<id>.md`, whose front matter says which page it asks
and whose blanks are what it asks:

```markdown
---
asks: [[/docs/brackets]]
---
# Lead time for the Q1 brackets

- lead time: {{lead_time: ? days}}
```

That one write is the whole act. It appears in their world as `her/<you>/ask/<id>.md`; the page's matching blanks
are bound to `/her/<them>/answer/<id>` and fill when the answer lands there, whoever answers and however it travels.
`send` writes the same file for you from a page's open blanks. No approval is asked. The world itself refuses an ask
to anyone with `/optouts/<them>` (only the owner can take an opt-out back), and an ask says plainly that it comes
from an agent. Ask once per blank: a blank already bound is not asked again unless you name it.

Say where the ask came from: `from: [[/docs/brackets/p03]]` (the line's block) in its front matter. Then the line's
backlinks show what was asked from it, and you can see that you already acted. The world refuses a second ask to
the same person for the same blanks while the first is still open.

To answer someone, write `our/<them>/answer/<id>.md` with their id, filling their blanks as values:
`- lead time: {{lead_time: 9 days ^[the drawing]}}`.
