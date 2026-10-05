# enki

`enki` is a PLAN runtime structured as three packages with a mechanically
enforced dependency direction:

| package | prefix | contents |
| ----------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pkg/axsys` | `ax_` | GC-oblivious systems substrate: arena, vector, string builder, allocator, sha256. Knows nothing about the heap or value representation. |
| `pkg/plan` | `pl_` | The PLAN core: value representation, semispace Cheney heap with safepoint+reserve discipline, the explicit-frame reduction machine (whnf/nf), primops, pins, and the content-addressed store (LMDB or in-memory backend). |
| `pkg/enki` | `en_` | Everything above the core: the wisp PLAN-assembly front end (parser, macro expander, module loader) and the `wisp` / `assembler` apps. |

## GC Discipline

The collector runs only inside `pl_gc_reserve`; allocation (`pl_bump` and
every constructor) never collects and hard-asserts previously reserved
headroom. Code measures sizes, reserves, re-fetches values from rooted
locations, then builds inside a no-collect window. The collector scans
exactly the registered root sources — no conservative scanning, no C-stack
scanning. A `GC_STRESS=1 make` build collects on every reserve, turning any
rooting violation into a deterministic failure:

```sh
GC_STRESS=1 make BUILD_DIR=build/stress test
```

## Quickstart

Enter the reproducible shell:

```sh
nix develop
```

With direnv installed, automatic shell entry is:

```sh
direnv allow
```

The Makefile also works without Nix when the required tools are installed
(gmp, lmdb, openssl):

```sh
make
make test
make BUILD_TYPE=asan test
```

## Nix Builds

```sh
nix build
nix build .#enki
nix build .#enki-debug
nix build .#enki-asan
nix build .#enki-ubsan
nix build .#enki-tsan
nix build .#enki-coverage
```

Each package is derived from the same `mkenki` helper and calls:

```sh
make BUILD_TYPE=<type>
make install BUILD_TYPE=<type> PREFIX=$out
```

Coverage builds use GCC so lcov gets a matching gcov tool. On Linux, debug and
release also use GCC, while sanitizer, tidy, and fuzz builds use Clang. On macOS
the sanitizer builds use Clang for platform compatibility. This gives CI
coverage across both compiler families without a separate compiler matrix.

## Tests

Run everything:

```sh
make test
nix flake check -L
```

- `tests/unit` — Greatest suites for the axsys containers, the plan core
  (value representation, nats, GC movement), the reduction machine
  (laziness boundaries, recursive-let knots, primop strictness order),
  pins/store round trips, the wisp front end, and an end-to-end check that
  `wisp reaver/src/plan reaver` exits zero.
- `tests/property` — theft property tests.
- `tests/fuzz` — libFuzzer targets.

Run tests under each sanitizer:

```sh
make BUILD_TYPE=debug test
make BUILD_TYPE=asan test
make BUILD_TYPE=ubsan test
make BUILD_TYPE=tsan test
```

TSan runs the full Greatest suite plus the focused multithreaded stress tests
in `tests/unit/*_tsan.c`. Each Greatest test process has a 60-second timeout.

Property tests use a fixed seed in CI. Override it locally with:

```sh
THEFT_SEED=0x1234 make test-property
```

Greatest and FFF are vendored as single headers under `tests/support/`. Theft
is vendored under `tests/property/vendor/theft/` as a tiny deterministic
single-purpose runner, because upstream theft is not reliably packaged in
nixpkgs.

## Coverage

Generate local HTML coverage:

```sh
make coverage
```

The report is written to `build/coverage/html/index.html`.

Build the reproducible report:

```sh
nix build .#coverage
nix run .#coverage-report
```

The Nix build writes the report under `result/html/`.

## Clang PGO

Build a Clang profile-guided `wisp` and `assembler` locally:

```sh
make pgo
```

The target builds an instrumented binary under `build/pgo-generate`, runs this
training workload from `build/pgo/run`:

```sh
../../../build/pgo-generate/bin/wisp --file-root ./reaver/src ../reaver/src/plan reaver main
```

and merges the generated profiles into `build/pgo/enki.profdata`. Any snapshots
created by the workload stay under `build/pgo/run/snap`. It then rebuilds the
optimized binaries under `build/pgo/bin` with
`-fprofile-instr-use=build/pgo/enki.profdata`.

Useful overrides:

```sh
make pgo PGO_CC=/path/to/clang LLVM_PROFDATA=/path/to/llvm-profdata
make pgo PGO_WORKLOAD="--file-root ./reaver/src ../reaver/src/plan reaver main"
```

## SPLAN Profiling Zones

RPLAN code can mark explicit spans with the direct op-83 primops
`["ZoneStart", label]`, which returns an opaque handle, and
`["ZoneEnd", handle]`. Handles belong to the logical PLAN thread that created
them; zones may be ended out of nesting order, but duplicate, unknown, and
cross-thread handles are runtime errors.

Export those spans as a Chrome Trace JSON file with either CLI spelling:

```sh
wisp --profile-json trace.json DIR MODULE [FUNCTION ARGS...]
wisp --profile-json=trace.json DIR MODULE [FUNCTION ARGS...]
```

Open the resulting file in `chrome://tracing`. Each logical PLAN thread is a
separate lane, and spans are paused while an actor is yielded or blocked. The
JSON export contains explicit zones only; automatic law attribution remains a
Tracy-only feature.

## Formatting And Analysis

```sh
make format
make format-check
make tidy
nix fmt
```

`make tidy` consumes `compile_commands.json` (generate with Bear) and runs
clang-tidy with checks from `.clang-tidy`. `nix fmt` uses treefmt-nix with
clang-format for C and headers, alejandra for Nix, and mdformat for Markdown.

## Debugging Linux builds with Docker

The Docker workflow uses a pinned Nix 2.34.7 image and the same `tools/nix-ci`
runner as GitHub Actions. The default platform is `linux/amd64`, matching the
GitHub Ubuntu runner:

```sh
make linux-check
```

On Apple Silicon, use the native platform for faster iteration:

```sh
make linux-check LINUX_PLATFORM=linux/arm64
```

Checks stage a clean source copy inside the container, excluding Git metadata,
build artifacts, snapshots, and the local `reaver` checkout. This keeps linked
Git worktrees reproducible without modifying the host workspace. The Docker
harness disables Nix's inner syscall filter for cross-architecture emulation;
Docker remains the outer isolation boundary, and native CI keeps the filter.

Open an interactive Linux development shell with the current worktree mounted
read/write at `/src`:

```sh
make linux-shell
# or, on Apple Silicon
make linux-shell LINUX_PLATFORM=linux/arm64
```

Nix downloads are cached in a Docker volume specific to the image version and
architecture. Remove a cache when a clean Nix store is needed:

```sh
docker volume rm enki-nix-2-34-7-linux-amd64
docker volume rm enki-nix-2-34-7-linux-arm64
```
