# Hyp: nodes controlled by namespace records

Hyp runs independent, socket-free guest namespaces in a local supervisor.
Each guest has its own sovereign, selected system publication, journal and
Lain dependency index. The scheduler holds these values privately; control
records contain an opaque instance reference, never a native actor handle.

## Run

```sh
WISP=/path/to/working/wisp extras/x/hyp --check
WISP=/path/to/working/wisp extras/x/check --mount hyp
```

From the repository root, `extras/x/hyp` compiles the real Grove schema,
publishes it under `/<host>/gov/hyp`,
installs its tree at `/<host>/hyp`, and creates two guests through control
record mutations. It writes into one guest through a request record and
checks a `/hyp/dev/0x22/hello` read through the live supervisor actor. Both
commands are finite checks; they do not leave a background server running.
`--node` selects the host identity; the default `0x11` is a local fixture.

For embedding, `hyp_app/boot` publishes and installs the control app,
`hyp_app/serve` returns the live supervisor capability, and
`hyp_runtime/access` plugs into the existing Helm supervisor loop. Native
`hyp:start` builds a complete demo and returns its supervisor capability.
The demo guest authority is `0x22`; aliases and identities are separate.

## Namespace API

```text
/<host>/hyp/instances/dev     config, want, epoch, observed?
/<host>/hyp/mounts/dev        instance, generation
/<host>/hyp/requests/1        /sys/req, /sys/res?
/<host>/hyp/watches/root      instance, query, epoch, res?, revision?

/hyp/dev                     virtual entry into the selected guest root
/hyp/dev/sys                 that guest's selected system publication
/hyp/dev/0x22/hello           that guest's ordinary record
```

Short slot names denote declarations in the published Grove schema, such as
`/<host>/gov/hyp/config`. They are shared vocabulary, not children of the
instance record. `/sys/req` and `/sys/res` use system slots.

### Create and run

Make `instances/dev` with these typed values (illustrative notation):

```text
config = hyp/config(child_identity, trusted_system_pin,
                  initial_sovereign, empty_device_policy)
want   = hyp/wanted/running
epoch  = 1
```

The scheduler validates the authority, confinement and system publication,
allocates a new instance, and writes `observed = hyp/observation(epoch,
instance_ref, running)`. Configuration is immutable after creation. Invalid
configurations reject the host mutation. Explicit device configurations
currently reject; guests do not inherit the host's feet.

Poke `want` with `stopped` or `running` to suspend or resume execution.
A change increments epoch; a repeated value does not. Stopping retains guest
state and queued requests. Resuming drains pending work. Epoch is a lifecycle
intent sequence; ordinary revision history still belongs to Shrine.

### Mount an alias

Make `mounts/dev` with `instance = instance_ref` and `generation = 1`.
Rebinding increments generation. Several aliases may name one guest.
Culling a mount removes only the alias. It does not delete guest data.
Culling an instance control record also retains its existing guest; recreating
that control path allocates a fresh reference rather than reusing old work.

Explicit supervisor reads under `/hyp/dev/...` select the guest namespace.
Host subtree traversal never expands a guest, and guest transactions never
advance host ancestor cases. Requests use canonical guest paths, preserving
slot identities, brands and references. Version arguments belong to the guest.

### Submit work

Create an immutable `requests/1` record:

```text
/sys/req = hyp/request(instance_ref,
    helm/card/step([child_identity, 'hello],
        writ/poke({ /sys/lede: text("Hello") })))
```

The scheduler executes the ordinary guest Helm transaction and writes one
`/sys/res`: `accepted(revision)`, `rejected(reason)`, or `page(query, value)`.
`helm/card/peek` and `helm/card/install` use the same request envelope.
Requests to stopped guests remain pending. Missing instances produce a
rejection receipt. Aliases are resolved before request construction: rebinding
cannot redirect a request that already contains an instance reference.

Guest rejection does not undo host submission. Completed request records are
not executed again. The updated guest state and receipt are retained together
in the supervisor's next immutable runtime value. A new request path is a new
invocation, even if its payload is identical.

### Maintain a standing read

Make `watches/root` with an instance reference, `query = hyp/query([], y,
none)`, and epoch 1. The scheduler projects the committed guest view into
`/sys/res` and records its guest revision after work is processed. Other host
applications can subscribe to this ordinary host record. Unchanged answers
do not mint new host revisions. Culling the watch cancels it.

## Files and enforcement

- `main.grove`: codecs, roles, norms, pure actions and empty installation tree.
- `main.foil`: nominal protocol values and codecs.
- `runtime.foil`: validation, independent guest state, scheduling and routing.
- `publication.foil`: pinned Foil prelude used to compile the Grove aliases.
- `boot.foil`: publication, installation, embedding and actor integration.
- `tests.foil`: lifecycle, isolation, routing, mutation rejection and watches.

The native Grove compiler's `prepare-with` selects a prelude from the same
prepared publication. Hyp's transparent aliases retain the original Foil
moments. The default Grove compiler prelude is unchanged.

Grove roles enforce record shapes. The Hyp supervisor additionally enforces
immutable configuration/requests, driver-owned observations/results, allowed
collection paths, and known mount targets. These rules apply to writes through
the Hyp supervisor, including ordinary `make` and `poke` mutations. Access to
its raw underlying namespace value is trusted embedding code, not a bypass
exposed to its clients. Pure Grove actions are published definitions; runtime
normalization also supports direct record edits without requiring `/sys/op`.

## Current execution boundary

This is an in-process scheduler inside one Helm actor, with separate guest
supervisor state. It does not spawn a native process or device actor per guest.
All guest progress comes from submitted requests. Native networking, guest
feet, durable process restart, checkpoint/restore, destructive deletion and
recursive hypervisor installation are not implemented. Ordinary HTTP Explorer
routing and boundary-listing UI are not extended by this app; explicit Helm
reads and request records are the supported mount interface.

Runtime values and journals last for this run. The in-memory receipt behavior
is not a claim of crash-safe transport delivery. Instance references and
control epochs are not cryptographic capabilities. This executes trusted local
code under the existing runtime, as described in the
[hypervisor proposal](../../../../doc/hypervisor.md).
