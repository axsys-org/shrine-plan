# Your world as files

Your world is a folder of markdown pages. Where you run beside the world, that folder is on disk (a git
repository, one file per page: `docs/brackets.md`), and you use your own Read, Edit, Write, Grep and Glob on it;
`git log -p` is its history, each change in its writer's name. Over MCP the same files are these tools:

| Tool | Use it to |
|---|---|
| `read` `/docs/brackets.md` | see a page: its blocks, values, blanks, sources, references, embeds and wakes |
| `edit` `/docs/brackets.md`, old → new | change one exact snippet; it fails if the snippet is not there once (someone changed the page: read it again) |
| `write` `/docs/new.md` | write a whole page |
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

## Wakes are lines

A list item that starts with `when`, `at`, `after` or `every` is a wake: what to watch, at most one comparison, and
after `→` what to do when it fires. Put them in the page's `## Watch` section or in `/agent/wakes.md`:

```markdown
- when [[/her/keystone/answer/q42]] appears → fill the table; tell me if we are covered
- after {{48h}} from [[/our/keystone/ask/q42]] if [[/her/keystone/answer/q42]] is empty → follow up once
- when [[/her/acme/widgets#price]] > [[#ceiling]] → tell the owner; look for a third supplier
```

Deleting the line removes the wake. Passive things need no wake: references keep pages live and blanks fill
themselves. Declare a wake only where a judgment is needed.

## Saving

A save is one write of the whole file. If the world refuses it (malformed syntax, someone changed the page while you
edited, an ask to someone who opted out), the file is put back as the world has it and the reason is written beside
it as `<file>.rej`, with what you saved: read the reason, fix, save again. A good save removes the `.rej`. Half-typed
syntax is text, so a draft never fails; only finished constructs bind. Deleting a file retires its page (it stays
in history). Files under `her/` are other worlds' publications: read-only; quote them, or ask them.

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

To answer someone, write `our/<them>/answer/<id>.md` with their id, filling their blanks as values:
`- lead time: {{lead_time: 9 days ^[the drawing]}}`.
