# Library hands

Hands a host installs into a world's `hands/hands.foil` (the agent's own module), each a group under `+  hands`,
compiled live by the hands mount (`/io/fs/hands/op/rescan`) and taken up at the world's next boot. The host only
copies text from here; the behaviour is the kernel's.

- `filing.foil`: files what a gateway observed for this world (a mail read, a form sent) as the world's own
  answer at `/our/<asker>/answer/<id>`. Seed: `(hands_kit/seed 'filing "/her/<gateway>/file" "/her/<gateway>/file")`.
- `attention.foil`: the world's attention. Slots `['held …name]` hold the cursors (relative paths, space-separated)
  holding a name; each held name is hunted at care z; when one moves, its holders (and the holders of names above it) are poked `asking`.
  Seeds: `attention0 … attention15` (shards by the top segment's crc32 mod 16), each `(kooked [(pact/rel ['kook 'attention)])`.
  Measured 2026-11-09: exact fan-in; latency grows with total hunts (500 ≈ 2 s). Hunting tops only does not work: hear gets the top back, never the name beneath it that moved.
