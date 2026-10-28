# Shrine: the architecture

The world is records at names, with references. The kernel indexes references both ways and evaluates cells.
Everything else is somebody writing. The overlay reads all of it as one tree from wherever you stand.

    ┌──────────────────────────────────────────────────────────────────────────────────┐
    │  the scheme        where a source lands, which slot is its identity   (templating)│
    │       │                                                                           │
    │       ▼                                                                           │
    │  the mirror        /web/<domain>/<path>   /registries/<source>/<id>   /<node>/…   │
    │       │                                                                           │
    │       ▼                                                                           │
    │  the gradient      prose → references → sentences on things → things pulled out → residue│
    │       │                       (by hand, or by a cell: the same move by formula)   │
    │       ▼                                                                           │
    │  the namespace     records at names; slots forward; the index backward; same      │
    │       │                                                                           │
    │       ▼                                                                           │
    │  the overlay       any standings, read as one tree; components; islands           │
    └──────────────────────────────────────────────────────────────────────────────────┘

Four layers, one direction of motion, no layer invents a word the one beneath it does not have.

## 1. The kernel does four things

- **Names.** A record at a path holds slots: values, or references to other names. `/h/<care>/<case>/<len>/<path>`
  pins a name at a case; case 0 is live. A world another node wrote sits under its own node: `/0x11/0x13/user/…`
  is 0x13's, kept by 0x11, untouched.
- **References both ways.** The reverse index is derived state, maintained where every write already passes,
  snapshotted so a pinned read sees the edges of its time. `/r/<len>/<path>` reads what references a name.
  Nothing is searched for; everything is named.
- **Cells.** A record with a formula (`/sys/weft`) and an input (`/sys/tack`) is a cell. `/x/<cell>` is its result,
  `/c/x/<cell>` its context, `/o/<case>/…/<definition>/…/<data>` applies a definition to data without a cell.
  Read at x a cell is one answer, at y a list, at z a tree; the tree is namespace. A cell's result can be another
  cell's input, or a standing. The only tell is that nobody wrote it.
- **The overlay.** One definition under `/weft/graph`, applied by path, never by closure. From any standings it
  walks slots forward and the index backward, through `same`, to a depth, and draws one virtual root per connected
  component with each standing unfolded as a world beneath. It ships no vocabulary: a folder is a slot as its
  author spelled it, the note's slot when the reference sits in prose, or the cell that reads the thing. What
  kind of edge a hop is, is what holds it. Nothing drawn is stored.

That is the whole kernel surface this product uses. No second store, no index service, no overlay language, no
supervisor card, no view cache: each of those was a wrapper around something the kernel already did, and each
was cut. Native means fewer spellings, not more.

## 2. The scheme: the front line

A source scheme is a template, outside the kernel, in the source's own terms. It says three things and no more:

    where it lands        the hierarchy mirrors the source: domain, then path, then region (the web);
                          source, then kind, then id (a registry); itself (another node)
    which slot is identity the segment or slot that makes two arrivals the same thing: the url, the uei,
                          the lei, the registry id
    which fields are shared the slots two sources fill in common (name, street, zip, naics), so the union
                          compares like with like and a candidate can be judged on what is stated

and, beside them, how to fetch: endpoint, key, paging. The landing places are records too: the site, the
registry, the section, each a thing whose parts are what landed there. A new source follows the scheme to its
place and lands beside its siblings; read the place as a world and every source that landed there is a line, with
what each connected to beneath it. Placement is deduplication: a thing that arrives twice
lands at one name, and a thing that arrives from two sources lands at two names that share fields, which is
exactly what a judgement needs. The scheme never decides a relation. Relations come from the references the
content carries, and from the hierarchy itself: a region beneath a page, a plant beneath its registry, are
relations through placement, drawn by the overlay like any other.

    sources/usaspending.json       sources/web.json
      land:   /user/registries/usaspending/<kind>/<id>     land:   /user/web/<domain>/<path>
      identity: uei                                        identity: url
      shared: name, street, zip, naics, parent             shared: title, text
      fetch:  endpoint, key, paging                        fetch:  firecrawl, trafilatura

Provenance is the higher-order relation. Every line carries `source`, and every source sits in a bucket the
scheme made; the overlay follows both. Stand on two buckets and the hops between their records say how the
buckets relate: a `same` on street and zip, a `parent` through a filing, a `registration` by the same identifier,
a reference in a text's prose. A new source landing in a bucket inherits those crossings as the first thing to try, and a cell
left at the bucket does the crossing by formula for whatever lands later, comparing the fields the scheme calls
shared. Nothing new is written for this: the bucket, its kinds and its records are things; the crossings are
slots; the pattern is a cell.

## 3. The gradient: content becomes namespace

A text is prose until its sentences land. The move is always the same (`DIGESTION.md` has the worked case):

    0  the text lands where its scheme says; its prose is its note, its url its source, its headings its hierarchy
    1  a reader writes each name into the prose as its path in brackets; the index holds it under the
         note's slot; a hyperlink is already that, the author's own reference, landed where its scheme says
    2  a sentence that pins something becomes a record beneath the thing it is about:
         the slot it pins, the sentence in the source's words with its brackets, the source
    3  values come out as slots; a sentence about something unnamed becomes the path that names it
    ∞  what no sentence pinned stays on the text; the residue is the work left

One shape for everything said about a thing: one slot, one sentence, one source. A value and a reference are
placed the same way, so two sources that disagree are two records under one folder, nothing chosen. Identity is
the one judgement that remains, and it has the same shape: `same → other`, the sentence of evidence, the source.

A view is this move done by formula, and views are the only decomposing tool. Three pages that share a name are
related by the name and nothing else; no topic, no tag. A cell whose formula is an operator and whose input is a
name pulls, out of several notes, the thing they share and the things that share it, and leaves that at a name:
read at x a count, at y a list, at z a tree, and the tree is namespace. Point a slot at it and its result is a
folder there; change a parameter and it is reused at another name; tack one on another and a view reads a view.
Every thing a view reads shows it as a folder under the view's own name. The page's vocabulary is whatever people
and agents named; the kernel never learns a domain word.

## 4. The overlay: where source and record blend

A standing is any name: a thing somebody described, a page a hand fetched, a registry record, a cell's result.
They are the same kind of record, so the picture reads the same from each.

    Verisk                                        a thing
      acquired
        McKenzie Intelligence Services            "the deal, completed on 29 July 2026, adds …"   verisk.com/press
          founder
            Forbes McKenzie                       "founded in 2014 by [forbes_mckenzie], a former …"
      /web/verisk.com/newsroom/emerging-risks     "… [verisk]'s ISO general liability …"   what has not moved yet
      ← flood review                              a cell somebody left
        exposure · history · open

    /web/verisk.com/press/2026-07-29              a page
      text   "Verisk [/orgs/verisk] today announced it has acquired …"      its references, in its prose
      ← source
        acquired/mckenzie_intelligence_services · founder/forbes_mckenzie       what has moved

Early, a source is a leaf: a line at the bottom with the sentence that names the thing. As it breaks down, its sentences move up into the tree as
the words on the hops they justify, each still carrying its references, so a well-digested source is not gone
from the tree, it is spread through it, one clause per hop. Read down a branch and you read the source back in
the order the world uses it. Relations arrive two ways and are drawn alike: through the scheme (a region beneath
its page, a plant beneath its registry) and through the content (a reference in a sentence, a slot pulled out of it).
The holder says which.

Several standings read together find what no single source stated: standings that meet over any reference share
a root; a standing nothing reaches stands alone. The grey hops, the sentences that name a thing, are the only places the
picture can change, and they are listed. Digest them and the picture moves.

## 5. The motion

Three lines, in order of strength: placement and identity (a path is a fact); structuring (a slot somebody
committed to, by hand or by formula); notes with references (a relation that exists, that nobody has committed
to). Everything moves from the third toward the first. The only decisions anyone makes are where something lives
and what to call it; the kernel makes neither. Progress is how much is still only prose.

The agent's loop is the same motion: stand, digest, judge, read again, fetch where nothing reaches, leave a view
when the question recurs (`skills/shrine-mcp/cartography.md`).

## 6. What this cut, and why

| was | is | why |
|---|---|---|
| a Python index of references, with its own clock | `/r`, derived state committed with the epoch | one store |
| `mentioned`, `candidate`, `_of`, `tentative`, routes, gaps | the slot's name, `←`, components, islands | the kernel names no edge |
| `mentions`, `links`, `candidates` records, topics, tags | a path in brackets inside the prose | a reference in prose is a reference |
| `claims {slot, value, by, why}`, `same {why}` | a record under the slot's folder: value, note, source | one shape |
| a look card, a view cache, a query transport | `/x`, `/o`, `/r` read through the four MCP tools | nothing called them |
| an overlay token language, routed cells, crews | a cell is a record with a formula and an input | the kernel had it |
| the page assembling sections from five views | the page reads `overlay` and `union` | one view |

## 7. Where it stands

Built, on `ic-bare-loop-main`: the four kernel things, with a reference inside prose indexed like any other; the
overlay with components and islands; cells as folders under their names; computed results read on demand;
`source` followed and drawn as attribution; a text naming a thing drawn as the sentence around the bracket, the
bracket a link; the page as the tree. On `ic-bare-loop`: ten schemes as
JSON (`hands/schemes/*.json`), read by the registries and web hands for placement, identity, shared fields and
fetch; the web hand lands regions by the page's heading hierarchy with hyperlinks written into the prose; the digest
hand writes records with sources and notes.

Next, in order: the digest hand
retargeted to the one shape (sentence as note, one record per sentence); value assertions as folders; `claims`
and `why` retired; the bracket in a note rendered as the link it is; the web landing at `/user/web/<domain>/<path>`.

## 8. Convergence

The direction is the state where every reference is in a slot. A source arrives as prose. Each move takes a name
out of brackets into a slot, pulls a thing out of a note, judges two names one, or leaves a view that does one of
those by formula. Every move is a write the index keeps, so the unplaced prose only shrinks and the edges only
grow; the distance to the limit is visible on every page as the sentences still sitting on it. The limit is never
reached, because sources keep arriving, and that is fine: it is a direction, not a destination.

At the limit there is no grey. Then the overlay from any standing is everything true of it, the same tree read
from any root in its component; several standings either share a component, and their worlds are one tree, or
nothing in the sources ever related them, which is a fact, not a gap; and the union of a thing is just its page,
every world's statement already a slot with its source, agreements and disagreements side by side. The views were
never three: the overlay is the one read, the union is that read restricted to one identity by world, and the
grey is a reference whose holder is a text. The brackets are the whole job; they are what makes the picture from
two standings differ from the picture from one.

One caution the thesis needs: a wrong `same` connects what the sources never related, which is why a judgement
carries its sentence and its source, and why a retraction is a write like any other. Monotone means nothing is
lost, not that nothing is wrong.
