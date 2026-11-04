# net: networked names

The generic substrate for one world observing another's published names. It knows
publishers, names, revisions and whether a judgment has fallen behind a revision.
It knows nothing about any business.

## Records

```
/<self>/net/names/<publisher>/<name>/current   written only by the shrine-mesa sidecar: the viewed slots of
                                                the acquired revision, plus remote_case, publisher, source (name@case)
/<self>/net/names/<publisher>/<name>/seen      written by whoever judged against a revision: remote_case is the
                                                revision the judgment relied on
/<self>/net/stale                               a cell over the whole names subtree (z care); never stored
```

`<publisher>` is the publisher's node id (a hex segment such as `0x11`); `<name>` is one path
segment the publisher chose. The acquired revision is source-attributed, not verified: the
remote epoch and case are recorded, and until Mesa and Groundwire the signature is the
sidecar's to check.

## Publications (phase 1)

What a world exposes is a record under its own root, written by the owner or an agent on the
owner's behalf, never by the sidecar:

```
/<self>/net/publications/<name>   one name this world exposes; <name> is one lowercase segment
   path    required, text         the local path whose revisions are exposed, e.g. /0x11/pub/aluminum
   to      required, text         "public", or the node id of one peer such as 0x12
   slots   optional, text         the slot names to expose, space-separated; absent means every slot
   note    optional, text
```

The sidecar lists `/<self>/net/publications` (care `y`), reads each child, and watches the record
at `path`: every new case is bound under the Mesa name `<name>@<case>` and announced to the peers
`to` names (every configured peer for `public`). Nothing not listed here is ever bound. Visibility
at this libmesa commit is traffic policy, not authentication: every bind is `Access::Public`, and
`to` decides only who is told.

The role's contract is judged on every update: a poke or remake that leaves a publication without
`path` or `to`, or with either not text, is refused (`curb_need`, `curb_type`). The first write of a
record under the tree is not judged: the tree stamps the contract onto the record in that same write,
and the kernel treats a new contract as adopted over the record it arrives with (`guard_diffs` in
`lain_poke.foil`). The sidecar therefore skips a publication that lacks `path` or `to` and says so in
its log; the next complete poke makes it a publication.

On the acquiring side `/net/names/<publisher>/<name>/current` is written once per acquired
revision: a sidecar that restarts, or a notice delivered twice, compares `remote_case` with what
the world already holds and writes nothing for a revision already acquired.

## Outreach, answers and self (phase 2)

Three more trees under `/<self>/net`, so that an inquiry can reach a mailbox and come back as a record
under the answerer's own name. The host service (`shrine-mesa host`) reads and writes them; it knows no
business terms.

```
/<self>/net/self                      this world's own statement, seeded by the tree, no contract:
   name, contact, verified, publisher   poked by the host (who host) and the owner
/<self>/net/outreach/<id>/request     an agent's proposal: to (a mailbox), about (a local path), note
/<self>/net/outreach/<id>/approval    the owner's approval: only an event written by `owner` counts; note optional
/<self>/net/outreach/<id>/sent        written by the host once the mail went: at (a time), note
/<self>/net/answers/<id>              on the answerer's side: text, to (the inquirer's node), about (the
                                       inquirer's path); each change is a case the inquirer acquires
```

One norm two deep covers outreach (`/[id=@tas]/[kind=@tas]`; the parents are structural and stay
empty, as under `/names`), with one role whose slots are all optional: the three kinds are statements,
nothing is special-cased, and "an approval is required before mail goes out" is the host's rule about
writers (it tails the event log and acts on an approval whose `who` is `owner`), not a contract. An
answer requires `text` and `to` on every update; its first write is unjudged like any create under a
`#like` tree. `/self` is a tree without `#like`, so its pokes are free.

Two things the probes on a light world showed (2026-11-03). A slot named like an import alias resolves to
the import: `text: text` with `#import text=lib/grove/types/text` made the lash look for the type's own
path and refuse every poke with `curb_need`; the key is spelled as an absolute cord, `"/text": text`, which
`grove_roles/slot` takes literally. And a role whose slots are all optional stamps no contract: records under
`/outreach` (and under `/names`, whose `observed` role is all-optional too) carry no `/sys/lash`, so
nothing about them is judged, not the norm's `#here` shape (records one, two and three segments deep
and an uppercase id were all accepted), not a slot's type (`to: 7` was accepted). A role with a required
slot stamps the lash on the record, and every later update is judged: presence of the required slots
(`curb_need`) and the type of every present slot, optional ones included (`curb_type`); `answers` and
`publications` behave so. The host validates what it acts on (`to` must be a mailbox) and never assumes
the shape.

## Deployment

The runtime binds a world's HTTP port on every interface at this commit (`lsof` shows `*:<port>`;
`x/eden` passes only the port), and the MCP mount is unauthenticated, so on a pilot host the firewall is
the boundary: open 22, 80 and 443, nothing else. nftables, for one:

```
table inet filter {
  chain input {
    type filter hook input priority 0; policy drop;
    iif lo accept
    ct state established,related accept
    tcp dport { 22, 80, 443 } accept
  }
}
```

The host service listens on loopback and Caddy terminates TLS in front of it (the block is in the
shrine-mesa README); the Mesa sockets are loopback on one host. `demo/phase2.py --firewalled` asserts
from a second address that the world ports are closed; without the flag it reports which are open.

The answer travels by phase 1: the host writes `/<answerer>/net/publications/<id>` with `path`
`/<answerer>/net/answers/<id>` and `to` the inquirer's node, and the inquirer's service lands each case
at `/<inquirer>/net/names/<answerer>/<id>/current`. The host's own records (invitations, claims,
passkeys, token hashes) are its registry file, not records in a world; what a world knows of itself
is `/self`.

## Reading the overlay

Over MCP, with the node spelled: `mcp/read path=/x/<self>/net/stale care=y`. Each child is
`/<publisher>/<name>` with `current` (the acquired revision), `seen` (the judged one),
`publisher` and `name`. A name with no `seen` was never judged and is not listed; a name
whose `seen` equals `current` is not listed. `/c/x/<self>/net/stale` shows the cell's context,
including `/sys/tack/case`, the input subtree's current case.

## Why the cell is written from activation

A Grove `@tree` seed accepts only a y-care tack, and the names subtree is three deep. The
`@sewn` declaration `stale` is published with the Grove template at `/<self>/gov/net/stale`;
`activation.foil` instantiates the template at `/<self>/net` and then writes the cell record
`{sys/weft: (safe 1 .x /gov/net/stale), sys/tack: (safe 0 .z /net/names)}` through
`grove_install/change`.

## Running it

```
python3 x/eden --node 0x12 --mount net --mount mcp --mount probe --port 8302 --world <dir>
```

`mount.json` depends on `codecs` for the Grove `text` type.

## Phase 0, measured (2026-11-02)

`demo/phase0.py` boots two worlds from this checkout (A `0x11` with `mcp probe`, B `0x12` with
`net mcp probe`), starts the shrine-mesa publisher beside A and the reader beside B
(`/Users/ianchanner/shrine-mesa`, commit 462745f, libmesa 2e94a13), and asserts the loop:

| what | measured |
|---|---|
| A's revision acquired in B (flow notice, signed named read, world write) | 0.16 s (revision 1), 0.11 s (revision 2) |
| `/x/0x12/net/stale` listing the name after A's next revision | 0.14 s after the write in A |
| `kill -9` of B's runtime, restart, overlay unchanged | 2.6 s |
| re-judging at the new case | the overlay empties |
| runtime footprint after the run | A 69 MB, B 197 MB |

What is real: the acquisition is a publisher-signed Mesa read verified by the reader's engine, the
notice a durable flow with receipts, the overlay a kernel lens over records, persistence the
world's own. What is not yet: the bind is `Access::Public` (libmesa's signed-public profile refuses
any other access at this commit), there is no requester authentication or encryption, the sockets
are loopback, and the publisher keys are local seed files.

## Phase 1, measured (2026-11-03)

`demo/phase1.py` boots A (`0x11`) and B (`0x12`), both with `net mcp probe`, writes A's publication
`{path: /0x11/pub/aluminum, to: 0x12}`, starts one `shrine-mesa serve` beside each world
(`/Users/ianchanner/shrine-mesa` eb7918e, libmesa 2e94a13), writes 500 revisions at about twenty a
second while killing with `-9`, at random, each world's runtime and each service five times (a service
stays down for three revisions and restarts from its state directory; a world is rebooted at once), and
compares B's acquired history with A's through pinned reads of both records.

| what | measured |
|---|---|
| A's 500 cases in B | 500, none lost, none duplicated, in order, every slot matching |
| the run, first write to last, with the twenty kills | 48.5 s; 5.8 s more to drain after the last write |
| revision 1 in B, counted from the services' start | 0.22 s |
| named reads on B, signature and every LSS leaf verified (502 reads across 6 lives) | 12.6 ms on average, 5.0 ms at best |
| stalled announcements or reads, across 6 lives of each service | 0 |
| notices delivered again after a kill between the world write and the delivery commit | 4, each recognised and not written |
| world restart after `kill -9` | 1.6 to 3.6 s |
| first boot; footprint after the run | 41 s and 88 s; 100 MB and 240 MB RSS |

The first run against the service's first commit (609c14a) did not pass: the publisher bound every
case in order but announced about four at a time, waited for them to settle, and slept a second on
every stalled announcement, so B lagged hundreds of cases behind. eb7918e moved the world calls off
the service loop, widened the flow window to 32 with look-ahead binds, and rearms a stall after 50 ms;
the run above is the fixed service. What the service holds after 500 revisions is one binding and one
fence per publication (`RetireBefore` after the peer settles), and a store rotated to a new flow
generation every 40 rows, since `mesa-store` frees nothing below its 16,384-row cap.

## Phase 2, measured (2026-11-03)

`demo/phase2.py` runs the whole claim on one laptop against `shrine-mesa host` (`/Users/ianchanner/shrine-mesa`,
the host commit named in its README): the host boots A (`0x11`, registered with `add-world`), an agent writes
a need and an outreach request in A over loopback, the owner approves it through the host's token route, the
host mails one link; a software WebAuthn authenticator (P-256, attestation `none`) stands in for the
stranger's browser.

| what | measured |
|---|---|
| A booted by the host | 43 s |
| the owner's approval event seen, the invitation mailed, `sent` written | 0.34 s |
| the recipient world provisioned behind the answer: new node `0x20`, seed, directory, boot | 46 s (one run of the first boot took 239 s) |
| the answer acquired in A at `/0x11/net/names/0x20/o1/current` | 46.7 s after the POST, all but a second of it the boot |
| the claim link: mailbox verified, passkey registered, session open | 0.07 s |
| the owner's edit acquired in A as the next case | 0.35 s |
| the token: reads its own world; another world 403; absent or unknown 401; `who` forced to `owner` | as required |
| `kill -9` of the host, both worlds and both services; the host restarted; both worlds back | 4.3 s |
| a fresh client, no cookie: passkey sign-in, an edit, acquired in A | 0.44 s |
| A's history of the acquired name after the run | exactly the three answers, newest first |
| unknown routes on the host, a session used at another node | 404 |
| the world ports on the machine's LAN address | open: the runtime binds every interface (see Deployment); the host and Mesa sockets loopback only |
| RSS, two worlds, before the kill and after the restart | 756 MB and 393 MB |

The first run did not pass: the acquired revision carried the answer's `/sys/lash` (the contract a role with
required slots stamps) and A refused the write ("`/sys/lash`: {type, value} with type str, bool, nat, path or
reference"); the service now drops system slots on both sides, since a contract is the publisher's, never
content. What is real: the stranger's words are a record under a node of their own, acquired by the inquirer
through a signed Mesa read, kept across a kill of everything, and changed only with the passkey; what is
provisional, and said on the claim page: the host holds the publisher key, and a verified mailbox is the pilot's
claim of a business.

## Relationships, /our and /her, wakes (2026-11-04)

The relationship machinery adds no Grove: every record below is free, written by a named principal,
and its paths are the convention the relationship skill states
(`extras/mounts/mcp/skills/shrine-mcp/relationships.md`), known to no code in the kernel. The host
(`shrine-mesa host`, its README section "Relationships") is the external bridge: mail and calls in and
out, prospective worlds, the wakes, the agent.

```
/<self>/needs/<name>                           the owner's words; /needs/<name>/approval a standing approval
/<self>/relationships/<peer>                   own record: contact, refers → a need, peer (a node when known)
/<self>/relationships/<peer>/conversation/<id> every message either way, by the channel's principal: mail,
                                               phone, web, or the agent
/<self>/relationships/<peer>/observations/<n>  one statement off one piece of evidence, source → it, pinned
/<self>/relationships/<peer>/unresolved/<n>    open questions with a due
/<self>/judgments/<peer>                       an ask cell over /relationships/<peer> (care z), beside the
                                               folder: inside it is a cycle; /judgments/<peer>/result the answer
/<self>/agent/wakes/<id>                       when the agent wants to run again: why, at | on | cell
/<self>/agent/runs/<id>                        every run the host made, by host
/<self>/her/<peer>/<name>                      what the peer publishes to this world, landed by the sidecar
/<self>/our/<peer>/<name>                      what this world publishes to the peer; the publication record is
                                               /net/publications/<name>_<peer> {path, to}
/<self>/attention/<n>                          notes the host mails to the owner
```

On a prospective world (reserved by the host for a mailbox at first contact), each inquirer's agent
writes only under `/proposed/relationships/<inquirer>/…` (inquiry, conversation, `proposed_terms/<name>`,
`proposed_capabilities/<name>`) through a token scoped there, revoked at the claim; what the owner
publishes at the claim is `/our/<inquirer>/<name>`, acquired by the inquirer at `/her/<peer>/<name>`.

Three things the probes and the gate settled: a cell placed inside the folder it reads answers
`/sys/view/fault: cycle` (so judgments live beside their folders); a path or slot segment is letters,
digits and underscore (`proposed_terms`, `maximum_price`); and an ask cell's context asks "no answer
yet" from the moment it is written, so a wake naming it fires at once, which is what a fresh
relationship wants.

`demo/relationship.py --wake-only` is the wake gate (one world, the stub agent); `demo/relationship.py`
the relationship gate (the inbox fixture under `demo/fixtures/` playing Precision Works, the gate
writing what the agent would); `--many` two inquirers and one prospective world. All deterministic.
The real runs, with a real mailbox, a real call and the real agent, are recorded separately.

| measured 2026-11-04, this laptop | |
|---|---|
| wake gate: a time, a referenced name, an asking cell; a wake declared before `kill -9` fires after the restart | 5 runs, every cause once, nothing spurious |
| the reply by mail, threaded home as a conversation record by `mail` | 1.06 s after the request |
| `kill -9` of host, worlds, services and fixture; everything back | 4.3 s |
| the owner's publication acquired at `/her/<peer>/<name>` | 0.01 s after it |
| a later change by the owner, the next case at `/her`, the judgment asking again | 0.33 s, no mail |
| two inquirers, one prospective world: scoped corners, the claim listing both, publication per inquirer, neither sees the other's | holds; three worlds 803 MB RSS |
| three fresh worlds booting at once on 8 GB | 4.4 GB RSS: boot them one after the other here, or on the VPS |
