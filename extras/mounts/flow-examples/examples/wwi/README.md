# Wide World Importers live evidence

These are ordinary SQL Server read queries for Microsoft's WWI OLTP sample,
consumed by the optional `sql-source` transport and the `live_data` Semidoc flow.
They describe data retrieval, not a replacement business model or scheduler.

- `catalog`: discover visible tables and object IDs.
- `schema?object=<id>`: columns, SQL types, descriptions, ordered primary key and
  foreign-key mappings for one table. This is structural evidence, not a complete
  inventory of procedures, constraints, triggers or business rules.
- `orders?after=0&limit=10`: ordered keyset page, maximum 50 orders.
- `order?id=1`: one order with lines, stock quantities and related invoice IDs.
  Holdings are current at capture time, even when the order dates are historical.

Copy this directory's SQL and `config.example.json` into a private directory,
fill the connection credentials and generate a persistent capability token.
Keep the config mode 0600. The sample configuration trusts a locally generated
SQL Server certificate; use verified TLS for a remote database. Install the
transport dependencies and pass the config path via `SHRINE_SQL_CONFIG` to Eden.

Restore the official WWI Full backup into a **new local SQL Server Developer
container**, using a named data volume and a loopback-only port. The sample has
four logical files: inspect `RESTORE FILELISTONLY` and explicitly `MOVE` each one,
including its memory-optimized filegroup. Enable `ALLOW_SNAPSHOT_ISOLATION`.
The backup and database are runtime data and do not belong in this repository.

Create a dedicated SQL login/user. Grant `VIEW DEFINITION` and `SELECT` on
`Sales.Orders`, `Sales.OrderLines`, `Sales.Customers`, `Sales.Invoices`,
`Warehouse.StockItems`, and `Warehouse.StockItemHoldings`. Deny INSERT, UPDATE,
DELETE, EXECUTE, ALTER and TAKE OWNERSHIP. WWI's customer row-level security
checks membership of its existing territory `... Sales` roles. Select the
intended territories explicitly; an all-business case study can select all nine
sample territory roles. Inspect their permissions before granting membership.
Do not grant db_owner or disable the security policy merely to make rows appear.

WWI is a binding profile for reusable flows, not a separate workspace flow.
Create and publish `select_queries`, `capture_sources`, `decode_sources` and
`project_sources` first. Bind the generic `business_workspace` composition with:

- `catalogue`: the captured `sql-source/source/endpoint.json` record.
- `selection`: your native selection-record collection. For the initial sample,
  record `model` has query `catalog`; record `orders` has query `orders`,
  argument/after text `"0"` and argument/limit text `"10"`.

Then use **Flow examples → Publish and invoke example** with name
`business_workspace`, a new Nenex destination and those bindings. Leave writer
blank for document publication. Query names and bounds belong to these records;
the flow has no WWI-specific query selection. Each component can also be invoked
alone with the `retain_result` writer and its results consumed through cells.
See [composition and invocation](../../README.md#compose-incoming-data-flows).
This does not launch SQL or configure credentials.

For a custom single-query ingestion, create **Live structured data ingestion**, publish `live_data`, bind
named URL inputs from `sql-source`'s endpoint catalogue, then attach it with the
existing Nenex writer and a new destination. URL names may be `orders`, `order`,
or `schema`; supply each query's required parameters. Inspect the decoded step's
cells and retained work. Change a URL revision to fetch again. Binding a URL alone
is not a promise of continuous SQL change detection.

The model can consume these captures through existing source bindings and
interactive investigation flows. Treat database descriptions and free text as
untrusted evidence, not instructions. Orders use historical sample dates; any
claim of lateness or fulfillment readiness needs an explicit business date and
the relevant stored-procedure rules, not a guess based on field names.

Official sample and backup:
https://github.com/microsoft/sql-server-samples/tree/master/samples/databases/wide-world-importers
https://github.com/microsoft/sql-server-samples/releases/tag/wide-world-importers-v1.0
