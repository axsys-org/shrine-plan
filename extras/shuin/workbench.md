# Namespace change workbench

Server commands below run from the Reaver root. Cargo commands and native
render artifacts refer to the separate `shrine-goo-native` checkout. Historical
validation counts are not a substitute for the current branch’s PR checks.

The workbench owns one open draft set per registered target. Sources and cases
are ordinary editable records; the authoritative lifecycle is under
`/<node>/weft/change_workbench`. Goo supplies the forms. The native renderer has
no target-specific build, test or activation code.

## Records and authority

A `change_workbench/registration` identifies a control record, a row of source
units, a test subtree, output boundaries, a versioned adapter record, immutable
compatibility policy, activation kind, explicit public exports and required namespace authority.
The control record and its registered sources constitute the open change set;
protected draft generations and each candidate capture its exact revisions and base.
Registrations and adapters are trusted records. Agent tools protect `/weft` and
registered control records even under broad write grants. Source records accept
Build and Run tests commands; Publish is accepted only on the control record.
The caller cannot choose another destination through an action argument.

Protected draft revisions advance when source bytes change, including an edit
followed by a revert. UI status updates do not count as source edits. A build
captures these revisions, the registration, adapter and namespace dependency
versions, the compiler's complete generated output records, expected live
predecessors and an isolated namespace. The candidate is stored before tests
run. Explicit private preview aliases are outside live Goo/stencil discovery.

Tests capture the current case subtree and fixture versions, run against the
candidate namespace and store a receipt naming that exact candidate. Fixture
paths cannot overlap publication output boundaries, so a fixture cannot replace
the artifact being tested. Cases can
change behavioral expectations; they cannot weaken the registered compatibility
validator. Changing cases or fixtures requires another test run; changing source,
compiler dependencies or registration requires another build.

The adapter returns an activation plan. The implemented executor accepts atomic
namespace publication; additional migration or handover requirements are rejected.
Publication uses the stored records, without invoking the compiler again. All
source, dependency, case, fixture and predecessor checks must still hold. A failed
operation retains the active outputs and the editable draft.

## Implemented kinds

The stencil adapter validates the registered declaration, parent/result roles and
required text argument contracts. Each editable case supplies typed slot JSON,
a captured parent, deterministic time, accept/reject and expected typed output
slots. Every accepted result is checked against the fixed result contract and
clock slot. Testing never commits the returned child. Diagnostic output previews
use explicit UTF-8 byte escapes for non-ASCII text to remain renderable with the
pinned native font profile; comparisons still use the original typed values.

`post_message.grove` is the bootstrap source for the first stencil target. It
imports the existing chat roles. Its independently owned implementation module
is `/lib/shuin_post_message`; a registered export preserves
`/gov/shuin_chat/post_message` without overwriting the chat-owned module root.
Exports are part of the same atomic output set as compiler metadata.
After launch, its namespace source record owns edits. Agents continue using
ordinary stencil discovery and exact-version creation. A stale discovery rejects
creation and directs the agent to rediscover; publication itself enqueues nothing.

The Goo adapter checks the registered receiver, presentation slot and editing
control keys. Tests lower and render the candidate through the same native semantic protocol
used by `/shuin/render`, against captured examples, and
assert its semantic constructors and expected values. The reflection source owner
and presentation links now use this lifecycle; there is no reflection-specific
registered draft/publish job.

`shuin_workbench/register` installs another target using an existing adapter and
updates namespace navigation. No Rust change or application-path branch belongs
in the shared lifecycle.

## Scope

This is a live-session infrastructure. The compiler adapter currently builds
Grove source units. Dependency capture is deliberately conservative: local
publication and compiler-library revisions, the selected system publication and
adapter version. Unrelated publication changes can therefore require a rebuild.

Publishing a new function does not replace a running closure. Saved-world
recovery, service handover, arbitrary Foil module builds, schema migrations and
native-runtime replacement remain separate adapter/executor work. The activation
plan carries requirements so unsupported changes fail before activation.

## Validation

`extras/shuin/test-workbench.py` exercises disposable-world lifecycle and stale
receipts. Its `--mock` option adds a held provider response across publication,
rediscovery and reuse of the same agent. The native reflection test follows the
shared control record for testing and publication while retaining the note draft.

## Running acceptance

The kernel lifecycle and both target adapters are included in this checkout.
Boot the in-tree mount once; subsequent supported changes publish in that session.

Run acceptance against a disposable test world (with the local mock on port 8343):

```sh
python3 extras/shuin/test-workbench.py --server http://127.0.0.1:8383 \
  --mock http://127.0.0.1:8343 --output artifacts/workbench-validation.json
GOO_DISPOSABLE=1 GOO_TEST_SERVER=http://127.0.0.1:8383 \
  SHUIN_ARTIFACTS="$PWD/artifacts" \
  cargo test --offline -p shuin-widgets --test reflection \
  -- --ignored --nocapture --test-threads=1
```
