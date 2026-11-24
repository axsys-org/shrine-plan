# Foil / Grove for Neovim

Local editing support for the current Foil and Grove sources, with optional
compiler wire integration. Requires Neovim 0.9+.

Install **both** `editor/foil-vim` (filetypes, syntax, indentation) and
`editor/foil-nvim` (Lua navigation and completion). For example, with lazy.nvim:

```lua
{ dir = "~/dev/shrine-perf/editor/foil-vim" },
{ dir = "~/dev/shrine-perf/editor/foil-nvim",
  opts = { keymaps = true } },
```

Or add both directories to `runtimepath`, enable `filetype plugin indent on`
and `syntax on`, and call `require("foil").setup({})`.

## Local editing

- `.foil`: current Rex syntax, slash-qualified names, sibling `;/` and child
  `#/` anchors, relative constructors, generics, strings and quoted path data.
- `.grove`: declarations, `@type`/`@role`/`@view`/`@pane` and other kinds,
  `#import` and metadata directives, embedded `! foil` and `! goo` expressions.
- `.goo`: standalone Goo syntax, including `%slot` references.
- Two-space indentation and `'` comments. Indentation is deliberately
  conservative: bare `+ name` and Grove `name =` headers open a level;
  compact `+ name :` constructors and `! foil` do not.

In Foil and Grove buffers, `gd` jumps to a declaration in the current buffer,
`K` and `<leader>fi` show its source, and `<C-x><C-o>` completes declaration
names. `:FoilInspect [name]` also works locally. Sibling and child anchors are
resolved against the enclosing declarations, including additive namespaces.
Completion preserves the anchor spelling you typed. Set `keymaps = false`
to use your own mappings.

This is a source index, not a compiler or language server: local navigation
covers declarations in the current buffer, including embedded Foil. It does
not resolve imported names, infer instance methods, synthesize generated
`read_str` declarations, or provide compiler diagnostics. Quoted Grove paths
are indexed by their path names. Standalone Goo gets syntax and indentation,
without declaration navigation.

## Compiler wire integration

Start a compiler service from the repository root (with `wisp` on PATH, e.g.
inside `nix develop`, or set `WISP`):

```sh
x/repl --no-repl                      # loopback port 8679
x/repl --mount chat --no-repl          # include mounted Foil modules
x/eden --mount chat --wire-port 8679   # Eden plus an editor compiler
```

`x/foil` invokes the same service. On a terminal, `x/repl` also accepts Foil
expressions and `:m MODULE`, `:c`, `:t`, `:q`. `--port` selects a different wire
port. `x/lain-dev` has been replaced by the optional Eden wire service.

The editor compiler is isolated from Eden's live namespace. Compile reads
saved source, rebuilds the requested module and its dependencies, and retains
a session cache. Source changes invalidate the session cache;
subsequent queries rebuild against the current files. Eval does not publish
its result into Eden. Grove publication still belongs to Eden's mount pipeline.

Eden's wire endpoint also accepts `mount/status`, `mount/save`, and `mount/reload`.
`x/reload-core` uses `core/reload` to replace the non-`sys` runtime and all
selected mounts together, preserving live state and rejecting failed candidates.
The CLI tools `x/save-mount` and `x/reload-mount` use these to update a selected
mount and wait for live publication. See [mount authoring tools](../../MOUNTS.md#mount-authoring-tools)
for scaffolding commands, the JSON protocol, and restart requirements.

No network requests occur by default. Opt in **before opening Foil buffers**:

```lua
require("foil").setup({
  wire_enabled = true,
  host = "127.0.0.1",
  port = 8679,
  timeout = 120000, -- milliseconds; allow longer for large initial compiles
  compile_on_save = true,
  keymaps = true,
})
```

This enables server-backed Foil hover, definition lookup and completion,
compile-on-save diagnostics, plus these commands/mappings. Compilation also
runs the native style checker from `stdlib/base` with its default rules and
the CLI's tab/trailing-whitespace checks. Findings retain their rule IDs and
error/warning levels in the separate `foil-lint` diagnostic namespace, even
when compilation succeeds. Fixing and saving clears the old findings; replies
for an older request or edited buffer are ignored.

Diagnostics read saved files. `FoilLint` checks just the saved source without
requiring its imports or declarations to typecheck. It leaves existing compiler
diagnostics alone. The TODO-gated `lapidary` and `ufcs-lift` rules remain off,
matching `x/foil-lint` defaults.

| Command | Mapping | Action |
| --- | --- | --- |
| `FoilConnect` | | Ping the configured server |
| `FoilCompile` | `<leader>fc` | Compile the saved module and dependencies |
| `FoilLint` | | Lint the saved module without typechecking it |
| `FoilDoctest` | `<leader>ft` | Run module doctests |
| `FoilEval [expression]` | `<leader>fe` (normal/visual) | Evaluate |
| `FoilInspect [name]` | `<leader>fi` | Inspect a mirror entry |
| `FoilCalls [name]` / `FoilCalledBy [name]` | `<leader>fu` (callers) | References |
| `FoilRepl` | `<leader>fr` | Open the wire REPL |

Grove always uses local editing support; it is never submitted as a Foil module.
Foil module names come from the nearest `mount.json`'s `modules` or `tests`
mapping, or from `.../foil/<module>.foil` (e.g. `stdlib/runtime`).
`b:foil_module` overrides inference. The server returns the owning source file for definition jumps, including
cross-mount references; older servers fall back to the current mount's mappings
or the current `foil/` source root.

## Checks

From the repository root:

```sh
nvim --headless -u NONE -i NONE -n -l editor/foil-nvim/tests/run.lua
```

These exercise filetype detection, syntax, indentation, anchor navigation,
completion, mount aliases, keymap cleanup and mocked wire requests. They do
not require a running server. `WISP=/path/to/wisp python3 x/foil-wire-test.py`
(or the `foil-wire` command suite in `x/check`) exercises the real compiler,
TCP protocol, edits, mounted modules, and Neovim client. Samples for visual inspection are in
`editor/foil-vim/samples/`.

The JSON wire operation `{"op":"lint","module":"stdlib/runtime"}` returns
`diags` with `module`, `line`, `col` (one-based), `source`, `rule`, `level`, and
`msg`. Compile replies include these style findings alongside compiler errors;
their `ok` continues to describe compilation success. `lint_ok` reports whether
the checker completed, independently of whether it found style violations.
