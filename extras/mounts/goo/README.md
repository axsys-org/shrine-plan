# Standalone Goo in Foil

This package implements Goo's compiler, geometry planner, HTML renderer and application views in Foil (items 03–33):
[phase types](TYPES.md), [diagnostics and results](RESULTS.md),
[tree/config codecs](CODECS.md), [validated measurement transport](MEASUREMENT.md),
[semantic passes](SEMANTICS.md), and [ASCII leaf measurement](ASCII.md), [layout](LAYOUT.md), and [prepared HTML rendering](HTML.md), and [CLI/HTTP application](APPLICATION.md). Parsing
and printing use the retained, locked Rex component. Goo interpretation, normalization, visibility, adjacency,
and orchestration run in Foil; the host supplies process I/O and UUID entropy.
The Haskell Goo compiler is used only by differential tests.

From the parent repository, with Nix and Python 3 available:

```sh
extras/mounts/goo/bin/goo build
extras/mounts/goo/bin/goo fmt --check
goo/scripts/porting/build-codec-oracle.sh # test-only Haskell codec oracle
goo/scripts/porting/build-semantic-oracle.sh # test-only full Haskell oracle
goo/scripts/porting/build-ascii-oracle.sh # test-only direct Haskell measurer
goo/scripts/porting/build-layout-oracle.sh # test-only direct Haskell planner
goo/scripts/porting/build-html-oracle.sh # test-only direct Haskell renderer
extras/mounts/goo/bin/goo test
extras/mounts/goo/bin/goo test-types
printf 'text("Hello")' | extras/mounts/goo/bin/goo passes
extras/mounts/goo/bin/goo html --width 375.25 extras/mounts/goo/examples/profile.goo
extras/mounts/goo/bin/goo serve --port 8000
printf '%s\n' '{"version":1,"action":"source","source":"text(\"Hello\", %title)"}' | extras/mounts/goo/bin/goo adapter
```

The executable resolves its files relative to its own location, so it also works
from another directory. Compiler, adapter and static HTML commands need no dev
server, browser, npm installation, or port. The HTTP application binds localhost. Build and execution diagnostics stay off the adapter's JSON stdout.
Large JSON arguments use balanced transport chunks to avoid enormous decimal
literals in the runtime reader; output uses indexed UTF-8 JSON frames rather than
integer pretty-printing. Static SSR sends its HTML as length-delimited UTF-8 bytes
with a small status frame. Payload bytes and numeric lexemes are unchanged.

## Build

The build uses the parent locked `eden` shell for Wisp and this package's locked
default shell for the isolated Rex executable. A temporary flake containing the
package's `flake.nix` and `flake.lock` selects that shell without copying caches
or nested builds into the Nix store. GHC compiles only `rex/Main.hs` and
`rex/Goo/Rex/Layout.hs`, with an explicit package allowlist; it does not build
the Haskell Goo library.

Foil modules compile through `foil-source` and `foil-publication`, including the
system publication and the package's `goo_app/types`, `goo_app/results`,
`goo_app/adapter` and `goo_app/tests` roots.
The deterministic development authority is local and unpublished. Deployment
identity and packaging belong to item 34.

A successful build atomically selects a generation under `.build/`. Its manifest
records SHA-256 hashes of source inputs, both locks, the runtime, retained Rex
executable and Foil snapshot. Builds reuse an unchanged verified generation;
source changes require another build. One-shot invocations clone the immutable
snapshot into a temporary directory and run against a private data-only file root. The
HTTP server keeps a bounded pool of preloaded snapshots with exclusive leases and
periodic recycling. Neither path invokes the Foil compiler or test fixture launcher.

## Protocol

One JSON value on stdin produces one JSON value on stdout. An object produces an
object; an array of requests produces an ordered array of responses. Version is
exactly integer `1`. Supported actions are:

- `capabilities`: reports the implemented stages and `complete: true` for the eleven compiler stages.
- `source`: the item-01 oracle envelope, including all eleven stage names.
- `parse`, `echo`, `print`, `goo-print`: the item-02 Rex boundary protocol.
- `codec`: checked normalized/semantic tree decoding and encoding (see [CODECS.md](CODECS.md)).
- `validate-measurement`: checked plan/metric/trace/result transport (see [MEASUREMENT.md](MEASUREMENT.md)).
- `ascii`: native leaf styles, widths, sizes, lines and heights (see [ASCII.md](ASCII.md)).
- `fonts`: compiled frozen font metadata and glyph advances.
- `layout`, `plan`: ASCII or injected measurements through the native planner (see [LAYOUT.md](LAYOUT.md)).
- `fixture`: normalized wire tree through visibility, adjacency, and the planner.
- `render`: semantic tree to prepared inspection, HTML fragment, and static document (see [HTML.md](HTML.md)).
- `tests`: structured Foil unit-test results.

For `source`, the first six stages (`parse`, `read`, `core`, `normalized`,
`visible`, `semantic`) expose actual pass outputs. Expected errors reject at
the originating stage; synchronous pass exceptions retain earlier results.
Successful semantic compilation proceeds to native ASCII measurement and planning.
`metrics`, `layout`, and `trace` expose the validated result. Backend errors are
attributed to `layout`, preserving all prior compilation outputs. Successful
geometry proceeds to prepared output and native HTML, reporting **`outcome: "complete"`**
when both succeed. Width, scale, and direction belong to one prepared context.
The `fixture` action supports recorded leaf measurements without running ASCII
measurement, preserving the frozen browser replay contract.
Protocol and runtime failures use `{version:1, ok:false, stage, error}`.

Cancellation propagates outside this response protocol. SIGINT exits 130 and
SIGTERM exits 143, stopping the active child process group without emitting an
ordinary failure response. Parse diagnostics are typed internally before JSON
projection; their existing external shape and wording are unchanged.

## Formatter

`fmt [--check] [files...]` defaults to package Foil sources. This initial formatter
proposes CRLF normalization, removes trailing horizontal whitespace and leaves one final
newline. It does not reflow expressions or rename anything. It compares native
Foil Rex trees before and after, ignoring only regenerated spans, and refuses a
change that alters syntax or string payloads, or whose parse contains error leaves.
The current native parser treats CR as an error leaf, so CRLF input is refused
rather than silently repaired. It computes every candidate before
writing any file. `--check` exits 1 when a safe formatting change is needed and 2
for invalid or unsafe input. Formatting uses the last verified compiled parser
while permitting source changes; rebuild after formatting.

## Tests

`test` runs compiled Foil checks, positive/negative compiler clients, actual
signal/cancellation checks, 1,070 differential codec cases and 954 round trips,
and exact semantic-prefix comparisons against 397 frozen oracle responses.
It also checks every one of the 369 source files at budgets 0/1/2, adversarial
inputs, all ordered rules and uniform provenance, UUID allocation/lifetime,
and measurement result validation against the production Haskell validator.
Rex transport, retained printers, process framing, formatter preservation, and
immutable build artifacts remain covered. Frozen references are never regenerated.

`test` also checks all 7,920 frozen ASCII accuracy cases, exact binary64 arithmetic
and text lines, all eight faces/760 glyphs, and wrapping boundary probes.

`test-metrics` runs just Gate M. `test-gate` runs the semantic and measurement
differential suites; `test-types` runs compiler clients.
`python3 goo/scripts/porting/check-ascii-corpus.py` additionally measures every
frozen nonempty semantic tree against Haskell. The oracle builders above are test setup only.
Unicode remains outside this port's current scope. Gate S evidence is in
`../../../goo/porting/gate-s/`; the later gates have corresponding `gate-m`, `gate-l`,
`gate-h` and `gate-u` evidence directories. Packaging begins at item 34.

The `codec` action validates and re-encodes versioned normalized/semantic tree
requests entirely in Foil. See [CODECS.md](CODECS.md) for the request shape,
defaults, numeric precision, and structural checks. The separate codec oracle is
only required by the differential test suite, not adapter execution.

`test-layout` runs Gate L independently: all 480 frozen plans/traces, synthetic
boundaries, emitted-edge mutations, and the separate ASCII geometry suite.
The full `test` command includes it and source-prefix comparisons through trace.
`python3 goo/scripts/porting/check-layout-rules.py` adds 388 positive checks
covering every ordered rule pair, fallback, and uniform mode at two widths.

Gate U is a separate application suite: see [APPLICATION.md](APPLICATION.md) for
exact source/snapshot/page comparisons, CLI checks, HTTP tests and the live
browser lifecycle harness. `test` continues to cover the compiler and Gates S–H.

## Mount and production boundary

The implementation lives in `extras/mounts/goo`. `mount.json` declares the flat
`goo_app/*` module bag, including the Rex boundary. Native source files are here;
`src/*.foil` and the old `goo/foil` path are compatibility links, not second copies.
The standalone executable is `bin/goo`. Its default asset/example root is this
package; `GOO_ROOT` selects an alternative. The build uses this package's locked
Rex toolchain and the parent repository's locked Foil runtime. It does not build
or load the Haskell Goo compiler. Historical oracles and differential evidence
remain in the top-level `goo/` tree and are needed only for the test commands.

`html` compiles, measures, lays out and paints within Foil. Inspector operations
retain intermediate values in the leased worker while the retained Haskell
printer receives only Rex batches. The host receives final application output,
not serialized Goo pass histories. Preview-only requests skip Rex projections and
the printer. See [production boundary evidence](../../../goo/porting/ssr-boundary/README.md).

The mount catalog supplies modules; it does not automatically start this standalone
HTTP server or attach its routes to another application. Run `bin/goo serve`.
