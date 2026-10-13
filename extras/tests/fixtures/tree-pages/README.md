# Incremental Inspector regression fixture

This test-only mount installs 80 real sibling records below
`/0x11/app/tree_pages/root/wide`, a structural parent with no record, and a
nested record that must remain unloaded until its own branch is expanded.
It uses the normal Inspector, source endpoint, Mash components and selection
owners. No browser response is mocked.

To run it from the Reaver checkout, expose the fixture alongside normal mounts:

```sh
python3 - <<'PY'
from pathlib import Path
import tempfile
root = Path.cwd()
extras = Path(tempfile.mkdtemp(prefix='goo-tree-fixture-'))
(extras / 'mounts').mkdir()
for mount in (root / 'extras/mounts').iterdir():
    if mount.is_dir():
        (extras / 'mounts' / mount.name).symlink_to(mount, target_is_directory=True)
(extras / 'mounts/tree-pages').symlink_to(root / 'extras/tests/fixtures/tree-pages', target_is_directory=True)
print(extras)
PY
```

Pass the printed directory to the standard Eden launcher:

```sh
nix develop .#eden --command python3 x/eden --mount tree-pages \
  --extras-root /tmp/goo-tree-fixture-REPLACE --port 8094
node extras/mounts/explorer/scripts/check-tree-browser.mjs \
  http://127.0.0.1:8094 /path/to/mash /tmp/goo-tree-results
```

The browser script defaults to Chromium, Firefox and WebKit; `BROWSERS=chromium`
selects one engine. It checks deferred disclosure, continuation beyond 64 children,
structural keyboard access and retained instances across collapse/reopen.
Native `tree_pages` checks also cover stale epochs, invalid continuation and parent
paths, exact page counts, descendant capture admission and disclosure hints.

Verified on 2026-10-05:

- 68 Explorer JavaScript tests passed.
- 632 native assertions passed across mount contracts, web, Explorer, debugger
  and Grove debugger, including the 10 new child-page assertions.
- The real fixture passed in Chromium 151.0.7922.34, Firefox 153.0 and WebKit 26.5.
  Each engine also passed the existing nine topoi focus/preservation cases.
- Nested expansion and selection, visible children after collapse/reopen, and
  actual HTTP rejection of stale epochs and out-of-source parents passed.
- The server returned HTTP 409 for a compiler key without a Goo path spelling;
  that branch remains available through the physical debugger.

For the responsive pane regression, also symlink `extras/tests/fixtures/panes`
as `mounts/panes` in the temporary extras root, launch with both
`--mount tree-pages --mount panes`, then run:

```sh
node extras/mounts/explorer/scripts/check-layout-browser.mjs \
  http://127.0.0.1:8095 /path/to/mash /tmp/goo-layout-results
```

This gate uses real server-prepared `sm`/`md`/`lg` variants. It checks sidebar and
page overflow at 380, 532 and 1400 pixels, deep selection, local variant switching
without additional render requests, native input/caret preservation, synthetic
composition deferral, sub-sm panes, text scale/RTL and a real action followed by
fresh layouts. It restores the fixture's Card A title after its save assertion.
Run browser gates sequentially against the boot-compiler fixture server to avoid
their concurrent 64-child render bursts competing with each other's deadlines.

Responsive verification on 2026-10-05: 71 JavaScript tests and 643 native
assertions passed. The layout gate passed in Chromium 151.0.7922.34,
Firefox 153.0 and WebKit 26.5. Synthetic composition coverage does not claim
manual platform IME testing. The incremental-tree gate also passed in all three
engines with the size variants enabled, including continuation beyond 64 members
and nine existing focus/topos cases per engine. Its original 30-second deadlines
remain unchanged; slot/role lookup is shared across a row's three variants.
The Chromium application gate also passed all 10 scenarios with 105 real render
responses and one deliberate domain action, covering stale replies, instance
replacement, independent selections, dirty-input guards and control remounting.
