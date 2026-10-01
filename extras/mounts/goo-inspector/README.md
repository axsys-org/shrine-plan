# Goo inspector

A separate, read-only inspector built on the existing Goo pane/session and view
renderer. It changes no Goo grammar, IR, renderer, runtime, source adapter, or
interaction protocol. The mount owns the pane composition in `model.js`;
`inspector.grove` contains only a content view, never pane declarations.

## Run

```sh
WISP=/path/to/wisp python3 x/eden --mount goo-inspector --mount srs --port 8174
```

Open <http://127.0.0.1:8174/goo-inspector>. `srs` is optional demo data. The mount
depends on explorer, debugger and codecs, so existing inspection transports,
exact-value tools and published Goo views are available. The configured node
root comes from the server, rather than a hardcoded `0x11` fixture.

Try `/0x11/app/srs/cards` on the default node. Select `demo`; Values follows the
selection. Views lists its authored recipes with read-only previews and links
to their declarations. Evidence shows observation versions and links to deeper
inspection. Browse selected children descends. Parent, breadcrumbs, address
entry and browser Back navigate between workspaces.

## What is implemented

- Keyed Namespace and inspection panes with a Values / Views / Evidence deck.
- One existing Goo selection shared by the child list and synthetic follower.
  Arrow keys move focus, Enter selects, and clear returns to the current object.
- An authored Goo record summary in `/sys/slot/inspector_summary`; path labels
  use existing member identity. Synthetic content uses `/sys/slot/synthetic`.
- Current-object reflection when no child is selected, including leaf objects.
- Matching authored view previews, publication diagnostics present in those
  previews, and declaration navigation. Preview controls are disabled and never action-bound; their text stays accessible.
- Version/lifetime evidence and bounded slot excerpts from the existing debugger
  read descriptor. Reference excerpts link back into this inspector.
- Explicit refresh preserves selection and active deck within a compatible
  workspace. A changed source lifetime creates a new workspace, as does path
  navigation. Stale navigation/detail responses cannot replace a newer context.
- Broad namespace roots, structural paths and populations beyond Goo's 64-physical-child limit use the
  existing debugger's epoch-bound pages of 40 navigation links. Next replaces
  the current page to keep DOM retention bounded; it is not a new Goo source.
- Exact values, provenance, history and operations remain available through
  clearly labelled links to the existing debugger/Objects tools.

## Boundaries

This is an application composition using the existing `GooPanes` JavaScript
entry point; it does not add a pane-composition DSL. Content previews run through
the existing server Goo pipeline. Address controls, metadata and navigation
links are ordinary mount-owned shell UI. This is not a claim that every pixel
or debugger data type is authored in Goo.

The only live `follow` recipe is synthetic. Authored previews are cloned from
existing rendered views with controls disabled: no invocation, provider sampling, or
mutation occurs. Pane-bearing recipes are listed with an open-separately link;
they are not recursively mounted. The inspector does not monkeypatch Goo globals
or fabricate namespace records for inspection results.

Synthetic reflection remains a bounded preview (including its existing text and
collection limits). Exact-value expansion, slot selection, operation forms,
historical browsing, automatic refresh and arbitrary paginated Goo selections
are not implemented. The library root is explicitly refused by this shell: the
existing printable-path reader throws `quip-print-error / ts-not-symbol` on
opaque module names such as `apps/srs/main`. Use a narrower path or the existing
physical inspector; fixing that backend is outside this mount. Evidence and Goo views are separately versioned reads,
not an atomic combined snapshot. The debugger backend and its authority rules
are reused without alteration. A URL reload creates new page-local ownership.

## Files and checks

- `mount.foil`: GET-only page/assets and configured root; no namespace writes.
- `inspector.grove`: universally applicable optional-lede summary role/view.
- `model.js`: pane composition, path and read-descriptor boundary validation.
- `app.js`: mount navigation, existing read adapters, previews and evidence.
- `host.py`: real HTTP page/assets, configured node, method rejection checks.

```sh
node --test extras/mounts/goo-inspector/tests/*.test.cjs
node --test extras/mounts/explorer/tests/*.test.cjs
WISP=/path/to/wisp python3 extras/x/check --mount goo-inspector --jobs 2
```

## Verification recorded September 30, 2026

- The full mount check passed web (135 checks), explorer (292), debugger (28)
  and Grove debugger (1). Its initial mount-contract failure was a local JSON
  import error; after correction, `extras/x/check --mount goo-inspector
  --contracts-only` passed the remaining contract check: **457 passing checks
  across those runs**. The initial failed invocation is not reported as a pass.
- `node --test extras/mounts/goo-inspector/tests/*.test.cjs
  extras/mounts/explorer/tests/*.test.cjs`: **22 passed**, no failures/skips.
- The mount's HTTP checks passed against the real 8174 instance: page/assets,
  configured node and POST rejection. Served JS/CSS matched working-tree bytes.
- Browser: selected the SRS card through the actual Goo list; Values reflected
  its fields; Views displayed authored recipes with grading controls disabled;
  refresh retained selection, deck and expanded preview; declaration navigation
  displayed stored declaration slots; broad-root navigation showed bounded links.
- Runtime inspection reported one selected member, one follower, and **zero
  domain-action activations or dispatches** after those local interactions.
- `/lib` rejection was exercised without issuing its known failing read.
  Multi-page continuation and hardware-specific keyboard/assistive technology
  were not manually rehearsed; they should not be inferred from the browser run.
- Existing Goo sources and assets were compared with their hashes at task start:
  unchanged. `git diff --check` passed.
