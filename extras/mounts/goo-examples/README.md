# Goo example gallery

`examples.grove` is one module containing all 369 legacy `.goo` fixtures from
`../goo/examples`. It installs 169 objects under `/app/examples`. Each `g001`–
`g100` family has three views on the same object; the other fixtures have one.
Filename hyphens become underscores in Grove namespace identifiers.
Every family has its own required marker slot and role, so unrelated views do
not match its object. These are static fixture presentations, with their literal
sample content retained in the views.

Run alongside the SRS demo:

```sh
x/eden --mount goo-examples --mount srs --port 8137
```

The first publication of this large module can take several minutes.

Open `http://127.0.0.1:8137/views/0x11/app/examples`, select an object, and use
Parent to return to the gallery. The module template is `/gov/examples`.

Regenerate after changing or adding original examples:

```sh
python3 extras/mounts/goo-examples/generate.py
python3 extras/mounts/goo-examples/generate.py --check
```

The generator parses the legacy call/block syntax, including doubled Rex quotes
and `escaped(...)` payloads. It removes outer parentheses, formats the calls for
Grove's Goo frontend, converts `%role` to an explicit v2 role string, and turns
legacy `optional` annotations into `opt(rank)` subtrees. Other configuration
fields and compound boundaries remain intact. Hard line breaks and tabs remain
escaped payloads and are decoded by the binding bridge.

## Deliberate adaptations

- The v2 renderer measures ASCII only. Common typography becomes ASCII
  punctuation, accented Latin letters lose their accents, and remaining Unicode
  runs become `[Unicode]`. The 50 affected fixtures and every original/adapted
  string are recorded in `adaptations.json`; original examples are untouched.
- This is a gallery of compositions, not a reproduction of the adversarial test
  harness. All views use the namespace preview's 720px width, scale 1, LTR layout,
  and full optional budget. Original width lists, budgets, direction, text scale,
  and hidden paths are retained in the manifest but are not applied. Thus a case
  titled “vanishing root” need not vanish here.
- Controls remain disabled previews. No sample action executes and no input saves.
- Each view gets its own `/demo/goo/views/<normalized-source-name>` slot, so the three variants
  never compete for a slot. Missing-view reflection and precedence are unchanged.
- The bridge supplies its usual outer column root and deterministic preview IDs.

The HTTP asset path now uses byte-preserving responses, so bundled TTF fonts
retain trailing zero bytes and load without falling back to a different font.

## Validation

`extras/x/check --mount goo-examples` checks the mount interfaces and renderer
suites. `x/eden --mount goo-examples --check` additionally boots the namespace and
runs `host.py`, which requests every object and requires all 369 previews to
render with no per-view errors. `generate.py --check` detects stale output.
