# Cartography: connect real things by judging, never by guessing

The world holds records from independent registries (`/user/registries/...`: USAspending, SAM, EPA ECHO, SEC
EDGAR, GLEIF, USPTO, ImportYeti, EIA, NIST MEP) and texts the web hand fetched, each with its own identifiers,
none joined. The kernel draws what connects. Your job is to look, digest, judge, and write back; the picture
recomposes on the next read. This loop is the same for an industrial atlas, supplier discovery, a corporate
x-ray, grid intelligence, failure investigation or an invention genealogy: only the standings and the questions
change. One view is the way of looking: a thing as a world. It is the same picture for you and for the person.

Your whole vocabulary is two writes. A note with references: what you found, in the source's words, every thing
it names written as its path in brackets. A view: what you want pulled out of what is there, by formula, at a
name. Everything else is reading: stand on something, read it as a world, see where it is thin. You never edit
anything shared, so you need no coordination with anyone: you add a note at a source's place or a view at a name,
and the overlay folds it in for everyone on the next read. The moment two notes reference the same name, the work
behind them is connected, whether or not either writer knew of the other.

## The loop

1. **Stand.** A session stands at a path, reads it as a world and writes there, notes and views, nothing else. Read
   the thing at `/x` (its own slots), then its world:
   `read /o/<case>/4/<node>/weft/graph/overlay/<n>/<path>` at care z, or the page at `/live?at=<path>`. Beneath
   `/0/<path>`: folders are slot names, forward (`out/<n>/<slot>`, what the thing asserts) and backward
   (`in/<n>/<name>`, what references it, under the name of whatever holds the reference: a slot as its author
   spelled it, or a cell by its own name; a text that names the thing is a line with its sentence). Each item names its world, the world asserting the hop
   (`by`) and the holder (`via`); the holder's other slots are the note on the line. A hop whose key sits in brackets
   in the holder's text is a name, not an assertion: that is the pointer to what to digest or judge next. Folders
   beyond the subject arrive closed, as counts; read the thing there as a world to open them.
2. **Choose standings.** For a question over several things, write a cell (`sys/weft` →
   `/h/x/<case>/4/<node>/weft/graph/overlay`, `sys/tack` → the first standing, `standing/<k>` → the others, `depth`
   1 to 6) and read `/x/<cell>` at z: `standings`, `components`, `islands`, then one virtual root `/<n>` per
   connected component with its standings unfolded beneath. Standings meet over any reference; a standing reached
   inside another's unfolding is listed there as seen. An island (a root of one) is the next thing to connect: a
   bracketed name reaching into it is a judgement waiting; none means a fetch.
3. **Digest.** Before reading a new source, stand on its landing place (`/user/web/pages/<host>`, `/user/registries/<source>`)
   as a world: the names its siblings already placed, the crossings they made into other buckets, and the cells
   left there are what to try first; none of it is a conclusion, all of it is where to look. The texts still to
   digest are the ones whose `← source` folder is empty, read from any landing place, so no queue hand is needed. Then
   the text: it is prose until its sentences land. Write each thing it names into the prose as its path in brackets,
   `[/0x11/user/orgs/verisk]`; that is a reference, the index sees it, the overlay follows it. Then each sentence
   that pins something as a record beneath the thing it is about: the slot it pins, the sentence in the text's
   words with its brackets, `source` → the text. A value that disagrees with another source is a second record under the
   same folder, never an overwrite. No record of any other kind, no topic: the shared name is the relation. The rules are in `hands/DIGESTION.md`.
4. **Judge.** A registry record's `candidates`, or a bracketed name reaching into an island, says what might be
   the same thing. Open
   both records and compare what the registries *state*: street and zip, NAICS and SIC, CAGE, legal name, parent,
   state of incorporation. Two records are the same thing when their stated identifiers agree beyond a shared name;
   a name alone is never enough. Write the judgement beneath the thing, in the one shape every assertion has:

       /user/registries/usaspending/recipients/<uei>/same/<slug>   {same -> the other record, note: <the sentence of evidence>, source -> what shows it}

   The note is what the overlay shows on the hop (older judgements say `why`; both are read). Keep it concrete:
   "1400 73rd Ave NE 55432 on both; NAICS 335312 on both; CAGE 44940 at that address".
5. **Read again.** The judged record's folders now hang under the standing (a facility's permits and inspections,
   an importer's suppliers, a patent's inventors); the components merge; the islands fall. That change is the proof
   of the judgement.
6. **Fetch where nothing reaches.** An island with no hop into it is a gap no registry bridges. Ask the web hand
   (`/agent/<a>/asks/<id> {asked, scope, shape}`) or the registries hand for the missing record; what comes back
   lands as a record with a source, and the loop continues from step 1.
7. **Leave a view when the question recurs.** A perspective worth reusing is a cell under `/user/views/<name>`:
   the overlay over these standings, a union over a company's identities, a grouping you wanted. It appears on
   every thing it reads as a backward folder of its own name, holding what it computes; the next agent finds it
   there and reads it instead of rebuilding. The kernel ships no vocabulary for groupings: the names on the page
   are the ones you and the person chose.

## Writing rules

- Never write a `same` without its note. Never promote a mention or a candidate by copying its target into a slot.
- Never invent a relation the sources don't state; "supplies", "operates", "owns" come from a record that says so
  (a shipment, a permit, a filing, a sentence), cited by `source`.
- A disagreement between sources is a record too: two `same` judgements with different notes, or two value records
  under one folder, never a silent choice.
- Path segments: lowercase letters, digits and underscore, starting with a letter; the registry's identifier stays
  in a slot.

## What each case changes

| case | standings | what to judge | the view to leave |
|---|---|---|---|
| industrial atlas | a manufacturer (recipient or LEI) | its facilities, registrations, importer, patents | the manufacturer as a world |
| supplier discovery | an MEP opportunity + candidate makers | NAICS/PSC in SAM against the item; facility and awards as capability evidence | overlay: opportunity + candidates |
| corporate x-ray | a CIK | GLEIF children and parents, recipients sharing its UEI tree, EDGAR Exhibit 21 names | union over its identities |
| grid intelligence | an EIA plant | its operator against SAM/GLEIF entities; ECHO facility at its address | the plant as a world |
| failure investigation | an NHTSA campaign | manufacturer against registry entities; component against patents | overlay: campaign + maker + patents |
| invention genealogy | a patent | assignee against entities; inventors against authors | walk from the patent |
