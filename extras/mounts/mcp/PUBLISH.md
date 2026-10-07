# Publishing tools from an app

An app publishes a tool by seeding a record under its instance at
`/app/<app>/mcp/<name>`. The MCP server lists it as `<app>/<name>` and runs
it through one of its own built-ins. No code runs in the publishing app: a
published tool names a thing, a button or a set of properties.

| Slot | Meaning |
|---|---|
| `lede` | The tool's description, shown to the model. |
| `tool_kind` | `read`, `press` or `write`: the built-in that runs it; or `foil`: a published function is run. |
| `tool_target` | The path acted on. `{argument}` is filled from the call. For `foil`: `module/entry`, a function `\ args=row[[name=str value=str]] ^ str` answering JSON text. |
| `tool_label` | For `press`: the button's label. May also hold `{argument}`. |
| `tool_params` | `name: description; name: description`. Every parameter is text and required. |

Arguments named in `tool_target` or `tool_label` fill those holes. The
remaining arguments are the press's inputs or the write's properties; a
property name beginning with a slash is a full slot path (`/sys/lede`).

In Grove, declare the four slots once and seed the records:

```
tool_kind =
  @slot

"/mcp/grade" =
  @tree
  lede: "Grade a review card: Again, Hard, Good or Easy."
  %/tool_kind: "press"
  %/tool_target: "/app/demo/cards/{card}"
  %/tool_label: "{grade}"
  %/tool_params: "card: The card's name, such as demo; grade: Again, Hard, Good or Easy"
```

`extras/mounts/grove-dev/demo.grove` carries three: `demo/grade` (press),
`demo/show_card` (read) and `demo/add_note` (write).

The server imports published tools when it starts and whenever
`mcp/import-tools` is called; call it after `mcp/install-app` or a change
to an app's `/mcp` records, then list the tools again. Importing replaces
an app's earlier entries, so a removed record disappears from the list.

The Urbit convention this replaces: an agent publishes tool definitions at
`/x/mcp/*` scry paths and handles each call by poke. Here the definition is
a record like any other, and the call is one of the server's own reads,
presses or writes, so the app's contracts and buttons stay in charge.
