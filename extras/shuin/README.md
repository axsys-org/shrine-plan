# Shrine application mounts and acceptance tools

This directory supplies the server-side tools for the native Shrine integration.
The canonical production source is [../mounts/shuin-chat](../mounts/shuin-chat);
[../mounts/shuin-chat-test](../mounts/shuin-chat-test) adds destructive fixtures
only when explicitly selected. The Rust client remains in
[shrine-goo-native](https://github.com/axsys-org/shrine-goo-native).

## Boot from this checkout

```sh
python3 extras/shuin/run-chat-server.py --port 8267
# Optional local typed namespace interface:
python3 extras/shuin/run-chat-server.py --port 8277 --with-mcp
```

The wrapper uses this repository's `x/eden` and editable `extras`; no sibling
checkout, external integration patch or temporary kernel copy is needed. The
normal Eden Nix environment selects the runtime. `WISP=/path/to/wisp` overrides
it explicitly. The separate Enki GC headroom patch is not part of this import.

The wallet uses a separately started local Anvil on port 8545 (override with
`SHUIN_ANVIL_PORT`). Export `OPENROUTER_API_KEY` before launch to use real agents.
Booting the mount alone does not submit a provider request. The host writes the
credential into a private temporary file; it is not bundled into namespace data.
Keep credentials, runtime binaries and private study transcripts out of Git.

Connect the separate native client to this server, for example from its checkout:

```sh
cargo run -p shuin-gallery -- --server http://127.0.0.1:8267 --scene agents
```

## Features and ownership

- Namespace-defined scenes, navigation, titles/help, inspector and action menus.
- Chat messages created with the published `post_message` stencil.
- Bilingual Berakhot 2a commentary, with source attribution in the mount's
  [fixture README](../mounts/shuin-chat/talmud-source/README.md).
- Local development wallet behavior and HTTP effects owned by Shrine.
- Agents with typed read/write hunts, provider/tool receipts, pending grants and
  lossless type-directed namespace export; see [agents.md](agents.md).
- Prefix/title path search indexed only under `/<node>/app`; see
  [path-inputs.md](path-inputs.md). This is not the superseded full-namespace,
  substring/fuzzy search proposal.
- A shared source/build/test/review/publish workbench; see [workbench.md](workbench.md).
- Namespace-defined commentary menus; see [context-menus.md](context-menus.md).

The kernel changes are ordinary Reaver source now: Goo context/composition/path
values, bounded rendering, idx, exact-version stencil creation, reflected type
metadata, change-workbench admission and construction optimizations. Application
policy stays in the mounts; Rust remains the generic renderer.

## Disposable verification

These tests mutate a disposable world. Never aim them at a kept user session.
Start the deterministic mock provider in one terminal:

```sh
python3 extras/shuin/test-agents.py --mock-only --mock-port 8343
```

Start a fresh test world in another terminal (no paid credentials are needed):

```sh
SHUIN_AGENT_TEST=1 OPENROUTER_API_KEY=shuin-test-key \
SHUIN_OPENROUTER_URL=http://127.0.0.1:8343/api/v1/chat/completions \
python3 extras/shuin/run-chat-server.py --port 8341 --test-fixtures
```

Then run the checks. Use fresh worlds/mock processes for independent agent and
stencil actor runs; their assertions assume empty histories.

```sh
python3 extras/shuin/test-namespace-text.py --server http://127.0.0.1:8341
python3 extras/shuin/test-agents.py --server http://127.0.0.1:8341 --mock-port 8343
python3 extras/shuin/test-stencils.py --server http://127.0.0.1:8341 --actor
python3 extras/shuin/test-workbench.py --server http://127.0.0.1:8341 \
  --mock http://127.0.0.1:8343 --output /tmp/shuin-workbench.json
python3 extras/shuin/check-search-index.py --wisp /path/to/wisp \
  --output /tmp/shuin-search-oracle.json
```

`measure-path-search.py`, `report-path-search.py`, `profile-search-construction.py`
and `report-search-construction.py` preserve the disposable benchmark/profiling
workflow. `--without-search-index` is restricted to test worlds. Neither functional
tests nor diagnostic construction timings establish the original 10,000-path
HTTP/native performance gates. `measure-commentary.py` measures server preparation;
native rendering and IME checks remain in the client repository.

## Study setup

With MCP explicitly enabled, `setup-berakhot-swarm.py --server URL` creates five
study agents and queues a finite seminar; it refuses to overwrite existing agents.
`setup-berakhot-consensus.py --server URL` creates a separate ballot study using the
same shared channel. Both are namespace provisioning tools, not Unix agent loops:
Shrine owns the provider requests, tools and inbox processing. Real execution uses
the launcher's provider credential and incurs provider usage.

The plurality study requires all five valid ballots, committed messages and empty
inboxes before a unique substantive leader with at least two votes qualifies.
Its round advancement and final verification remain operator-controlled. There is
no persistent consensus coordinator. Only setup code is imported here; live study
state and paid-provider transcripts are not part of the repository.

## Import verification

See [VALIDATION.md](VALIDATION.md) for passing acceptance checks, reproduced
baseline failures and the runtime used. The broad existing gate is not green.

## Provenance

Imported from the working source of `shrine-goo-native` at base commit
`d472dc47084791cff1813dc1279374607ab17997`, including the subsequent uncommitted
integration work. The combined kernel patch was based on Reaver `d0deab27` and
applied on top of `66ff9f52`. The existing launcher edits required by the branch’s mount manifests were
preserved verbatim in the separate prerequisite commit `59a06105`. Historical incremental patches are unnecessary in this tree.
Generated protocol-profile and icon metadata remain paired with the native client;
their font-dependent generators are maintained there. The Talmud source generator
and its attributed offline inputs are included here.
