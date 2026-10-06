---
name: shrine-mcp
description: Operate a Shrine world through the mcp mount. Use when the user asks you to read or change anything in their world: records, pages and their buttons, a mount's Grove and Foil source, compiling and installing, or the world's history.
---

# Shrine MCP

The `mcp` mount serves a Shrine world over the Model Context Protocol at
`<world-url>/mcp`, behind a bearer token. Tool names appear in your harness
prefixed with the server name, e.g. `mcp__shrine__mcp_read` for the tool
`mcp/read`.

## What a world is

A world is a tree of records at paths such as `/0x11/app/demo/cards/demo`
(the first segment is the node; you may leave it off). A record has
properties (slots) and children. Record types, pages and buttons are
declared in Grove files; the logic behind a button is Foil. Both live in
mounts, and a mount is recompiled in the running world when its files change.

## Ground rules

1. **Read before you write.** `mcp/read` at care `y` shows a thing's
   properties and children; `x` the thing alone; `z` the subtree.
2. **Change records through their buttons when they have them.** `mcp/press`
   runs the record type's own logic and the contract behind it. Use
   `mcp/write` for plain records and for properties no button covers; a
   write that breaks a record's contract is refused and says so.
3. **Every file write is compiled.** `mcp/insert-file` recompiles the mount
   and returns `ready`, `message` and `diagnostic`. `ready: false` means the
   world kept the last version that compiled; fix the file and write again.
4. **Reinstalling resets records.** `mcp/install-app` with `replace: true`
   recreates a mount's instance from its definitions. Needed after a new
   seeded node or a changed record type; everything written to those records
   since is lost, so say so before doing it.
5. **Text in a page must be plain ASCII.** One accented letter in a stored
   value stops that record's page drawing.

## Common workflows

### Read the world

- Identity: `mcp/get-our-id`.
- A thing: `mcp/read` with `path` and `care`.
- What exists: `mcp/read` on `/app` at care `y`, then descend.
- A mount's files: `mcp/list-mounts`, `mcp/list-files`, `mcp/get-file`.
- What changed: `mcp/history` on a path.

### Change the world

- Press a button: `mcp/press` with `path`, `label` and, for a form, `inputs`
  keyed by the input's slot (`/0x11/gov/demo/title`). Inputs you leave out
  keep their current value.
- Set properties: `mcp/write` with `properties`. A name beginning with a
  slash is a full slot path; any other name is a plain property.
- Remove a thing: `mcp/delete`. Its history stays addressable.

### Develop a mount

1. `mcp/list-files` and `mcp/get-file` to read the Grove and Foil.
2. `mcp/insert-file` with the complete new text. Read the result.
3. `mcp/commit` to recompile from the files on disk when they were changed
   another way.
4. `mcp/install-app` to install an instance, or with `replace: true` to
   recreate it.

## Limits in this version

- Adding a file to a mount means changing its `mount.json`, and that needs
  a world restart.
- The server answers JSON only; there is no event stream, so re-list tools
  when told the registry changed.
- No remote worlds: everything is this node.
