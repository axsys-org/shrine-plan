# Grove Canvas implementation status

Work in progress on `codex/grove-canvas`; no release-complete claim. Source is
uncommitted. Earlier product worlds and their engines remain separate.

## Native use and live model construction (2026-10-02)

Current construction work is in `grove-native-material-v16`, browser port 8184,
native port 8188. Earlier worlds below remain pinned and available. No broad
regression campaign or latency tuning was run during this continuation.

The material under `extras/mounts/medium/constructions/` was authored through
`native/author` and installed through `native/instantiate` into the running world.
It is not hidden application behavior in the mount's startup fixtures. Useful
pieces now include field presentations, a model-authored Task-to-Interval
projection, timeline and upcoming projections, native JSON contact decoding and
guarded merge, and a native workspace composed from those presentations.

Actual use edited one original person through a table and saw that identity in
the other people presentation and task ownership. Editing an estimate changed
the temporal result. Switching the shared mapping to deadlines updated both time
views. Importing the explicitly synthetic JSON contact changed the selected
original person's name while retaining unrelated fields and references.

The OpenRouter author now runs a bounded native tool loop: discover, source,
frame, inspect, author and instantiate. A native work record owns its request,
generation, cancellation, progress and result. The Python host carries provider
requests and enforces fresh construction locations; it does not evaluate an
application or generate browser business logic. Established controls make no
model requests. The native Canvas host now starts and stops this transport itself;
one world lock prevents duplicate managed workers. The toolbar reports actual
provider authentication and native-listener readiness via `/api/agent`, and its
AI control opens the native authoring surface from any current surface. A read-only
answer or reuse of an existing evaluated surface no longer requires manufacturing
a fresh construction. The standalone command remains for host development only:

```sh
python3 extras/mounts/medium/native_agent.py \
  --world "$HOME/.local/share/shrine/development/grove-native-material-v16" \
  --port 8188
```

The first real browser request searched existing definitions, reused the field
and guarded record machinery, compiled a new presentation and instantiated it
over the three original project tasks. Using the result changed the original
`/app/user/personal/next/author` status; inspection identified its exact slot and
case. The first presentation was cramped. A second model request improved the
layout but did not create a genuine multiline editor. A third hit its work bound
with Foil compiler errors; that failure remains in its receipt.

A targeted OpenRouter repair then produced the retained `textarea/areas` native
tree transformation. It converts existing field inputs into textareas while
preserving correspondence and action attributes. Codex composed it with the
original field/record machinery into `workbench.grove`. A real multiline edit
updated `/app/user/personal/next/world` `/next_step` to case 2. Its owner link
opened the same native person. This assembly was not wholly autonomous model
output. Compiler feedback now selects the stronger repair lane for subsequent
authoring turns.

Native sources and provider receipts are retained. Live request transcripts are
in the world's `native-authoring/`; `model-built-binding.png` captures the first
model-produced control's original binding. Superseded uninstalled source drafts
were archived once with path/hash/recovery records in
`~/.local/share/shrine/archives/native-construction-drafts-2026-10-02/`.

Limitations remain concrete: authoring uses bounded Pure in the live owner,
not disposable compile workers; the development transport uses administrator
authority with restricted fresh locations, not the finished agent-principal and
grant architecture. Source spans remain
zero, presentation quality is uneven, and complete connected IDE/self-authoring
acceptance and user sessions remain unproved. This is working native construction
and use, not completion of the personal OS.

The native desk at `/0x11/app/user/desk/home` composes the task presentation and
the existing OpenRouter request/progress presentation with native action dispatch.
Its input is the same tasks, person, project and author work record. No browser
application subsystem was added for this composition.

The next ingestion slice uses the actual user-supplied media specification as
input. `/app/user/ingestion/raw` retains its UTF-8 source exactly: 12,326 bytes,
SHA-256 `180b9b7582edef4650cc3400188a43bba3851300f8a40878a12b413f3815ea78`.
The original bytes were compared with the text read back through native discovery;
`text-ingestion-receipt.json` retains the result. A native anchor links bytes
11,914–12,151 (length 238, end exclusive 12,152) at source case 1 to the existing
project. The parameterized `text_basis` functions validate the captured revision
and range. `text_anchor` presents the computed excerpt, original source and an
editable annotation using the already retained textarea/field/record machinery.
The real browser annotation edit succeeded. Source and annotation are separate
native values; only the annotation is writable through this binding.
Option-click inspection resolved `/app/user/ingestion/raw` `/text`, source case 1,
and the native typed byte selection; the anchor had advanced independently to
case 2. `reading-live.png` and `reading-binding.png` retain the actual browser
surface. This use exposed a general modifier-input defect: the host depended on
receiving an earlier Alt keydown. Pointer/click inspection now also honors the
modifier on the input event itself. No application semantics moved into the host.

This is one UTF-8 ingestion path, created through native authoring with retained
source provenance. It is not a general upload UI, every file-format decoder,
media tracking, or automatic semantic identity inference. Mask/registration,
uncertainty and provenance requirements are now standing guidance in `AGENTS.md`.

## Earlier native boundary and memory checkpoint (2026-10-02)

The earlier experimental native surface is `http://127.0.0.1:8181/`, backed by
`~/.local/share/shrine/development/grove-native-material-v5` and its pinned engine.
It is separate from the previous 8161/8164 prototype entry points. The older
sections below are historical results, not the current runtime status.

Real browser interaction changed Value A from 12 to 19 and the native sum from
40 to 47. Inspection resolved the original `/0x11/app/material/values/a`, opaque
slot `/value`, case 56, and `/0x11/gov/material/records/prepare`. Screenshots
`live-edit-showcase.png` and `live-binding-showcase.png` are in that world.
No model or browser evaluator computes the sum. The native form/overlay and
subscription path updates it. Source spans still report zero: source navigation
is not complete. This small construction is not connected OS acceptance.

A second live walkthrough opened two occurrences of the same surface after the
user had changed the values. Editing A from 22 to 23 updated both occurrences and
their sum from 53 to 54 (B remained 31). Inspection showed A case 60, the original
opaque `/value` slot, the same `records/prepare` implementation, and the sum overlay
at case 64. `shared-occurrences-showcase.png` and `shared-binding-showcase.png`
retain the actual browser surface. Explorer/inspector interaction remains rough;
no UI polishing was done for these walkthroughs.

Native actions now use the owner's existing hive rather than rebuilding it.
Hoisted fixed ABI constructors and that index reuse reduced measured warm edit
p95 from roughly 798 ms to 152.28 ms. The 150 ms gate remains unpassed.
`first-100-read-and-latency.json` retains that measurement separately.

The original v5 10,000-read run preserved `pins.pack` at 159,551,994 bytes, but charged
memory grew from about 732 MiB at read 5,000 to 1,010 MiB at read 10,000.
The final-half range was 291,127,936 bytes, exceeding the 16 MiB limit. See
`native-surface-acceptance.json`. That engine failed the resource gate. The
aggregate guard was not raised.

An instrumented Enki build now reports per-actor store/heap/root/queue usage in
the multithreaded executor. Its 28 actor tests / 51,359 assertions pass. It has
not been used to reinterpret the v5 journal; investigation uses a fresh world.
The diagnostic-only change is retained in `x/enki-lifetime-probe.patch`.

The v7 isolated probe repeated 2,048 unchanged frames: canonical store memory
stayed at 179,201,272 bytes, queues stayed empty, and charged memory grew by
111,690,112 bytes. Receiver update stacks grew by five or six entries per
receive despite constant value/frame depths. The evaluator was retaining
otherwise unreachable THKE update targets until the long-lived actor returned.
The repair makes those targets weak collector roots while preserving
targets still reachable from another consumer. `x/enki-weak-update-roots.patch`
contains the change and two regressions that fail on the old evaluator and pass
on the repaired one. Release evaluator (94 tests / 12,175 assertions) and actor
(28 tests / 51,359 assertions) suites pass. AddressSanitizer with collection at
every allocation also passes evaluator, actor, and store suites (164 tests /
64,203 assertions). Logs are under `~/.local/share/shrine/build/` with prefix
`canvas-update-root-asan-`.

The repaired engine completed the full 10,000 unchanged native frame requests in
a new v8 world, using the captured v5 application sources without copying its
journal. `pins.pack` remained exactly 151,344,420 bytes; charged memory peaked at
403,723,264 bytes and its final-half range was 622,592 bytes (0.594 MiB), below
16 MiB and the unchanged aggregate guard. Per-actor diagnostics also show a
constant canonical store and bounded update roots. This passes the read workload
on the repaired engine; it does not change the failed v5 result or establish the
unrun compile-cycle/hour-long gates. Evidence is
`grove-native-material-v8/native-surface-acceptance.json` and `out.log`.

That v8 run still failed its separate warm-edit latency gate: 40 measured edits,
p50 173.40 ms, p95 346.44 ms, maximum 393.29 ms. Functional native surface checks
passed, but the combined acceptance command correctly exited unsuccessfully.
Latency remains work to do; no complete acceptance claim follows from the memory
repair. The visible v5 world remains pinned and has not been silently switched.

Independent retained action checks, scoped inverse operations, and an ordinary
native matrix library pass 64 native assertions in `checks/3234ac586be8/run-92lk8x33`.
The positive retained-check regression exposed and fixed an incorrect nullary
verdict pattern; valid changes now pass as well as invalid changes being blocked.
The first compiled matrix-world check (v11) passed native painting,
interpolation, exact pixel correspondence, stale-basis rejection, inversion,
crop and stale-geometry rejection. It exposed a real undo failure: resolving the
original crop position against the already-cropped matrix. The repair retains
the original native occurrence and implementation in the owner-written receipt,
then checks the inverse against current values, scopes and commitments. It does
not relax stale pointer checks. The repaired surface suite passes 50 native
assertions in `checks/3234ac586be8/run-um_elv4q`, including retained-case undo,
changed-implementation rejection, current read/write scope enforcement, principal
and surface ownership, missing-provenance diagnostics, and protection against
surface actions rewriting owner receipts.

The fresh v12 world on `http://127.0.0.1:8182/` passes all 24 compiled matrix
HTTP checks in `grove-native-material-v12/native-matrix-acceptance.json`: painting,
interpolation, native pixel focus, invert, transpose, crop, stale geometry,
scoped undo/redo across geometry changes, and reuse by a cellular transition.
This world uses the repaired engine and new source; no old journal was reinterpreted.

Actual browser interaction painted the image, inspected `[7,3]` as the original
`/0x11/app/material/image` `/matrix` at case 14, cropped 24×18 to 8×6, and restored
the full matrix and prior paint through Cmd-Z. A second surface was placed beside
it, and its native cellular step changed four displayed samples. Inspection
resolved `/0x11/app/material/cells` `/matrix`, case 4, through
`/0x11/gov/material/cellular/prepare`. The image and simulation reuse native matrix,
painting, raster presentation and coordinate correspondence. No application logic
was added to the host for this checkpoint. Actual evidence in v12:
`pixel-binding-browser.png`, `crop-undo-browser.png`, `shared-matrix-browser.png`,
and `cellular-binding-browser.json`. Both v12 and the user's v5 remain available.

This proves small constructed matrices, not real-file image ingestion, continuous
simulation, million-position viewport tiling, or an enjoyable end-to-end authoring
environment. Source positions remain zero, inspector presentation is raw, and
workspace placement is still transient host state. No broader completion claim.

A follow-up v12 native surface run preserved shared records, original targets,
multi-subject actions, deduplication, stale-basis rejection and the overlay sum.
Its 100 unchanged frames preserved `pins.pack` at 170,332,982 bytes; final-half
charged-memory range was 1,327,168 bytes. This is a short regression run, not a
replacement for the earlier 10,000-read v8 measurement. Forty warm edits measured
p50 151.18 ms, p95 183.49 ms, maximum 197.94 ms while the two matrix occurrences
remained open. The 150 ms p95 gate still fails, and the combined runner exited
unsuccessfully for that reason. Evidence: v12 `native-surface-acceptance.json`.

The standing rendering guidance is now explicit in `AGENTS.md` and section 11 of
the plan: Canvas/SVG/raster for dense or custom drawing, DOM/native controls where
useful, and exact native correspondence underneath both. Keyboard and pointer
meaning belongs in native definitions. This is a constraint on ongoing work,
not a claim that native keybinding or general scene authoring is complete.

Disposable authored compilation, the connected
spreadsheet/IDE/image/game/workspace sequence, the 50-worker-cycle and one-hour
tests, and actual user sessions remain outstanding. Superseded shells are kept
until their native replacements pass; source was archived once beforehand.

## Direct interaction continuation (2026-10-02)

The same v4 development world is still active on browser port 8161 / native port
8165. Its exact native frame survived the host restart. No engine or historical
world was replaced during this continuation.

- The selected object's follow-up control now follows it on the canvas. A blank
  canvas double-click starts at that location. Card headers drag; native content
  remains selectable and interactive. Each selection retains its own intent draft.
- Holding Option while pointing uses native Goo occurrences to expose exact slots,
  source location and displayed basis. Those references accompany the model request.
  The host refuses stale pointing context before asking the author to act on it.
- Conditional native reads bring other clients' changes into the canvas. A local
  request gate prevents late reads from overwriting newer accepted work. A completed
  author job reads the current world rather than restoring its historical result.
- Submitted text is cleared only when the same text is echoed in the native view;
  edits made during execution and rejected values stay available. Native action
  controls show Updating while executing. Enter submits a single unambiguous control
  in its native group; multiline source uses Command/Ctrl-Enter.
- Author context explicitly summarizes historical source bodies and large unselected
  generated images. Current executable source, arbitrary checks, scalar values,
  exact identities, dependencies and action references stay available. This is a
  declared context projection, not a change to native data or a lossless full-world
  export. Explicitly selected image slots retain their full value.

A real OpenRouter interaction added direct value entry and a Set action to the
existing shared Number definition. Both uses retained their values, source identity
and downstream connections. Invalid input reports a native inline error. This was
one model attempt (Sonnet 5.5, 20.49 seconds), followed by successful native checking.
No application implementation was substituted in JavaScript or Python. Its scoped
context was 63,861 bytes versus 130,760 supplied bytes including derived HTML;
this is not a controlled latency comparison.

Fresh evidence under `~/.local/share/shrine/development/grove-self-construction-v4/`:

- `editable-number-request.json`, `editable-number-result.json`: actual before state,
  submitted intent, authored native source and provider receipt.
- `interaction-continuation-acceptance.json`: 11 native/HTTP checks passed, including
  retained identities/values, invalid input, valid propagation through Successor and
  both Interference uses, unchanged unrelated source, source-editor reflection,
  external-action visibility through conditional HTTP, and 20 unchanged conditional
  reads without native history or pin growth. Input values were restored by native
  actions; factual history remains. Reproduction: `x/check_medium_direct_use.py`.
- Host/model regression: 21 tests pass. Browser continuity logic: four Node tests
  pass (request ordering, draft acknowledgement, frame identity, opaque occurrence
  references). JavaScript module syntax and Python compilation checks pass.

These are not rendered browser or usability results. Browser automation remains
blocked by its URL policy; no alternate browser path was used. Ordinary native
updates measured 3.28–4.89 seconds and reads 1.23–1.39 seconds in this world. That
latency does not meet the intended immediate interaction bar. The native renderer,
evaluation and transport need profiling before claiming a fluid experience.

Pre-change source is preserved once under the existing source archive's
`interaction-continuation/manifest.json`. The native suites recorded below were
not rerun: this continuation changed the host/client and an ordinary native
definition, not the pinned compiler/runtime machinery.

## Native construction implemented (2026-10-02)

The implementation now exercises one recursive construction law: a source editor
is ordinary compiled Grove, and another use of that editor can change its shared
implementation. This is a working native construction slice, not a complete OS,
spreadsheet, self-hosted canvas or accepted user experience.

- `grove_definition` reflects an exact source owner, code root, revision and source.
  Source-only bindings are distinguished from data dependencies and edit authority.
- `library/source_editor.grove` uses native Goo input and a compiled action that
  proposes a `grove_definition_edit`. The owner compiles, checks consumers and
  settles the change atomically through its existing native author path.
- Multiple uses share code while retaining independent values and input bindings.
  A failed compiler or unauthorized source edit leaves the entire world unchanged.
- Applying an existing definition with supplied bindings needs no model call.
  Unused instances can retire without deleting their shared definition.
- OpenRouter authors Grove/Foil; the browser still contains no application evaluator.
  An actual generation produced Interference: native modular arithmetic makes a
  bounded SVG, Goo presents it, and native actions and shared inputs change it.
  A second instance uses the same implementation with a different native input.
- The duplicate medium shell and obsolete selector/Jev/type-review execution path
  were removed. The one browser surface retains viewport, drafts and interaction
  mechanics; native subjects remain authoritative.
- Goo inputs support a multiline code viewport. Presentation errors now retain
  their native view identity, source location and diagnostic in new engines.

Actual evidence (outside iCloud):

| Check | Result |
| --- | --- |
| Native construction, source editing, recursive editor, authority, retirement, detach/rebind and unchanged reads | 30/30, `grove-self-construction-v3/construction-acceptance.json` |
| Actual model-generated SVG, native updates, reused code, separate state, incompatible binding rejection | 8/8, `grove-self-construction-v3/model-visual-acceptance.json` |
| Native Goo dispatch/diagnostics and medium regression | 93/93 assertions, `checks/3234ac586be8/run-hyhr08a1/results.json` |
| Current host/model gates | 18 tests pass |
| Bounded local reconstruction gates | 6 tests pass |

Evidence paths above are under `~/.local/share/shrine/development/` except
`checks/`, which is under `~/.local/share/shrine/`. Original source is recoverable
from `~/.local/share/shrine/source-archives/native-construction-ffe5e40e9f0f/`.

A second actual model interaction evolved the shared Interference definition from
squares to circles through a selected instance. Both presentations changed; both
identities, exact input bindings and all three numeric state slots per instance
were retained. Unrelated source stayed unchanged. The successful generation took
14.54 seconds. `grove-self-construction-v4/model-evolution-acceptance.json` retains
before/after native frames and the provider receipt. Its earlier failed job confused
source replacement with reuse; the prompt and structured argument descriptions now
state that those are mutually exclusive. No hand-written application source was
substituted for the successful model result.

The model trial was not an uninterrupted success: three earlier bounded jobs
failed on Foil indentation and a Grove `show` slot argument. Frozen attempts are
retained under the world's `authoring/`. Correcting the reference yielded an actual
13.33-second OpenRouter generation, followed by native compilation and installation.
The visible ordinary actions took roughly 1–2 seconds in the small world; source
recompilation took roughly 4–6 seconds. These timings are not the experience target.

Browser navigation was rejected by the automation tool's URL policy. No alternate
browser path was used. The current UI has syntax checks and real native/HTTP
execution behind it, but has NOT been visually verified or tested with users.
The 20 unchanged-read checks establish no history/pin growth in that sample;
they do not establish the full endurance or memory gates.

The active world is now `grove-self-construction-v4`: browser on
`http://127.0.0.1:8161/`, native service on 8165. Opening the local page establishes
its same-origin HttpOnly session; no Codex browser or credential-bearing URL is
needed. Only this development server remains running.

The separate candidate reconstructed all 19 retained native operations and verified
all seven subject identities, source, bindings, and observable values. This requires
complete retained history and the explicitly reviewed pure medium action boundary;
it is not a general migration or a replay of external effects. The original v3
world is intact. v4's `reconstructed-frame.json` and v3's `transition-intent.json`
record the transition. v4's `restart-acceptance.json` contains five passes: exact
committed frame continuity, no history/pin growth over 20 resumed reads, normal
browser session establishment, shared native identities through HTTP, and execution
of the model-generated action after restart. `diagnostic-acceptance.json` verifies
that an actually rejected view reports its exact path, line and cause and leaves
the reconstructed world unchanged.

For rollback, stop the v4 owner, resume the intact v3 world with its original engine
and selected medium mount, and point its browser host at an available loopback port.
That opens the prior world; it does not erase or transplant later v4 edits.

## Current direction: a closed native computing environment (2026-10-02)

The [manifesto](grove-manifesto.md) states the premise; the
[native world specification](grove-native-world-spec.md) defines the required
semantics; [Grove Canvas](grove-canvas.md) maps them to implementation. A region becomes working
software; its native behavior, state, presentation and open boundaries can become
a reusable template in a larger composition. Constructors, editors, viewers and
transformations are themselves reusable native material; several can operate on the
same subject without owning or duplicating it. The small grammar remains the first
interaction gate. The progression is calculator, editor, native spreadsheet, drawing,
small compiler, simulation, development environment and a limited self-editing canvas.
The spreadsheet over shared Person/Organization/Task references is the first main
proof. Installed execution must survive model unavailability. Clock readings are
host observations; native time-related software is constructed as needed.

The closure requirement is explicit: a live result participates in subsequent native
composition immediately, before template capture. Template generalization is separate.
New definitions extend the available vocabulary through native publication/discovery;
no application-specific host registration may be necessary for each new kind.

The earlier specification revision changed documentation only. No runtime, active client, source
implementation or user state was changed as part of revising the plan. The previous
plan is preserved once, with its hash and recovery path recorded in the new plan.

### Latest recorded baseline, not a new test run

The most recent recorded small-grammar world is `grove-grammar-proof-v2`, with the
browser on port 8161 and its native service on 8162. The `grove-medium-v6` references
below describe earlier work; they are not the current-world configuration.

- Real OpenRouter authoring produced native multiplication, an input-driven update
  without inference, exact association reuse, a description changing the behavior,
  and a bare Person + Task association with an executable native action.
- Novel authoring took roughly 16–31 seconds in the recorded cases. The interface
  and these timings do not meet the new experience requirements.
- The small proof uses direct source authoring, bypassing the older mandatory
  selector/Jev/review chain described in the historical entry below.
- Recorded checks: 60 native assertions; 92 evaluator tests with 12,161 assertions;
  26 model/transport tests; four reconstruction-boundary tests. These are narrow
  evidence, not acceptance of this revised plan.
- Evidence: `~/.local/share/shrine/development/grove-grammar-proof-v2/acceptance.json`
  and `transition.json`; native results in
  `~/.local/share/shrine/checks/3234ac586be8/run-b7xyucmn/results.json`.
- The transition reconstructed all 14 retained native operations of the small
  predecessor world and checked identity/source/value continuity, including after
  restart. That predecessor remains pinned. This is a bounded recovery path, not
  a general migration or transfer system.

Still unimplemented or unproven for the new release: general native graphics and
input regions, broader action target sets, maintained dependency integration,
logical-clock execution, capture of complete computational templates, recursive
reuse, the live simulation and spreadsheet, latency/usability and endurance gates.
Existing native machinery is reused; none of these capabilities is established by
writing the plan. See the plan's file map and staged gates for implementation order.

## Historical work: native composition medium and Jev (2026-10-01)

The following record retains the configuration and claims from that date. References
to an active iteration or current world in this section are historical.

The separate medium is the active iteration, at `http://127.0.0.1:8161/`, with
the durable `grove-medium-v6` world. The older Canvas material below is historical
coverage, not a claim that its UX met the user's requirements.

OpenRouter replaces the former Codex CLI connection. Jev receives the operational
type context, exact source/bindings, open positions and relevant provenance. Its
questions include boundary/identity inference and position-specific candidate
rankings derived from the actual open inputs. The author emits ordinary Grove/Foil.
A second Jev pass receives those proposed declarations and checks for potential
identity or requirement loss as inference, followed by actual native admission.
The key stays in a private local file, never the browser or native namespace.

Latest progression implementation and verification (October 1, later session):

- Native definition-wide edits preserve occurrence identities and values while
  rechecking actual consumers. Optional fields remain absent until an action
  supplies them. Pattern instantiation and explicit value duplication are separate.
- `grove_binding_schema` supplies stable requirement keys, expected native roles,
  and declared shape. Native role checks and authored `accepts` both run within
  bounded effect-free execution. The schema has one realization per requirement.
- Requirement-key rebind/detach, genuinely unanchored inputs, and preserved
  detached-input provenance are implemented. Source editing cannot silently fill
  or rename an established requirement. Retirement remains unimplemented.
- 32 native assertions passed in `3234ac586be8/run-acotbwmw/results.json`.
  19 Python model/context tests pass, including bounded token-exhaustion recovery
  and retained receipts when that one recovery also exhausts its budget.
- 29 live progression checks passed in
  `grove-medium-progression-check/progression-acceptance.json`: actual compilation,
  Person/People reference continuity, definition versus occurrence scope, empty
  birthdays, native data entry, fresh/value copies, detach/reinsert, atomic
  rejection, and partial unanchored inputs.
- 10 further live checks passed in `requirements-acceptance.json`: native role
  rejection independent of custom `accepts`, exact-key addressing without index
  fallback, a higher-order requirement filled by one existing composition,
  constituent rejection, and prevention of implicit arity changes.
- In the browser, a real OpenRouter request added optional nickname editors to
  all four Person occurrences. The actual Grove/Foil source compiled on its
  first attempt. A real Goo action then set only Emma's nickname to `Emmy`.
  The original names, birthdays, identities, and input edges remained intact.
  The author was `anthropic/claude-sonnet-5.5` (12.62 seconds); the preceding
  tool selector was `z-ai/glm-5.3-flash` (9.94 seconds). This is one observation,
  not a latency target. Receipt:
  `authoring/attempt-839bda30262846dc9f5b198db385edd7.json`.
- Browser verification also retained Lucas's unsaved name draft across Emma's
  update. The draft was restored afterward. See `progression-browser-proof.json`
  and `progression-browser-frame.json`. Synthetic fixture coverage and browser
  automation do not substitute for participant usability sessions.
- Foundry rerendering no longer destroys the target between click and double-click.
  New default placements have room for the actual card width. Existing user
  placements remain intact. Older pinned worlds hide unsupported shared-edit and
  value-copy hints.
- 20 unchanged native reads preserved the exact frame and added zero pin bytes;
  see `progression-read-stability.json`. The progression's largest successful
  operation retained 7.10 MiB, with 37.38 MiB added over the 29-check sequence.
  This is bounded observed work, not full memory/endurance acceptance.

The new native features were verified in an isolated world on ports 8162/8163.
The user's v6 world on 8161 retains its pinned native engine and all existing
objects. Its host has the bounded generation recovery fix; the new native
contracts have **not** been installed by rewriting that world's journal.

Diagnosed fixture failures were a Foil method-chain layout error and Goo's
ASCII-only text measurement. The latter is still a product limitation. Author
instructions now state it explicitly; user data is never silently transliterated.

Earlier verified evidence (kept with its original scope):


- 15 Python transport/context tests: typed Decisions API, cancellation, bounded
  domains, dynamic hole questions, exact source/provenance and unknown-tool rejection.
- 27 native assertions passed in
  `~/.local/share/shrine/checks/3234ac586be8/run-wlvuc1y5/results.json`, including
  exact opaque field/type references and preserved open-position provenance.
- 13 live native/OpenRouter checks passed in
  `grove-medium-typing-check/typing-acceptance.json`: actual compiled role/codec
  revisions, detach retaining the requirement and prior anchor, a Jev question
  generated from that exact hole, inference causing no mutation, and native rebind
  preserving source and field identities. The live distribution favored restoring
  the previous boundary (0.98) and the original subject (0.72); neither was used
  as a substitute for the successful native recheck. Source, frame, receipt and
  logs are retained; the successful disposable store is removed after shutdown.
- Earlier v6 native live acceptance passed 25 checks, including four-level
  composition, action propagation, detach/rebind, stale and incompatible edits,
  native historical undo, and zero pin growth across 20 unchanged reads.
- Actual browser intent generated a lap counter through OpenRouter-selected
  `anthropic/claude-sonnet-5.5`; Shrine compiled it on its first attempt and its
  native action changed the displayed count. Receipt:
  `grove-medium-v6/authoring/attempt-465776f2dce1491d80d17d342e108272.json`.
- Jev live requests took 0.228–0.733 seconds in these few observations. The
  operational-typing review is recorded in `grove-medium-v6/jev-operational-typing.json`.
  This tiny sample is not a latency SLA or a calibrated correctness evaluation.
- Restart preserved the exact v6 native frame and its verification read added
  zero pin bytes.

The v5 storage regression was caused by raw compiled closures embedded into each
undo/world journal record. Undo now stores `(address, data-case)` and resolves
existing native history. v6 author/edit growth is bounded in observed acceptance
(roughly 6–7 MiB per source compile, below 0.5 MiB for structural/action edits),
not the previous escalating full-world copies. Endurance targets remain unproven.

Limitations remain explicit: existing pinned v6 has the prior frame contract,
so the new compiled-role export is tested separately and older frames expose
source with a stated metadata gap. General subset inverse lifting, structured collection construction, retained user
commitment checks, shared action forwarding,
and learned transformation crystallization are not complete. The model sometimes
creates a duplicate on refinement; author guidance now requests in-place identity
preservation, but this needs a native invariant rather than a prompt-only guarantee.

No commits, pushes, or replacement of historical native engines occurred.

## Working first interaction

The initial surface failed the user's experience review: it looked like a
scripted demonstration, and inspection depended on specially wired buttons.
That feedback is a failed Stage 2 usability signal, not a completed gate.

The latest user review also rejected the page-like component flow. The default
workspace now uses an infinite canvas with local pan, pointer-anchored zoom,
draggable subjects, keyboard arrangement, Fit, and restored camera/positions.
New concepts are real native constructions: a pending card appears immediately,
then its declared Grove editor opens in that position and focuses the first
input. Command-Enter invokes the sole declared action when unambiguous. Saving
returns to the same subject. No browser handler reimplements the domain action.

Presentation experiments now sit on this same plane beside their exact subject,
with a visible presentation connection. They can be dragged or moved by keyboard;
returning to the subject restores focus. Successful native evaluation exposes
the comparison, while reopening retains source and findings. Inspector context
is dismissed while the local instrument is in use, without changing native state.
Positions are not namespace addresses. No semantic relation is inferred from
proximity or a drawn line. Offscreen presentations load on demand, serially.

The current revision removes the synthetic concept graph, canned headline and
hardcoded reservation timeline. Equipment surfaces and schedules project the
actual native frame. The experiment timeline uses a selected reservation's
identity and times; selecting another record does not rewrite the experiment.
The six declared cases remain available under Rule checks, explicitly labelled.

Inspection is now a separate local interaction mechanism: hold Option and hover,
or toggle with Command-I and use hover/focus navigation. Enter pins a context.
Records, relation endpoints, derived outcomes, commitments and rule controls carry
explicit occurrence bindings. Inspection consumes action gestures so it cannot
also create records or change a range control. Its fixed panel does not reflow
the workspace. Removed pinned occurrences are not redirected to another row.

The default workspace now discovers native Grove roles and Goo presentations.
An ordinary `canvas.grove` template creates concept subjects; its declared view
and edit action are rendered and invoked without a concept-specific browser
handler. The separate equipment instrument still consumes its older `canvas/1`
frame adapter. Complete dependency tracing and agent source authoring remain
unfinished. Saving a concept's intention does not invoke an agent.

The native Goo bridge and catalog are shared with Explorer, without mounting
Explorer's development routes in the authenticated workspace. Rendered
occurrences carry exact subject, slot, presentation revision, source position
and declared control route. Inspector selection includes the presentation
revision, so a recompiled tree cannot redirect an old pinned occurrence.

An actual browser save exposed a substrate bug: replacing an installed root
re-ran Pact initialization and restored its seed values. `goo_runtime/change`
now sends only changed slots through native `poke`/talk. Equal results do not
append subject history. Removal from a behavior-owned record explicitly
requires an authored native operation; it is not silently treated as a replace.
The regression includes an installed root and surviving child, rather than
only an unformed test record.

Local drafts survive unrelated journal progress, source changes and concurrent
native edits. A stale draft shows its original, current and proposed values
before an explicit review. Acknowledging an older submission cannot erase typing
done during the save. Cross-subject navigation is not reversed by a late save.

Source inspection is scoped to a published presentation and exact revision.
A failed or pending source scan is reported rather than substituted for the
installed implementation. The agent's `read` and `source` tools use the same
native projection and source check as Canvas. Live acceptance is recorded below;
this capability is not evidence that localized agent authoring is connected.

Native presentation refinement now extracts the selected Grove view and imports,
compiles a bounded source edit through Rex/Grove, and renders an ephemeral
comparison through the shared Goo bridge. The original receiver, view slot and
native action/input placements must remain unchanged. A behavioral edit is
reported as requiring a separate assessment. Candidate controls cannot act on
live data. Invalid source, stale publications and changed input targets reject
without touching installed behavior. This is scoped structural checking, not a
claim of universal equivalence between presentation programs.

Canvas and actual MCP `eval` return the identical native comparison. The renderer
also accepts a bounded width (160–1600px); the canvas requests 316px. Older pinned
worlds retain their existing capabilities and width. Source drafts are currently
browser-session local: general persistent source candidates and their publication
remain unfinished. The development world's native engine was not replaced.

Normal-browser access exposed a host bug: every world used `canvas_session`,
but cookies are not isolated by TCP port. Test-world logins could overwrite the
development login, and every host restart also rotated browser authority. Each
world now has a private persisted browser session and a unique cookie name.
Cookies last 90 days; host restart no longer requires a new browser login. The
macOS Grove Canvas launcher reads the current private connection and opens the
default browser. Actual launch into Firefox was verified with native records
visible at the clean URL. Host checks, origin checks and restricted agent
authority remain enforced. No anonymous administrator endpoint was added.

Availability runs in native Foil over shared Shrine reservation records. The
browser provides a draggable/keyboard-operated handover interval, native case
comparison, exact-result inspection, source disclosure, candidate publication,
ordinary booking, and an inspector for retained intention. No browser or Python
availability evaluator exists.

The automated browser journey ran against the actual native owner:

1. Preview 15 and 20 minute intervals without installing them.
2. Inspect a result and follow its exact blocking reservation.
3. Demonstrate the same-person exception and publish it with a retained check.
4. Propose removing it: the remembered example fails and publication is disabled.
5. Repair that existing candidate through real MCP stdio, then publish in Canvas.
6. Create Sam’s Camera B reservation using the installed rule.
7. Preserve an unfinished 20-minute experiment and typed intention across booking.
8. Restart with the installed rule, records, commitment, intention and open
   candidate intact. The canonical state fingerprint matches exactly.

This is the first instrument, not a general visual Grove editor. Inspector text
records intention; it does not yet invoke an authoring agent. MCP is read and
candidate-continuation only. Grove/Goo instrument extraction and localized source
creation remain subsequent stages.

## Native integrity

- Scoped retained checkers have provenance and pinned native implementations.
  Endorsed demonstrations promote atomically on publication. Every later
  candidate is checked against old commitments; it cannot erase them.
- Native publication uses exact candidate/basis checks. Duplicate event IDs are
  idempotent; conflicting reuse is rejected. Separate agent authority cannot
  publish. Ordinary application actions use installed behavior.
- Candidate preview is ephemeral; saved candidates and real mutations persist.
  Unchanged reads do not change the native case, pin file or database.
- Outcome explanations come from the native result and exact reservation ID.
  Live comparison cases and frozen commitment inputs are visibly distinguished.
- Source disclosure reads the source captured with the installed native world.

## Runtime work and current blocker

Restart originally bypassed Reaver’s process-local bytecode compiler installation.
`eden/world/v4` restores the pinned compiler before serving the saved world; this
avoids resuming the application in the interpreter. Historical formats are not
reinterpreted. A dense-live-heap allocation regression also gained a native test
and proportional collection headroom.

The first 10,000-read run failed memory acceptance: the final half grew by
507,333,760 charged bytes, while the native case and disk stores stayed unchanged.
Completed HTTP actors retained their minimum semispaces. The new actor lifetime
patch collects terminated Spawn actors unreachable through live actors, embedder
roots, handles or queued capabilities. IDs never reuse. C-created actors remain
inspectable until scheduler teardown. Both deterministic and multithreaded
lifetime tests, plus AddressSanitizer actor/replay suites, pass.

A second whole-application endurance run still shows growth. Resource acceptance
is **open**. The actor fix is necessary but insufficient; the remaining retention
path is being investigated. The aggregate memory guard remains active. No live
pin was truncated and no failure is being relabelled as a pass.

Further diagnosis found growing update stacks in long-running actors. A fresh,
unaliased tail continuation now skips an unnecessary memoization root; the native
fuel-pause regression fails before that patch and passes after it. The whole-app
probe still grows, so this is not the complete fix. Existing Reaver sequencing
lowering/optimized compiler paths need investigation before changing a pinned
world format. Temporary update-argument logging has been removed from source.
Opt-in lifetime counters only inspect deterministic, non-MT scheduler state.

A disposable P5 compiler installation failed with `codegenOpt: unbound local C`
before serving HTTP. Its source, log and sampled stack remain in
`checks/canvas-p5-world`; the diagnosed runtime store was discarded. The source
continues to install `codegenLaw` in `eden/world/v4`. No active client was switched
to the experiment, and optimized compilation is not a verified memory fix.

A clean rebuild was necessary: a copied build directory's dependency files
referred to the original directory and failed to rebuild all structure consumers.
Fresh release evaluator, thread, actor and replay suites pass; evaluator and
replay also pass under ASan. Do not reuse copied build dependency metadata.

## Evidence on this machine

Receipts live under `~/.local/share/shrine/checks/` and runtime logs under
`~/.local/share/shrine/build/canvas-gc-headroom/`.

| Check | Evidence / result |
| --- | --- |
| Native Goo runtime / Grove template baseline | 20 / 8 checks, `run-eoqduwl3` |
| Native commitments / booking | 10 / 9 checks, `run-mtpxllzg` |
| Native Goo actions and installed-root regression | 28 checks; `3234ac586be8/run-ya2ist40/native` |
| Native Canvas lifecycle and generic surface dispatch | 34 checks; `3234ac586be8/run-ya2ist40/native-canvas` |
| HTTP native lifecycle and idempotence | `canvas-v4-journey.json`; real owner, not mocked frames |
| Browser lifecycle | `canvas-v5-browser.json` |
| Actual MCP repair | `canvas-v5-mcp.json` |
| Exact restart continuity | `canvas-v5-restart.json` |
| Host authority / transport | 15 tests, `canvas-transport-final.log` |
| Revised transport/module delivery | 20 tests; scoped source, native subject reads, principal boundaries |
| Draft and inspection state | 9 browser-module tests, including typing during an in-flight save |
| Local inspection interaction state | 4 tests: hold, release, pin, follow, and ordinary-use isolation |
| Generic native edits and actual MCP | `canvas-native-surfaces-v2.json`; exact authored control, idempotence, stale rejection and shared source |
| Generic native browser | `canvas-native-surfaces-v2-browser.json`; keyboard inspection, exact slots, authored source, concurrent edit and retained draft |
| Native presentation compiler | 14 checks; `3234ac586be8/run-impmi2d0/native` |
| Canvas native refinement and lifecycle | 40 checks; `3234ac586be8/run-ki_a73_0/native-canvas` |
| Shared Explorer/Goo regressions | 48 checks; `3234ac586be8/run-ki_a73_0/native-explorer` |
| Width, native compilation and actual MCP parity | 10 live checks; `canvas-spatial-v1.json` |
| Infinite canvas and source experiment browser flow | `canvas-spatial-browser.json`; native creation/edit/save, keyboard inspection, retained geometry/drafts, movable attached experiment, exact native projection unchanged |
| Current browser state / transport | 13 geometry/inspection/draft tests and 27 transport/session/launcher tests pass |
| Normal-browser access | `canvas-browser-access.json`; actual macOS launcher opens authenticated Firefox with native subjects |
| Revised browser surface | Focus inspection, no layout shift (920px before/after), protected range input, normal range evaluation, exact reservation selection; `canvas-inspection-browser.json` |
| Runner tests | 40 tests, four skipped |
| Enki actor lifetime | 28 tests / 51,359 assertions, release and ASan |
| Enki replay | 7 tests / 114 assertions, release and ASan |
| PLAN core / thread / eval | Passed on the headroom engine before actor lifetime additions |
| 50 serial native compilation cycles | `3234ac586be8/run-0isoawaz/acceptance.json`; zero successful stores retained |
| First read endurance failure | `canvas-v4-10000-reads-failed.json` |
| Current read endurance | `canvas-v5-10000-reads.json`; status and charged samples retained even on failure |
| Further failed probes | `canvas-lifetime-probe.json`, `canvas-tail-fixed-10000-reads.json`; interrupted growth is not a pass |

The 50 cycles compile distinct minimal Foil functions and invoke them through the
native compiler. They are a disposal regression, not a bound on arbitrary app
compilation. Automated browser checks are not participant usability sessions.

## Remaining work

Resolve whole-application memory growth, rerun endurance and verify sustained
operation. Review the first interaction before generalizing. Then extract native
presentation primitives through the existing Grove/Goo action path, implement
localized agent authoring and full tools parity, and complete the planned security,
undo/retirement, resource and usability gates. Five developer sessions, one
non-developer diagnostic and two real work sessions have not occurred. No result
here establishes the 100-concept/250-relation performance target.
