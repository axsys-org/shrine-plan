# The compile buddy

The forge for a terminal: one resident session next to your editor that
is a **compiler** (recompiles what changed, on demand or on save), a
**repl** (bare expressions evaluate against the focused module's live
subject), and a **test harness** (doctests run on every resync and
report inline). Same image bundles as the forge and the CLI — one
compiler, three faces.

```
x/buddy            # boots, compiles every module in parallel actors,
                   # runs the doctests, drops you at a prompt
x/buddy 9001       # custom poke port
```

```
bst> t = (bst/duo[nat] 1 10 2 20)
t : bst = ...
bst> (bst/got[nat] 2 0 t)
value: 20
type:  nat
bst>                       ← plain enter = resync changed modules
bst: compiled  7/7 doctests pass
bst> :m demo
demo> (point/x fst)
value: 3
```

## Commands

```
<expr>        evaluate against the focused module
name = expr   bind a repl variable (usable in later expressions)
:vars         list bound variables
<enter>       resync: recompile changed modules, run their doctests
:m <mod>      switch focus
:ls           entries of the focused module (with lore heads)
:s <dotted>   inspect one entry (type, lore+doctests, refs, law, source)
:r <dotted>   who-calls / called-by
:t            run every doctest in the focused module
:h            help
:q            quit (ctrl-d works too)
```

## Editor wiring: resync on save

The buddy listens on a poke port (default 8678); any connection means
"something was saved" and triggers the same resync as plain enter —
recompile changed modules in parallel actors, run their doctests, show
located diagnostics for anything that broke. In vim:

```vim
autocmd BufWritePost *.foil silent! call system('nc -w1 localhost 8678 < /dev/null &')
```

`:w` in vim, and the terminal next to it answers with green or red
before your eyes move. Change detection is by source bytes (this
environment's `Stamp` returns 0), so pokes on unchanged files are free
("up to date").

## Shape

`buddy.rvr`. The step function is pure over the forge state —
`(buddy-step b line) → [b' rows quit?]` — which is how `buddy-tests.rvr`
drives it. The resident loop is three actors: a stdin pump, a poke-port
pump (`Listen`/`Accept`), and the main loop `Recv`ing from both — the
select-shaped composition the actor runtime makes natural. Resync
compiles changed modules one-future-per-module (`async-all-deep
load-bundle`), the same parallel warmup the forge's `par` boot uses.

Browser commands (`:ls` `:s` `:r` `:t`) are the forge-cli handlers,
threaded on the buddy's state. Evaluation is the forge's `eval-text`:
elaborate → lower → compile → run, errors as located diagnostics.

Repl variables are grafted onto the focused subject at each eval as
FFI entries (a runtime value with its inferred type), so bare names
resolve exactly like sibling module declarations, they can reference
each other, and they survive resyncs — the graft happens against
whatever bundle is current. A failed binding leaves the variables
untouched.
