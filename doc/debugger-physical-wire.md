# Physical read wire contract — version 1

This is the bounded projection of [physical selection](debugger-physical-read.md),
not a replacement for derived views or a live-runtime migration. Work is on
`debug-prototype`; the existing port-8138 runtime must remain untouched.

## Identity and requests

`GET /debug-read/physical` accepts exactly `pathKey`, `collection`, and optional
`epoch`, `after`, `limit`. The collection is `children` or `slots`; limit is
1–40, default 40. Continuations require the captured epoch. Numbers are canonical
unsigned decimals. Query strings are bounded to 32,768 bytes; individual epoch
strings to 128 bytes. Duplicate, unknown, empty, malformed and control-bearing
parameters are rejected, not silently normalized.

Keys are **structural identities**, not display paths:

```
v1                      empty path / empty slot key
v1/ts:617070             one symbolic iota: app
v1/ts:617070/u:01        app followed by natural 1
```

Each slash-separated segment contains the exact aura tag and the minimal
little-endian byte payload in lowercase hexadecimal. All fourteen auras are
supported: dm, dr, ds, f, r, rd, rs, s, ta, ts, tu, u, w, x. Zero has an empty
payload. Nonzero payloads cannot end in a zero byte. This preserves binary,
control-bearing and non-printable keys without lexical reinterpretation.

Encoded keys are preflighted to at most 8,192 bytes **before formatting**. A
larger key produces `key_too_large`, never a clipped or skipped identity.
This is an honest transport limitation: arbitrary oversized keys still need
a future bounded opaque-handle/full-key access design before the broad release
gate is met. No fixed path-depth limit is substituted for this byte budget.

The client keeps the validated key's slash and colon literal in query values.
That alphabet contains no query delimiters, and both characters are legal in
a query. This matters for continuation: blindly percent-encoding both maximum
deep keys can exceed the query budget even though each key fits. The canonical
client encoding permits the largest accepted path and cursor together. Other
valid percent spellings are accepted only within the same raw-query budget.

Optional display spellings use a separate small preflight, a caught formatter,
valid text checks, and an exact parse round trip. `null` means there is no safe
display spelling; it does not mean the structural key is missing. Display
strings must never be used to construct continuation identities.

## Response

The version-1 JSON envelope contains only:

- `version: 1`, `resolution: "physical"`;
- `pathKey`, `displayPath`, `epoch`, `collection`, `after`, `next`, `limit`;
- `total`, `complete`, `own`, `entries`.

Epochs and counts are decimal **strings**, not floating-point JSON numbers.
Emitted counters are limited to 256 bits before decimal formatting. `next` is
the last included structural entry key; it is null exactly when complete.
The exact total belongs to the selected physical collection at that epoch.
An empty opaque slot key is valid and remains distinct from a null cursor.

Each child entry is `{key, displayKey, node}`. Its key has exactly one iota.
Each slot entry is `{key, displayKey, value}`; its key is one opaque path-shaped
record key, not a subtree. Ordering is native aura/payload order and native
lexicographic path order, never alphabetic display-string sorting.

`own` and child `node` summaries contain:

- `state`: live, tombstone or unknown;
- `recordEpoch`, `children`, `fields` (`fields` is the protocol's slot count, null without an own live record);
- `label`, `labelSource`, `help`, `helpSource`, `helpLine`;
- `kind`: namespace, record, role, action, norm, sewn, template, event, http,
  behavior or module, from fixed known marker lookups.

Labels come from `/sys/lede`, falling back to authored lore head. Help comes
from a text `/sys/help` or one nonempty entry among the first four lore body
lines. `helpLine` identifies that zero-based line; it is null for text help.
This bounded excerpt is **not the entire documentation**. No arbitrary scan
for an ideal paragraph, generic generated description, or pail formatter is
allowed. Metadata is looked up independently of the current slot page.

Text/natural value previews have `{type, encoding: "hex", hex, total, complete}`.
They contain at most 256 original little-endian bytes, retaining even invalid
UTF-8 and embedded controls. Completeness applies only to that scalar (or the
selected lore line), not a record, documentation bundle or unloaded collection.
The UI must validate before decoding, visibly distinguish truncation, and not
present these previews as the complete source value.

Actual `pails/p` references use `{type: "path", pathKey, displayPath}`. Other
unsupported pails are `{type: "opaque", reason: "unsupported_type"}`. Oversized
reference targets use opaque reason `key_too_large`. In particular a `safe`
reference is not simplified to a path because that would lose care/version.
These outcomes retain the slot's existence, not full access to its value;
bounded typed detail readers remain separate release work.

## Bounds and failure behavior

The entire success response is at most **131,072 bytes**. At most 98,304 bytes
are allocated to entry JSON including separators, leaving 32 KiB for bounded
identities and own metadata. A byte budget may shorten a page below its requested
limit. Its continuation still names the last included entry, so later entries
are neither skipped nor falsely marked complete.

The selected raw page must never be serialized into an actor message. Projection
and complete final-string forcing happen inside `physical_projection/safe_json`;
the supervisor sends only an encoded string or stable error. Malformed stored
data becomes `read_failed`, allowing later requests to recover.

The route uses numeric read correlation and bypasses ordinary namespace
task/commit/journal handling. A stale epoch is a 409 `epoch_conflict` before
index access; clients must keep already visible rows, offer an explicit fresh
read, and never silently merge different epochs. Missing records/paths are 404,
deleted records 410, derived targets or oversized keys 422, malformed queries
400. Projection failures are 500. Errors contain `{version: 1, error}`.

These byte and entry limits do not bound cold record/history pin loading,
large-key comparison cost or all derived evaluation. Projection intentionally
opens only the selected own records for fixed metadata probes, but a cold pin
can still contain a large record. Frontend DOM virtualization, bounded operation
registries, typed object readers and a safe live activation path remain separate.

An [inherited overwidth float ordering defect](debugger-ordering-limits.md) also
prevents complete comparator-cursor access for certain raw `rs`/`rd` collections.
The client rejects repeated merged keys instead of silently looping; the defect
is not fixed by the lossless codec or the byte budget. Physical traversal handles
or a separately authorized storage migration require further work.

## Client integration boundary

`debug/physical.js` owns strict request, response and continuation validation.
It must not reuse legacy journal pagination or normalize physical identities
through display-path utilities. Children and slots are separate collections;
unloaded slots cannot become an empty complete record. A future capability-gated
sidebar integration may use this adapter while preserving authored main views.
The presence of source code alone is not evidence that an older live runtime
supports the route. No probing or restarting the user's live session is implied.

See the progress log for verified tests and current integration status.
