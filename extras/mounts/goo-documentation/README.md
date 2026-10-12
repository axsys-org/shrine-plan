# Goo documentation

A read-only documentation browser and namespace explorer built from ordinary
Goo panes and an incremental namespace tree.

```sh
GOO_PATCH_MASH_ROOT=/path/to/mash WISP=/path/to/wisp \
  python3 x/eden --compiler none --mount goo-documentation --port 8136
```

Open `/goo-documentation`, or deep-link with `?path=/0x11/lib/pact/lore`.
The initial page opens the installed node's `lib/pact/lore` documentation. Library,
Declarations, Applications, System, breadcrumbs, Parent, and the path form all
navigate the same endpoint. **Browse** makes a tree member the new browsing root.
Select a record to read; expand a branch to load its children. **Values** shows
the synthetic Goo presentation, using each slot definition's `/sys/lede` as its
label. A missing, empty, or non-text title falls back to the slot path.
Structured lore is reflected into its heading, body lines, and authored example
pairs even when the view catalog supplies no type descriptor for it.
Other values without a known descriptor use the bounded value pretty-printer,
preserving their exact type identity and showing positional contents.
Browser Back/Forward restores the
browsing root, not page-local expansion or selection state.

Each workspace page allocates a context record at `/{self}/goo/ses/[numeric-id]`.
The record holds the role's `source_path` slot; render refreshes read that record
instead of constructing a receiver from the requested browsing path. IDs increase
across workspace endpoints and mount reinstalls. Context records remain in the
namespace after the page closes; a new page load allocates a new context. Browser
selection, active tabs, and expansion remain page-local.

The reader uses the stored `/sys/lede`, `/sys/help` (structured `lore` or text),
`/sys/mold`, and `/sys/src` fields. It also recognizes Grove source text.
Foil definition publication writes the captured heading to `/sys/lede` and the
remaining body and examples to `/sys/help`, without repeating the heading there.
Documentation and Values read the same stored prose.
For code records, Eden installs a read-only adapter to the existing compiler
metadata interfaces: it reads the exact pinned artifact on the record, resolves
the definition in that artifact's assigned context, and extracts its normalized
Rex definition and kind. It does not synthesize documentation from artifact
comments, read current source files, or recompile. Normalized source is
labelled explicitly. Examples show authored source and expected output;
they do not execute or claim a pass/fail result. Missing documentation has an
explicit empty state. Source starts collapsed. All prose and code are escaped
server-side; Unicode is retained.

## Boundaries

- `documentation.grove` owns the namespace selection, outline, two reading panes,
  tabs, and path navigation. No mount-specific JavaScript or client data model.
- `mount.json` declares the route, entry pane, path receiver and shell under
  `workspaces`. It has no mount-specific Foil host, activation, or HTTP hook.
  The shared `goo_workspace_mount` importer validates and publishes that
  registration; `goo_workspace` supplies the receiver, session and SSR wrappers.
  See [declarative workspaces](../../../MOUNTS.md#declarative-goo-workspaces).
- Existing `GooPanes`, `GooSession`, and `GooTopoi` own lazy paging, membership,
  encounters, selection admission, suspended tabs, and stale-response rejection.
- Shared `goo_documentation.foil` adds two read-only derived presentation slots:
  `/sys/slot/documentation` and `/sys/slot/documentation_summary`. They return
  through the same `/goo/render` and prepared-tree response boundaries, with real
  subject evidence and no action controls.
- The documentation body is semantic HTML produced by Weft, using existing
  namespace vocabulary and type formatting. It intentionally has `display: null`:
  it does not claim to be a measured Goo canvas display or a compiled Grove recipe.
  This allows natural document flow and full Unicode without introducing a second
  application runtime. The Values pane remains the existing Goo renderer.
- `goo-documentation-bridge.rvr` supplies that metadata adapter using
  `perc-entry-span`, the existing `compiler-inspect/entry-source`,
  `entry-parts`, and the artifact's defining
  context. Its derived reading card does not mutate the namespace record.
- Initial membership can name a path-valued receiver field; the server resolves
  it and the existing session admits it against the current source.

This mount doesn't edit records, publish definitions, run doctests, or search the
entire namespace. Tree loading uses the shared 64-child page / 4096-materialized-
node limits. Structural names can expand without a selectable record. Raw keys
without a Goo spelling are omitted with a visible count; opaque, lossless cursors
let later pages load even when a raw key ends a page. Those raw keys remain
available through the physical namespace debugger.
Navigation/reload fetches current state; this mount does not add a live watcher.

## Checks

```sh
WISP=/path/to/wisp python3 extras/x/check --mount goo-documentation
node --test extras/mounts/explorer/tests/*.test.cjs
node extras/mounts/goo-documentation/check-browser.mjs \
  http://127.0.0.1:8136 /path/to/mash /tmp/goo-documentation-browser
```

The native tests cover escaping, Unicode, lore formats, absent documentation,
read-only controls, source evidence, pane variants, prepared child summaries,
and route validation. The shared tree suite also checks pages consisting entirely
of unspellable keys, lossless cursor roundtrips, and continuation termination.

Verified against a real Eden mount on 2026-10-08:

- Native: 40 documentation checks, 519 explorer checks, 135 web checks, and the
  mount contract suite; all passed. Six profile-generation checks also passed.
- JavaScript adapters: 85 tests passed.
- Chromium 151.0.7922.34, Firefox 153.0, WebKit 26.5: all passed the real browsing
  flow, including initial lore/type resolution, keyboard selection, shared tab
  selection, lazy expansion, pinned-artifact source excerpts, path navigation,
  reload/Back, Library pagination through opaque cursors, raw-key notices, and
  a 760px-wide layout. No domain actions or uncaught browser errors occurred.
- HTTP smoke: default page, deep link, and stylesheet succeeded; unsupported
  methods, malformed paths, duplicate queries, and unknown routes were rejected.

These are browsing tests; no manual IME coverage or doctest execution is claimed.

The declarative host also has native contract tests in Explorer and loader/schema
checks in `x/eden-mounts-test.py`. `check-registration.py` exercises failed and
successful rescans against a **disposable** copy of this source bag: a compiled
entry with an unconnected selection port must preserve the previous workspace
and stylesheet; repairing the entry must publish the new asset bundle. It
restores the copied source afterward. Run it only against an Eden instance
launched with that copy in an extras root named `workspace-registration-extras`.

The declarative migration was verified on 2026-10-08 with 17 shared host checks,
16 loader checks (including the native descriptor round trip), the existing
40 documentation / 519 Explorer / 135 web checks, and mount contract checks.
The real invalid-entry rescan preserved identical page HTML and the previous
CSS; repair admitted the new asset bundle. Documentation browsing passed in
Chromium 151.0.7922.34, Firefox 153.0, and WebKit 26.5, run sequentially. The
manual `hello-grove` mount was loaded alongside it; its select/edit/save/reload
flow also passed in all three engines. The temporary server and test browsers
were stopped after verification.
