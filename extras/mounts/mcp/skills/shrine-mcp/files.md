# Your world as files

Your world is a folder of markdown pages. Where you run beside the world, that folder is on disk (a git
repository, one file per page: `docs/brackets.md`), and you use your own Read, Edit, Write, Grep and Glob on it;
`git log -p` is its history, each change in its writer's name. Over MCP the same files are these tools:

| Tool | Use it to |
|---|---|
| `read` `/docs/brackets.md` | see a page: its blocks, values, blanks, sources, references, embeds and wakes |
| `edit` `/docs/brackets.md`, old → new | change one exact snippet; it fails if the snippet is not there once (someone changed the page: read it again) |
| `write` `/docs/new.md` | write a whole page; pass `if_case` (the case you read) and a page that changed since keeps both writers' changes |
| `write_stream` `/docs/new.md`, chunk | write a piece at a time; stop whenever you like, read and search, resume with `at` |
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

## Writing as you think

`write_stream` takes chunks. Every paragraph or table that closes (a blank line) is written at once; the unfinished
rest is the page's draft, which others see as pending (`<!-- draft · agent is writing here -->`). Stop at any point:
read, grep, glob or look at history, then resume with `at` set to the anchor the last answer gave you. If someone
changed the page meanwhile, what you write still goes after that anchor. `done: true` writes the rest. A `[[` or
`{{` you have not closed is just text in the draft until you close it.

Every write takes the world's turn, one at a time and numbered (`seq` in the answer). Nothing is lost to a race:
a write planned on an older case is replayed onto the page as it is, block by block, and only a block you and
someone else both changed is refused, by name, with the page as it is now.

## Saving

A save is one write of the whole file. If the world refuses it (malformed syntax, someone changed the page while you
edited, an ask to someone who opted out), the file is put back as the world has it and the reason is written beside
it as `<file>.rej`, with what you saved: read the reason, fix, save again. A good save removes the `.rej`. Half-typed
syntax is text, so a draft never fails; only finished constructs bind. Deleting a file retires its page (it stays
in history). Files under `her/` are other worlds' publications: read-only; quote them, or ask them.

## Lines that do things

A line that starts with `@someone` (after an optional `when`, `at`, `after`, `if` or `every` clause) is an action,
and gets a card, `/cards/<page>__<anchor>`, in the same write. Its state shows after its anchor
(`<!-- do:a01 · done · asked 0x40 -->`).

| Line | What happens |
|---|---|
| `@0x40 lead time for 500 a month? {{lead_time: ? days}}` | asks them for the blanks on the line; the blank is bound to their answer |
| `@0x40 fyi: we moved the start to Jan 5` | tells them; no blank |
| `@agent find 3 anodizing shops near Newark → below` | a task for the agent edge; the answer is written under the line |
| `@agent fetch https://acme.example/pricing → below` | the page's words are written under the line, with where they came from |
| `when [[#lead_time]] appears @0x40 and the price? {{price: ? $}}` | waits, then asks |
| `at {{2026-11-08 09:00}} @0x40 still on? {{still_on: ? yes/no}}` | waits until then (UTC) |

The target is a world (`@0x40`) or a name with a contact record (`/contacts/keystone` with `world`); a name with no
way to reach them fails the card and says so. Rewording a line updates its card; changing what it asks sets it
going again; deleting a line takes back a card not yet acted on. The same line written twice is asked once. Someone
mentioned inside a sentence (`I asked @0x40 already`) is just text.

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
