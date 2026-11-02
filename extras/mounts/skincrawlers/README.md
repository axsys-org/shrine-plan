# skincrawlers

Start from the core checkout:

```sh
x/eden --terminal skincrawlers --wire-port 8679
```

`cli.foil` contains the terminal entrypoint, using `Input` and `Output`.
Try `look`, `name The Hollow`, then `look` again. `help` lists commands;
`quit` or Ctrl-D on an empty line exits with status 0.

At boot, `skincrawlers/install` instantiates the Grove definition from
`/<node>/gov/skincrawlers` at `/<node>/app/skincrawlers`. `look` asks the live
supervisor for that record with `helm/card/peek`; `name TEXT` updates its
`/sys/lede` slot through `helm/card/step` and `writ/poke`, waiting for the commit
acknowledgement. The terminal resolves the current node through a snapshot
request, so it also works with Eden's `--node` option.

The namespace owns game state. Reload publishes new definitions without
overwriting the running instance. Restarting Eden creates a fresh instance from
the Grove seed; game changes are currently in memory, not saved to Grove files.

After editing registered source files: `x/reload-mount skincrawlers`.
Manifest registration changes require an Eden restart.
Restart Eden after editing the running terminal loop; reload updates publications
but does not replace the function already reading input.
