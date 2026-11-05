# Flow authoring in Nenex

Select `flow-authoring` to add the Nenex/Goo document interface to the native
[`flows`](../flows/README.md) executor. The mount depends on `flows` and `nenex`.
It adds no scheduler, separate work store or background provider process.
The optional Goo action adapter currently ships in this package because its
declaration interpreter is Explorer-owned. Thus generic headless flow execution
is independent of Nenex, while selecting these Goo actions still selects this
integration and its Nenex dependency; packaging them independently remains work.

The existing `/gov/flows/authoring` controls author and publish Semidoc, compose
captured operations, attach occurrences, inspect declared actions and turn
selected retained traces into editable source. Their namespace operations,
receiver guards, cells, holes and attempts are the same ones used by headless
invocation. `/gov/flows/nenex` supplies the final writer and the captured draft
writer; the latter applies Nenex's existing source/attachment protection.

The vocabulary and authoring Grove units share this mount's publication owner.
Public addresses and logical module names remain unchanged. Persistent flow
contracts remain in `flows`, so installing document integration does not create
another nominal version of work records.

Refreshing the flow commands checks the existing destination claims, their
controllers/views and bound source feeds. It does not validate or replace
unrelated answering, Nenex or provider behavior. Orphan source records are
validated by their source hand when it reads them; an unrecognized retained feed
is left untouched and yields no current evidence, rather than being rebranded.
A refresh does not update a
captured attempt's writer or replace a running world's reader/compiler.

A revision with a document form but no captured draft writer is refused. A newly
selected writer applies to newly attached work; historical attempts retain their
original values. The executor never borrows a current writer to rescue an old
capture. For application-independent requests, no document form is required.
Existing controllers have no writer-policy update operation; selecting new
policy needs a new attachment. A retained publication receipt can also require
a new destination, since provenance handoff is not implemented.

Use `extras/x/check --mount flow-authoring --suite flow_document_boundary_tests`
for document guards and `--suite flow-authoring-only-tests` for the compiled Grove
surface. Integration test fixtures may select examples or controlled providers;
those selections do not become runtime dependencies of the native `flows` mount.

HTTP source work is optional: select [`flow-web`](../flow-web/README.md) separately,
or use `flow-examples`, which selects both integrations.
