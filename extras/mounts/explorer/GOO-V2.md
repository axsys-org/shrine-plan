# Grove → Goo v2

The namespace browser uses `lf/goo-v2`'s typed IR and renderer. Grove publication
still stores a symbolic expression template: `show` is resolved by field type,
and `present` receives the selected view's children. When an object is selected,
`goo_bridge` binds those expressions and constructs `goo/source` directly.

The remaining pipeline is the backend's own code:

`goo/source → goo/core → goo/normalized → goo/visible → goo/semantic → prepared HTML`

Normalization, visibility, adjacency rules, ASCII measurement, geometry planning,
and escaping are owned by Goo v2. The bridge uses the guarded `goo_html/prepare`
and `goo_html/fragment` entry points. The browser loads the backend's frozen CSS
and font assets. It renders at 720px, scrolling overflow rather than scaling
geometry after measurement. Controls sit in a disabled fieldset; no action,
provider, mutation, or navigation expression is executed.

## Mismatches and decisions

| Difference | Integration behavior |
| --- | --- |
| The incoming SRS sample predates `#on`, path styles, and the corrected action syntax. | Retain the frontend branch's corrected SRS declarations when resolving the merge. |
| Grove expressions versus concrete v2 payloads | Evaluate literals and direct role fields at render time. Missing fields disappear. Unsupported expressions are errors; nested receiver evaluation remains unimplemented. |
| A Grove view body can contain several roots; v2 requires one | Add one column-flow root. Preserve explicit groups and presentation boundaries. |
| Grove's `or` has no v2 node | Choose the first present alternative before producing v2 source. This is the existing preview fallback behavior, not competing-view precedence. |
| Grove unquoted absolute paths versus the v2 literal reader | Resolve absolute slot paths with the Grove path parser before adapting their role. Quoted style paths remain supported. |
| Grove style paths versus v2 leaf roles | Map exact legacy `/sys/slot/title`, `content`, `label`, `summary`, `caption`, and `icon` paths to `title`, `body`, `label`, `summary`, `caption`, and `icon`. Apply v2's existing aliases for its canonical paths. Preserve all unknown slots verbatim. |
| Singular `/sys/slot/...` versus v2 view context `/sys/slots/...` | Adapt only `label`, `summary`, and `scar` for v2's visibility defaults. Do not rename namespace declarations or data slots. |
| `action` versus `button` | Materialize a v2 button. Keep action arguments in the symbolic template and leave execution disabled. |
| Grove `input(path)` versus v2 `input(text)` | Read the exact data slot and materialize its text; absent values become empty inputs. Also accept literal text for native v2 input previews. |
| SRS edit inputs name `/sys/slot/req` and `/sys/slot/res`, but fields are `/sys/req` and `/sys/res` | Leave these inputs empty. No implicit data-slot remapping. |
| No native hyperlink, number, time, duration, or boolean node | Format these payloads as v2 text. Paths are displayed without the previous hyperlink behavior; time and duration remain raw numeric text. |
| No native `divider` or `icon` constructor | Reject with a visible bridge diagnostic. Text with an icon role and v2 primitives remain available. |
| No action/binding semantics in v2 layout IR | Group `on`, `action`, `myth`, and action arguments remain in the published template but do not enter layout IR. |
| Standalone UUID entropy provider versus pure namespace preview | Allocate nonempty view-qualified preorder IDs before visibility pruning. These obey the typed/wire opaque-ID validators and are unique across views on one page. They are not fresh UUIDv4 identities and are not persistent object identities across edits. |
| ASCII-only backend measurement | Show the backend's diagnostic for non-ASCII payloads; do not silently substitute a different renderer or font measurement. |

Reflection-driven missing views and competing-view precedence remain deferred.
Those frontend errors stay visible independently of other views.

`extras/x/check --mount explorer` runs bridge tests and the imported v2 type,
result, codec, semantic, ASCII, layout, and HTML checks. The standalone package's
Haskell differential-oracle scripts referenced by its README are not present at
those paths in this merged repository; these checks do not claim oracle parity.
