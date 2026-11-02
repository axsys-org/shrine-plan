# Digestion: prose becomes the namespace, progressively

One shape. A thing is a record at a path. Everything said about it is a record beneath it with one slot (a
reference or a value), the sentence that says it, in the source's words, and the source. A text is a record too:
its prose is a note, and a reference inside the prose is the path in brackets. Nothing else. The kernel reads that shape as it reads everything: a slot is a folder, a
note is the words beside a line, the index finds a line from the other end. Digestion is the gradual translation
of prose into that shape. Nothing is extracted and nothing is lost: a page never loses a word, each sentence gains
addresses, and what is still only prose is what is left to do.

## The gradient

    0  a text lands           one record; its prose is the note, its url the source; its headings its hierarchy
    1  brackets go on         a reader writes each name as its path in brackets; the index sees the reference
    2  sentences move         a sentence that pins something becomes a record beneath the thing it is about
    3  slots come out         the values a sentence states become slots; the note shortens
    4  things come out        a sentence about something unnamed becomes the path that names it, sentence in hand
    ∞  residue                what nobody placed stays on the text, and shrinks as the things grow

### 0. A text lands. It is a record. Its text is a note.

    /web/verisk_com/press/2026_07_29
      title  "Verisk Acquires McKenzie Intelligence Services"
      url    https://www.verisk.com/press/...
      text   "Verisk today announced it has acquired McKenzie Intelligence Services, a London-based
              geospatial intelligence firm founded in 2014 by Forbes McKenzie, a former British Army
              intelligence officer. The deal, completed on 29 July 2026, adds McKenzie's catastrophe
              response work to Verisk's extreme-event solutions, led by Bill Churney. Terms were not
              disclosed."

A page with headings keeps them: each region lands beneath the page under its heading, nested by level, with its
own text. A hyperlink the author wrote is already a reference: its target lands where
its own scheme says, a name that is empty until someone reads it.

### 1. Someone reads it and puts brackets around the names. Same record, same note.

    /web/verisk_com/press/2026_07_29
      text   "Verisk [/orgs/verisk] today announced it has acquired McKenzie Intelligence Services
              [/orgs/mckenzie_intelligence_services], a London [/places/london]-based geospatial
              intelligence firm founded in 2014 by Forbes McKenzie [/people/forbes_mckenzie], a former
              British Army [/orgs/british_army] intelligence officer. The deal, completed on 29 July
              2026, adds McKenzie's catastrophe response work to Verisk's extreme-event solutions, led
              by Bill Churney [/people/bill_churney]. Terms were not disclosed."

A path in brackets is a reference; the index holds it under the slot the prose sits in, `text`. Writing
`[/orgs/mckenzie_intelligence_services]` after "MIS" is the reader's judgement, and it is in the reference itself:
no candidate record, no why. A name the reader cannot place has no bracket, and stays prose, visible as such. Verisk's page now ends with the text and its sentence, because the index
found the slot and the overlay drew the hop with the words around the bracket:

    Verisk
      …
      /web/verisk_com/press/2026_07_29   "[verisk] today announced it has acquired [mckenzie] …"

### 2. Sentences move to the pages they are about. The note travels with them.

    /orgs/verisk/acquired/mckenzie_intelligence_services
      acquired → /orgs/mckenzie_intelligence_services
      note   "[verisk] today announced it has acquired [mckenzie]; the deal, completed on 29 July 2026,
              adds [mckenzie]'s catastrophe response work to [verisk]'s extreme-event solutions, led by
              [bill_churney]"
      source → /web/verisk_com/press/2026_07_29

    /orgs/mckenzie_intelligence_services
      note   "a [london]-based geospatial intelligence firm founded in 2014 by [forbes_mckenzie], a former
              [british_army] intelligence officer"
      source → /web/verisk_com/press/2026_07_29

    /web/verisk_com/press/2026_07_29
      text   "Terms were not disclosed."                        ← what nobody placed yet

A moved sentence keeps its brackets; they are references wherever the sentence sits. The slot is what the sentence pins; the note is the sentence; the source is the text.

### 3. Slots come out of the notes. The notes get shorter.

    /orgs/verisk/acquired/mckenzie_intelligence_services
      acquired → /orgs/mckenzie_intelligence_services
      acquired_on  20260729
      note   "adds its catastrophe response work to [verisk]'s extreme-event solutions, led by [bill_churney]"
      source → /web/verisk_com/press/2026_07_29

    /orgs/mckenzie_intelligence_services
      location → /places/london
      founded  2014
      note   "a geospatial intelligence firm"
    /orgs/mckenzie_intelligence_services/founder/forbes_mckenzie
      founder → /people/forbes_mckenzie
      note   "a former [british_army] intelligence officer"
      source → /web/verisk_com/press/2026_07_29

A value is placed exactly like a reference. When a second text says `founded 17 February 2011`, that is a second
record under the same folder with its own sentence and source; nothing is chosen and nothing is overwritten. The
thing's own `founded` holds a value only when someone settles it, by a plain write.

### 4. Things come out of the notes. Each takes its sentence with it.

    /orgs/verisk/extreme_event_solutions
      name    Extreme Event Solutions
      part_of → /orgs/verisk
      led_by  → /people/bill_churney
      gained  → /orgs/mckenzie_intelligence_services
      note   "adds its catastrophe response work"
      source → /web/verisk_com/press/2026_07_29

A sentence about something the world had no name for becomes the path that names it. A path several texts land
on is what makes a thing a thing: recurrence, not a schema, earns it a name.

### Identity, the one judgement that remains

    /people/forbes_mckenzie/same/forbes_mckenzie_0x13
      same   → /0x11/0x13/user/people/forbes_mckenzie
      note   "0x13 cites the same page; founder of [mckenzie] in both"
      source → /web/fintechprofile_com/forbes_mckenzie

Two records in two worlds are two things until a `same` joins them. It has the shape of every other assertion.
The world the record sits in says who judged. Joined, every sentence either world placed reads as one page. A
page that two people fetched is one page by its scheme (the url is its identity), and the hand that lands it
writes that `same` with the scheme's own words; two readers who digested the same page meet through it, because
`source` is a reference the overlay follows like any other.

## Read as a world. Everything above is one tree. Open any name and it is the top.

    Verisk
      acquired
        McKenzie Intelligence Services              29 July 2026
          location   London
          founded    2014 · 17 February 2011
          founder    Forbes McKenzie                "a former British Army intelligence officer"
          "a geospatial intelligence firm"
      extreme event solutions
        led by     Bill Churney
        gained     McKenzie Intelligence Services   "adds its catastrophe response work"
      /web/verisk_com/press/2026_07_29
        "Terms were not disclosed."
      ← flood review                                a cell somebody left; its lines beneath

Folders are slots. Lines are things, or values. The words beside a line are a source's sentence. A world tag
appears only when the world is not yours. A text that names the thing is a line with the sentence that names it,
dashed: named, not asserted. A cell that reads the thing is a folder under the cell's own name. Every line opens
the same page from there.

## Views are the decomposing method

Three pages that share names are related by the names, and nothing else; no topic, no tag. A view is a record
whose formula is an operator and whose input is a name: read at x it is a count, at y a list, at z a tree, and the
tree is namespace. It pulls, out of several notes, the thing they share and the things that share it, and leaves
that at a name. Point a slot at it and its result is a folder there, and the next reader never knows a formula
made it. Change a parameter and it is reused at another name. Tack one view on another and the result of the first
is the input of the second. Every thing a view reads shows it as a folder under the view's own name. Views are the
only decomposing tool: digestion by hand and digestion by formula are the same move.

## What the kernel knows, and what it never names

Forward, the kernel knows a slot. Backward, it knows one fact: something references this, and where the reference
sits (a slot of a record, or a cell's input). It ships no vocabulary for either: no `mentions`, no `candidates`, no
`links`, no `mentioned`, no `_of`, no `claims` protocol, no `why`, no topics. The labels on a page are the slot
names somebody wrote; a reference in prose is drawn as the sentence that holds it. A grouping anyone wants is a cell they
write, under the name they choose. The defaults stay small: the overlay (slots forward, references backward, to a
depth, several standings at once), the union (what every world says, by world), the frontier (one level).

## Rules for the digesting agent

- A text is one record per region, keeping the page's own hierarchy; a thing it names is written into the prose as
  its path in brackets. A name with no bracket is a name waiting to be placed.
- One record per sentence per thing: the slot it pins, the sentence in the source's words with its brackets, the
  source.
- A value that disagrees with another source is a second record under the same folder, never an overwrite.
- A thing a text names but says nothing about is a bracket until the first sentence about it becomes its path.
- Paths are the agent's naming: lowercase letters, digits and underscore, starting with a letter. The source's
  identifier stays in a slot.

## Today, and the step after

Built: a reference inside prose is indexed like any other (the web hand lands regions by heading hierarchy with
hyperlinks written into the prose as paths); assertion records with `note` and `source`, read as folders with the sentence beside the line;
`source` followed by the walk, drawn as attribution; `same`; a cell that reads a thing is a folder under its name;
a text naming a thing is drawn as the sentence around the bracket; standings, components, islands. Next, in order:
value assertions as folders (`founded ›
2014 · 17 February 2011`); the judge hand writing `note`, not `why`; `claims` retired into the one shape; the
bracket in a note rendered as the link it is; the web landing at `/user/web/<domain>/<path>`.
