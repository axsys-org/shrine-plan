# Shrine + Foil

This contains an implementation of Reaver, a Scheme-like language for
the PLAN ISA.  Because Reaver is implemented directly in PLAN Assembly,
any implementation of PLAN should be able to run this code.

Probably the best way to jump into Reaver dev is to look at the
stdlib, and just start extending that.  I also write up a quick manual
[here](doc/reaver.md).

Foil is documented in
[doc/getting-started.md](doc/getting-started.md),
[doc/foil-semantics.md](doc/foil-semantics.md), and the current implementation
sharp edges are documented in [PAPERCUTS.md](PAPERCUTS.md).

The [Shrine v5 bridge](tools/shrine-mcp/README.md) exposes native authoring,
observations, persistent context and the separate inspector. The
[Coursebook Canvas demo](tools/canvas-shrine/README.md) uses that bridge and
actual Foil forms to maintain coursework observations, deadline states and
local planning. Personal Canvas configuration and data are not included.

