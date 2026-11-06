# SQL source transport

An optional SQL Server transport for the **existing HTTP source hand**. SQL is
configured by the operator; agents select a named query and declared integer
arguments. There is no arbitrary-SQL endpoint, polling loop, work queue or
second capture store. Flows own requests, retained results, holes and retries.

Install the locked Node dependencies with `npm ci` in this directory. Provide
`SHRINE_SQL_CONFIG` as an absolute path to a private JSON file, then select
`--mount sql-source` with the normal `x/eden` launcher. The mount uses the
existing host cleanup to start and stop the companion. The companion contributes `bag/endpoint.json`
to the ordinary filesystem source bag, alongside the mount’s normal source files.
Logs and database credentials are not included. The endpoint catalogue contains a **read capability** in each URL. Anyone
who can read it can invoke those queries; do not publish it to untrusted readers.
The HTTP listener binds only to loopback. Remote database credentials still
require the database's normal transport and access controls.

Configuration has `port`, a persistent random URL-safe `token` of at least 32
characters, `connection` (the node-mssql connection configuration), and `queries`.
Each query declares a SQL `file` relative to the config and optional `parameters`,
with explicit SQL-int `min`/`max` ranges. SQL executes with bound parameters.
Use a dedicated read-only database principal; the adapter cannot make an
administrative login read-only. Snapshot isolation must be enabled on the source
database. Production connections verify TLS by default.

See [the WWI profile](../flow-examples/examples/wwi/README.md) for a concrete
example. Choose a fixed free port and retain the token across restarts so native
URL bindings remain valid. Configuration is read at startup. Changing query
files/configuration requires restarting this companion; it does not hot-publish
SQL definitions. A changed query's bytes have a new SHA-256 in its next capture.

Each successful response is `{source, data}`. `source` records database, query,
exact SQL text and hash, arguments, snapshot isolation, and start/finish times. The configured
query returns one JSON text column, normally `FOR JSON PATH` wrapped as in the
example. SQL emits JSON numbers; the adapter validates but does not reserialize
`data`, preserving decimal/bigint spelling and nulls. HTTP JSON then passes
through `web_sources` and the existing `library/decode_sources` operation. The
`live_data` Semidoc example composes the separately published `capture_sources`,
`decode_sources` and `project_sources` flows to project it into Nenex while keeping cohesive native
values in the step's cells for composition.

One response uses one read-only-by-permission snapshot transaction. Different
queries are **not** one coherent multi-query database snapshot. Retained query text, hashes and
capture intervals identify what was executed; they are not CDC cursors or proofs
of complete business coverage. Pages use explicit bounded keyset parameters;
there is no hidden exhaustive pagination. Empty rows are `[]`. An unavailable,
malformed or oversized response fails rather than reusing earlier bytes. The
whole response must fit the existing 131072-byte native HTTP limit; narrow the
query when it does not. SQL requests time out after 15 seconds. Disconnects
cancel the active request; the host's cleanup terminates the companion.

Refresh through the existing URL revision/retry operations. This transport
performs reads only. It establishes neither external write semantics nor an
atomic transaction between SQL and namespace publication.

`npm test` checks parameter boundaries, exact numeric text, provenance, failures,
restoration, cancellation and response limits. With a private configuration,
`SHRINE_SQL_CONFIG=/absolute/path/source.json node --test live.test.mjs` checks
the actual WWI queries and database permissions. Live tests are opt-in and
never start or stop a database.

The opt-in native proof is `SHRINE_SQL_CONFIG=... WISP=... python3 check-native.py`.
It starts an ephemeral companion through the same host cleanup and uses the
existing native test runner in a disposable world. It checks actual SQL Fetch,
structured decoding, Semidoc publication, shared hands, failure/hole/retry,
Nenex publication, work cells, and retained x/y/z history. Its initial failure
is injected at the transport reply boundary; the successful retry reads real
WWI data. It does not touch a running Shrine world or invoke a model provider.
