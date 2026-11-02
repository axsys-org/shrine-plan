# Foil, Grove and Goo syntax for Vim / Neovim

Filetypes, syntax highlighting and conservative indentation for `.foil`,
`.grove` and `.goo` files.

Foil support includes slash-qualified names, `;/` sibling and `#/` child
references, relative constructors (`.none`, `./some`), compact constructors
(`+ ready :`), generics, method calls, strings with doubled quotes, and quips.
Quoted tack paths such as `'@/y/%/cards` remain data; `%/` is no longer a
Foil declaration anchor.

Grove adds named and quoted-path declarations, `@type`, `@slot`, `@role`,
`@action`, `@norm`, `@sewn`, `@tree`, `@view`, `@pane`, `#import`, metadata
and relation directives, `get :`, and embedded Foil/Goo expressions.
Standalone Goo also highlights `%slot` references.

All three filetypes use two spaces and `'` line comments. Indentation follows
the previous line, adding one level after a bare Foil `+ name` or Grove
`name =` header. It preserves manual alignment for Rex expressions and does
not try to reformat whole files.

## Install

Add this directory to your plugin manager, or copy its `ftdetect/`,
`ftplugin/`, `syntax/`, and `indent/` directories into `~/.vim/` (Vim) or
`~/.config/nvim/` (Neovim). Enable `filetype plugin indent on` and `syntax on`.

Neovim users can also install [foil-nvim](../foil-nvim/) for local declaration
navigation and completion. See `samples/example.foil` and
`samples/example.grove` for highlighting examples.
