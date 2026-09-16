# Debugger value fidelity and exact byte reads

This contract distinguishes a displayed value from the bytes held by a physical
record. A pretty-printer, ellipsis, or numeric size label is not proof of either
completeness or truncation. The frontend never infers fidelity from those strings.

## Server-rendered slot metadata

Each `sh-limb` can provide:

| Attribute | Meaning |
| --- | --- |
| `data-value-state` | `complete`, `preview`, or `opaque` |
| `data-preview-reason` | Empty for complete; otherwise `byte-limit`, `numeric-summary`, `semantic-summary`, `unsupported-representation`, or `non-text-bytes` |
| `data-value-bytes` | Canonical decimal stored-byte count, or empty when unknown |
| `data-value-preview-bytes` | Canonical decimal count represented by the byte preview, or empty when not applicable |
| `data-value-epoch` | Verified sovereign snapshot epoch, or empty when unavailable |
| `data-value-representation` | `utf8-bytes`, `natural-le-bytes`, or empty for unsupported values |
| `data-value-url` | Validated same-origin exact-read URL, or empty when unsupported |

Missing metadata on an older kernel means **unknown**, never complete. Malformed
metadata disables exact reading for that slot without dropping the supplied
value or crashing the rest of the document. Generic semantic/compiled summaries
are opaque and have no exact-read action. Physical text and natural values may
provide one; derived `/h`, `/o`, and `/x` paths cannot use a physical fallback.

Text previews stop before a split UTF-8 scalar. HTML-normalized/control or invalid
byte sequences are not advertised as complete text. Natural values have a
minimal little-endian representation; zero has zero bytes. Existing atom-backed
storage does not preserve a separate trailing-zero length, so the reader does
not invent one. HTTP cord slots can have a text preview while their stored
representation remains a natural.

## Read-only transport, version 1

`GET /debug-read/value` requires exactly five query parameters:

- `path`: canonical physical record path.
- `slot`: the canonical, opaque path-shaped slot key, not a child suffix.
- `epoch`: canonical nonnegative decimal sovereign epoch.
- `offset`: canonical nonnegative decimal byte offset.
- `limit`: canonical decimal from 1 through 65536.

Duplicate, unknown, missing, malformed, empty query components and noncanonical
addresses are rejected. Decoded identifiers are capped at 4096 bytes each and
the query at 32768 bytes. The endpoint uses correlated supervisor reads, not the
ordinary journaling/execution route. It resolves the physical record assertion
at the requested epoch; no automatic fallback to the newest value is allowed.

A successful JSON response contains exactly these version-1 fields:

```json
{
  "version": 1,
  "path": "/demo",
  "slot": "/text",
  "epoch": "2",
  "recordEpoch": "1",
  "type": "text",
  "representation": "utf8-bytes",
  "encoding": "hex",
  "total": "5",
  "offset": "0",
  "next": "2",
  "complete": false,
  "hex": "6865"
}
```

`recordEpoch` is the actual assertion epoch and may precede the requested epoch.
All numeric identities and offsets are strings, including values beyond
JavaScript's safe integer range. Hex is lowercase and even-length. Its decoded
length is exactly `min(limit, total - offset)`. `next` is the exclusive next byte
offset, or null at the end; `complete` agrees with that terminal state. An offset
equal to the total returns an empty terminal window, including for zero.

Errors use `{ "version": 1, "error": "stable_code" }`: malformed input is 400,
unsupported method 405, future epoch 409, absent record/slot 404, tombstone 410,
unsupported or derived representation 422, and offset beyond the end 416.
Stored-payload evaluation or response-serialization failures return 500 rather
than leaving a supervisor reply pending.

## Frontend and Mash responsibilities

`values.js` validates metadata, builds byte-window URLs, validates envelopes and
formats exact windows. No source HTML is inserted into the document. Every
response must match path, slot, requested epoch, representation, total, offset,
and expected length/continuation. The first accepted assertion epoch must remain
the same across later windows in the open inspector.

`value-view.js` orchestrates explicit reads and recovery. Logical windows are
4096 bytes. UTF-8 reads include up to three prefix and suffix context bytes,
but the returned logical bytes exclude context. A character belongs to the page
containing its leading byte, avoiding duplicates and replacement at boundaries.
Invalid/non-printing sequences use visibly labelled hex. Naturals always use
hex with explicit little-endian labelling. Text decoding is never a substitute
for exact raw bytes.

Only two exact reads run at once. Queued cancellation removes the request;
closing, removed slots, and foreground navigation cancel pending work. Each
read has a 20-second deadline and a 196608-byte response-body cap, including
JSON/hex overhead. Rejected status/content-type bodies are explicitly cancelled.
There is no eager read, whole-value cache, or automatic page prefetch. A failed
read retains the original preview and the last good window; retry uses the same
identity and bounds. Late replies cannot reopen closed or replaced content.

Mash `sh-pail` owns the optional `status` and `actions` slot anatomy. Its status
region is live and atomic; its controls are outside that region. The debugger
supplies the domain-specific labels and state. Native Mash buttons and
`ui-scroll-area` own focus, pointer behavior, resizing/scrolling and touch targets.
Exact reading never replaces the supplied preview. Closing restores focus after
Mash has re-enabled its native button; read completion does not steal focus.

## Limits and verification boundary

The response and formatting work are bounded. Cold history/record loading and
own-slot lookup costs are not yet proven globally bounded by this endpoint.
This does not implement general physical-child paging, bounded derived evaluation,
generic lossless structural serialization, or whole-value export.

The protected 8138 process can hot-read frontend assets but already-loaded Foil
code is not replaced that way. New metadata/transport must be tested in a
disposable runtime; no frontend build silently activates it in the user's live
namespace. See the progress log for actual verification and activation status.
