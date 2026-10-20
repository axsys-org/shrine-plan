# Setup

Clone, check out the branch, tell your coding agent "read SETUP.md and set
this up." It does the rest; it may ask you to restart the app once. Then
open the live page link it gives you and start talking.

For the coding agent reading this after a clone, when the person says
"read SETUP.md and set this up". Three steps; ask the person only when
you have to, which is usually never.

What you cannot guess:

- Nix must be installed. `x/setup` enters its own Nix shell and brings
  everything else; nothing is set by hand.
- The first boot builds the runtime and the browser bundles. It takes
  several minutes, once; later boots take about a minute, and a kept world
  resumes in seconds.
- One world per machine. A world holds its namespace in memory, a loaded
  one takes a gigabyte or more, and two at once have crashed a laptop.
- `ask` cells need a model: an `ask` hand with an OpenAI-compatible
  endpoint (see step 1). Without it everything else works and an ask stays
  asking.

## 1. Run x/setup

```bash
python3 x/setup --world ~/worlds/team
```

It boots the world kept in that directory with the `mcp`, `probe` and
`explorer` mounts and a `clock` hand, waits for the foot, then prints the
world URL, the MCP URL, the live page link and the skill path, and stays
attached; Ctrl-C tears the world and its hands down. It notes the world's
directory and port in `.shrine.json` in the checkout, and `python3 x/setup`
with no arguments resumes that world in seconds with every record, cell and
case it had. Run it in a terminal of its own, not in the foreground of this
session.

`--hand` names a hand and the world keeps it, on its first boot or any
later one: `--hand "ask --model <name> --endpoint <chat completions url>"`
adds the model hand (`OPENAI_API_KEY` or `OPENROUTER_API_KEY` in the
environment is sent as a bearer), `--hand inbox` the one that wakes an
agent when a note lands for it (its plugs are records, see `hands.md`);
`--port N` picks the port of a new world (default 8300).

## 2. Connect your app, load the skill

Add the MCP URL (`http://127.0.0.1:8300/mcp`, HTTP, local only, no
credential) the way your app adds an HTTP MCP server. It serves four
tools: `mcp/read`, `mcp/write`, `mcp/history`, `mcp/apply`.

Load the three skill pages the way your app loads instructions:
`extras/mounts/mcp/skills/shrine-mcp/SKILL.md` (the one form of each
thing you use most), `knobs.md` (every knob) and `qa.md` (QA mode). Link
the folder, or point your instructions file at it.

If either takes a restart of your app to pick up, say so and stop; the
person restarts and says "continue".

## 3. Open the live page

`http://127.0.0.1:8300/live?views=/0x11/user/<folder>` shows a folder's
cells with their current answers and every write as it lands. Open it in
the person's browser when you start and again when the folder you work in
changes; with no browser, give the link on its own line.

That is the setup. `DEMO.md` beside this page is the ten-minute walk
through using it.

## By hand

What `x/setup` does, for a person doing it without it.

Boot, from the checkout with Nix on the PATH:

```bash
python3 x/eden --mount mcp --mount probe --mount explorer --extras-root $PWD/extras --port 8300 --world ~/worlds/team --hand "clock --timezone UTC"
```

The world is up when it prints its line:

```
Eden: http://127.0.0.1:8300; mounts: mcp, probe, explorer; world: /Users/you/worlds/team; hands: clock
```

Without `--world` the world lives in a temporary directory and is gone with
its process; without `explorer` it boots in under a minute and needs no
Node, and there is no live page. `--hand` names a hand (`clock`, `watch`,
`export`, `import`, `ask`; `extras/mounts/mcp/hands/hands.md` says what
each does and how to write one); the launcher starts each after the foot
listens, as its own process with its log at `DIR/hands/<name>.log`, and
stops it at teardown. A world runs the hands its `world.json` names and no
others, which is the first thing to check when an `ask` never answers.
Each hand's config is a record under `/0x11/agent/hands/<name>`.

Connect: Claude Code takes `claude mcp add --transport http shrine
http://127.0.0.1:8300/mcp`; any JSON-RPC client takes the URL, and a
`tools/list` call shows the tools.

The skill: `mkdir -p .claude/skills && ln -s
"$PWD/extras/mounts/mcp/skills/shrine-mcp" .claude/skills/shrine-mcp` for
Claude Code; any other tool takes `SKILL.md` in its instructions and
`knobs.md` when it needs a knob.

Agents: every write carries `who`; give each agent its own name and
history can be filtered by it. An agent keeps its plan, scratch and `seen`
epoch under `/0x11/agent/<name>` and wakes with `history after <seen> with
x`. Several agents in one world are fine: a write is one event, admitted
whole or refused whole, and a cell is computed on read. The launcher writes
`/agent/launcher/world` (`kept`, `directory`, `mounts`) at every boot, so
an agent can ask which kind of world it is in.

Stop a world with Ctrl-C or SIGTERM to the launcher, which takes the
runtime and the hands down with it; a kill of the runtime itself loses
nothing admitted before it.

A resume runs the mounts from the checkout: on every restart a kept world
scans each mount again, publishes what changed and serves the new routes
and files over the records as they were saved, so a code change reaches a
kept world on its next restart. A changed `mount.json` needs a fresh
world.
