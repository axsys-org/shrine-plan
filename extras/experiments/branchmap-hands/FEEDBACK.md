# Fresh harness feedback

The combined harness now supports the quote read model directly. Expressions, reference traversal, validation, conditional writes, and a kept world remove several reasons the earlier experiment needed external orchestration. The remaining gaps concern moving from a live read model to a durable, version-checked application action and keeping hands correct across time.

## What worked

**Expressions made quote arithmetic native.** `quantity * price_micros` and `cash_micros - cost_micros` calculated the quote inside cells. Signed subtraction preserved the insufficient-cash result as -140,000. A boolean expression rejected fractional, zero, oversized and unaffordable requests. Missing joint prices stayed missing, with a row-level hole. This is enough expressiveness for the read side of this toy exchange without adding a custom pricing primitive.

**References kept facts shared.** Requests pointed to offers and accounts. `follow` made the dependencies explicit through its secondary inputs. Updating a source price propagated through the chain, while pinning the secondary table preserved the old price. Backlink discovery found the request's offer slot. The updated skill's input-first and reference-first guidance fits this task.

**The kernel now protects conditional batches.** A stale `if_case` rejected both the price change and a marker record. The refusal included the actual and expected cases. This improves the substrate for transactions, but does not itself make a calculated quote an executable trade: the action must still check every relevant dependency and preserve the domain invariant.

**Kept-world resume preserves this application.** After normal launcher termination and restart, the quote rows, source history, full exchange display and Carol account matched their pre-stop values. The launcher remounted the current checkout. This resolves the earlier disposable-launcher gap for this application; it does not establish crash consistency or migration safety.

**The combined branches coexist in one runtime.** The MCP product suite passed 150 checks; the native exchange passed 42 domain checks, real Goo action checks, and goo-egui prepared-view validation at widths 480, 900 and 1200. The hand integration test passed 23 checks, including a local watch sink, CSV import/export and zero new events during a 60-second idle interval. That idle result is useful: background work did not manufacture journal traffic.

**The live page exposes the computation.** Browser inspection showed the view cells, formula names, row counts and author-tagged changes. This provides a useful construction/debugging surface alongside the application's Goo transaction view. It does not replace a participant-facing quote ticket and portfolio layout.

**Pinned live-cell behavior is explicit.** Reading an old `/h` reference to a live cell returned unavailable, as the new documentation says. My earlier criticism should distinguish source history from derived-result history. Pinned inputs work; a historical executable quote still needs a receipt containing its source versions and calculation version, or a fully pinned derivation. The live result reference alone is not that receipt.

## Reproduced gaps

**1. Ask-hand restart loses its discovery state.** A fake-model ask answered an initial input of 10 and an update to 20. A new hand instance resumed the saved cursor with an empty `asks` map. Updating the input to 30 produced no answer; the cell correctly remained stale. Explicitly relearning the cell restored the answer. `AskHand.__init__` creates an empty registry, while `learn` reconstructs it only from cell writes after the saved cursor. Persist the registry or rediscover current ask cells independently of the event cursor. See `hands/ask.py` and the saved `ask-probe.json`.

**2. Hand catch-up stops after one history page.** With the world at epoch 341, one `catch_up()` advanced only to 105. `Hand.take()` updates `self.seen`; `catch_up()` then compares the page cursor with that already-updated value and stops. The stock ask suite failed its first answer assertion on this accumulated world. Further ticks can advance the backlog, so this is incomplete catch-up rather than proof of permanently lost events. Compare with the cursor from before fetching the page, and test a backlog larger than one page. The combined branch leaves this code unchanged so the reproducer tests upstream behavior.

**3. Derived collection members still lack independent reads.** `/x/0x11/app/branchmap/accounts` listed four members. Reading `/x/0x11/app/branchmap/accounts/1` through MCP returned `exists: false`; Goo returned an empty child collection. The namespace inspector can list the account rows but cannot navigate them as ordinary records. A derived subtree needs an addressable member contract with stable domain identity; ordinal row paths alone are insufficient.

**4. Nested slot expressions require plumbing.** `follow` produces slots such as `/offer/price_micros`; expression identifiers accept letters, digits and underscores, while `/` is division. This implementation used four rename cells before arithmetic. A path-qualified slot accessor or a multi-field projection would reduce incidental graph structure without copying shared facts into the inputs. `lookup` is another current option when only one joined field is needed.

**5. First evaluation needs better visibility and limits.** On this machine, the first quote read took 29.248 seconds; the next eligibility read took 3.030 seconds. A separate five-second health request timed out during the initial evaluation. The corrected warm probe's calls all took less than half a second. These are observations from a mixed test session, not controlled performance benchmarks. Expose compilation/evaluation progress, per-cell timing, and a bounded or cancellable evaluation path so an agent can distinguish cold work from a wedged world.

## What would help next

**Connect quote cells to a native action contract.** Define a quote receipt with account version, offer/inventory version, formula version, quantity, price and total. Let the action atomically admit or reject that receipt, recompute/check the transition, and emit one domain receipt. Goo should display the live quote and submit its identity. Keep economic decisions in native code; a Python hand should not become the trading controller.

**Give custom native computations a documented authoring path.** The standard registry and expressions cover useful queries. Canonical claim normalization, complete-family issuance and settlement still use the custom Foil/Grove mount. A documented route from a trial calculation to a reusable typed computation, including tests, publication, upgrade and source identity, would bridge those two workflows. An `ask` cell is appropriate for model interpretation, not deterministic settlement.

**Bound and record model-hand work.** Source inspection of `ask.py` shows one input read with `limit=500`, no continuation loop in `answer`, and an answer record containing the case/model/prompt rather than provider usage and request receipts. Add complete-input handling or explicit truncation, request/response provenance, retry limits and spend budgets before using it for a long Astra run. This is source-based feedback; no paid endpoint was exercised here.

## Scope of the evidence

This run tested the supplied combined revisions with the existing native application and a new quote graph. It was not a fresh Astra construction run. The retry skill supplies that experiment separately and records prior exposure, model/settings, fixed inputs and separate milestone results. It does not preselect the implementation or claim a blind comparison merely because the filesystem is fresh.

The previous live Grove rescan/replacement `sewn_norm_failed` failure was not reproduced in this pass. Do not infer that it is fixed from startup, ordinary action tests, or kept-world resume. No full core/compiler suite, crash-recovery test, authentication boundary, real venue integration or real model inference is claimed.
