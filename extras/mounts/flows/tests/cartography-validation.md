# Cartography validation

The shipped procedures are `web-evidence.semidoc`, `cited-assertions.semidoc`
and `cartography.semidoc`. This is a bounded library example: selected HTTP
sources become cited claims, a selected Grove constructor projects those claims,
and the ordinary revision hand maintains a concept document. It does not install
search, a graph database, a refetch scheduler, or another work lifecycle.

## Native regressions

The focused native runs passed 205 assertions:

- `flow_cartography_tests`: 23 checks of formats, explicit subject selection,
  response shape, exact quotations, typed claim keys, projection constraints,
  live subject spelling and review refusal.
- `flow_cartography_lifecycle_tests`: 18 checks using the shipped Semidoc bytes
  and real native admission, hands, holes, Cells and document writer. HTTP and
  model outcomes are controlled. An invalid quotation is retained; an explicit
  retry replaces its head; conflicting evidence refuses review; changed evidence
  resolves the same hole and publishes. The test compares the old attempt's
  exact x/y/z history before and after completion.

The shared request guard suite passed 54 checks, including captured response
validators, thrown validator containment and retained-answer validation. Native
installation passed 10 checks, and the Nenex flow interface passed 64. The HTTP
suite below adds 36. A broader combined UI/domain compilation exhausted its existing deadline;
it is not counted as a successful UI run. Test deadlines were not increased.

The HTTP/source suite also passed all 36 checks, including nine checks of Nenex
URL creation and guarded updates. They verify metadata preservation, idempotent
rebinding to the same URL, unguarded collision refusal, stale-form rejection,
the rendered update control, and exact retained x/y/z source history. The HTTP
checks cover unavailable evidence and late responses to removed/rebound commands.

The compiled Grove gate also passed its two agreement/conflict cases. It runs
the actual published `graph/main.grove` report against collected claims, including
its codecs and norm boundaries, and checks that citations and proposal references
survive. An untyped `spun` wrapper around graph policy does not establish this:
the norm requires one symbol-keyed member per claim. Qualification reuses the
native physical-key codec and preserves segment auras; no identity registry is
introduced. A selected projection exception becomes a domain refusal.
The existing checker's mount-contract gate passed against the final sources.

Run the existing checker from the repository environment:

```sh
extras/x/check --mount flows --suite flow_cartography_tests --suite flow_cartography_lifecycle_tests
extras/x/check --mount flows --suite cartography-publication-tests
```

The checker selects graph as a test dependency for these cases. Native flow
installation and production mount dependencies remain independent of graph.

These checks establish deterministic admission and lifecycle behavior with
controlled outcomes. They do not establish the correctness of model judgments,
the availability of arbitrary websites, or general performance characteristics.

## Reproduce through Nenex

Use a disposable world with the `flows`, `graph` and `codex` mounts and an
authenticated Codex bridge. Leave any retained working worlds alone.

1. In **Flow examples**, create and publish **Web evidence** (`web_evidence`),
   then **Cited assertions** (`cited_assertions`), then **Cartography**
   (`cartography`). The parent captures both child definitions.
2. Author an ordinary subject page through **Edit page source**. Give one heading
   an explicit `/subject` path and a precise question in its title. A typed native
   record can alternatively supply `/question` as plain text; a multiword Semidoc
   attribute retains its value-list boundaries and is not that text field.
   Bind the heading's actual namespace address, available from its
   block tools, rather than assuming the page root has the same fields.
3. On `cartography_flow`, **Bind web source** twice with distinct source keys.
   Bind `projection` to the raw `/0x11/gov/graph/report` record, `subject` to the
   authored heading, select `/0x11/io/codex/work_provider`, and attach maintenance
   to a new destination with `/0x11/gov/flows/nenex` as writer.
4. Inspect **Live flow work**, request evidence, validated value cells and the
   working overlay. Completed provider output still passes the captured native
   validator; a schema alone does not authorize publication.
5. Use **Update web source** to introduce a source with a contradictory value
   for the same explicit subject/property. Inspect its waiting review hole and
   retained attempt. Restore agreeing evidence through that same control. The
   native hand should allocate fresh work, resolve that hole and publish without
   deleting the failed attempt or its captures.
6. Edit generated prose deliberately, then update a source again. The writer must
   refuse to replace the edited generated document. Inspect the retained work
   and verify the authored edit remains.

One small public-source experiment compares the extra-resource test command in
CPython's versioned primary-source READMEs:

- `https://raw.githubusercontent.com/python/cpython/3.10/README.rst`
- `https://raw.githubusercontent.com/python/cpython/3.12/README.rst`
- `https://raw.githubusercontent.com/python/cpython/3.13/README.rst`

Treat the versioned texts as competing proposals for one selected policy, and
ask for exactly one `/resource_test_target` claim containing the literal command.
Keep the version scope explicit: different version instructions are not a claim
that either source is globally false. The adapter treats these served plaintext
bytes literally; it does not claim an RST parser. Actual captures, rather than
these mutable branch URLs alone, identify the evidence used by each attempt.

Exact substring validation establishes citation fidelity. It does not prove
semantic entailment or truth. Acceptance reasons and review remain explicit
provider judgments. Claims stay addressable work values; publishing independent
sovereign assertions needs an explicitly selected writer policy.

## Recorded live run — 2026-11-03

A disposable world used port 8331 with the real HTTP foot and authenticated Codex
bridge. All flow creation, publication, source binding, retry and document editing
used Nenex. Program-source scans and registration refresh used the existing native
operations through the local namespace API. No flow driver or scheduler was added.

- The two child Semidocs and parent were created from Nenex's catalogue. The
  subject was authored through the source editor. A precise heading supplied the
  question; quoted multiword attributes retain their Semidoc value-list boundaries.
- The live maintenance attachment followed explicit parent publication. Attempts
  retained their own definitions. A frozen version-2 selection also remained
  inspectable; adoption applies to retained occurrences, not live followers.
- Real Codex attempts `request_7` and `request_8` each supplied one accepted
  `/resource_test_target` claim, with value `make testall` and an exact quotation.
  The selected compiled Grove projection, shared review and revision hand produced
  generation 1 of the concept and compact provenance children.
- Updating source `b` from the 3.12 README to 3.13 produced `make buildbottest`.
  Review attempt `request_14` was refused with `cartography_conflicting_evidence`;
  generation stayed 1. **Retry work** created `request_15` with `retry_of` pointing
  to `request_14`. Both failures remained retained at the same waiting review hole.
- Restoring source `b` to 3.12 resolved that same hole with `request_18` and
  published generation 2. The refused attempts remained readable.
- Editing an existing generated paragraph and adding an editorial note through
  Nenex, then rebinding `b` to the 3.11 README, left generation 2 intact and blocked
  publication with `flow_generated_page_edited`. The authored edits survived.

The review hole is below
`/0x11/app/nenex/w/cpython_resource_policy/review/holes/cartography_flow/$step_8_reviewed6_judged`.
The controller is
`/0x11/app/nenex/w/cartography_flow/work/maintenance_cartography`.
Exact captures, value cells, working overlays, failed outcomes and links are in
that world's native work/history, not a parallel saved document bundle.

Normal mount publication preserved the original controller and source record's
x/y/z references. Native regressions compare exact prior x/y/z values across the
lifecycle; after the final publication, all nine saved x/y/z references for the
two refused requests and waiting hole remained readable with their earlier
status and attempt head. The current hole separately retained its resolved head.
No live world was restarted or migrated. Port 8327 stayed running. The old 8330
process stopped during validation without a kernel OOM or coredump record; it was
not restarted and its world files were not changed.

The final display fixes keep live subjects out of invalid zero-case citation
spellings, hide adoption on live followers, and shorten section labels while
retaining full work records. Subject spelling has a focused native regression;
the rendering changes are checked by compilation and the disposable interface.
The dedicated Cells surface rendered generation 2, the protected-write refusal,
evidence/context links and retained attempts. The embedded Nenex Cells pane
repeatedly aborted during page loading. Direct reads of its native record and
result/context pair took approximately 0.05 and 0.42 seconds; this does not
establish the cause of the browser failure. Embedded loading remains unresolved;
no timeout was raised to conceal it.
Earlier failed fixture candidates and compilation timeouts are not counted as
passes. This run establishes the bounded lifecycle, not general research quality,
latency, load capacity, or storage performance. Cold startup and publication took
minutes; native arena growth is outside this library's scope.

The subsequent Nenex presentation change retires automatic generic Cells viewer
embedding. Authored flow occurrences retain their existing status, bindings,
holes and controls. Cell bindings, captured evidence and validated values link
to the standalone inspector. The embedded-pane failure recorded above describes
the earlier presentation; the flow does not depend on that viewer being mounted
inside the document.

That presentation change passed 121 native assertions: 67 interface checks,
36 authored-occurrence checks and 18 provider/hole/retry checks, including exact
retained x/y/z history. The production mount-contract gate and action-chrome
regression passed. The native worker emitted every passing record and its
completion marker, then exited; its command wrapper had been terminated before
writing the usual result report, so an overall wrapper PASS is not claimed.
Earlier malformed fixture candidates are excluded. Deadlines were unchanged.

In a fresh disposable world on 8332, the existing Evidence sources example was
created through Nenex, published through its Goo action, and selected into an
ordinary frozen cell. The reader loaded no generic Cells viewer scripts or
mounts. Its inspection link opened that same captured definition in standalone
Cells, retaining source x-case 1. Existing worlds were not restarted or modified.
