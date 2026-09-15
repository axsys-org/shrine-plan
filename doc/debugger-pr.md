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
`--entry start-debug-srs`; ordinary `start-debug` does not publish `/gov/srs`.
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
legacy explorer. `/debug` requires a published Grove page and returns 503 if
it is missing. `node x/build-debug.mjs --legacy` is an explicit compatibility
build for old documents; never use that output for a native launch.

## Paired PR order

1. **Mash:** reusable tree/path-row, overlay, tooltip, menu, scrollbar, triptych,
   icon and semantic-token contracts with their tests and catalogue examples.
   Keep debugger-specific namespace policy out of component implementations.
2. **Shrine:** Grove declarations, generic Weft fragment bridge, opt-in debugger
   data contract, namespace HTTP adapter, binding code and verification tools.
   Link the Mash PR and pin its exact resulting commit in
   `debug-dependencies.json` before treating this as a release build.

The paired Mash changes are committed as
`568b50db204abf56369d4af4abdefcd41aaa79fa` and pinned in
`debug-dependencies.json`. `node x/build-debug.mjs --release` and
`python3 x/check-debugger.py --release` reject an absent pin, mismatched SHA,
dirty Mash checkout or wrong pnpm version. Development build provenance still
records the actual base SHA, dirty flag and source-content digest. Do not pin
an earlier base commit while relying on uncommitted component changes. Use a
clean checkout of the pinned commit for release verification; an unrelated
staged change in a development checkout still makes that checkout dirty.

## Review boundary and checklist

- Read [the declaration audit](debugger-declaration-audit.md) for precise
  ownership. “Grove-declared” describes UI declarations, not a JS-free runtime.
- Review the complete dirty diffs before staging. The staged Mash
  `.prettierrc.json` deletion is unrelated and must not enter these PRs.
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

## Verified hardening pass — 2026-09-15

- Source-built with Mash's declared pnpm 10.33.0; native build-boundary checks
  passed with no browser DOM constructors in the debugger bundle.
- The unified debugger gate passed: real Grove compilation, 19 published
  records, the actual debugger host entry, normal Grove backend regressions,
  and seven inert browser scenarios (including dark, touch and rejection of
  a missing declaration).
- 226 focused Mash component/browser tests and all workspace type checks
  passed. 120 native HTTP/debugger/journal checks passed.
- A separate fresh debugger-only namespace passed the real browser check:
  mani, Mash controls and scrolling, inspector cases, responsive layout and
  startup without SRS. It made 12 bounded GETs, no writes, and reported no
  browser errors or contract violations.
- The disposable runtime was stopped. Existing previews on 8138 and 51571
  and their served assets were preserved.

The paired-commit verification additionally passed 813 Mash UI tests, 170 Shrine
component tests, eight token tests, workspace build/type checks, lint, exports,
parts, token-consumer and catalogue checks. A clean checkout of the pinned commit
passed full formatting and a release asset build. All seven inert browser
scenarios passed again against those exact assets, with zero errors, live GETs
or debugger-owned DOM factories. Build-boundary checks, ten runtime-helper
tests, 18 runner unit tests (three optional probes skipped), seven launcher
tests and 189 pure physical-parser checks also passed.
After removal of the obsolete fixture launch functions, all 126 checks in
`tests/journal_http`, `tests/journal_page`, `tests/value_read` and
`tests/physical_http` passed in a fresh native worker.
The migrated native-Grove journal socket harness passed 43 real HTTP requests,
including strict invalid-query cases, concurrent reads and preserved epochs.
Its six saved-document scenarios also passed the production browser-parser
bridge, with no live requests or rewriting of artifacts.
The migrated value socket harness passed 64 real HTTP requests, including
bounded/exact chunks, invalid requests, concurrent reads, editing, deletion,
and immutable earlier values. Its HTML checks use source-slot metadata rather
than treating manifest-preview limbs as live slots.
Its untouched native HTML and 14 saved chunks also passed the production
DOM/metadata/byte parser bridge, including old-after-edit/delete fidelity.

This is focused debugger evidence, not a full kernel regression claim. The
paired Mash commit is now pinned. Review and stage only the intended Shrine
changes; neither these commands nor the Mash commit publishes either repository.

## Disposable transport regression checks

With Wisp available, these commands stage compiler-only state automatically.
Each compiles the production Grove declaration, owns a new ephemeral runtime,
checks real HTTP responses, and stops that runtime even on failure. Never pass
a live namespace snapshot as `--template`.
Cold native/Grove compilation can take several minutes. `TRANSPORT-*` markers
in the printed log identify compilation progress; startup is bounded to 900
seconds and each harness stops its own process in `finally`, including on
assertion failure. Avoid starting a second copy just because startup is quiet.

```sh
python3 x/debug-runtime-tests.py
python3 x/journal-http-test.py
python3 x/journal-http-test.py --eden
python3 x/value-http-test.py
python3 x/physical-http-test.py --scenario large
python3 x/physical-http-test.py --scenario epoch
```

Use the printed artifact directories to check production parsers against the
untouched responses, without any more live requests:

```sh
node x/debug-journal-contract-test.mjs /path/to/journal-artifacts
VALUE_ARTIFACTS=/path/to/value-artifacts node x/debug-value-contract-test.mjs
PHYSICAL_ARTIFACTS=/path/to/large-artifacts \
  PHYSICAL_EPOCH_ARTIFACTS=/path/to/epoch-artifacts \
  node x/debug-physical-contract-test.mjs
```

The journal/value bridges require explicit `MASH_ROOT` for their browser parser
dependency. These transport checks supplement, rather than replace, the native
declaration/browser gate above.
