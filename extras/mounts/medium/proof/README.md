# Small grammar proof

The current product direction is the [closed native computing environment plan](../../../../doc/grove-canvas.md).
This proof is its starting point and a regression fixture, not its presentation or
computational ceiling. The plan extends native regions, reactions and executable
template capture. Those additions are not implemented by this documentation update.

This is a deliberate reset of the product surface, not a claim that the earlier
canvas plan is complete. The prior interface and pinned worlds remain recoverable.

The acceptance boundary is:

- NAME: a native subject, created without inference.
- NAME + PROPERTY: a native opaque slot with a literal text value; editing it is
  native and never calls a model. Richer types require authored codecs/checks.
- NAME + NAME: exact references become an immediate provisional association.
  Existing exact associations are reused; new meaning may develop in the background.
- Description is optional intent on a subject, property, or association. New meaning
  goes directly to a capable source author, then native compilation and admission.

The proof bypasses the old selector/interpretation/Jev pipeline. It retains native
checks and at most two repair attempts after the first actual compiler diagnostic.
No inferred correspondence is advertised as a native proof. Known exact boundary
reuse has no model call; arbitrary structural/semantic matching is not implemented.

The host retains native source and its Goo surface together. Derived values are
Foil computations. The browser owns placement, focus, draft text, and rendering of
native frames. Moving a card performs no network request. Retiring an unreferenced
subject removes an active root with native undo; it does not delete shared history
or pretend to compact the persistent store. Referenced subjects cannot be retired.

Run from the repository root:

```sh
MEDIUM_PROOF=1 MEDIUM_PORT=8161 python3 x/eden \
  --runtime /Users/ianchanner/.local/share/shrine/build/canvas-gc-headroom/bin/wisp \
  --protocol canvas/1 \
  --world /Users/ianchanner/.local/share/shrine/development/grove-grammar-proof-v2 \
  --mount medium --port 8162
```

The first world boot compiles the native closure. Subsequent starts use its pinned
engine and store. Model credentials stay in the existing host configuration.

Tests: `python3 extras/mounts/medium/test_proof.py`,
`python3 extras/mounts/medium/test_model.py`, and native
`x/check mount:medium:tests/medium --jobs 1 --timeout 240` with the configured WISP.
Actual browser/model execution is recorded separately; mocked transport tests are
not evidence that a generated behavior works.

## Shape emerges from use

The October 2 follow-up keeps names and stable references as the starting point.
A literal property editor is optional convenience, never a schema prerequisite.
Composition can establish positions, derived values and actions. Once established,
its native subject can participate in another composition without flattening or
copying its constituents. Description remains optional at every boundary.

A hierarchy in the presentation does not transfer ownership or authorize an effect.
Shrine's addressed namespace can remain a tree while records participate through
several explicit references. A task shared by a person and a project is one subject.
An inverse view should derive from the same established relation, not maintain a
second independent copy of the fact. One observed participant does not prove a
universal one-only constraint; future cardinality changes must check consumers.

This reset proves the small boundary first. Emergent collections, shared inverse
views, pattern matching across new instances and automatic cardinality evolution
are follow-on work, not claimed capabilities of this proof. Native properties are
currently text literals; authored behavior supplies richer checks and codecs.

## Observed acceptance, October 2

Real OpenRouter authoring and native browser execution established:

- Price 20 + Quantity 3 produced native multiplication and displayed 60.
- Changing quantity to 5 produced 100 without another inference.
- Selecting the same connection reused its identity without another inference.
- A description changed that connection to addition and displayed 25.
- Bare Person + Task produced an assignment and a working native action without
  asking for a schema or requiring literal properties first.

First establishment took 31.1 seconds with a compiler repair; the later description
change took 16.4 seconds. The bare-name author's model call took 16.24 seconds.
These are working behavior results, not a claim that latency or presentation
quality meets the intended experience. The first assignment presentation exposed
numeric state; the author guidance now asks for human state labels. That guidance
alone is not a verified presentation-quality guarantee.

60 native assertions, 92 evaluator tests (12,161 assertions), 26 model/transport
tests and four reconstruction-boundary tests passed. Actual receipts and sources
are under the local development worlds; `grove-grammar-proof-v2/acceptance.json`
records the cases and limitations.

The corrected live world was reconstructed from all 14 retained native operations
of the original small world. Subject identities, properties, references, source
and visible values were compared, including after restart. The original world's
pins were unchanged and remain the rollback source. `x/replay_medium_local.py`
refuses incomplete histories, physical actions, and nonempty destinations. It is
a narrow local recovery tool, not a general world migration or package-transfer
implementation. The transition receipt lives in the new world's `transition.json`.
