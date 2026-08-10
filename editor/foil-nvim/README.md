# foil-nvim

The buddy, in the buffer: a Neovim client for the wire port
(doc/buddy-wire.md) served by the resident `x/repl` session.  The
editor, the terminal repl, and the `/ns` explorer share one live
image; everything here is namespace traffic against it.

- **compile on save** — `:w` resyncs the module; compiler errors land
  as located `vim.diagnostic` entries, the report in the echo area
- **eval** — `<leader>fe` on a line or visual selection: `value : type`
  in a float (`:FoilEval (add 2 3)` works too)
- **hover** — `K`: kind, type, and the entry's lore head
- **jump to definition** — `gd` (the mirror's `['defline]` slot)
- **inspect** — `<leader>fi` / `:FoilInspect [name]`: the whole entry
  record — type, doc, refs, source
- **who-calls** — `<leader>fu` / `:FoilCalledBy` / `:FoilCalls` into
  the quickfix list
- **completion** — omnifunc (`<C-x><C-o>`) over the module's entries
- **repl** — `<leader>fr` / `:FoilRepl`: a prompt buffer with
  repl variables (client-side prelude, so they survive resyncs),
  `:m` focus switching, `:c` / `:t` passthrough

## install

Needs Neovim 0.9+.  Install `editor/foil-vim` too (filetype, syntax,
indent — this plugin only speaks the wire).

lazy.nvim:

```lua
{ dir = "~/dev/reaver/editor/foil-vim" },
{ dir = "~/dev/reaver/editor/foil-nvim",
  opts = { port = 8679 } },  -- opts -> require("foil").setup(...)
```

Or manually: add both directories to `runtimepath` and call
`require("foil").setup({})`.

## run

```sh
x/repl                 # http 8090, poke 8678, wire 8679
```

then `:FoilConnect` to check the wire.  `setup` options:

```lua
require("foil").setup({
  host = "127.0.0.1",
  port = 8679,
  compile_on_save = true,
  keymaps = true,        -- the buffer-local maps listed above
})
```

The module name for a buffer is derived from its path
(`.../foil/<mod>.foil`, nested names included); set `b:foil_module`
to override.
