# Grove debugger: build, verify, review

Suggested Shrine PR title: **Add a namespace-native debugger declared in Grove
and rendered through Weft/Mash.** Older SRS Grove interfaces already exist in
this repository; avoid an unqualified “first-ever Grove interface” claim.

## Build and test

Prerequisites: the repository's Wisp dev shell (`nix develop`), Python 3.9+,
Node 20.19+, `lsof` for real-runtime ownership checks, and Mash's declared
package manager (`pnpm@10.33.0`). Install Mash dependencies from its lockfile
and the Playwright Chromium browser once:

```sh
cd /path/to/mash
pnpm install --frozen-lockfile
pnpm --filter @mash/visual-tests exec playwright install chromium
cd /path/to/shrine-plan
export MASH_ROOT=/path/to/mash
# If not in the Wisp dev shell: export WISP=/path/to/wisp
# Optional explicit executables: NODE, PNPM, PYTHON.
python3 x/test_runner_tests.py
python3 x/eden-launcher-test.py
python3 x/check-debugger.py
```

The last command is also registered as `x/check debugger`. It stages a
content-keyed compiler if needed, uses a disposable snapshot, compiles current
Grove declarations, builds Mash's packages and browser IIFE from source, then
runs inert browser tests. It writes its log, source digest, asset hashes and
screenshots under the printed temporary artifact directory. No existing
namespace or snapshot is queried. `--backend-only` skips browser prerequisites.

For a separate real preview:

```sh
node x/build-debug.mjs
python3 x/debug-grove-runtime.py launch
```

The build always requires explicit `MASH_ROOT`; there is no sibling-directory
guess or ignored/prebuilt asset input. It writes `.check/debug-assets/foil` by
default. `DEBUG_OUTPUT_ROOT` can name another staging directory. The launcher
chooses a free port, freezes source and verifies build hashes before listening.
It never copies a live namespace snapshot. SRS is opt-in via
`--entry start-debug-srs`; ordinary `start-debug` does not publish
`/<node>/gov/srs`. `--node` selects a nonzero hexadecimal authority; the
disposable preview default is `0x11`.
Do not point build output at an active preview's served files.

After the controller prints its manifest, a separate terminal can verify it:

```sh
python3 x/debug-grove-runtime.py assets /path/to/runtime.json --source .check/debug-assets
GROVE_RUNTIME=/path/to/runtime.json node x/debug-grove-declaration-http-test.mjs
python3 x/debug-grove-runtime.py stop /path/to/runtime.json
```

The seal is one-time, records actual bytes and requires proven PID/cwd/port
ownership. Test only the disposable runtime you started. The HTTP test uses
bounded GETs, does not install SRS or run operations, and verifies the rendered
mani, Mash controls, inspector cases, responsive layout and asset hashes.
Artifacts remain after shutdown. Never restart a user's preview to run tests.

For an explicit port, `python3 x/eden --debug --port 8140` uses the same staged
native assets and a compiler-only snapshot; add `--srs` for the example app.
`--srs` alone retains the original SRS explorer, not the debugger. `/ns` is the
legacy explorer. `/debug` requires the installed `/<node>/app/debug/page` view (from
the `/<node>/gov/debug` template) and returns 503 if
it is missing. There is no legacy browser build; `--legacy` is rejected.

## Paired PR order

1. **Mash:** reusable tree/path-row, overlay, tooltip, menu, scrollbar, triptych,
   icon and semantic-token contracts with their tests and catalogue examples.
   Keep debugger-specific namespace policy out of component implementations.
2. **Shrine:** Grove application template, generic installed Weft/Tack adapter, opt-in debugger
   data contract, namespace HTTP adapter, binding code and verification tools.
   Link the Mash PR and pin its exact resulting commit in
   `debug-dependencies.json` before treating this as a release build.

The paired Mash changes ([Lucide PR #58](https://github.com/axsys-org/mash/pull/58),
stacked on the debugger components) are committed as
`8eed9f2d63bc380ac57a349f5263f908beca09b5` and pinned in
`debug-dependencies.json`. `node x/build-debug.mjs --release` and
`python3 x/check-debugger.py --release` reject an absent pin, mismatched SHA,
dirty Mash checkout or wrong pnpm version. Development build provenance still
records the actual base SHA, dirty flag and source-content digest. Do not pin
an earlier base commit while relying on uncommitted component changes. Use a
clean checkout of the pinned commit for release verification; an unrelated
staged change in a development checkout still makes that checkout dirty.

The build requires Mash's semantic Lucide entry point; the older Carbon
checkout is not accepted. Grove keeps semantic icon names rather than importing
Lucide or installing an application-owned icon pack.

## Review boundary and checklist

- Read [the declaration audit](debugger-declaration-audit.md) for precise
  ownership. “Grove-declared” describes UI declarations, not a JS-free runtime.
- Review the complete dirty diffs before staging; exclude unrelated local
  documents and operating-system metadata instead of blanket-staging them.
- Broad namespace transport changes (physical/value/journal reads) have their
  own tests. Include only required dependency changes, or stack separately;
  do not blanket-stage the worktree.
- The standalone `x/{journal,value,physical}-http-test.py` transport harnesses
  use `debug_transport_fixture.py` and `tests/debug_http.foil` to compile and
  publish the actual Grove debugger. No legacy renderer fallback is enabled.
  Their synthetic indexes retain exact epochs and malformed-index fixtures;
  real Eden scenarios publish into their disposable namespace. Keep pagination,
  immutable values, mutation/epoch conflicts and malformed-request coverage;
  remove obsolete renderer/layout assumptions instead of deleting that coverage.
- Run authority-isolation and derived-read coverage when porting runtime APIs.
  A composed root has no single physical epoch; `/sys` and `/<node>` histories
  must not borrow each other's clocks or write permissions.
- Run Mash type checks and its touched component/browser suites. Run the
  restored Shrine inventory gate for the intended scope; focused debugger
  success does not substitute for full kernel/transport regression coverage.
- Check source hygiene with `git diff --check`, production dependency pinning,
  native startup without SRS, opt-in SRS startup, and missing-declaration 503s.
- Keep generated bundles, `.check` snapshots, runtime manifests, screenshots
  and temporary logs out of the source PR. They are build/test artifacts.
- Older visual research and migration notes in `doc/archive/` are local-only
  and ignored by Git. This guide and the declaration audit are current.

No commit, staging operation or PR publication is implied by running this gate.

## Consolidated test ownership

- `x/check-debugger.py`: current Grove compilation, clean pinned Mash build,
  build/icon boundary, request queue/cache, exact values, physical parser, and
  the single inert browser suite `x/debug-declaration-test.mjs`.
- `x/debug-grove-declaration-http-test.mjs`: read-only checks against a runtime
  owned by the disposable controller, including mani and asset provenance.
- `x/debug-grove-workflow-test.mjs`: real, explicitly scoped install, rejection,
  inspector and immutable-value workflow in a disposable SRS namespace.
- `x/{journal,value,physical}-http-test.py`: distinct transport semantics;
  `x/debug-{journal,value,physical}-contract-test.mjs` verifies their untouched
  saved artifacts with the production browser parsers.
- `x/debug-runtime-tests.py`, `x/test_runner_tests.py`, and
  `x/eden-launcher-test.py`: ownership, compiler isolation and launcher safety.

Twenty-eight prototype-era browser harnesses are removed, not carried as a
second compatibility gate. Exact value parser checks now live in a compact pure
suite; case/layout/navigation checks share compiler-produced Grove markup.
The old standalone Preview mode, browser DOM factory, duplicate Foil debugger
renderer/model, stylesheet handoff and global tooltip controller are gone.
Semantic/fidelity tests now import the published Grove modules; HTTP transport
tests keep their boundary and pagination assertions. Toolbar hints use declared
Mash tooltips without application-side enhancement.
This does not claim full kernel regression coverage or migration of every old
visual assertion. Run the specific transport gates when changing that boundary.
