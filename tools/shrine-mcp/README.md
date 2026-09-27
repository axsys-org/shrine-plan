# Shrine v5 — native authoring

Keep ordinary coding tools. Work directly with persistent Shrine nodes, opaque slots, children, crews and real Foil forms. Optional libraries help maintain evidence and commitments; they do not prescribe an application schema.

Start a **new** v5 world using your compatible Wisp and seed:

```sh
python server.py --directory /absolute/world --wisp /absolute/wisp --seed /absolute/seed --port 8776
python viewer.py --connection /absolute/world/connection.json --port 8777
```

The server writes a private authenticated connection file. The inspector is separate at `http://127.0.0.1:8777/`. The default host is loopback. Install dependencies from `requirements.txt` into a virtual environment.

A small native example through `client.Client`:

```python
from client import Client
s = Client('/absolute/world/connection.json')
s.call('write', op='make', path='/counter', fields={'n': 1})
value = s.call('eval', expression='(add 2 3)')['value']
s.call('write', op='poke', path='/counter', fields={'native_result': value})
print(s.call('read', path='/counter'))
```

For authored behavior, compile an actual Foil module, install its exported form in a node's `form` slot, then attach a native `kook` and `cpail` through `/sys/limb` and `/sys/crew`. See `tests/fixtures.py` for a complete custom projection that uses only native operations and actual Foil. The tests exercise rebinding, children, cascades, historical values and external requests.

Optional repository participation:

```sh
python codex.py attach --connection /absolute/world/connection.json --root /absolute/repo
python codex.py install --connection /absolute/world/connection.json --root /absolute/repo
```

Use `--global-hooks` to participate from ordinary desktop/CLI work across directories; each session attaches only a compact physical source and retains its own work identity. `SubagentStop` records a completion on its original work basis without trying to deliver unsupported additional context.

The installer preserves existing hooks and prints their location. Review new hook definitions in Codex `/hooks`; installation does not change hook trust. Attach MCP using the server URL and bearer token from the private connection file. Existing software remains authoritative; outbound mutation requires explicit source configuration and authored native policy.

Read `PROTOCOL.md` for wire formats, immutable module imports, evidence scope, delivery and recovery. Read `skills/shrine-work/SKILL.md` for concise agent guidance. Native libraries are ordinary source in `src/foil/shadow_forms.foil` and `shadow_io.foil`.

## Maintained surface

| File | Role |
|---|---|
| native.py | Native owner, pinned engines/values, journal reconciliation, bounded execution |
| records.py | Lossless native references and JSON/slot transport |
| observe.py | Factual observations, artifacts and concrete physical execution |
| context.py | Rebuildable indexes and explained graph navigation |
| server.py | Nine MCP/HTTP operations, authentication and durable dispatch |
| client.py | Shared SDK |
| codex.py | Optional lifecycle adapter and repository attachment |
| viewer.py | Separate read-only inspector |

`shadow.foil` owns native headless assembly. `shadow_forms.foil` and `shadow_io.foil` are optional libraries. `shadow.rvr` connects compilation/evaluation and transports native values. `helm/exec_effects` preserves effects while `helm/exec` retains its earlier return contract.

Run product verification:

```sh
SHRINE_WISP=/absolute/wisp SHRINE_SEED=/absolute/seed python -m unittest discover -s tests -v
```

Tests use an isolated world; `SHRINE_TEST_WORLD` can retain it explicitly. No benchmark, model runner, alternative expression language or automatic migration is part of this bridge. Old worlds require their archived compatible bridge and pinned engine.
