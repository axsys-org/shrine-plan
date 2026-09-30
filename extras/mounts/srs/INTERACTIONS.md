# Interactive SRS rehearsal

Launch the reference Grove and explorer:

```sh
x/eden --mount srs --mount debugger --port 8161
```

Open `/views/0x11/app/srs/cards/demo` (substitute the node if using `--node`).
The explorer initially shows every matching view. In the front presentation,
**Show** switches that presentation to the back. **Again**, **Hard**, **Good**,
and **Easy** run the published `finish` action and refresh the previews.
There is no automatic transition after grading. The edit presentation has an
explicit **Save** button for the prompt and response.

Inspect the concrete card in `/ns/0x11/app/srs/cards/demo` to see the new due
time and interval. Intervals are milliseconds; timestamps are Apollo `dm`
ticks (1024 per second). Again schedules one minute from the server's clock.

Goo interaction bindings are resolved from the published view on the server.
The browser sends the control identity, edited text, and object/publication
versions. Enum arguments are compiled nominal values, not browser strings.
`become` selects exactly one matching role/slot view and affects its preview
only. A group supplies `on`, `action`, and `myth`; a button adds its arguments.
`/sys/now = .provider` uses the server clock. `.input(...)` and `.poke` currently
support text fields. Unsupported expressions and providers are reported.

Stale controls and changed publications are rejected. Refresh the page before
retrying; an error does not discard entered text. Competing views and arbitrary
inverse writes to transformed records remain unsupported. The SRS `/next`
declaration is a `weft`/`tack` binding; the explorer does not yet expose that
binding as queue children. Use the concrete `/cards/demo` object for this
interactive rehearsal.

Verified with the browser: Show, text Save, Again, and Good in the development
fixture. HTTP replay of a successful Save is rejected with 409. The action
and backend compiler suites and 169 native regression checks pass.
