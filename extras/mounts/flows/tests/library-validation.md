# Learning, technical atlas and ingestion validation

Validated on November 3, 2026, in `ct/harness-main-compat`. No runtime or `src/`
changes were needed for these examples.

## Native checks

- **58 library checks passed**, completed normally with exit 0 in 1,095.605
  seconds. The final run used the actual shipped Semidoc and sample JSON bytes.
  It covers cohesive JSON variants, original envelopes, null/false/zero,
  duplicate members and number lexemes; format/media refusal; deletion and
  restoration; completed-run capture; learning refusal, retry and resumption;
  retained native history; and complete atlas publication through the Nenex writer.
- **Compiled authoring Goo passed**: 76 individual assertions plus its module
  check, completed normally with exit 0. This includes forwarding explicit JSON
  format and own-record inspection care through the actual production Grove.
- Mount contracts passed. The native JSON variant probe, Goo profile checks,
  existing Nenex publication JavaScript check and source packaging checks passed.
- The full combined authoring/Codex-surface gate was not freshly established by
  this run. Its existing entry still runs both reports. The focused authoring
  entry excludes the provider-specific fixture; no existing assertions were deleted.

Reproduce the focused gates from the repository root:

```sh
extras/x/check --mount flows --suite flow_library_tests
extras/x/check --mount flows --suite flow-authoring-only-tests --timeout 3600
node extras/mounts/nenex/tests/publication.cjs
```

The longer allowance is for cold compilation of the authoring test. Application
timeouts were not increased. Native test providers supply controlled responses;
they do not establish model judgment quality or a fresh Codex bridge run.

## Live use in the existing world

All three examples were created from Nenex's catalogue, published through Goo and
attached using the existing maintenance forms in the same world on port 8332.
Source publication and the existing published harness-refresh action installed
the catalogue. The process was not restarted or patched.

1. **Format ingestion** completed without a provider. Its `decoded` step retains
   a native JSON object; the final result retains data and the original envelope
   beside its document projection. The output is `.../w/format_ingestion`.
2. **Task learning** binds a frozen own-record inspection of that actual completed
   import, with the labelled sample task and instructions. Three agent-authored
   revisions were accepted through `submit_revision`, producing the lesson and
   proposal children under `.../w/task_learning`. The instruction capture remains
   at its original x case; no instruction file or automatic hook was changed.
3. **Technical atlas** binds nine shared manual sources and an inspection of the
   native decoder. Its four concept revisions use the same native revision work,
   captures, holes and writer. The completed tree is `.../w/technical_atlas`, with
   language/runtime, interfaces, computation and compact provenance children.

The live atlas initially exposed a missing test boundary: a source named `cells`
generated `reference/cells`, which the document writer correctly reserves.
Renaming the evidence to `cell_examples` fixed the example; the writer guard
was not weakened. The existing feed was rebound with `watch_sources`, retaining
the same file, mount and watch owner. The authored Semidoc was corrected and
deliberately republished. Unchanged accepted revisions were reused; current
replacement requests were submitted through their actual draft-case guards.
The new native atlas test completes publication rather than stopping at requests.

The original four accepted atlas requests remain. A superseded computation
request also remains with `flow_stale_request`, without authorizing the final
result. Twenty-seven retained x/y/z references, including the original world
samples and blocked atlas work, still resolve. Nine selected output documents
exist, the sample instruction capture is unchanged, and the selected decoder's
frozen cell remains at x case 1 with observed source case 1. Its original live
selector has source case 0; that is distinct from the retained observed case.

The live MCP checks compare availability, exposed scalar properties and slot
descriptors. Historical reads omit some descriptor-reference metadata. These
checks are not exhaustive equality of every opaque live-world value. Disposable
native regressions compare retained typed history and capture values directly.

## Limits observed

The live world has no Codex provider mounted. Revision prose in this demonstration
was authored by this agent and submitted through the existing guarded native
operation. Selecting an available provider uses the same requests; a fresh
automatic Codex run was not performed here.

Cold source publication and first Goo preparation were slow. The compact source
form twice reported a timeout without applying the correction. The draft was
retained; a namespace read verified the saved source before the existing native
`author` operation applied the correction with its positive case guard. Native
publication then used the corrected saved source. This run does not establish a
fresh warm compact-source-save round trip or resolve cold compilation performance.

The JSON adapter uses the existing decoder's documented numeric dialect, not
strict RFC or domain validation. Decoded values remain in generic result cells;
selecting domain structures, derived cells and views is not implemented here.
Atlas prose distinguishes declarations from
execution evidence. Learning produces proposals requiring deliberate adoption;
it does not install rules or runnable procedures from generated prose.

Detailed receipts and native reports are retained locally under
`.check/flow-library/`, `.check/flow-library-suite-atlas-final/library/` and
`.check/extras-9x7r6pwz/`. The atlas screenshot is
`.check/flow-library/technical-atlas.png`.
