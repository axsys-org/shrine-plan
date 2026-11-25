# Shrine Doom — terminal edition

A native Foil/PLAN adaptation of [garrytan/bel-doom](https://github.com/garrytan/bel-doom),
using its extracted Freedoom E1M1 WAD. The WAD loader, integer math, BSP traversal,
texturing, sprites, collision, player, enemies, doors, lifts, pickups and combat
are Foil. Python is only the terminal device: keys, pacing, palette conversion,
ANSI half blocks, and optional frame export. There is no Bel interpreter,
JavaScript engine, browser, or game-specific native jet.

From the repository root:

```sh
nix develop .#eden --command x/doom
# Or, with the runtime already available:
WISP=/path/to/wisp x/doom
```

Requires Python 3, Wisp, and a truecolor terminal on macOS or Linux. The default
resolution is 96×60; `--width 64 --height 40` reduces render cost. The launcher
uses the same compiler staging as `x/check`, copies sources to a disposable
workspace, and compiles against Shrine's actual system publication. It does
not modify the existing `snap/` or start Eden. P6 is installed by default, as in
Eden; `--compiler none` selects the boot compiler for comparison.

| Keys | Action |
| --- | --- |
| W/S or up/down | Forward/back |
| A/D or left/right | Turn |
| Q/E | Strafe |
| F | Fire pistol |
| Space, U, Enter | Use a door/switch; respawn after death |
| R | Toggle running |
| Shift + movement letter | Run temporarily |
| N | Restart level |
| Esc, Ctrl-C, Ctrl-D | Quit |

Terminals do not report key releases, so movement uses short key-hold windows.
Resize the terminal at any time. Raw mode, cursor visibility and the alternate
screen are restored on normal exit, exceptions and Ctrl-C.

## Replays and verification

```sh
WISP=/path/to/wisp extras/x/check --mount doom
python3 extras/mounts/doom/test_terminal.py
WISP=/path/to/wisp x/doom --headless --frames 16 --keys wf \
  --width 64 --height 40 --ppm /tmp/doom.ppm --state /tmp/doom.json
```

`--state` records the HUD, frame SHA-256, and measured frame times.
`--profile /tmp/doom-profile.json` records separate native simulation, visibility,
raster, packing and write timings, with warm median/p95 summaries and every
frame hash. `--renderer reference` selects the original ray/BSP renderer for
comparison; the projected span renderer is the default. See
[PERFORMANCE.md](PERFORMANCE.md) for reproducible benchmarks and runtime-primop
recommendations. Replay a JSON
array such as `[{"keys":"w", "tics":10}, {"keys":"af", "tics":20}]` with
`--script route.json`. The included `demo.json` is the first 220 tics of the
reference route; try `x/doom --script extras/mounts/doom/demo.json`. Inputs advance exactly one tic per frame; slow frames
slow the simulation rather than dropping inputs. Interactive pacing caps at
35 tics/s; this implementation is not yet a full-speed Doom engine. Startup takes approximately 13–15 seconds on the development machine.
Current warm measurements and their exact methodology are recorded in
[PERFORMANCE.md](PERFORMANCE.md); they are development measurements, not
performance guarantees.

A non-TTY invocation defaults to one frame and emits no ANSI drawing.
`--frames` bounds a run, `--ppm` exports the final Foil-rendered image, and
`--keep-work` retains the staged source and engine log. Failures retain their
log automatically. `--wad` accepts a compatible single-map E1M1 WAD; arbitrary
IWADs and map selection are not supported.

Tests cover signed arithmetic, the wire format, ray intersections, BSP sector
lookup, player collision, shooting and cooldown, health/armor, pickups, barrel
chain explosions, doors, lifts, exits, respawn, deterministic replay, truncated
WAD rejection, fragmented socket reads, terminal escape sequences, profiler
units/percentiles, projected near-plane and portal clipping, opaque coverage,
masked textures, sprite depth, plane sampling and sky. Textured-wall, portal and
masked-wall fixtures also compare both native renderers byte for byte.

## Engine boundaries

- `math.foil`: zigzag signed integers and a fixed 360-entry sine table. Ray
  directions use 1024ths; geometry is integer map units.
- `wad.foil`: directory/lumps, patch posts, composite textures, sectors, lines,
  segs, subsectors, BSP, things, palette and COLORMAP. The supplied WAD omits
  BLOCKMAP, so a conservative 128-unit collision grid is built in Foil.
- `game.foil`: immutable `dg/world`, `dg/new`, and `dg/step world keys`. Enemy
  sight follows the BSP; local collision uses the grid. The random index is
  part of the world, so identical inputs are deterministic.
- `render.foil`: shared art/camera/sprite helpers and the retained ray-renderer
  reference (`dr/render`).
- `spans.foil`: the default `ds/render world art width height`. One front-to-back
  BSP pass, bounding-box and opaque-span culling, clipped wall runs, shared plane
  scanlines, prepared sprite columns and cached weapon overlays. Both renderers
  return column-major palette buffers.
- `main.foil`: native file/socket I/O and the terminal protocol.
- `boot.rvr`: the existing Foil compiler/publication bootstrap. No gameplay.
- `terminal.py`: the device adapter. No map parsing, geometry, AI, collision,
  damage or pixel selection.

A localhost connection carries a 768-byte palette once. The host then sends a
little-endian u16 key mask (bits 0–8 = `wsadqefur`, 512 = restart, 1024 = quit).
Each input returns ten little-endian u32 values (tic, health, armor, ammo,
kills, items, flags, zigzag x, zigzag y, angle in degrees), followed by `width * height` column-major palette bytes.
Flags 1 and 2 mean dead and level complete. Native byte bars preserve trailing
zero pixels; commands are assembled across partial socket reads.

This is a playable first-level adaptation, not binary-compatible Doom. It has
a pistol only, simplified enemy chase/instant attacks, static directional
sprites and corpses, integer movement, and a text HUD. Sound, save games,
network play, additional levels/weapons, full actor animation, locked-key
rules and the reference's full HUD are not implemented. No browser frontend
or live Shrine namespace session is installed by the CLI.

## Attribution

Reference: `garrytan/bel-doom` at `18c55084719901903c31a4f7c34dca3bbc3df84d`, MIT (see `LICENSE-bel-doom`). The implementation
uses its pure world/step/render structure, WAD formats, map conventions, and
E1M1 content as a reference; it is not a wrapper around its interpreter.
`e1m1.wad` contains Freedoom 0.13.0 content under its BSD license (see
`COPYING-freedoom.txt`). Doom is by id Software. No proprietary Doom IWAD is
included. The reference's `bel.bel` is not included.
