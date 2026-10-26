# Cartography: connect real things by judging, never by guessing

The world holds records from independent registries (`/user/registries/...`: USAspending, SAM, EPA ECHO, SEC
EDGAR, GLEIF, USPTO, ImportYeti, EIA, NIST MEP), each with its own identifiers, none joined. The kernel draws what
connects. Your job is to look, judge, and write back; the picture recomposes on the next read. This loop is the
same for an industrial atlas, supplier discovery, a corporate x-ray, grid intelligence, failure investigation or an
invention genealogy: only the standings and the questions change.

## The loop

1. **Stand.** Read the thing at `/x` (its own slots), then its world: `read /o/<case>/4/<node>/weft/graph/as_world/<n>/<path>`
   at care z, or the page at `/live?at=<path>`. Folders are the slot names of records pointing here; items say which
   world asserts them; `tentative` marks an item reached only through a text or a candidate.
2. **Choose standings.** For a question over several things, write a workspace cell
   (`sys/weft` → `/h/x/<case>/4/<node>/weft/graph/workspace`, `sys/tack` → the first standing, `standing/<k>` → the
   others, `depth`), read `/x/<cell>`: components, islands, routes with each hop's strength, gaps with their count of
   tentative routes. An island with a tentative route is the next thing to judge; an island with none needs a fetch.
3. **Judge a candidate.** A `candidates` record names what might be the same thing. Open both records and compare
   what the registries *state*: street and zip, NAICS and SIC, CAGE, legal name, parent, state of incorporation.
   Two records are the same thing when their stated identifiers agree beyond a shared name; a name alone is never
   enough. Write the judgement as a record beneath the thing:

       /user/registries/usaspending/recipients/<uei>/same/<slug>   {same -> the other record, why: <one sentence of evidence>, by: <you>}

   `why` is the note the overlay shows on the hop. Keep it concrete: "1400 73rd Ave NE 55432 on both; NAICS 335312
   on both; CAGE 44940 at that address".
4. **Read again.** The judged record's folders now hang under the standing as established edges (a facility's
   permits and inspections, an importer's suppliers, a patent's inventors). The workspace's components merge; the
   meter's solid reach grows; the tentative count falls. That change is the proof of the judgement.
5. **Fetch where nothing reaches.** An island with no route is a gap no registry bridges. Ask the web hand
   (`/agent/<a>/asks/<id> {asked, scope, shape}`) or the registries hand for the missing record; what comes back lands
   as a record with a source, and the loop continues from step 1.
6. **Leave a view when the question recurs.** A perspective worth reusing is a cell: the workspace over these
   standings, a `relations` over a facility, a `union` over a company's identities. Cells are records; the next agent
   finds them under `/user/views` and reads them instead of rebuilding.

## Writing rules

- Never write a `same` without `why`. Never promote a mention or a candidate by copying its target into a slot.
- Never invent a relation the registries don't state; "supplies", "operates", "owns" come from a record that says so
  (a shipment, a permit, a filing), cited by `source`.
- A disagreement between registries is a record too: two `same` judgements with different `why`, or a `claims`
  record under the thing, never a silent choice.
- Path segments: lowercase letters, digits and underscore, starting with a letter; the registry's identifier stays
  in a slot.

## What each case changes

| case | standings | what to judge | the view to leave |
|---|---|---|---|
| industrial atlas | a manufacturer (recipient or LEI) | its facilities, registrations, importer, patents | as_world of the manufacturer |
| supplier discovery | an MEP opportunity + candidate makers | NAICS/PSC in SAM against the item; facility and awards as capability evidence | workspace: opportunity + candidates |
| corporate x-ray | a CIK | GLEIF children and parents, recipients sharing its UEI tree, EDGAR Exhibit 21 names | union over its identities |
| grid intelligence | an EIA plant | its operator against SAM/GLEIF entities; ECHO facility at its address | as_world of the plant |
| failure investigation | an NHTSA campaign | manufacturer against registry entities; component against patents | workspace: campaign + maker + patents |
| invention genealogy | a patent | assignee against entities; inventors against authors | walk from the patent |
