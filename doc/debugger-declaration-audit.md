# Debugger declaration boundary

The debugger definitions are published under `/<node>/gov/debug`, including a reusable
Grove template. An instance is installed at `/<node>/app/debug` through the same
`grove_install/instantiate` path as SRS. Its `/page` tree declares `weft: %/page`
and an instance-relative `tack` to `/input`; its title and head assets are data
on that installed view. This supersedes the earlier renderer-only registry.
`<node>` is the configured hexadecimal authority, for example `0x11`; `/sys`
belongs to the selected immutable system publication, not that authority.

## Ownership

- `src/grove/debugger/application.grove`: inspection slots, codecs and role.
  Optional page/cursor metadata is separate from the
  selected records, target, local authority, version metadata, operation list and presentation scope.
- `src/grove/debugger.grove`: page/inspector norms and sewn transformations.
- `src/grove/debugger/instance.grove`: concrete instance seeds, declared after
  their norms and sewn transformations.
- `src/grove/debugger/chrome.grove`: shell, sidebar, menus and named templates.
- `src/grove/debugger/presentation.grove`: Weft formatting helpers.
- `src/grove/debugger/model.grove`: namespace presentation data interpretation.
- `src/grove/debugger/document.grove`: lore, mani, slots, children and operations.
- `grove-debugger-source.rvr` concatenates those source parts into one Grove
  compilation unit. It does not generate HTML or select a host renderer.
- `grove_ui_runtime.foil` is the reusable fragment/record bridge. Default Grove
  compilation uses the role prelude; UI is an explicit host choice.
- `grove_app.foil` captures an installed view's real weft/tack pins and projects
  named request inputs using the input norm schema stored with that compiled
  sewn. It never substitutes the latest norm at the same path for a pinned
  renderer's schema. The sewn transformation still checks both norms;
  malformed inputs cannot bypass them.
  Older compiled sewn metadata must be recompiled; an absent or incompatible
  boundary fails capture instead of falling back to a mutable endpoint read.
- `debugger_contract.foil` holds internal transport carriers and explicit leaf
  wrappers. The aggregate is no longer a single opaque `/data` application slot.
  Only the debugger host opts into these codecs.
- `web.foil` adapts finite inspection results to named inputs and HTTP framing.
  It no longer chooses a `page` entry from a captured component registry or
  chooses the application stylesheets/scripts.
  A missing published debugger returns 503; it never silently renders the old UI.
- Mash owns Web Component implementation, public props, interaction primitives,
  focus/ARIA contracts, semantic tokens and catalogue recipes.
- Browser application code owns namespace requests, data binding, navigation,
  cache/queue limits, local preferences and anchored-overlay coordination.
  It clones concrete Grove templates rather than inventing tag/layout trees.

“Grove-declared” does not mean JavaScript-free, a capability sandbox, or that
browser-local preferences are sovereign namespace state. The browser's retired
renderer and compatibility build have been removed. A build-time check rejects any application `createElement`
call; Mash's own implementation is intentionally outside that restriction.
The duplicate Foil debugger renderer and model are removed. Semantic tests in
`src/grove/tests/debugger.grove` import the actual published Grove modules.
Toolbar hints are declared `ui-tooltip` compositions, not a document-wide
JavaScript controller. The debugger loads only its own CSS and Mash's recipe;
it has no legacy `/style.css` fallback or stylesheet handoff machinery.

## Evidence and release gates

See [the PR guide](debugger-pr.md) for reproducible commands and remaining
release requirements. The gate compiles the current Grove sources, checks the
normal compiler separately, builds real Mash source with its pinned package
manager, and exercises Mash-only/desktop/dark/touch/exact-case fixtures without
contacting a live namespace. Missing declarations must fail without enhancement.
Real HTTP verification is a separate, manifest-owned disposable runtime test.

## Request-local state and current limits

The installed `/input` is a valid empty inspection. Each HTTP response projects
its own finite selected data onto that input in memory, without writing a
navigation event or advancing the namespace epoch. It does not bind the input to
the inspected namespace root with an unbounded y/z dependency. Saved paths and
browser history remain client-local preferences, not shared sovereign state.

This is a namespace-installed Grove view with a privileged inspection adapter,
not an ordinary capability-scoped application. The host chooses the finite reads
and supplies typed named values; the reusable `grove_app` boundary knows only
the installed pins, the compiled input schema, and the checked HTML-producing
transformation. The installed app's crew does not authorize those host reads.
Request-local projection is not an update to `/input`, a subscription, or a
promise that separately fetched sidebar and hover views form one coherent epic.

The generic adapter currently supports own-record input norms and HTML output;
it is not a universal Grove application server, reactive binding mechanism, or
capability sandbox. It captures a view for the server lifetime. Updating an
installed declaration does not hot-swap an already captured renderer. This
application restructuring and the namespace-runtime API port are separate
verification gates. The latter must exercise separate local/system histories,
qualified paths, immutable system records, and read-only derived views; a
successful rebase alone is not evidence of runtime compatibility.

The composed namespace root exposes authority links without hydrating either
subtree. Physical reads select the owning history before interpreting epochs.
Journal rows show actual namespace commits and changes, not the retired task,
effect or acknowledgement payload. Browser parser labels normalize version
metadata for display; stored publisher-owned slot identities are preserved.
Physical records retain their owning authority's case and epoch metadata.
Derived `/h`, `/o`, and `/x` views do not borrow the physical source's counters:
their history metadata is unreported until the runtime supplies it for the exact
derived target. An underlying source's history is not the output's history.

Earlier findings and migration notes are local-only archives; this document
and the PR guide describe the supported declaration boundary.
