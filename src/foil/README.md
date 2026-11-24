# Foil source layers

Production modules are listed in [modules.tsv](modules.tsv), in these
dependency layers:

| Order | Source | Responsibility |
| --- | --- | --- |
| Bootstrap | `sys/` | Public system definitions and their stable publication roots. |
| 1 | `types.foil` | Shared private container, store, namespace, and dispatch representations. |
| 2 | `stdlib/json.foil` | JSON values, parser, and encoder. |
| 2 | `stdlib/rex.foil` | Typed Rex construction, parsing, and traversal. |
| 2 | `stdlib/lint.foil` | Style diagnostics and rules; imports Rex. |
| 2 | `stdlib/base.foil` | Container operations, record helpers, vocabulary, reference indexing, pure view/graph policies, standalone utilities, and imports of the three modules above. |
| 3 | `namespace.foil` | Versioned storage, namespace composition, reads, transactions, dispatch, reactions, and publication primitives. |
| 4 | `vanes.foil` | Pact, HTTP, fetch, chore, filesystem sync, and schema behaviors. |
| 5 | `stdlib/runtime.foil` | Helm and Eden, actor adapters, Grove/Goo, presentation, compiler publication, and mount integration. |

For a first reading, pick a question and follow it across the files:

- **What changes when I poke a record?** Start at `writ` and `yell` in
  [sys/shrine.foil](sys/shrine.foil). Follow `sovereign_run_event` to
  `namespace/step` in [namespace.foil](namespace.foil).
  [tests/namespace_dispatch.foil](tests/namespace_dispatch.foil) shows both
  a child write that commits and a forbidden journal write that rejects
  the whole event.
- **What did this path contain at case 2?** Read `care` and `safe` in
  [sys/shrine.foil](sys/shrine.foil), `track` in [types.foil](types.foil),
  then `namespace/page`. Case numbers are local to a path and care;
  the clock maps them to store epochs.
- **Why did a failed edit leave the old assets visible?** Read
  `source_mount/reconcile_one` in [stdlib/runtime.foil](stdlib/runtime.foil).
  [tests/source_mount.foil](tests/source_mount.foil) follows the same mount
  through a successful publish, a failed one, and a repair.

Imports may point to the same or earlier layers; the complete production
import graph must remain acyclic. `types.foil` imports the required `sys`
modules. Runtime imports `stdlib/json` with a prefix for JSON parsing,
which must remain distinct from its own semidoc `parse` declaration.
Section comments identify the remaining groups within each file.

## Source inventory and ownership

Each tab-separated row in `modules.tsv` records a loader name, dependency
layer, and publication owner. Every production `.foil` file needs a row;
fixtures and mounted applications have their own inventories. The layer gate,
production compile roster, source publisher, and live reload capture use this
inventory. Missing files, unknown owners, ownership chains, duplicate entries,
and ownership across the system/local boundary are rejected.

A loader name chooses a source file. A publication owner chooses the root
passed to the publisher's resolver. JSON, Rex, and lint all retain
`stdlib/base` as their owner. For example, JSON's `json/str` declaration still
publishes beneath `/<node>/lib/stdlib/base/json/str`, even though its source
is now `stdlib/json.foil`. Declaration paths within the file remain unchanged.
Multiple files may share an owner, but cannot claim the same declaration.

Bare imports of `stdlib/base` still expose the extracted declarations through
transitive imports. An explicit `[at=…]` prefix applies only to the directly
imported module, so prefixed JSON callers import `stdlib/json` directly.
This follows the existing import rules; source aliases do not determine brands.

When extracting another section, add its inventory row with the existing
owner, preserve its declaration paths, and update imports. Moving a type to a
new owner changes its public path and requires a migration. Merely moving it
to another source file with the same owner does not.

`types.foil` may include constructors and small representation helpers. Helpers
that need slot vocabulary belong in `stdlib/base.foil`; operations that
interpret or change the store belong in `namespace.foil`. Higher layers retain
their own private data types. HTTP and filesystem actor adapters live with Helm
in the final layer, above the corresponding service behaviors.

Fallible store and dispatch operations use `either[iota T]`: `err` carries the
failure code and `ok` carries the result. Kernel success carries
`[fate=fate ack=maybe[path]]`; a command acknowledges its path, while a
notification has no acknowledgement.

Import module names omit the extension, for example `- namespace` or
`- stdlib/runtime`. Declaration paths such as `namespace/create` and `http/cfg`
do not change. Local publishers split canonical owner names into path segments
using `foil-source:module-segments`; Eden's boot declaration is published beneath
`/<node>/lib/stdlib/runtime/eden/boot`. The publisher chooses the authority and
publication prefix. Historical `[order=…]` annotations are not layer boundaries.

`x/slot_catalog.py` owns `sys/slots.foil` and the explicitly marked generated
sections in `stdlib/base.foil` and `stdlib/runtime.foil`. It updates only those
sections, preserving all surrounding handwritten code. Edit
`slots/system.slots.json` to change the generated vocabulary and documentation.

`tests/` contains native tests and shared test harnesses classified in
`test-inventory.json`. `test_fixtures/` contains compiler examples and fixtures;
`fixtures/` contains filesystem test data. Production cannot import these
directories. Application tests remain in `extras` and run through
`extras/x/check`.

Run `python3 x/foil_layers.py` to check boundaries, missing imports, and cycles.
`x/check` runs this gate and its regression tests before compiler and runtime
suites. Run `x/check foil-compile-all-tests` to compile all production sources;
native and compiler fixture coverage stays in the other test suites.

The event, schema, and view definitions live together in `sys/shrine.foil`.
Their public brands now use that module, with `crew/pail` replacing `cpail`
and `flaw` replacing `definition_reference`. Consolidation also changes
declaration ownership and source module names. The earlier `sys` consolidation
requires rebuilding system artifacts and their callers together. Subsequent
local file splits preserve declaration ownership through the inventory.

## Live core reload

Start Eden with `x/eden --wire-port 8679` and the desired mounts, then run
`x/reload-core --port 8679` after editing production Foil sources. This rebuilds
the local production graph rooted at `stdlib/runtime`, including the extracted
JSON, Rex, and lint modules, followed by all selected mounts in dependency order.
The launcher captures every local inventory source and the manifest before
preparation; the editor also invalidates its cache when the manifest changes.
The existing `/sys` publication and node identity remain selected. The running
launcher must include this inventory-aware loader; Foil reload does not replace
the Reaver host or Python launcher.

Reload retains the defining moments and published records of existing types
whose schemas are unchanged, including opaque type parameters. It matches
types by canonical declaration path across source modules, so extraction and
source-file retirement preserve existing brands and stored typed values.
Functions and values receive new publication cases. Removing a type or changing its schema
requires an explicit migration; reload rejects that candidate. Newly introduced
types are published normally. The host's continuation entrypoints must also
retain compatible parameter and return types.

The supervisor serializes preparation with namespace requests. Requests queue
while it compiles, validates, and publishes into an isolated candidate. A core
or mount failure discards the candidate, preserving the active code, namespace,
and history. A successful handoff retains actor handles, HTTP sockets, pending
responses, and stream registrations; subsequent requests use the new code.
Application activation hooks are not rerun, so boot seeds do not overwrite live
application records. Registered feet outside Eden's HTTP and filesystem pair
currently cause reload to reject rather than leave a partly upgraded world.

`python3 x/core-reload-test.py` (with `WISP` set) exercises successful replacement,
retained current and historical records, failed candidates, and a repaired
reload in an isolated checkout and world. It requires loopback listener access.

Add `--split-stdlib` to that regression to boot with a reconstructed monolithic
base, commit JSON and lint values, then introduce the extracted files and new
inventory into the running world. It checks typed reads of both current and
historical values after replacement and after rejected candidates.
