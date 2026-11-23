# Namespace-defined context menus

Server commands below run from the Reaver root. Cargo commands and native
render artifacts refer to the separate `shrine-goo-native` checkout. Historical
validation counts are not a substitute for the current branch’s PR checks.

The generic context-menu system slots and their title/help entries are
registered by this checkout.

The native scene shell recognizes `/sys/slot/context_menu`. It hosts the returned
Goo view using the existing bound `Surface`: text, groups, inputs and actions.
There are no gematria values, commentary action names or save/reply policies in
the Rust menu host.

A record can put a `pails/p` view address in this slot. The published view must
be an ordinary `@view` with `#for ; /sys/slot/context_menu`. Its actions use the
normal Grove receiver, argument binding, publication checks and exact invocation
receipts. A missing slot falls back to the existing matching Grove `@action`
menu. A malformed slot produces a diagnostic instead of falling back silently.

An owning pane can instead advertise a contextual provider. Its projection has
`slots["/sys/slot/context_menu"] = {scope, revision}`. That scope record holds a
`shuin_menus/provider`, whose `open(scope, clicked_target, identity, state)`
returns a namespace and menu record address. This is how a reading pane captures
its accepted highlighted range without moving selection when a gloss is
right-clicked. The owning reader remains an `@pane`; the popup is an ordinary
`@view`, not another commenting topos.

`POST /shuin/menu` accepts `operation=open|read|invoke`. Opening carries a unique
identity and optional scope revision. Invocation carries the existing frozen Goo
binding and inputs. After an accepted Grove action, an optional
`/sys/menu/commit` (`shuin_menus/committer`) performs additional namespace writes
in the same transaction. If it rejects, both the Grove write and its invocation
receipt roll back. Exact accepted retries skip the continuation. The server
renders the current slot after each action, allowing a menu action to change
its own view into a form. `/sys/menu/closed` (`pails/b true`) closes the popup.
These callbacks are published namespace code, not client-supplied programs.

The reading provider lives in `shuin-chat/commentary.foil`; its menu and form
recipes live in `shuin-chat/commentary.grove`:

- Highlight source text and right-click: quotation, gematria, **Add gloss…**.
- Right-click a gloss: its source quotation, gematria, **Add gloss…**, and
  **Reply to gloss…**. Reply targets the clicked gloss, even if another is selected.
- Add/reply opens a Goo input with **Save left**, **Save right**, and **Cancel**.
  Adding from a gloss creates a separate annotation at its source range;
  replying retains that gloss as the parent.

Gematria uses standard Hebrew values (mispar hechrechi), with ordinary final
letter values and zero contribution from vowel marks, punctuation and other
scripts. The implementation is Foil. Reference checks include `שלום = 376`,
`תּוֹרָה = 611`, `ךםןףץ = 280`, and Latin text = 0. See
[Sefaria's overview of gematria methods](https://www.sefaria.org/sheets/533734?set-language-cookie=).

The popup retains its editor across reading polls. Dirty drafts, IME composition,
and unresolved requests prevent dismissal or scene/window release. Cancel is an
explicit Goo action. Requests disable editing until resolved; uncertain outcomes
retain the exact request for Retry. The menu freezes source lifetime/revision,
quote, parent and reading revision. A concurrent context/source change rejects
Save while retaining the local draft for copying or cancellation. There is no
automatic reanchoring or silent rebasing.

Current limits: 128 menu records per reading session and the existing 1,024 Goo
receipt bound per disposable world. Menu records remain inspectable under the
reading context's `menus` child. Opening, form transitions and saving use the
server; no offline fallback is implied. The legacy inline composer capability
remains available to other commentary pane recipes, but the shipped Talmud pane
no longer declares it. Japanese IME acceptance remains user-owned.

Verification command (against a disposable `--test-fixtures` server):

```sh
GOO_DISPOSABLE=1 GOO_TEST_SERVER=http://127.0.0.1:8341 \
MENU_CAPTURE="$PWD/artifacts" CC=/usr/bin/clang CXX=/usr/bin/clang++ \
cargo test --offline -p shuin-widgets --test commentary -- --ignored --test-threads=1
```

Verified on 2026-11-19: 91 offline tests across `shrine-client`, `shuin-goo` and
`shuin-widgets`; all six live commentary/menu acceptance tests; five system-slot
catalog tests. The live suite includes dropped-response retry, exact clicked
parent, both margins, stale context/source rejection, native right-click and
keyboard activation, draft/focus retention, Escape/close guards, and shell
fallback to the existing Grove action catalog. The actual 2× Vello captures are
`artifacts/Talmud-menu-native.png` and `artifacts/Talmud-menu-form-native.png`.
