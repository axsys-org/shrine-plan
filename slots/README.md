# Slot documentation: `reaver.slots/v2`

A `*.slots.json` file documents shared record keys. `system.slots.json` is the
canonical catalog for `/sys` and generates compiler declarations in
`src/foil/sys/slots.foil`, the `system_vocabulary` facade, and the namespace seed
records in `src/foil/slot_documentation.foil`. Edit the catalog, then run:

```sh
python3 x/slot_catalog.py
python3 x/slot_catalog.py --check
python3 x/slot-catalog-test.py
```

The checker requires valid documentation and byte-for-byte agreement with the
generated declarations. `x/check` runs it before the runtime suites.

```json
{
  "format": "reaver.slots/v2",
  "slots": [
    {
      "path": "/sys/face",
      "title": "Presentation binding",
      "summary": "Component constructor and cared scope used to present a datum."
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `format` | Exactly `reaver.slots/v2`. Incompatible format changes need a new version. |
| `slots` | Nonempty array of slot documents. Order is immaterial; generation sorts by path. |
| `path` | Unique absolute `/sys/...` key. Each segment matches `[a-z][a-z0-9_]*`. A slot cannot also be a namespace prefix. |
| `title` | Nonempty, single-line human-readable name. Published only as `/sys/lede`. |
| `summary` | Nonempty, single-line description of meaning, including absence/reset semantics when relevant. |

All fields are required. Unknown fields and duplicate JSON members are errors.
JSON comments are not supported. `system.slots.schema.json` supplies the structural
JSON Schema; the Python checker additionally enforces unique paths, non-overlapping
slot/prefix names, and generated-file agreement.

Version 2 replaces the version 1 `payload`, `scope`, and `machinery` fields with
`title`. Content/presentation filtering is maintained separately in
`src/foil/slot_presentation.foil`; editing documentation does not change that policy.

The catalog is deliberately about slot keys, not every path in the namespace.
`/sys/slot/*` and `/sys/slots/*` presentation selectors, Goo labels, application-local
fields and service addresses have separate contracts. Dynamic keys accepted by
open records are not exhaustively cataloged. Add shared keys here before using them.

During system bootstrap, the generated documentation seeds are the sole source
of values on these slot records: `/sys/lede` holds the title and `/sys/help` holds
structured `lore` containing the summary, with an empty heading. The title is not
repeated in `/sys/help`. No `/sys/mold`, compiler artifact, or compiled path value
is added to these records. Values and Documentation read the same stored fields.

The Foil path constants remain available to compilation, and the slot paths retain
their assigned publication versions. Their compiler artifacts are retained in the
system build's module images, separately from the namespace records. Other compiled
definitions still publish their compiler metadata. Schemas and behavior guards
remain responsible for validating values stored under slot keys.

## Unification and ownership

The initial unification moved 69 former publisher-vocabulary keys under `/sys`,
including the Codex bridge family, producing 99 catalog entries. Six specialized
keys have since been consolidated, leaving 93 entries:

| Former key | Shared key |
| --- | --- |
| `/sys/doc` | `/sys/help` |
| `/sys/code` | `/sys/content` |
| `/sys/overlay_cache/source` | `/sys/from` |
| `/sys/overlay_cache/result` | `/sys/content` |
| `/sys/goo/receiver` | `/sys/content` |
| `/sys/goo/patch_query` | `/sys/content` |

The values retain their specific types; readers validate those types after
looking up the shared key. `bond` and component-specific helpers delegate to the shared
vocabulary. `source_mount/slot` and `grove_dev/slot` share
`system_vocabulary/source_slot`.

Service addresses still use `/{who}/...`. Publication preparation injects the
explicitly assigned publication authority into the compilation context as `who`.
`runtime_context/service` uses that context, independently of vocabulary location.
System compilation has no runtime owner and cannot evaluate this helper. The
context pin, including `who`, participates in compiler cache identity. Compiled
artifacts retain their defining context; importing an artifact does not rebind its
services to the importer. Recompile it to change its owner.

This is a fresh-publication migration. Rebuild system and local artifacts and
restart the namespace. Existing persisted records using publisher-prefixed keys
or the six retired keys above are not rewritten or read through aliases.
There is no automatic state migration.
The publisher-owned compiler artifact key (`/{who}/compiler/artifact`) is unchanged.
