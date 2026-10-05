# Root recovery checkpoint

The October 3 live-use failure is recorded in the development world's
`sequential-use-receipt.json`. v21 stopped at the 1 GiB pin guard. It remains
unchanged, including its full journal and pinned engine.

`x/recover_silo_root.c` is an offline recovery utility, linked against the
preserved engine's Enki libraries. It opens the source read-only, checks an
explicit expected root, walks native Silo subpin references under size/count
bounds, and writes only into a new, exclusive destination. It verifies every
stream's SHA-256 and length, commits the identical root through Enki's native
batch API, closes the store, reopens it read-only, and rechecks every stream.
It does not evaluate programs, reinterpret records, change refs, or rewrite the
source. Run only against a stopped source owner. This is not a production
in-place garbage collector or a history-retention policy.

Historical roots stay in the source world. The recovery destination starts its
own root journal; its receipt points back to the original history. A separate
LMDB dump/load restored and compared the 45 derived-cache entries for the same
engine. The original failed empty destination was retained as `snap-incomplete`.

Observed result: 35,609 reachable objects / 423,442,576 bytes, identical root
`359dcd12c5bbf2cc2de44f3df2c89e6720ce71772615b7975fd316bd45ab6b3a`,
source journal sequence 532. Cold byte verification succeeded. Application
restart did not: the pinned engine exceeded the 1536 MiB charged-memory guard
(1575 MiB, then 1553 MiB with the derived cache restored). v22 is therefore a
verified recovery copy, **not a working replacement deployment**. Do not infer
successful rollout or endurance from the recovery receipt.

Next work must diagnose that actual startup failure and restore native use
without discarding committed work or hiding it by raising the guard. The queued
construction-plan request has not been fulfilled. No second-collection reuse or
broader personal-OS acceptance has been claimed.

## Continued recovery, October 3

The original stopping point was not recovery completion. Startup profiling and
a cold-load sample exposed quadratic allocation while flattening long SILO APP
spines and repeated storage for equal immutable decoded subtrees.
`x/enki-linear-silo.patch` retains the focused decoder/storage repair and two
regressions. It also reduces the serial compiler scratch heap from 64 to 8 MiB.
The wire encoding and canonical hashes are unchanged; PIN identities never
enter the bounded subtree cache, and load rollback invalidates it.

The 6,000-field regression failed on the old decoder (9,630,400 bytes allocated),
then passed with byte-identical re-encoding. Decoder checks: 14 / 152 assertions.
Store/pin checks: 42 / 669 assertions. Full cold loading verified every native
object hash. Subtree sharing reduced measured cold-load peak footprint from
1,442,713,856 to 391,776,576 bytes on the same v23 root.

v23 reached readiness but exceeded the unchanged guard during resumed use.
v24 is an explicit migration into a new journal from its latest root
`bcc65b670c784d195dd3865f0229b5ba5ed771d5a445ecd8712fd529aa094b86`: 36,854
verified objects / 430,717,944 encoded bytes. Its manifest pins the corrected
engine; migration-receipt.json records both engine identities and preserves the
saved closure's original compiler basis. v21–v23 and their compatible engines
remain retained. No historical journal was reinterpreted in place.

v24 reached EDEN-WORLD-READY, served the normal browser entry at port 8186,
restored the complete flow and accepted the continuation through the browser.
Initial live owner charged memory: 496,880,512 bytes; aggregate limit remains
1,610,612,736 bytes. This is recovery/use evidence, not endurance acceptance.

The resumed v24 browser session installed three native task records through
Astra and the checked proposal UI. During the next authoring request, repeated
activity transactions crossed the separate 1 GiB pin-file limit at journal 199.
Peak measured aggregate memory was 592,975,232 bytes, with no memory error.
Journal inspection showed 1.6–4.2 MiB of historical serialization per small
activity update. The unchanged guard stopped the process; the task records and
all acknowledged activity remained committed.

`x/enki-packed-silo.patch` adds lossless physical envelopes to a new backend
revision (3), without changing canonical Silo streams or their hashes. Revision
2 remains readable only; old engines reject the new backend. Inflated objects
are bounded to 128 MiB, checked for exact length/trailing bytes and compression
checksum, then pass the ordinary canonical hash validation. Raw envelopes are
used when compression does not help. Native agent transport no longer writes
an identical progress reply for every tool; the actual start/result activity
records remain native and visible.

Focused storage verification: 43 tests / 6,683 assertions passed, including
cold compressed reload, canonical hash identity, and corrupted checksum
rejection. v25's migration receipt records exact root
`60feadf02fe2f5dff62c139fd5eb6a8ca66f262f5f62f5d2006a88b66bd1a6d2`,
41,405 byte-verified objects, 490,070,447 logical bytes and 103,767,627 physical
bytes. Historical v24 remains untouched. This reduces physical storage; it
does not claim bounded lifetime history or resolve the cost of rewriting
growing native history structures. Those remain measurable limitations.
