# Registries: real things, independently recorded, connected by the world

The better bet than a web crawler: public registries that already record who is paid, where the facilities are,
who owns whom, what ships to whom, and what the plants are. None share a schema or agree on identity. Each is
written into the world as its own records, keeping its own identifiers and asserting only what it asserts. The
overlay draws what connects, and every unjudged match is a `candidates` record: a tentative edge, grey, never
promoted until an agent judges it `same`.

## Tested 2026-10-26 (what actually came back)

| source | access | identifiers and links it carries | first contact |
|---|---|---|---|
| USAspending | keyless API | recipient UEI, DUNS, parent name/UEI/DUNS, street, zip, business types; awards with agency, amount, NAICS, description; subawards with free-text descriptions naming real things | NAICS 335312: Cummins Power Generation, GE Aviation Systems, ABB, Discovery Energy...; subaward "excitation system replacement, Chief Joseph Dam, Bridgeport WA" (Reivax North America under Canadian Commercial Corp) |
| EPA ECHO / FRS | keyless, two-step (`get_facilities` → `get_qid`) | Registry ID, street, city, zip, NAICS, SIC, program flags, permits, inspections, lat/long | Cummins Power Generation Inc, 1400 73rd Ave NE, Fridley 55432, NAICS 333618 335312: the award's address |
| SEC EDGAR | keyless (user agent required) | CIK, SIC, EIN, state of incorporation, tickers, business address; full-text search; Exhibit 21 subsidiaries in 10-Ks | Cummins Inc CIK 26172, SIC 3510, 89 filings mentioning Cummins Power Generation |
| GLEIF | keyless API | LEI, legal name and address, status, direct and ultimate parent, children; fuzzy name completion | Cummins Inc LEI ZUNI8PYC725B6H8JU438 with parent links; the US subsidiary has no LEI, its UK and Singapore siblings do |
| ImportYeti | public pages via Firecrawl (plain fetch refused; API metered) | importer address, total sea shipments, "imports under N names and M addresses", suppliers with country, shipment counts, HS codes, goods | Cummins: 74,169 shipments, 310 names, 300 addresses; suppliers Bharat Forge (India, 2,076), Sundram Fasteners, Metaldyne, Shanghai Dong Feng Motor... |
| EIA-860 via PUDL | keyless parquet on S3 (EIA's own site serves HTML to downloads) | plant id, name, city, state, zip, lat/long, operator utility id and name, generators, ownership | Chief Joseph: plant 3921, Bridgeport WA 98813, operator USACE Northwestern Division, 27 units |
| NHTSA | keyless | manufacturer, campaign, component, summary | vehicle-centric; later |
| SAM.gov, PatentsView API, EIA API | key required | | USAspending already carries SAM's identifiers; PatentsView bulk files are signed links from its download page |
| Open Supply Hub, Thomasnet | subscription / no bulk | | skipped |

## The routes that exist on first contact

- award → recipient (UEI) → ECHO facility at the same street and zip → permits and inspections: three registries,
  joined by an address, judged by a person or an agent, drawn as a candidate until then.
- subaward → its description names "Chief Joseph Dam" → EIA plant 3921 → operator USACE: the description is a text,
  so the hop is a mention and the route is tentative end to end. That is the pointer: open the subaward, read it,
  judge it, and the plant becomes an established part of the contractor's world.
- recipient → parent UEI (USAspending) and → LEI parent (GLEIF) and → CIK (EDGAR): three independent statements of
  who owns whom, agreeing or not, each attributed.
- importer (ImportYeti, matched by name) → suppliers abroad with goods and HS codes: the supply chain nobody
  publishes, as customs evidence, tentative until the importer's 310 names are judged to be the recipient.

## The hand

`extras/mounts/mcp/hands/registries.py <base> [--naics 335312] [--since 2024-10-01] [--top 25] [--importers 4] [--pudl DIR]`
writes under `/<node>/user/registries/` (paths in its docstring). Candidates land at
`.../recipients/<uei>/candidates {echo_<id>, gleif_<lei>, edgar_<cik>, importyeti_<slug>}` and plant mentions at
`.../subawards/<id>/mentions`; `graph_views/mention` treats both as tentative (`candidate` and `mentioned` folders).
PUDL tables are read with pyarrow (a venv; the system Python refuses pip).

## What the agent does with it

Stand on a recipient. The overlay shows its awards (solid), its parent (solid), its candidates (grey): a facility at
its address, an LEI, a CIK, an importer. The meter counts the solid reach; the grey is the work. The agent opens a
candidate, compares street, zip, NAICS, name, writes `same` with its evidence, and the next read is wider. Islands
are the leads: a contractor with no facility, a facility with no contractor, a supplier nobody names.

## First load (2026-10-26, NAICS 335312, top 20 recipients, FY2025-26)

Into the migrated saved world: 20 recipients, 60 awards, 57 subawards, 52 ECHO facilities, 8 LEI records, 12
EDGAR companies, 3 importers with 7 suppliers each, 2 EIA plants named by 7 subawards; 213 records. Path segments
are lowercase letters, digits and underscore and start with a letter (`seg()`), the registry's own identifier stays
in a slot. Every record carries `name`, since the walker treats a record without one as a folder, not a thing.

Seen in the viewer at `usaspending/recipients/lszhmmeg8481` (Cummins Power Generation): its award with the full
description as a note, and its candidates. Until the kernel with the `candidates` rule is published, a candidates
record draws as a solid `candidates/<slug>` folder; after it, as a grey `candidate` edge.

## Open
- The first load wrote recipients under their uppercase UEI and facilities under bare numeric ids before the
  segment rule was settled; the second load wrote the legal spellings. The earlier ones are duplicates to cull,
  with Ian's word.

- The migrated saved world died under the hand's first writes until the boot script kept SIGPIPE ignored, as x/eden
  does (`restore_signals=False`); a client dropping a connection must not kill the runtime. A booted clone is
  rebooted with `.check/native-views/resume_candidate.py` (seconds), never with `boot_candidate.py` again: the full
  install republishes the mounts into a snapshot that already holds them and fails.
- ImportYeti slugs are guessed from names; a wrong guess is a wrong page, so the importer is a candidate, never
  more, until judged.
- EDGAR matches on the first word of a name; it will offer wrong public companies for common words, which is what
  candidates are for.
