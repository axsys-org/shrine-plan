# Eden source mounts

`x/eden` boots Shrine's namespace, Pact, supervisor, filesystem driver and HTTP
transport. It does not install a browser application or build browser assets.
Unregistered HTTP routes return 404.

```sh
x/eden
x/eden --list-mounts
x/eden --mount debugger --mount srs
x/eden --extras-root ../shrine-extras --mount explorer --mount codex
```

The `shrine-extras` input in `flake.lock` selects the default extras revision.
`--extras-root` selects an editable checkout, including that checkout's Nix
configuration. Dependencies are loaded once, before their consumers. Only selected
mounts and their dependencies prepare host tools or assets. Mash and Node belong
to the debugger's extras environment, not the core Eden shell.

Each flat bag has a version-1 `mount.json`. It maps logical Foil module names to
filenames, declares ordered Grove units and their publication roots, and declares
assets, dependencies and optional activation, HTTP and host entrypoints. See the
[extras repository](https://github.com/axsys-org/shrine-extras) for the schema and
application checks. Core rejects unknown names, cycles, core-module overrides,
overlapping publication ownership and duplicate route claims. HTTP dispatch uses
the longest matching path prefix, with segment boundaries.

## Source, definition and instance identities

For node `0x11` and mount `srs`:

- `/0x11/io/fs/srs` is the mount control record.
- `/0x11/io/fs/srs/source/<filename>` contains imported bytes.
- The `apps/srs/main` Foil module retains its compiler identity beneath the
  publisher's `/lib` root.
- `/0x11/gov/srs` is the published Grove template.
- `/0x11/app/srs` is one possible installed instance.

A compiler custom reader reads only the captured source records, plus declared
dependency artifacts and core sources. Extras are never overlaid into core's Foil
source directory. The runtime prohibits symlinks outside its file root, so a
private scanner captures each requested bag into a separate `mounts/` directory
before importing it. Every request reads the current checkout. Missing files in
old namespace history are excluded from the compiler snapshot.

## Explicit rescan

Warp the mount control record with its `op/rescan` operation. With explorer
mounted, this is also available through the ordinary operation UI, or:

```sh
curl --data-urlencode 'op=/0x11/io/fs/srs/op/rescan' \
  http://127.0.0.1:8130/op/0x11/io/fs/srs
```

The control record's publisher-owned `fs/source/status` slot reports the scan
epoch, readiness, message and last successful publication. `fs/source/diagnostic`
contains the publication failure, if any. The filesystem `res` report records
known and missing files. Read failures, missing inputs and compilation failures
retain the previous successful definitions. Obsolete scan completions are ignored.
Unchanged captured bytes do not compile or publish again.

Each mount is compiled against one captured namespace state. Its complete candidate
is installed only after all Foil modules, Grove units and required assets validate.
Activation runs on initial selection. Existing instances and feet retain their
captured code and state; rescan does not rerun activation, replace drivers or
migrate instances. New installations can use the newer definitions. Route handlers
and asset responses are captured by the running HTTP foot. Restart to select new
mounts, change a descriptor's runtime contract, or replace that foot.

Watching, persistence and automatic instance migration are outside this interface.

## Checks

```sh
python3 x/eden-mounts-test.py
python3 x/test_runner_tests.py
x/check foil:tests/source_mount foil:tests/fs_reconcile foil:tests/http_foot foil:tests/inspect_read
x/eden --check
x/eden --extras-root ../shrine-extras --mount debugger --mount srs --mount codex --check
```

Application suites live in extras. Core Grove compiler tests use independent
fixtures in `src/grove/fixtures`; they do not read SRS or debugger sources.
