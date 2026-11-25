# Native renderer performance

The engine, visibility, projection, texture selection, sprites, and framebuffer
remain Foil on PLAN. There are no Doom-specific native operations. The default
renderer is `spans`; `--renderer reference` preserves the original per-column
ray/BSP implementation for comparisons.

## Measured checkpoint: 2026-10-22

Apple Silicon/macOS, pinned Enki PGO runtime, P6; two sequential runs of each
renderer/resolution, 100 replay frames per run, first ten excluded. The table
averages the two warm run means. Full summaries, p95 values, runtime path,
source hashes and final frame hashes are in [benchmark-results.json](benchmark-results.json).

| Resolution | Ray reference | Projected spans | Speedup | Optimized throughput |
| --- | ---: | ---: | ---: | ---: |
| 48×30 | 188.8 ms | 41.8 ms | 4.52× | 23.9 fps |
| 96×60 | 504.6 ms | 67.7 ms | 7.46× | 14.8 fps |

The two optimized run means were 40.8/42.8 ms at 48×30 and 65.6/69.8 ms at
96×60. The 35 fps target is 28.6 ms for the entire frame; neither resolution
meets it yet. These headless rates leave terminal output cost unmeasured.

| Native phase | 48×30 reference | 48×30 spans | 96×60 reference | 96×60 spans |
| --- | ---: | ---: | ---: | ---: |
| Simulation | 2.0 ms | 2.1 ms | 2.4 ms | 2.0 ms |
| Visibility/projection | 139.4 ms | 19.2 ms | 304.5 ms | 19.9 ms |
| Raster + per-column packing | 47.2 ms | 20.4 ms | 197.4 ms | 45.6 ms |
| Final frame/header packing | 0.042 ms | 0.038 ms | 0.088 ms | 0.077 ms |
| Socket write | 0.031 ms | 0.028 ms | 0.037 ms | 0.033 ms |

The measurements overturn the initial suspicion that final framebuffer
concatenation might dominate. Visibility is now almost resolution-independent;
raster work dominates at the default size. Its timer includes column setup,
sampling, composition and column-byte construction, so it does not isolate the
cost of individual primitives or allocation.

A separate five-second macOS sampling run began after engine startup during the
full 220-tic replay. Of 3,960 main-thread samples, 2,483 (62.7%) had the evaluator
`pl_run` at the leaf; 66 (1.7%) passed through `pl_gc_reserve_slow`. The latter
includes collection/reservation work. This points toward execution/call overhead
before collector tuning. JIT addresses were partly unsymbolicated and zone
tracing was enabled, so these are diagnostic sample proportions, not exact CPU
shares or per-frame allocation counts. This run is excluded from the timing table.
The full route completed with the same final gameplay state as the original port:
tic 220, HP 98, ammo 45, one kill and one pickup, position (561, 262), angle 356.

## Reproduce the measurements

```sh
WISP=/path/to/wisp python3 extras/mounts/doom/benchmark.py \
  --out /tmp/doom-bench --sizes 48x30 96x60 --runs 2 --frames 100 --warmup 10

WISP=/path/to/wisp x/doom --headless --script extras/mounts/doom/demo.json \
  --width 96 --height 60 --profile /tmp/doom-profile.json --warmup 10
```

The benchmark alternates renderer order and runs processes sequentially. Each
uses the same first 100 inputs of `demo.json`, P6, and the supplied E1M1 WAD.
Startup and the first ten frames are excluded from warm summaries. Every frame's
HUD/state must match across renderers and resolutions, and repeated runs of each
renderer must produce identical frame hashes. Different renderer hashes are
expected: the new projection and Q16 sampling have different subpixel rounding.

Profiles include all samples, phase distributions (mean, median, nearest-rank
p95, min/max), round-trip times, frame hashes, and HUD state. `--warmup` changes
only the summaries, not the replay or raw samples. It is valid for a short run
to have no warm samples; summaries then contain null distributions.

Native timestamps explicitly force each phase's computed values before reading
the next timestamp. Static level/texture data is forced once during startup;
projection forcing does not recursively revisit texture rows every frame.

- `step`: simulation and forcing the changing world fields.
- `visibility`: BSP traversal, clipping/projecting segments, cached ray/segment
  coefficients, sprite projection, and forcing that metadata.
- `raster`: vertical portal clipping, wall runs, shared floor/ceiling scanlines,
  masked textures, sprite composition, and packing each column.
- `pack`: assembling already rendered columns and the wire header.
- `write`: native socket write.

Round-trip timing includes the simulation and native renderer but excludes
Python ANSI painting. Profile log formatting happens after the measured native
write; small transport/logging/scheduling costs can make phase sums differ from
the round trip. These are elapsed times, not CPU-cycle or allocation counts.
Optional `--trace /tmp/doom-trace.json` enables Wisp trace output with named
`doom.step`, `doom.visibility`, `doom.raster`, and `doom.pack` zones. Law sampling
requires a profiling-capable runtime. No per-phase heap-byte or GC attribution
is claimed by the ordinary timing report.

## Algorithm changes

The BSP is walked front to back once per frame. Child bounding boxes are tested
against the remaining camera frustum. Opaque wall spans close horizontal screen
intervals, narrow that frustum, and allow fully hidden geometry to be rejected.
Each column then clips through the surviving portals, stopping when no vertical
opening remains. Masked middle textures remain transparent depth-tested layers.

Wall sidedefs/materials and affine ray/segment coefficients are resolved before
pixel loops. Each wall column selects its texture column and light-map row once;
Q16 texture y advances by addition. Floor/ceiling projection is shared by a
horizontal scanline per sector and height, with wrapped Q16 texture coordinates.
These scanlines are lazy: unused samples do not read textures. Sprite texture
columns/scales/light rows are prepared once per screen column. The two weapon
images are scaled exactly once at startup, including transparent edges.

## Runtime operations worth accelerating next

**Do not start with trigonometry.** `dz/sin` and `dz/cos` index a 360-entry
integer table. There is no transcendental sin/cos/atan call in a pixel loop.
Square root is used by map loading and gameplay, not the raster loop.

1. **Signed scalar arithmetic exposed directly to Foil/P6.** Zigzag add, subtract,
   multiply, truncating divide, comparison, and negation currently expand into
   several natural-number operations and calls. Both projection and portal setup
   use them heavily. The local Enki working tree already contains proposed
   `I63*` operations; the pinned runtime used here predates them. Connecting those
   general operations to Foil is the most direct next experiment. Native/JIT
   lowering and inlining matter as well as having a C implementation.

   These are not drop-in replacements for every `dz` function: `I63Abs` returns
   an encoded positive integer, while `dz/abs` returns a natural magnitude;
   `I63Mod` has signed remainder semantics, while `dz/mod` wraps into a positive
   texture range. `dz/div` also handles a zero denominator differently. I63
   operations wrap at their fixed width; Foil's natural-backed helpers do not.
   Keep adapters and boundary/property tests, and establish intermediate bounds.

2. **Signed multiply/divide with a wide intermediate.** A general
   `mul_div(a, b, c)` that computes the product without intermediate overflow and
   specifies truncation toward zero would accelerate fixed-point projection and
   texture setup. A separate floor-rounding variant is useful for screen bounds.
   It should have an explicit division-by-zero contract and a pure reference
   implementation. Fusing this operation also avoids intermediate PLAN objects.

3. **Only after another profile: fused dot/cross products or a general sampled
   byte span.** Two-term dot/cross operations with wide intermediates could reduce
   geometry call overhead. A generic indexed byte-span sampler (count, source,
   fixed-point start/step, optional translation table and transparency) could help
   rasterization at larger sizes. Neither should include WAD, BSP, monster, or
   game-state semantics. Validate exact bounds/rounding/transparency behavior
   against Foil. This is a candidate, not a demonstrated requirement yet.

`load8`, `loadvar`, shifts, natural arithmetic and row indexing already have
native runtime support. A new trig jet or framebuffer concatenation primop is
not supported as the first priority by the phase timings. Improving generic
strict small-scalar loops and reducing closure/record allocation may be as
valuable as adding operations. The sampling result supports prioritizing evaluator
and call overhead; exact allocation attribution still needs an instrumented runtime.

No speedup for these proposed runtime changes has been measured here. They are
ranked experiments, not a promise that one jet will reach 35 fps at 96×60.
