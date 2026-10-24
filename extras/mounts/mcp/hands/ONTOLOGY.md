# Paths, overlays, references: the ontology scheme

Nothing in the system knows what an organisation, a place or a product is, or what any slot name
means. Meaning is the model's judgement. The system has three structural things, and only three.

## 1. The path is the hierarchy

A record's path says what it is under. London lives at `places/united_kingdom/london`: being under
the United Kingdom needs no slot, because the path says it. Grouping folders are plain records in
the path: one worker is `orgs/verisk/bill`, many are `orgs/verisk/workers/<name>`, acquisitions are
`orgs/verisk/acquisitions/<name>`. A grouping folder has a name and, if useful, a description, and
nothing in the system knows what its name means.

## 2. One real record, placed anywhere by overlay

A thing has one real record, at the path where it most truly lives, holding its own slots and its
own children: McKenzie Intelligence Services lives at `orgs/mckenzie_intelligence_services`. Every
other place it belongs, it appears by overlay: `orgs/verisk/acquisitions/mckenzie_intelligence_services`
is a record whose `/sys/weft` is the standard `gather` formula and whose `/sys/tack` is the real
record, live, at care z. Reading the overlay's `/x` gives the real record, its slots and its whole
subtree, current to the moment. The overlay may carry slots of its own that describe the placement
and nothing else: `note: acquired 29 July 2026`, `since: 20260729`.

- **Descendants, recursively.** Under a path are its real children and its overlays; under an overlay
  is the real record's own subtree. So `orgs/verisk` at depth z shows its workers, its acquisitions,
  and each acquisition's own contents, without a copy anywhere.
- **Ancestors, aligned the same way.** A real record's ancestors are its own path's parents, plus the
  parents of every overlay that places it. McKenzie's ancestors are `orgs`, and, through its overlay,
  `orgs/verisk/acquisitions` and `orgs/verisk`. Nothing declares this; it is read from where the
  overlays sit.
- **Regrouping never moves a name.** A container introduced later gets overlays of its members; the
  real records stay where they are, because peers hold their names. A record filed in the wrong place
  is made at the right path and the old one is poked to `moved_to`.

## 3. Relations are placements, and their slots are computed

A record holds literals only: its name, its description, its own numbers, days and short texts. Every relation is a
placement. That Forbes McKenzie leads McKenzie Intelligence Services is an overlay of Forbes at
`orgs/mckenzie_intelligence_services/leaders/forbes_mckenzie`, carrying `role: founder` if the source says so. The
grouping folder's name is the relation's label, read from the container's side, and the same overlay is read from
Forbes's side as among the leaders of the company. One placement gives both directions; nothing is stored twice.
A fact's provenance is a placement too: the text it came from, placed under `<thing>/sources`.

The relational slots are then computed by the kernel. For every thing with relations, the links hand keeps a view at
`/user/views/related/<its path>`: a `gather` cell whose input is the thing and whose secondary inputs are its
placements, one slot per relation. Reading its `/x` gives the thing's literals with `leaders`, `acquisitions_of`,
`works_at` and the rest as live slots, recomputed from wherever the overlays sit. (The view lives outside the thing
because the kernel refuses a live view beneath its own input as a cycle.) A peer reads the view like any record.

## 4. The protocol: following a name

A peer that follows a path at a care receives the record (x), its children (y) or its subtree (z).
Overlays come with it, each naming a real record that may live in another world, resolved there by
name, live or pinned. One real record sits in many hierarchies across many worlds, with no copies,
no agreed schema and no agreed hierarchy: each world places things by overlay where its owner thinks
they belong, and every peer reading that world sees its placements over the shared records.

## 5. What the index computes

The links hand keeps paths, overlays and references in memory, current with the stream:

| query | answers |
|---|---|
| `around?at` | ancestors (path parents and overlay parents), descendants (children and overlays, resolved), relations read from placements in both directions |
| `placements?of` | every overlay that places a real record, with its notes |
| `between?a&b` | the shortest connection between two names through paths, overlays and references |
| `resolve?text` | which names a text refers to |
| `profile`, `shapes`, `signals` | label statistics, label-set groups, structural facts worth a look |

Signals are structural and judged by the model: dangling references, orphans, names written as text,
numbered labels, shared literals, texts not yet decomposed, overlays of records that no longer exist.

## 6. What the agent does

It files a new thing at the path where it most truly lives, under its container when one exists,
inside a grouping folder when the container has many of its kind. It places the thing everywhere
else it belongs by overlay, with a note when the placement has a story. It writes every other
relation as a reference. It reuses grouping-folder names and slot labels that already exist nearby.
Its rules name no domain.

## Research notes

Kernel: cells are pure functions of their slots, tack tree and secondary inputs, recomputed on read
(`sys/view.foil:24-29`, `lain_peek.foil:764-843`); `gather` with no secondary inputs returns its input
unchanged, so an overlay is a native cell today. Prior art: Freebase compound value types and Wikidata
qualifiers (facts with qualifiers as their own nodes), polyhierarchy in faceted classification (one
item under several broader terms), ISO 25964's split of broader terms, and owl:sameAs taken as a
judgement. The design here keeps one real record per thing and expresses every other placement as an
overlay, which is polyhierarchy without duplication.
