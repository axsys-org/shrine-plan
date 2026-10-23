# Shrine MCP: sources

Chains start at a source and nowhere else. This page holds the rule once,
the format of a kind page, and a kind page for each kind of source we
know. Read the rule, then the kind you have met; for a kind not here, the
last section says how to write its page as you go.

## The rule

1. A source is a record at `/user/<scope>/sources/<artifact>`: `where` it
   is, which `script` binds it, the version `marker` last read, and
   `every` for a source that changes on its own. Nothing under it is
   written up front except its skeleton.
2. The artifact's own stable structure is the namespace under it: the
   structure its citations use (paragraph numbers, sheet and row,
   heading, record id). Pagination, offsets, line numbers and the time of
   extraction are slots on a region, never its path, because they move
   between versions.
3. The contents are eager, the leaves are lazy. Write the levels a reader
   navigates (the parts, the sections, the sheets: the table of contents,
   each a record with only `source`) so what exists can be seen and
   pointed at; a leaf (a paragraph, a row, a footnote) is written when
   something points at it, at the path its locator gives it. One
   question extracts one region. Nothing is extracted unasked, and a bulk
   extraction is never the answer to a question; when a whole source is
   wanted, say so and let the hand do it.
4. A region never carries prose. Its slots are its position (`page`,
   `row`, `line`), a digest of its words (`body`), the slots the hand
   owns (`source`, a reference to the artifact record, `digest`), and
   the facts the source states there, decomposed: a name is a path
   segment or a reference, a number a number, a date a day, a flag a
   flag; a quotation slot only when the words themselves are the fact
   and they are short (a defined term, a sworn statement). The sentences
   stay in the file, one read away through the locator; what you would
   have copied as `text` is instead the facts under the region, written
   when you read it, which cells can compute over. No interpretation,
   no status, no kind. A fact is evidence of what the source says, with
   the period, unit and currency the source gave it; a revenue in a
   report is the report's figure for that year, never a timeless fact
   about the company, and it keeps that scope through every view above
   it. A reading of a region, by you or by a model, is an interpretation:
   a record in the scope that references the region, stamped with its
   case, never written into the region.
5. Change is scoped: on a new version, re-read the regions that exist,
   rewrite the ones whose digest moved with `if_case`, cull the ones the
   source no longer has, in one event signed `source_<artifact>`.
   Untouched regions are untouched, so the chains over them do not move.
   A region the source lost is culled, so every view over it faults
   instead of going on presenting what it used to say; a changed region
   moves its case, so a pinned reading stays a reading of that case.
6. A run that finds no change writes nothing, and nothing else is ever
   written by the binding.
7. Acquire freely, structure rigorously. Any tool, skill or combination
   may get at the source; what enters the world is anchored with its
   provenance and decomposed by the source's own factual and conceptual
   structure, not by its format or the convenience of the extraction.
   Nesting and multiple cardinality are kept as the source has them.
8. The smallest meaningful unit the source supports, and no smaller: the
   minimum faithful, addressable structure that allows the most
   composition above it. Each unit stays traceable to its field, row,
   passage or code region, so a change can later be traced back through
   the views to the exact region it concerns and applied there. Nothing
   imported may make that impossible; nothing derived is stored as if
   it were the source.
9. Activity is not a source. A system you operate (a repository, an api,
   a database, a service) is anchored by its objects, not by what you
   did to it: an operation becomes an observation record only when it
   is evidence, reusable or needed for recovery, with the resource it
   addressed, what was sent and what came back by reference, and the
   day. A successful response is not the state you wanted; re-read the
   resource. After a change outside, re-read the anchors it touched.

The binding is code, not records. The world holds the artifact record
and the regions; how a region came to be at its path lives in the script:
how to open the source, how to walk its structure into paths, how to
extract a region by its locator, how to tell the source moved and which
regions a move touches, and for a dynamic source how a request is formed
from a path and where its response lands. A script is deterministic (the
same source at the same version gives the same paths and content) and a
path alone reproduces its region (a request's parameters are in its
path; a query is its region's name).

On first contact you are the script: open the file with what you read
files with, write the skeleton you can see and the one region the
question needs, at the path the hierarchy gives it. The next question
extracts the next region. Promote the extraction to a hand (`hands.md`)
only when the source changes without you present, or when you find
yourself re-extracting the same source every session.

Identity across sources is the object-and-scope rule at the leaves: the
same customer in a csv and a pdf is one object under `/user/<scope>/…`,
and each source's region references it, made once with `reference`.
Never merge on a name's resemblance.

Static and dynamic sources differ in what is observed, not in the rule.
A document, a dataset, a page is content and structure: the anchor is
the region, change is a revised passage, the views interpret, relate and
aggregate, and the usual action is to read and answer. A repository, an
api, a database is state and operations: the anchor is the object at a
version, change is a state transition you may have caused, the views
derive dependencies and consequences, and the usual action is to
inspect, edit, execute. Both land in the same world, and a customer from
a pdf, from an api and from a database is one object once the evidence
says so, feeding the same views.

## The format of a kind page

```
## <kind>
What it is      one sentence; what counts, what does not
Hierarchy       the artifact's own structure as paths; which level a view tacks; skeleton vs content
Locator         what names a region; what is NOT a locator and goes in a position slot
Content         which slots are content, in the source's words and types; which are position
Change          the version marker; what a re-read touches; cull; hand or lazy
Reading it      the library or tool, in a line; the two or three traps
Example         one tree: the record, skeleton, two regions, one view, one change
```

A kind page is a screen, or it is two kinds. The example is a tree that
could be pasted into a write.

## csv

What it is: rows with a header, one record per row. A file with several
sheets is a spreadsheet.

Hierarchy: flat, the rows under the artifact; the row is the region a
view tacks at y. No skeleton needed.

Locator: the key column, chosen once (`key`); the row's path is
`segment_of(key)`. Row number is not a locator.

Content: every column as a slot in the header's words, numbers as numbers
(a leading zero stays text), dates as `YYYYMMDD` when the column is a
date; position: `row`.

Change: file mtime or digest; re-read every row, rewrite changed, cull
missing; usually lazy extraction is not worth it, take the file whole.

Reading it: `csv` from the standard library; traps: encoding, a quoted
newline, a thousands separator.

```
/user/finance/sources/ledger_2026     where: ~/books/ledger-2026.csv   script: rows   key: id   marker: mtime 1792523370
  /t_0001    date: 20260103   account: "4000"   amount: 12500   amount/scale: 2   memo: "Northwind Jan"   row: 2   source: ref ..   digest: 9f3a..
  /t_0002    date: 20260104   account: "6100"   amount: 4000    amount/scale: 2   memo: "hosting"         row: 3
/user/finance/views
  /by_account   by over sources/ledger_2026 (y)   key: /account   op: sum   slot: /amount
→ a row's amount corrected in the file: that row rewritten, by_account moves, nothing else does
```

## pdf

What it is: a document with its own numbering. A pdf of scanned images
is a media source until it is transcribed.

Hierarchy: the document's own parts and numbering (parts, sections,
numbered paragraphs); the paragraph is the region a view tacks at x, the
section at y. Skeleton eager (the parts and numbers), paragraphs lazy.

Locator: the document's paragraph or section number; the page is a slot.

Content: `text` as printed; position: `page`.

Change: the file's digest; a new version re-reads the paragraphs that
exist as records; renumbering is a new artifact.

Reading it: a pdf text library; traps: a paragraph across a page break,
footnotes interleaved, headers repeated on every page.

```
/user/legal/sources/complaint        where: ~/Downloads/complaint.pdf   script: numbered_pleading   marker: sha256 e41b..
  /parties
    /p1 … /p37                       (skeleton: not yet extracted)
  /facts/injuries/victims/vazquez
    /p118        page: 30   words: 61   body: 77ab..   source: ref ..   digest: 9c01..   ← something pointed at it
      /injured   who: ref /user/people/andres_vazquez   on: 20060314   where: "Sadr City"   by: ref ../../../weapons/hs_50
      /struck    count: 2   part: "left arm"
  /signature     page: 56   words: 40   body: 1e8f..
    /firm        name: "Sparacino PLLC"   signed: 20260927
/user/legal/views
  /injuries_by_day   by over sources/complaint/facts/injuries (z)   key: /on   op: count
→ a corrected filing: p118's body moves, the region is rewritten, the facts under it are yours to re-read; the rest stays
```

## json

What it is: one object or an array of them, from an export or an API
dump.

Hierarchy: the object's own structure; arrays of objects keyed by their
id slot when they have one, by index when they do not (and then the
source is a poor one).

Locator: the id slot, named once (`key`), or the object's own keys.

Content: the leaves as slots; nested objects as nested records; a key
that names another object stays text until `reference` makes it a
pointer, once.

Change: digest; re-read whole, scoped by id.

Reading it: `json`; traps: ids as numbers in one place and text in
another, null versus absent.

```
/user/crm/sources/hubspot_export     where: ~/exports/hubspot.json   script: json_tree   marker: sha256 02cc..
  /companies/c_104   name: "Northwind Industries LLC"   tier: "gold"
  /contacts/u_9      company: "c_104"   email: "jo@northwind.example"
/user/crm/views
  /refs/contacts   reference over sources/hubspot_export/contacts (y)   key: /company   table: ref ../companies   into: /company_ref
```

## static website

What it is: pages that do not change per request. A page that answers
differently to parameters is an api.

Hierarchy: the url path, then the page's headings; a section under a
heading is the region.

Locator: the url path and the heading text (slugged); not the position
in the page.

Content: `text` under the heading, `title`; position: `fetched`,
`etag`.

Change: the page's etag or last-modified; re-read the sections that
exist; a heading gone is a cull.

Reading it: an html parser; traps: headings that repeat, navigation
text, pages that render by script.

```
/user/research/sources/wikileaks_cables   where: https://wikileaks.org/plusd/   script: html_headings   marker: per page
  /cables/06VIENNA3028_a                   title: "Steyr-Mannlicher: Reloading After Sanctions"   fetched: 20261020   etag: "a81f…"
    /summary                               text: "…"
    /paragraphs/4                          text: "…154 rifles in the first batch…"
```

## api

What it is: an endpoint that answers a request; the response is the
content. Includes any query-shaped source.

Hierarchy: the endpoint, then a request named by its parameters, holding
its response flattened; the response's rows under it when it has rows.

Locator: the parameters, in the path (`/forecast/chicago/20261021`), so
the path alone reproduces the request. Not a request id.

Content: the response's fields; position: `fetched`, `status`.

Change: the response's own version when it has one, else `every`; a
region older than `every` is re-requested and rewritten only if its
digest moved. Always a hand for reads that recur.

An api is also something you operate: a resource, an operation on it, a
state before and after. You make the request yourself; what enters is
the resource as read, and, when it is evidence, the operation as an
observation (the resource by reference, what was sent, what came back,
the day), never a universal action primitive. A `200` says the server
answered; read the resource again for the state.

Reading it: `urllib`; traps: rate limits, auth from the environment
(never a slot), pagination of the response.

```
/user/ops/sources/weather_api        where: https://api.example/v1   script: http_json   every: 3600   auth: env WEATHER_KEY
  /forecast/chicago/20261021         request: {q: chicago, day: 20261021}   fetched: 20261020   status: 200   high: 61   low: 44
/user/crm/sources/crm_api            where: https://crm.example/v2   script: http_json
  /customers/42                      limit: 150000   balance: 42000   etag: "9b1…"   fetched: 20261020
  /operations/op_104                 resource: ref ../customers/42   sent: {limit: 150000}   status: 200   when: 20261020
/user/ops/views
  /cold_cities   where over sources/weather_api/forecast (z)   expr: low < 45
→ a hole at /forecast/denver/20261021 is a request not yet made; the hand makes it on its next pass
→ after op_104 the hand re-reads customers/42; views over its limit move, the operation stays as evidence
```

## file system

What it is: a tree of files; the container every other kind lives in. A
file that is opened becomes its own source with a reference back.

Hierarchy: the tree as it is.

Locator: the path.

Content: `size`, `kind`, `modified`, `digest`; a file's contents are not
content here, they are the opened source's.

Change: a scan; mtime per file.

```
/user/ops/sources/laptop             where: /Users/ian   script: tree   marker: scan 20261020T14
  /Downloads/complaint.pdf           size: 2310442   kind: pdf   modified: 20260928   digest: e41b..
/user/legal/sources/complaint        file: ref /user/ops/sources/laptop/Downloads/complaint.pdf   …
```

## code

What it is: a repository or a folder of source files: files, symbols,
dependencies, tests and behaviour. You edit, run and test it with your
own tools; the world keeps what exists and what changed.

Hierarchy: the tree, a file as a region; a definition inside it as a
sub-region named by its qualified symbol, lazy. A symbol's identity is
its name under its file, never its line.

Locator: the file path and the symbol; line numbers are position and
move when lines above are inserted.

Content: `text` of the definition, `language`, `lines`, `digest`;
position: `from`, `to`.

Change: the commit; re-read the files git says changed, and the symbols
in them. A test run is an observation at a commit, by reference, not a
`passed: true` on the file.

```
/user/eng/sources/shrine_cells       where: /Users/ian/shrine-cells   script: git_tree   marker: commit 8a7042f
  /src/foil/lain_poke.foil           lines: 848   language: foil
    /sovereign_kernel                text: "+ sovereign_kernel …"   from: 606   to: 624
  /observations/test_run_42          commit: "8a7042f"   suite: "foil"   failed: 0   ran: 213   when: 20261020
/user/eng/views
  /dependents_of_kernel   where over sources/shrine_cells (z)   expr: contains(text, 'sovereign_kernel')
  /regression             diff over views/failed_tests (y)   other: ref /h/y/<case>/…/views/failed_tests
```

## database

What it is: tables with primary keys, relationships, and queries. The
schema is one implementation of the facts, not the conceptual model:
keep it as the authoritative structure and derive the meaning above it.

Hierarchy: schema, table, row by primary key; a foreign key is a
reference once `reference` has run; a query as a region named by its
parameters, its rows beneath.

Locator: the primary key; the query's parameters. Never the row's
position in a result.

Content: the columns; position: `fetched`, and the row version or
transaction token where the database gives one.

Change: a change marker when the database has one, else `every`; a row
gone is a cull. A hand. A change you make with SQL is the database's
transaction, with its own constraints; afterwards the affected rows are
re-read and the views over them move. Never copy the database's own
aggregates; derive them from the rows, or reuse the view that does.

```
/user/crm/sources/crm_db             where: postgres://crm   script: sql   every: 600   marker: lsn 0/5A3C
  /tables/customers/42               name: "Northwind"   region: "US"   xmin: 88213
  /tables/invoices/900               customer: ref ../../customers/42   amount: 15000   paid_at: 20261020
  /queries/revenue_by_tier/2026_q3   sql: "select tier, sum(total) …"   fetched: 20261020
    /gold                            total: 985000
/user/crm/views
  /unpaid         where over sources/crm_db/tables/invoices (y)   expr: paid_at = ''
  /receivables    by over views/unpaid (y)   key: /customer   op: sum   slot: /amount
  /exposure       gather: receivables + sources/crm_api/customers limits, by customer
```

## spreadsheet

What it is: a workbook with sheets, cells and formulas.

Hierarchy: workbook, sheet, row by key column or named range.

Locator: the key column or the range name; the row number and the cell
address are position.

Content: the columns; a formula cell's computed value is content and the
formula text a slot beside it when it matters.

Change: mtime; re-read per sheet.

```
/user/finance/sources/budget_2026    where: ~/books/budget.xlsx   script: workbook   marker: mtime
  /sheets/revenue/r_north            region: "North"   q1: 120000   q2: 135000   row: 4
  /ranges/targets                    from: "revenue!B2:C9"
```

## office documents

What it is: docx and pptx.

Hierarchy: a document's numbered sections and headings; a deck's slides
then shapes. A table inside is a nested row source.

Locator: the section number or heading; the slide number; not the page.

```
/user/legal/sources/msa_draft_v3     where: ~/contracts/msa-v3.docx   script: headings   marker: sha256
  /7_termination/7_1                 text: "Either party may terminate …"   page: 11
  /tables/pricing/tier_1             seats: 50   price: 1200
```

## markdown and text

What it is: a text file with headings; the commonest source and the one
most tempting to swallow whole.

Hierarchy: headings, nested by level.

Locator: the heading, slugged; line numbers are position.

```
/user/eng/sources/design_notes       where: ~/notes/cells.md   script: headings   marker: mtime
  /holes                             text: "…"   level: 2   line: 40
    /first_pending_wins              text: "…"   level: 3   line: 58
```

## email and chat

What it is: threads of messages.

Hierarchy: thread, message by id, quoted parts as sub-regions,
attachments as nested sources.

Locator: the message id; never its position in the thread.

Change: the mailbox's uid validity and uid; `every`. A hand.

```
/user/sales/sources/northwind_thread   where: imap://…/INBOX   script: mail_thread   every: 300
  /m_48811     from: "jo@northwind.example"   sent: 20261019   subject: "Q4 order"   text: "…"
    /attachments/po_1182.pdf           kind: pdf   size: 88211    (opened → its own source)
```

## git history

What it is: a repository's commits; the past is part of the structure.

Hierarchy: commit, then the files it touched.

Locator: the commit hash; the file path.

```
/user/eng/sources/shrine_cells_history   where: /Users/ian/shrine-cells   script: git_log   marker: HEAD 8a7042f
  /8a7042f     author: "Ian_C"   when: 20261020   message: "kernel: if_case …"   files: 5
```

## logs and streams

What it is: lines in time with no stable id.

Hierarchy: time windows (day, hour), then notable lines.

Locator: the window; the offset is the marker, the line number position.

```
/user/ops/sources/foot_log           where: ~/worlds/fresh/out.log   script: lines_by_window   window: hour   marker: offset 884120
  /20261020/13                       lines: 412   errors: 2
    /e_1                             at: 20261020T13:41:02   text: "Incomplete request headers"   line: 3581
```

## time series and calendars

What it is: samples or events at instants; sensors are this.

Hierarchy: day, then the instant.

Locator: the instant.

```
/user/ops/sources/office_temp        where: mqtt://sensors/office   script: samples   every: 60
  /20261020/1300                     c: 215   c/scale: 1
```

## media

What it is: images, audio, video.

Hierarchy: boxes and time ranges.

Locator: the start instant or the box; the content is a transcript or a
caption, which is derived, and the region says by what.

```
/user/research/sources/deposition_video   where: ~/media/depo.mp4   script: transcript   marker: sha256
  /00_00_04    text: "Ardell Thomsen."   until: 00_00_06   speaker: "A"   derived_by: "whisper-large"
```

## archives

What it is: zip and tar; a tree of nested sources.

```
/user/legal/sources/discovery_bundle   where: ~/Downloads/production-004.zip   script: archive   marker: sha256
  /exhibits/ex_12.pdf                  kind: pdf   size: 400211   (opened → its own source)
```

## paste

What it is: something the person put in the chat: a table, a list, a log,
a message, a block of text. It is a source, not a question. Any other
kind on this page that arrives as a paste is that kind, with `where` the
chat.

Hierarchy: the paste's own: rows if it is a table, items if a list,
headings if it has them, the message itself if it is one.

Locator: the paste's own key, else its position (`item/3`), which here is
a locator because the paste never changes.

Content: the quotation, in the person's words; position: `pasted` (the
day).

Change: none; a second paste is a second artifact. Never a hand.

```
/user/sales/sources/paste_20261020_q4     where: chat   pasted: 20261020   script: none
  /rows/northwind    customer: "Northwind"   amount: 4200   status: "open"
  /rows/acme         customer: "Acme"        amount: 900    status: "closed"
/user/sales/views
  /refs/customers   reference over sources/paste_20261020_q4/rows (y)   key: /customer   table: ref ../customers
```

## other

A source not on this page is not a problem; the rule is the same. Write
its kind page as you meet it, in the format above, and the one judgement
that needs understanding the source is the hierarchy: which structure of
its own the source's citations use. Everything that moves between
versions is a position slot; everything that names a thing in the
source's own terms is a locator; what the source says is content and what
you think about it is a view. Keep the page beside this one so the next
agent meeting the same kind reads it instead of guessing.
