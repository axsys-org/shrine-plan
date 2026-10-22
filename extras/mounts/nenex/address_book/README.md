# Shared addresses and CRM projections

The Nenex publisher declares address and contact roles in `../library.grove`.
Slot identities are under `/0x11/gov/nenex_ui`; use the full identities, not
bare keys such as `address`, `person`, or `status`. This uses the existing
publisher so definitions can be rescanned without restarting the running world.

An address is structured data. Number, unit and postal code are **text**;
street, locality, region and country are **path values** to shared records.
The initial role describes the US-style demonstration; international address
formats require additional roles/formatters rather than invented components.

A contact refers to a person and optionally an organization. Its optional
`contact_workplace` points to a nominated contact-address association. Each
association has its own contact, address, purpose, verification and evidence
paths. Additional associations can coexist without replacing the nominated
one. The present projection uses the nomination; it does not automatically
select an address based on dates or interpret a workplace as a home address.
Dates, when supplied, are source-reported ISO date strings, not an automatic
validity policy. Absent facts remain absent.

Entity links use path pails, which Nenex discovers as typed outgoing edges.
Every join target carries `/sys/about` naming its stable subject identity.
Cell dependency bindings use safe references with explicit care. Source
records retain the imported/generated values; corrections change the normalized
address, not the evidence. `/h` can pin an earlier address. Evidence records
are ordinary namespace records, not access-controlled immutable storage.

`model.projections` binds the existing native Foil `lookup` and `join` cells:

1. Resolve address component labels against the shared directory.
2. Derive address lines and a mailing-style display label.
3. Resolve contact person, nominated association, purpose and verification.
4. Join the shared address label into the contact projection.

Outputs live at `/x/<cell>` and are read-only. This is a composition of existing
cells, not a new `/o` constructor or a second evaluator. No fields are copied
back from projections. To edit, write the source address, person, or association.
Missing joins preserve a contact without producing an address label. The display
label is not a postal validation or deliverability result. These bounded demo
joins are linear scans; large imports need indexed/bounded inputs and profiling.

Grove roles provide structural types and matching. They are not database foreign
key constraints or an admission policy rejecting arbitrary namespace writes.
The installer checks its inputs and refuses to overwrite an existing directory.
All generated addresses and contact associations are marked synthetic and
`demo_unverified`; the importer never infers personal addresses from map data.

## Use

The existing Nenex mount publishes the roles after a normal rescan:

```
apply path=/0x11/io/fs/nenex operation=/0x11/io/fs/nenex/op/rescan inputs={}
```

Wait for `/sys/fs/source/ready` on the mount control record. Failed publication
keeps the prior definitions. No world restart or application reset is needed.

Run the isolated live integration check, then seed the existing sample CRM:

```sh
python3 extras/mounts/nenex/address_book/install.py --check
python3 extras/mounts/nenex/address_book/install.py --install
```

`--base`, `--crm` and `--directory` select another instance. The projection
recipe accepts independent contact, directory and association inputs; the test
uses its own namespace rather than the user's records. Success culls the test
subtree; a failed check leaves its unique subtree for diagnosis. Tests exercise
shared-address propagation, unknown relationships, text postal codes, pinned
history, source evidence preservation, unrelated facets and derived-write refusal.

The installer adds person facets to all sample contacts and nine fictional
workplace associations sharing three addresses. Existing CRM fields remain for
compatibility. A replay batch is saved to `/tmp/nenex-address-records.json` by
default (`--batch-file` changes it). The current world is ephemeral: retain the
batch and the original CRM seed before restarting. Re-running installation on
an existing directory refuses rather than resetting edits.

## Official Austin catalog

`download_austin.py` retrieves the City's entire published Addresses layer with
`returnGeometry=false`. It captures the object-ID set, retrieves bounded ID
ranges, checks every requested ID, and retains exact source attributes in
`records.jsonl`. The SHA-256 and retrieval interval live in `manifest.json`.
This is a complete capture of that published layer, including surrounding areas
and utility address points; it is not a city-limits or residential-address filter.
The server does not provide a transactional snapshot across download requests.

```sh
python3 extras/mounts/nenex/address_book/download_austin.py
python3 extras/mounts/nenex/address_book/austin.py prepare
python3 extras/mounts/nenex/address_book/austin.py install
python3 extras/mounts/nenex/address_book/austin.py verify
python3 extras/mounts/nenex/address_book/austin.py search --query '301 W 2ND'
```

The full source and replay records are under `.local-data/austin-addresses/`
(excluded locally from Git). Preparation archives the source and metadata under
`archives/<source-sha256>/` so a later download cannot replace earlier evidence.
Preparation preserves source Place IDs, fractions,
directions, street types, parent IDs, segment IDs and source object IDs. It never
supplies absent locality, postal code or unit values. The address role consequently
requires number, street and source; its locality/postal components are optional.
`ADDRESS_TYPE=1` is the source's Address classification. Other source codes remain
available; code 16 occurs in the data but is not documented in the retrieved domain.

The real catalog lives at `/0x11/user/austin_addresses`, outside the synthetic CRM.
Addresses are grouped by `PLACE_ID // 1000`; the source ID set guarantees at most
1,000 rows per page. Street designations use a digest of the normalized component
tuple and 256 bounded hash buckets. These identities describe source street-name
values, not proven physical street connectivity. Both are expanded by native
Grove/Foil lenses published by Nenex. There is no geometry dependency.

`/x/<page>` is useful for displaying a collection. An individual virtual child
requires the native `/o` lens, whose syntax includes the pinned function case and
source-page path length. Each page's `result` is that lens path. Append
`/place_<PLACE_ID>` to address a particular record; the local `search` command
returns the complete usable path. The record's `/sys/about` is the same path,
and its street slot points to an independently readable street lens record.
Function versions and source-snapshot identities are explicit in these references.
A new snapshot needs explicit rebinding; existing CRM evidence can keep old refs.

The packed source pages are ordinary versioned records and the expanded address
slots are read-only. A local correction should be stored as a separate overlay
input/association, not written into the source lens. Raw provenance is retained in
the exact local archive and its digest; each address also identifies its source
page, Place ID and Object ID. Local artifacts are required to replay after restart;
the live world remains ephemeral.

To use real records in a bounded CRM view, build `model.address_selection` from
specific `/o` paths and pass its output to `model.projections(address_table=...)`.
The table contains references, not copied address fields. No real address is
assigned to any synthetic or real person by the import. The existing demo CRM
continues using its explicitly fictional addresses.

`install` checkpoints acknowledged batches in `installed.json`; a transport failure
stops rather than guessing whether the pending batch committed. Replaying that
same deterministic batch is safe for this owned snapshot. Do not reuse the cursor
after rebooting a world; verify its catalog and start a fresh import into the new
world. `verify` checks every address and street binding/count and samples first/middle/last/
largest expansions, including direct reads of address and street references.
It does not claim to have re-read every expanded field of every address.

The v2 packed encoding uses `|` between fields and `~` between records, rejecting
these reserved delimiters in source strings before publication. This avoids the
runtime JSON parser's cost for repeatedly escaped tabs/newlines. It is an internal
encoding, not an alternative address schema; the original raw JSONL is unchanged.
The native `/o` lens is published separately from Grove's `/x` presentation
wrapper so individual children can be resolved, pinned and used as dependencies.

After the catalog is installed, the real-reference integration check is:

```sh
python3 extras/mounts/nenex/address_book/check_austin_crm.py
```

It reads Place ID 91412 and its street, binds that address into a temporary,
explicitly synthetic CRM contact, verifies the derived address label, and culls
that test subtree. It does not alter the user's CRM associations.
