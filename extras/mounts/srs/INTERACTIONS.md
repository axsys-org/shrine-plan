# SRS cards and review

The SRS mount publishes roles, actions, queue logic, seed cards, two Goo views,
and a collection workspace:

- `content`, selected by `/sys/slot/content`, shows the question (or subject path)
  and answer. Cards without an answer show an explicit empty state.
- `review`, selected by `/sys/slot/review`, adds the due time, interval, and
  Again / Hard / Good / Easy buttons. Each button invokes the existing `finish`
  action on the presented card using server-provided time.

The application entry at `/{self}/app/cards` stores `/sys/face` as a path to
`/{self}/gov/srs/workspace` and `/sys/from` as the card collection at
`/{self}/app/srs/cards`. Its **Panes** tab opens a card list and the selected
card's review controls. Selection is local to the pane; grading changes the
selected card. The entry's receiver fields live in that namespace record.

Start `x/eden --mount srs --mount goo-documentation` and open
`/goo-documentation?path=/0x11/app/cards` for the workspace, or
`/goo-documentation?path=/0x11/app/srs/cards/demo`, then choose **Views**.
The same views are available at `/views/0x11/app/srs/cards/demo`.
Declarations live under `/{self}/gov/srs`; they match the card role rather than
one hard-coded instance path. The mount still supports the namespace page at
`/ns/0x11/app/srs/cards/demo`.

Installation and rescan checks remain in `host.py` and `rescan_check.py`.
The interaction regression specimen is test-only in `extras/tests/fixtures/panes`;
it is installed by the Goo application compatibility gate, not the production
mount catalogue.

`check-views.mjs` exercises both views through the documentation browser, grades
with all four buttons, checks the stored schedule and retained question/answer,
and verifies a second installed instance. It mutates the demo card, so use a
disposable namespace:

```sh
node extras/mounts/srs/check-views.mjs \
  http://127.0.0.1:8130 /path/to/mash /tmp/srs-views-browser
```

Verified on 2026-10-12 against a disposable Eden instance: installation checks
and the view/grading flow passed in Chromium, Firefox, and WebKit, including
server-clock due times and matching a separately installed instance.

`check-panes.mjs` verifies the application entry, conditional Panes tab, selected
card grading, tab/resize continuity, and invalid preferred-pane bindings. Like
`check-views.mjs`, it must run against a disposable namespace.

Verified on 2026-10-12 in Chromium, Firefox, and WebKit: the preferred pane
renders the collection, grades the selected card, retains selection across tab
switches and resize, hides on entries without a face, and rejects non-pane or
incompatible declarations. Native web, explorer, documentation, and mount
contract checks passed, alongside 86 JavaScript tests and the slot catalog checks.
