# Setup: a world, an agent, a browser

Six steps from a clone to an agent working in a world you can watch. Nothing
here needs more than Nix, Python 3 and the AI tool you already use.

## 1. Boot a world

From the checkout, with Nix on the PATH:

```bash
python3 x/eden --mount mcp --mount probe --mount explorer --extras-root $PWD/extras --port 8300
```

`x/eden` enters its own Nix shell and brings the runtime; you do not set
`WISP` or anything else. The first boot with `explorer` builds the browser
bundles and takes a few minutes; later boots take about a minute. Without the
live page, `--mount mcp --mount probe` boots in under a minute and needs no
Node. The world is up when it prints its URL:

```
Eden: http://127.0.0.1:8300; mounts: mcp, probe, explorer
```

Run one world at a time on a machine. A world is a process that holds its
namespace in memory: a loaded one takes a gigabyte or more, and two at once
have crashed a laptop.

## 2. Connect your tool

The MCP endpoint is `http://127.0.0.1:8300/mcp`, local only, no credential.
Four tools: `mcp/read`, `mcp/write`, `mcp/history`, `mcp/apply`.

Claude Code, from the checkout:

```bash
claude mcp add --transport http shrine http://127.0.0.1:8300/mcp
```

Claude Desktop (the Code tab): Settings, MCP servers, add an HTTP server named
`shrine` at that URL. Any other client that speaks JSON-RPC over HTTP takes
the same URL; a `tools/list` call shows the four tools and their descriptions.

## 3. Give the agent the skill

The skill is three pages under `extras/mounts/mcp/skills/shrine-mcp`:
`SKILL.md` (the one form of each thing you use most), `knobs.md` (every knob)
and `qa.md` (QA mode).

Claude Code: link it into the project's skills folder and it loads on demand:

```bash
mkdir -p .claude/skills && ln -s "$PWD/extras/mounts/mcp/skills/shrine-mcp" .claude/skills/shrine-mcp
```

Any other tool: paste `SKILL.md` into the system prompt, and `knobs.md` when
the agent asks for a knob it does not have. The pages are plain Markdown and
stand on their own.

## 4. The live page

`http://127.0.0.1:8300/live?views=/0x11/user/<folder>` shows a folder's cells
with their current answers and every write as it lands, over the world's
stream. The agent opens it in your browser when it starts and again when the
folder it works in changes, closing the old tab; if its tool has no browser,
it gives you the link on its own line. A green chip in the page header
appears when an agent keeps a QA tree; a click opens that view, back returns.

## 5. The ask hand, when a cell needs a model

Formulas run in the world. An `ask` cell is answered by a hand, a process you
start beside the world:

```bash
OPENAI_API_KEY=... python3 extras/mounts/mcp/hands/ask.py http://127.0.0.1:8300 --model <name> --endpoint <chat completions url>
```

`--fake` answers deterministically without a model, for a try. The hand
follows the stream, answers every ask that is pending (including those
written before it started) and writes each answer as `<cell>/result`. Its
model and endpoint can also live in the world at `/0x11/agent/hands/ask`.

## 6. Sessions, more than one agent, and what survives

Every write carries `who`; give each agent its own name and history can be
filtered by it. An agent keeps its plan, scratch and `seen` epoch under
`/0x11/agent/<name>` and wakes with `history after <seen> with x`. Several
agents in one world are fine: a write is one event, admitted whole or refused
whole, and a cell is computed on read.

A world lives as long as its process. A new boot is a new world: the standard
cells and the mounts' seeds are there, your records are not. Until a world is
proven to keep its records across a reboot, keep what you would not want to
retype as a batch you can write again (one `records` list is one event), and
mirror anything you must not lose, such as a QA tree's bugs and score, to a
file at the end of a stretch. `tests/perf.py` and `tests/product.py` show
the seeding shape.

## Check it

With no world up, the compile checks and the Foil suites:

```bash
bash x/foil-check --node 0x11 lain_peek weft_std http_foot
python3 extras/x/check --mount mcp --contracts-only
bash x/check foil:tests/cells
```

Then one fresh world and the tests against it, in order: `safety`, `stream`,
`ask`, `library`, `product`, `signature` (the oracle, one seed), each as

```bash
python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/product.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
```

The walkthrough in `DEMO.md` is the ten-minute version of using it.
