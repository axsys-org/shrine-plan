# Hello Grove

Runnable companion to [Making a Grove and Goo mount](../../tutorials/grove-goo-mount.md).

From the repository root:

```sh
python3 x/eden --compiler none --mount hello-grove --port 8137
```

Open http://127.0.0.1:8137/hello-grove. Select a note, choose **Edit**, change its
text, and choose **Save and read**. Reload and select the note again to see the
saved value. This development launcher creates a fresh namespace on restart.

The mount has no custom JavaScript. Grove owns the views and selection; the Foil
host installs the seeds and delegates to the existing Goo workspace host.

## Verification

On 2026-10-08, the mount contract checks passed and the real sample compiled,
published, and installed in Eden. The six profile-generation checks also passed.

The companion browser check passed in Chromium 151.0.7922.34, Firefox 153.0, and
WebKit 26.5. It exercised keyboard selection, Edit without a domain write, saving,
reload restoration, restoring the original sample, a 680px layout, and absence of
uncaught browser errors. Manual IME behavior and server-restart persistence were
not tested; the development launcher starts a fresh namespace each run.

```sh
WISP=/path/to/wisp python3 extras/x/check --mount hello-grove --contracts-only
node extras/mounts/hello-grove/check-browser.mjs \
  http://127.0.0.1:8137 /path/to/mash /tmp/hello-grove-browser
```

The browser check uses the Mash integration-test Playwright dependency. Run it
against a disposable tutorial instance; it changes the first note and restores
the original body after each successful engine run.
