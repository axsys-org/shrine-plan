# Shrine manifesto for a shared computational world

Shrine proposes a computer whose useful vocabulary can grow through use. People
construct persistent objects, the behavior that operates on those objects, and the
presentations through which they encounter them. Each construction remains material
for the next one. AI helps author the abstractions; native software retains and
executes them.

This is the product's ambition. The [native world specification](grove-native-world-spec.md)
states the required semantics, the [implementation plan](grove-canvas.md) gives the
work and acceptance sequence, and the [status record](grove-canvas-status.md) states
what has actually been demonstrated.

## The boundaries we inherit

A person can appear in a contact list, a planning spreadsheet, a calendar and a
project workspace. Each tool may give that person another identifier, another
representation and another set of rules for editing it. Work accumulates around
moving information between these representations and deciding which one to trust.

The problem extends beyond data. The machinery we build often becomes less
accessible once it becomes an application. A useful calculation is buried in a
screen. A presentation depends on a private data model. A workflow produces an
output that another tool can only consume through a special integration.

Shrine begins by making these boundaries choices. A file, application, document,
window, plugin or dashboard can be a useful construction. None needs to be the
fundamental unit from which every other experience is derived.

The underlying material is persistent identity, native values, relations,
computation, behavior, constraints, presentation and history. Useful categories
can emerge from arrangements of that material and remain open to further change.

## One world for objects and the software about them

Consider a persistent person, `Person#17`. A spreadsheet computes over that subject.
A scheduler presents it. A project relates it to work. An editor changes an
authorized field. Each use can preserve the same native reference.

The spreadsheet can own a projection and some local calculations without owning
a second person. Renaming the person changes the authoritative subject. Dependent
calculations and presentations update through native dependencies. A reader can
inspect the result and follow it back to the same subject and implementation.

This demands real engineering. Dependencies must be maintained, edits checked,
stale results identified and concurrent actions coordinated. The benefit is that
these mechanisms operate over shared native identities instead of reconciling
independent application copies of the same fact.

A compiler, editor or spreadsheet can also be a subject. Its definitions,
implementations, inputs and conditions are available to other native constructions.
A compiler may execute a program in one relationship and serve as an input to a
development environment in another. Its executable role does not place it outside
the world it operates on.

Common native material does not require identical types or permissions. A person,
compiler and image have different contracts. The shared property is that they
remain addressable, inspectable and composable through the same system.

## Construction has closure

A successful construction must return something that can participate again.

```text
native subjects + authored behavior + presentation
                         │
                         ▼
                  native construction
                         │
                         ▼
              material for further construction
```

A spreadsheet can become part of an experiment. Its evaluator can be used by a
different presentation. A chart can consume its result. A workbench can use the
whole arrangement. These possibilities must survive the moment the software becomes
pleasant to use.

A live result is immediately referenceable. Creating a template is a further act:
it describes which structure to construct, which behavior to share, which state
to initialize and which connections remain open. Generalization gives a proven
arrangement more possible uses; it does not confer membership in the native world.

Decomposition is equally important. A person should be able to inspect and reuse a
constituent without translating it into another framework. Separation must respect
ownership, constraints and consumers, leaving explicit needs where a connection is
removed. Closure includes the ability to understand what remains connected.

## The machinery becomes material

The world contains more than the objects produced by software. It also contains
the means of producing, transforming and presenting those objects.

An image can have a viewer, an editor and a thumbnail generator. A constructor can
create images. Those behaviors can be combined into a workbench, while the image
and each behavior retain their own identities. The workbench can become material
for another construction.

A constructor can itself be edited and composed. A presentation can be presented.
A development tool can operate on the definitions of the environment in which it
runs. The productive machinery is available inside the world it helps produce.

This is the substance of the Factorio analogy. As useful arrangements accumulate,
the environment gains better material for constructing subsequent arrangements.
The gain comes from retained native software and explicit reusable boundaries,
rather than depending on a model to remember how it built something last time.

## Apply the machinery to the world

A spreadsheet, calculator or development environment is useful because it can
operate on other native subjects. Applying it establishes the connections between
what its behavior requires and what those subjects provide. A compatible existing
connection can be reused. A disagreement becomes a precise place to continue work.

That continuation may be a choice, a supplied fact, a projection or substantial new
software. A spreadsheet column asking for a completion estimate might lead to a
native estimator over tasks, dependencies and durations. Once established, that
estimator is available to a timeline or scheduler as well. It remains visible as
software in the world rather than disappearing into spreadsheet-specific glue.

The common construction loop is small: apply, examine the remaining boundary,
author or select what is needed, check it, and continue. Familiar application
examples exercise that loop; they do not require a new host subsystem for each kind.
The amount of useful native software can grow substantially while the added host
mechanism stays small. Achieving that separation is an engineering requirement,
not evidence that every missing runtime capability is already implemented.

## Rich surfaces with precise native correspondence

A presentation can look like an instrument, an editor, a scene or a planning board.
Its appearance need not expose the decomposition that makes it coherent. A label
can read a person's name; a bar and a number can present the same derived workload;
a drag can invoke a specific assignment action.

Inspection must recover those relationships: the subject, the value, its basis,
whether it is authoritative or derived, and the operation an edit would invoke.
This precision makes visual freedom possible without forcing every interface into
generic cards. The surface can be visually integrated while its native constituents
remain independently addressable and reusable.

## Use and development occupy the same place

When a region becomes a spreadsheet, the user calculates in it. When it becomes an
editor, the user writes in it. Construction produces the operational surface in
place, with no required handoff to an exported application.

Inspection opens another depth of the same object. A result can reveal its inputs,
rule, cases and history. A gesture can become an experiment. A correction can become
an example the system retains. A missing connection can appear where its absence
matters, rather than in a remote setup questionnaire.

The normal surface should look like the software being used. A grid should feel
like a grid, an image like an image, a timeline like time arranged spatially. The
canvas must not force every construction into a card or make users navigate a
permanent graph of implementation details.

Building, using, inspecting and modifying are different interactions with the same
native subject. Candidate and committed states remain distinguishable. That
discipline supports fluid interaction by preserving a working basis while the
user explores changes.

## AI authors the intermediate abstractions

The practical difficulty of this vision is the distance between a small intention
and useful software. A person can say “these go together” without knowing which
types, references, functions, controls or checks make that arrangement work.

The model supplies that abstraction work. It can author new native behavior,
constructors and presentations, investigate a failure or reuse an existing pattern.
It must have enough expressive freedom to produce something beyond a fixed widget
catalogue. Its interpretation remains a proposal checked against native state,
authority and retained commitments.

The user should mainly be judging and manipulating the result. Language is available
where it helps, alongside examples, direct edits, drawings, inspection and ordinary
use. The model can communicate through a working experiment or a useful control.
It should reduce the translation the person must perform.

Once established, the result is software. Existing calculations, editors,
constructors and presentations continue to function with model access disabled.
The model assists evolution; it does not supply hidden runtime meaning on every use.

## A clock is an observation

The host supplies physical facilities such as rendering, keyboard and pointer input,
clock observations and, where authorized, other system operations. Native programs
interpret those inputs and act through declared boundaries.

Calendar time, animation timelines, logical steps and scheduling policies can be
constructed as native software. None needs to become a compulsory ontology for
every subject. A simulation may advance by explicit steps; a sequencer may use
scheduled observations from a clock. Their semantics remain inspectable in the
native world.

This keeps the base small while preserving the ability to build rich temporal
software. The same discipline applies to filesystems, devices and remote services:
physical access is a boundary, while the meaning built around it remains native.

## Rebuilding familiar software discovers reusable machinery

A calculator tests whether computation is real. An editor tests sequence changes,
selection and history. A spreadsheet tests references and maintained calculations.
A drawing tool tests geometry, composition and direct manipulation. A compiler tests
recursive transformations and diagnostics. Games and simulations test transitions,
constraints and events.

Each exercise should leave behind usable parts. An editor contributes editing
actions and presentations. Spreadsheet work contributes grids, ranges and evaluators.
A compiler contributes parsers, transformations and diagnostics. These parts should
be available to constructions that were never anticipated by the original exercise.

The progression eventually returns to the environment itself. An editor, compiler
and project view can form a development environment that changes native canvas
definitions. The browser and VM can remain the bootstrap while increasingly much
of the user-facing environment is described and changed from within.

Familiar applications are therefore tests of expressive power. Feature parity with
every existing product is not the release criterion. The significant result is
that useful software was established and its machinery increased what could be
built next.

## The promise must survive implementation

The first release has to demonstrate shared identity, native execution, local
inspection and repeated composition with real generated code. A visually convincing
simulation cannot substitute for those properties. A claim of universal dependency
tracking cannot substitute for actual traces and declared scopes.

Performance and control are part of the promise. Moving a view should be immediate.
Established actions should not call a model. A failed inference must preserve the
working object and the user's draft. The system must remember demonstrated cases
and commitments when it proposes later changes.

This is a proposal for a userland whose vocabulary people can manufacture. The
measure of success is a person making something useful, understanding and changing
it in place, then using the result and its machinery to build something that the
environment did not previously know how to express.
