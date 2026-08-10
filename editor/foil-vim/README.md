# foil.vim

Vim/Neovim plugin for the **foil** surface language — the rex-based,
rune-organised front-end to PLAN.

Provides:

(Static layer only — for live-image features in Neovim (eval, compile
diagnostics, hover, jump-to-definition, completion, a REPL buffer) add
`editor/foil-nvim` on top; it talks to the resident `x/repl` session
over the wire port, doc/buddy-wire.md.)

- filetype detection for `*.foil`
- syntax highlighting (runes, tags, comments, binders, member access,
  qualified names, builtins)
- comment string and `gc`-style commenting via the `'` rune
- 2-space `expandtab` defaults
- minimal indent (autoindent + a body-bump after `+ name` headers)

## install


### manual
Drop the contents of this directory into `~/.vim/` (or `~/.config/nvim/`
for Neovim). The standard layout (`ftdetect/`, `ftplugin/`, `syntax/`,
`indent/`) is auto-loaded.

```sh
cp -r ftdetect ftplugin syntax indent ~/.vim/
```


