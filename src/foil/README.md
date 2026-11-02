# Foil source layers

Production code consists of the unchanged bootstrap modules and five layer
files, in this dependency order:

| Order | Source | Responsibility |
| --- | --- | --- |
| Bootstrap | `sys/` | Public system definitions and their stable publication roots. |
| 1 | `types.foil` | Shared private container, store, namespace, and dispatch representations. |
| 2 | `stdlib/base.foil` | Container operations, record helpers, vocabulary, codecs, and standalone utilities. |
| 3 | `namespace.foil` | Versioned storage, namespace composition, reads, transactions, dispatch, reactions, and publication primitives. |
| 4 | `vanes.foil` | Pact, HTTP, fetch, chore, filesystem sync, and schema behaviors. |
| 5 | `stdlib/runtime.foil` | Helm and Eden, actor adapters, Grove/Goo, presentation, compiler publication, and mount integration. |
o
Each layer imports its predecessor; `types.foil` imports the required `sys`
modules. Runtime also imports base with a prefix for JSON parsing, which must
remain distinct from its own semidoc `parse` declaration. Imports may only point to earlier layers, and the bootstrap import
graph must remain acyclic. Section comments identify the former modules inside
each file. Additive namespace declarations retain their existing member names.

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
do not change. Local publishers split module names into path segments using
`foil-source:module-segments`; Eden's boot declaration is published beneath
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

Consolidation preserves public `sys` definitions but changes private declaration
ownership and source module names. Rebuild local compiled artifacts and
publications together with their callers. Removed module paths and stored
private identities are not compatibility interfaces.
