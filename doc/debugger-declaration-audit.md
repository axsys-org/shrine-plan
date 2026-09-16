# Debugger declaration boundary

The debugger UI is declared in Grove, published under `/weft/debug/v1`, and
rendered by calling its real Weft sewn value. This is not a parallel JavaScript
renderer dressed in Mash tags.

## Ownership

- `src/grove/debugger.grove`: typed page, composition and inspector contracts.
- `src/grove/debugger/chrome.grove`: shell, sidebar, menus and named templates.
- `src/grove/debugger/presentation.grove`: Weft formatting helpers.
- `src/grove/debugger/model.grove`: namespace presentation data interpretation.
- `src/grove/debugger/document.grove`: lore, mani, slots, children and operations.
- `grove-debugger-source.rvr` concatenates those source parts into one Grove
  compilation unit. It does not generate HTML or select a host renderer.
- `grove_ui_runtime.foil` is the reusable fragment/record bridge. Default Grove
  compilation uses the role prelude; UI is an explicit host choice.
- `debugger_contract.foil` holds this application's typed input carrier. Only
  the debugger host opts into it. General Grove compilation does not import it.
- `web.foil` owns hydration, typed transport data, HTTP framing and assets.
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
Older Foil presentation helpers still have isolated semantic tests; they are
not a runtime fallback for a missing published Grove declaration.

## Evidence and release gates

See [the PR guide](debugger-pr.md) for reproducible commands and remaining
release requirements. The gate compiles the current Grove sources, checks the
normal compiler separately, builds real Mash source with its pinned package
manager, and exercises Mash-only/desktop/dark/touch/exact-case fixtures without
contacting a live namespace. Missing declarations must fail without enhancement.
Real HTTP verification is a separate, manifest-owned disposable runtime test.

Earlier findings and migration notes are local-only archives; this document
and the PR guide describe the supported declaration boundary.
