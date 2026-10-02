# SRS domain fixture

The SRS mount publishes roles, actions, queue logic and seed cards. Its Goo views
have been removed. Start `x/eden --mount srs --mount goo-inspector` and inspect
`/goo-inspector?path=/0x11/app/srs/cards` or the namespace page
`/ns/0x11/app/srs/cards/demo`.

Installation and rescan checks remain in `host.py` and `rescan_check.py`.
The interaction regression specimen is test-only in `extras/tests/fixtures/panes`;
it is installed by the Goo application compatibility gate, not the production
mount catalogue.
