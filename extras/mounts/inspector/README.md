# Native inspector

Mount `inspector` explicitly to serve `/live`. It adds a read-only namespace,
cell, overlay and history inspector over the existing MCP transport. It depends
on `explorer` for the shared presentation assets and on `mcp` for native reads.
Goo and Nenex do not acquire an MCP dependency just to render documents.

`/live?views=/0x11/app/nenex/w` inspects a subtree. `/live?at=/0x11/app/nenex/w/home`
opens one record. Cell results and contexts use native `/x` and `/c/x`; historical
references and MCP history keep their existing native meanings. Optional graph
overlays are read when installed; inspection never creates or rebinds a cell.

This inspector has no chat, task queue, workspace mutation or cursor-writing
interface. Agent work is invoked through the existing shared native operations,
Goo controls and explicitly selected providers. Direct MCP read/write/history/apply
remain available through the separately mounted MCP service.

Run `node --test extras/mounts/inspector/tests/goo-live.test.cjs` for its adapter
and renderer checks. After editing its CSS or JavaScript, run
`python extras/mounts/inspector/version-assets.py`; the mount's host check verifies
that the served assets match the page's hashes.
