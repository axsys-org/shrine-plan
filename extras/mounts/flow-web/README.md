# HTTP work provider for flows

Select `flow-web` to install the existing HTTP provider and register its native
foot. Its only mount dependency is [`flows`](../flows/README.md); Nenex and Explorer
are not required. The host hook only supplies `/0x11/io/web` to Eden's existing
foot registration.

The native `web_fetch` operation describes provider requests and `web_sources`
decodes completed responses into evidence envelopes. They keep their existing
`/0x11/gov/flows/operations/...` addresses. Requests, outcomes, captured guards,
holes, retries and retained attempts use the shared native work contracts.
The foot performs transport for newly observed commands. It does not schedule
flow retries or own another queue.

Provider installation and behavior refresh belong to this mount. Refreshing
Nenex authoring does not replace the selected HTTP provider. Its persistent
result contracts remain owned and pinned by `flows`.

Run `extras/x/check --mount flow-web --contracts-only` to check the standalone
provider entrypoints. The integration transport checks in
`../flows/tests/check-web-transport.py` exercise a disposable local HTTP source,
including failed and restored responses; they are not a public-web availability
claim.
