# Typed Foil Compiler Core Specification

**Status:** Proposed
**Scope:** Compiler data-model consolidation, RTTI and generic printing, followed
by independently gated pure compile-time splices
**Reference implementation:** `src/reaver/foil.rvr` and `src/reaver/foil-*.rvr`

This document is normative. `MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, and
`MAY` have their usual requirements-language meanings.

## 1. Purpose and release boundaries

Foil currently represents compiler data with handwritten tagged rows, positional
accessors, and several partially overlapping traversals and compilation paths.
This specification replaces those with:

1. one generated representation for each compiler data family;
2. one structural Type traversal and one policy-driven value walker;
3. one structured diagnostic model;
4. one typed compilation engine shared by cold, memory-cached, and
   artifact-cached operation;
5. stable module-qualified identities, RTTI, bounded reflection, and generic
   pretty printing; and
6. a separately linked, capability-free execution environment for pure
   compile-time declaration generators.

There are three release boundaries:

- **Core consolidation:** canonical schemas, diagnostics, entries, artifacts,
  and the single compiler engine.
- **RTTI release:** stable brands, transitive schema registries, inspection,
  and pretty printing. This release does not depend on splices.
- **Splice release:** pure compile-time transformers, generated declarations,
  and deterministic replay. This release depends on the RTTI release.

Splices MUST NOT delay the RTTI release.

## 2. Goals and non-goals

### 2.1 Goals

- A compiler concept has one canonical runtime representation.
- Generated constructors and accessors replace handwritten tag and `Ix`
  conventions.
- Reflection metadata describes the canonical representation; it is not a
  second mirror representation.
- Cold compilation, memory-cache replay, and artifact replay have identical
  observable semantics.
- Nominal identity is stable across imports, mounts, caches, processes, and
  source edits that do not rename a definition.
- Reflection is bounded, deterministic, generic-aware, and unable to execute
  inspected values.
- Compile-time transformers are deterministic and transitively unable to
  obtain runtime capabilities.
- Replaced code is deleted in the same record-family landing that installs its
  replacement.

### 2.2 Non-goals

- Changing the Reaver fixed global-entry ABI.
- Replacing private Subject storage, except for the typed adapter at its
  boundary.
- Redesigning externally consumed MIR or PLAN forms.
- Exposing raw Subjects, TC storage, IR storage, cache internals, or arbitrary
  compiler values through reflection.
- Providing compatibility for old artifacts, snapshots, or branded runtime
  values unless an explicit converter is specified.
- Building a general effect system as part of splice support. V1 uses a
  separately compiled safe universe instead.

## 3. Architectural invariants

### 3.1 One representation per family

A record-family migration is atomic:

1. add the generated schema;
2. migrate all producers and consumers of that family;
3. delete its handwritten tags, constructors, positional accessors, adapters,
   and structurally duplicate walkers; and
4. remove that family from the hygiene allowlist.

Here, a landing is the mergeable change set, not necessarily each private
development commit on its branch. Scaffolding may exist during development,
but the merged landing MUST satisfy the atomic rule.

No landing may retain a second canonical representation for temporary
compatibility. A thin boundary adapter is permitted only where this
specification explicitly preserves an external or private representation.

The initial representation exceptions are:

- Reaver's fixed global-entry ABI, including `.entry-type`;
- private Subject/storage encoding inside one named Subject bridge;
- externally consumed MIR and PLAN forms; and
- raw runtime rows inside the reflection inspection bridge;
- legacy std/Cairn `0`/singleton optional results inside
  `foil-option-bridge.rvr`; and
- legacy raw left/right result rows inside `foil-result-bridge.rvr`.

There is one planned **migratory** boundary exception: from A6 through D3,
lowering may project semantic DefinitionIds to the
  historical slash/path runtime brand through the exact adapter specified in
  Section 7.1.

In addition, every clean source build uses the sealed, stage-0-only
BootstrapLayoutRef metadata token specified in Section 5.1. Its checker support
is a permanent exact macro-implementation allowlist entry, but token-bearing
metadata is transient build state: it is replaced before the canonical compiler
image or any user artifact is accepted. It is never a runtime Type or identity
representation.

Every exception MUST have an exact hygiene allowlist entry and a justification.
The allowlist MUST shrink as migrations land. New exceptions require an
explicit specification change.

### 3.2 Layout brands and definition brands are different

`define/data` uses a **LayoutId** to distinguish compiler ADTs. A LayoutId is an
internal representation discriminator and does not imply Foil nominal identity.

RTTI uses a **DefinitionBrand**, which is the encoded `DefinitionId` of a Foil
nominal declaration. A DefinitionBrand appears in branded runtime values.

The two concepts MUST NOT share an implicit namespace or be converted by
guessing. This distinction lets the dependency-free data layer bootstrap the
compiler before RTTI exists.

### 3.3 Typed code and the unsafe boundary

Every new or materially changed handwritten compiler helper above the
dependency-free Reaver macro/runtime substrate MUST use `define/typed`.
Migrating a helper cluster is blocked until Typed Reaver can express the forms
and types used by that cluster. Missing Typed Reaver features are prerequisites,
not reasons to scatter untyped exceptions.

Helpers emitted by `define/data` or `define/foil-schema` MUST carry equivalent
generated type metadata; they need not literally expand through the surface
spelling of `define/typed`. For the dependency-free bootstrap only,
`define/data` emits the neutral HelperSignature descriptors specified in
Section 5.1. A3 teaches Typed Reaver to consume/check neutral signatures in
BootstrapLayout mode and supplies the helper-cluster capability used by
later migrations. A4 immediately checks its Maybe/Either helpers before any
consumer moves; helpers generated after A3 are checked at expansion. Helpers
generated before A3 are the sole staged
exception: they may be used only by the macro/runtime bootstrap and exact
allowlisted bootstrap call sites, and the exception expires at A3. It never
applies to a handwritten helper.

The handwritten implementation of `define/data` itself and its minimal
descriptor-expansion/runtime support are the sole permanent typing exemption.
They live below Type and Typed Reaver, may be called only by macro expansion,
must be covered by neutral HelperSignature golden/property tests, and have one
exact macro-implementation hygiene entry. This exemption does not include any
compiler-family helper, generated helper consumer, parser, resolver, or bridge.

Untyped parser, evaluator, filesystem, and lowering primitives may be exposed
only through one named typed unsafe bridge. Raw exceptions MUST be captured and
converted to `Diagnostic` at that bridge. Direct primitive declarations or
trusted annotations outside the bridge are hygiene failures.

### 3.4 Hygiene enforcement

Source-hygiene checks MUST reject new instances of:

- handwritten Type, SAST, TC, or compiler-record tags;
- positional accessors for migrated compiler records;
- `IR_ENTRY`, `ENT`, or additional entry adapters;
- direct builtin signature or `insert-ffi` registration tables;
- duplicate Either/Maybe helpers or ad hoc optional encodings;
- additional compilation engines or import resolvers;
- additional general Type or typed-value walkers; and
- unsafe primitive bindings outside the named bridge.

Tests and the macro implementation itself may use exact, documented allowlist
entries. A broad directory or pattern allowlist is forbidden.

## 4. Identity model

Identity is established before any canonical Type, compiler entry, artifact,
RTTI schema, or splice is produced.

### 4.1 PackageId and ModuleId

```text
PackageId {
  authority : Path,
  name      : Path,
  version   : Nat
}

ModuleId {
  schema-version : Nat,
  package        : PackageId,
  module-path    : Path
}
```

`Path` is a canonical row of atomic PLAN Nat segments, not a printed path
Cord. A Cord spelling denotes its underlying PLAN Nat; Cord and Nat are not
distinct segment variants. Compound values, laws, pins, and Subject storage
keys are forbidden in these semantic paths.

The compiler host MUST provide a `PackageId` as part of the compilation realm.
The repository's builtins use a reserved versioned package identity. Two
packages with the same module path MUST still produce different ModuleIds.

A resolver MUST assign ModuleId before parsing, elaboration, registry
construction, or splice execution. ModuleId:

- MUST identify the stable logical source module;
- MUST NOT depend on source contents, generated output, an import alias, a
  mount path, a Subject key, a unit/content pin, compilation order, or cache
  mode;
- MUST remain equal when a module's contents change without a logical rename;
  and
- MUST change when the package identity or logical module path changes.

Content identity is represented separately by `SourceDigest`,
`CompilerDigest`, and `ArtifactDigest`.

Current content/unit pins may remain as physical storage identities inside
`foil-subject-bridge.rvr`. They qualify hidden Subject keys and support replay,
but MUST NOT appear as semantic ModuleId, DefinitionId, TNOM identity,
ModuleView identity, or runtime DefinitionBrand. A source edit may change the
physical unit pin while leaving all logically unrenamed DefinitionIds equal.

### 4.2 DefinitionId

```text
DefinitionId {
  module     : ModuleId,
  local-path : Path
}

IdentityError =
    InvalidSemanticPath(Path)
  | DuplicateModule(ModuleId)
  | DuplicateDefinition(DefinitionId)
  | UnknownDefiningModule(ModuleId)
```

Every source declaration, compiler-facing generated declaration, derived
accessor, FFI entry, and compiler-generated semantic declaration MUST receive a
deterministic DefinitionId. The dependency-free define/data macro/runtime
implementation and its private expansion helpers are not Foil/compiler
declarations and are identified only by LayoutId plus HelperKind.

A4's generated Maybe/Either helpers are initially layout-addressed because
DefinitionId does not yet exist. A5 atomically attaches their final
DefinitionIds, derived from the checked-in owning LayoutId and HelperKind,
before ModuleView, artifacts, public manifests, or RTTI can observe them. This
attachment does not change their runtime layout or leave a second identity.

- A source or generated declaration uses its final local declaration path.
- Generated provenance is stored in `Origin`; it is not part of identity.
- Derived accessors use a specified path derived from the owning definition and
  field name.
- Builtins use the reserved builtin PackageId and ModuleId.
- A materialized generic specialization uses the InstantiationId defined in
  Section 7; it does not mint a new declaration identity or runtime brand.
- A transparent alias has its own declaration identity for tooling, but its
  complete AliasTarget is stored separately; a resolved nominal target and its
  runtime values retain the target NominalRef.definition.
- Imports and mounts resolve to the defining DefinitionId and never mint a new
  one.

Two declarations with the same final DefinitionId produce
DuplicateDefinition. There is no collision winner or tie-breaker. B4 converts
each IdentityError variant to its stable identity Diagnostic code.

### 4.3 DefinitionBrand encoding

```text
DefinitionBrand = Nat
encode-brand-v1 : DefinitionId
                  -> Either BrandEncodeError DefinitionBrand
decode-brand-v1 : DefinitionBrand -> Either BrandDecodeError DefinitionId
definition-brand-v1? : Nat -> Bool

BrandEncodeError = PathLengthOverflow | PayloadLengthOverflow

BrandDecodeError =
    MissingEnvelope
  | WrongDomain
  | WrongVersion
  | TruncatedFrame
  | NonMinimalNatural
  | LengthOverflow
  | TrailingBytes
```

V1 uses a canonical, injective, length-delimited encoding, not a hash:

```text
payload = ascii("FOIL-BRAND") || 0x01
       || frame-path(package.authority)
       || frame-path(package.name)
       || frame-nat(package.version)
       || frame-nat(module.schema-version)
       || frame-path(module.module-path)
       || frame-path(definition.local-path)

frame-nat(n)  = u64be(byte-length(minimal-unsigned-big-endian(n)))
             || minimal-unsigned-big-endian(n)
frame-path(p) = u64be(item-count(p)) || concat(map(frame-nat, p))
brand         = unsigned-big-endian-to-nat(0x01 || payload)
```

Zero is encoded as a zero-length natural payload. The leading `0x01` preserves
the payload's leading bytes when converted to Nat. Path and payload sizes MUST
fit in unsigned 64-bit lengths; exceeding a limit returns the corresponding
BrandEncodeError.
Because every canonical Path segment is a PLAN Nat, `frame-nat` also frames a
segment written in Cord syntax by framing that Cord's underlying Nat. Decode
therefore produces the canonical Nat path; source spelling is not identity.

The encoding MUST be independent of registry order, cache mode, process, and
source contents. Generic instantiations retain the erased brand of their
declaration. Golden vectors and collision/property tests are required before
any runtime value writes a V1 brand.

The byte operations above are independent of PLAN Cord packing: framed naturals
are converted to minimal unsigned **big-endian** bytes exactly as written, and
the ASCII domain prefix is compared byte-for-byte. `definition-brand-v1?`
returns true only when decode-brand-v1 consumes a well-framed V1 payload with
no trailing bytes. A syntactically valid but registry-absent brand is
`reflect/unknown-brand`; an arbitrary Nat that is not a valid V1 frame is
`reflect/not-a-brand`.

BrandEncodeError and BrandDecodeError are dependency-free generated families
landed in A5. B4 owns the exhaustive conversion from each variant to a stable
Diagnostic code; identity and brand modules below Type do not import
Diagnostic.

TPAIL fitting, nominal constructors, match dispatch, host-side Pail validation,
and reflection MUST use this predicate/decoder rather than the historical
slash-byte test. Human-readable names come from DefinitionId/Registry metadata,
not by treating brand bytes as a printed path.

## 5. Generated data foundation

### 5.1 Neutral schema descriptor

`define/data` consumes one neutral descriptor containing:

```text
LayoutId {
  authority : Path,
  name      : Path,
  version   : Nat
}

DataDescriptor {
  layout-id,
  type-parameter-count,
  variants : Row VariantDescriptor
}

VariantDescriptor {
  stable-tag,
  name,
  fields : Row FieldDescriptor
}

FieldDescriptor {
  name,
  cardinality,
  foundation-type : FoundationTypeExpr,
  structural-child-role
}

FieldCardinality = One | Row
VariantTag = Nat

FoundationTypeExpr =
    Parameter(index : Nat)
  | Self
  | Scalar(FoundationScalar)
  | Data(LayoutId, Row FoundationTypeExpr)
  | RowOf(FoundationTypeExpr)
  | Function(Row FoundationTypeExpr, FoundationTypeExpr)

FoundationScalar = NatValue | BoolValue | UnitValue | RuntimeValue

DataError =
    MalformedOuter
  | WrongLayout(expected : LayoutId)
  | UnknownVariant(layout : LayoutId, stable-tag : Nat)
  | WrongArity(layout : LayoutId, stable-tag : Nat,
               expected : Nat, actual : Nat)
  | ChildCountMismatch(layout : LayoutId, stable-tag : Nat,
                       expected : Nat, actual : Nat)

HelperSignature {
  helper-kind,
  layout-id,
  type-parameter-count,
  arguments : Row FoundationTypeExpr,
  result    : FoundationTypeExpr
}

HelperKind =
    Construct(stable-tag)
  | SchemaPredicate
  | VariantPredicate(stable-tag)
  | TrustedGetField(stable-tag, field-index)
  | SafeGetField(stable-tag, field-index)
  | TrustedSetField(stable-tag, field-index)
  | SafeSetField(stable-tag, field-index)
  | CaseDispatch
  | EnumerateChildren
  | RebuildChildren
```

For a `Row` field, `foundation-type` is the element type and the generated
helper signature wraps it in RowOf. Parameter indices are zero-based and MUST
be less than `type-parameter-count`. Self denotes the current DataDescriptor
with its in-scope parameters. The lower layer rejects unbound parameters,
unknown referenced LayoutIds, and ill-kinded recursive use during descriptor
expansion.

The descriptor contains no Foil Type values and performs no Subject lookup.
LayoutId is an explicit compile-time constant; it MUST NOT be inferred from an
import alias or physical source path. Its authority/name/version tuple is
globally unique within a compiler image. Duplicate LayoutIds with unequal
descriptors are a bootstrap failure.

Every generated value has the exact logical row layout:

```text
[LayoutId, VariantTag, field-0, ..., field-n]
```

VariantTag is a stable Cord/Nat unique within its LayoutId. Every declared
field occupies exactly one slot; a `Row` cardinality field contains a row in
that slot. Optionality is represented by Maybe, not a missing slot.

Stable tags and field order are schema ABI. Changing LayoutId, tags, or field
order requires a LayoutId version change and an atomic migration of persisted
boundaries.

From this descriptor `define/data` MUST generate:

- constructors;
- whole-schema and per-variant predicates that validate tag and arity;
- named field accessors;
- immutable field updates;
- exhaustive case dispatch;
- variant and field metadata; and
- structural child enumeration and rebuilding metadata.

It also emits a complete HelperSignature manifest for those helpers. The
manifest is neutral data over FoundationTypeExpr; it neither imports nor
executes Typed Reaver. Signature elaboration has two specified modes:

- `BootstrapLayout` elaborates Data/LayoutId and Self to a sealed
  `BootstrapLayoutRef(LayoutId, arguments)`, encoded in the existing legacy
  TNOM metadata shape under a reserved, injectively LayoutId-framed compiler
  path. Its arguments use the existing TNOM argument slots. Source syntax,
  ordinary nominal lookup, lowering, fitting, and runtime constructors cannot
  create or consume this reserved path. Typed Reaver intercepts it only while
  checking generated helpers; its one-step view is the exact structural sum for
  `[LayoutId, VariantTag, fields...]`, including singleton natural tags.
  Equality/WF compare LayoutId and arguments and unfold at most one layer under
  an active-ref set, so recursive and cross-layout descriptors remain finite.
  The token may serialize only into transient stage-0 generated-helper
  `.entry-type` metadata. It is forbidden in user modules, canonical compiler
  results, caches, and artifacts.

The reserved legacy nominal path is exactly
`["$foil-bootstrap-layout-v1", layout-key]`, where `layout-key` is the Nat made
from `0x01 || ascii("FOIL-LAYOUT") || frame-path(authority) ||
frame-path(name) || frame-nat(version)` using Section 4.3's framing rules.
Source identifiers beginning with `$foil-bootstrap-` are rejected. Decode MUST
roundtrip to the complete LayoutId and reject trailing bytes; there is no hash
or collision fallback.
- `CanonicalData` elaborates the same reference to TDATA(LayoutId, arguments).

A3 checks every helper emitted by the A2 substrate in BootstrapLayout mode
before any compiler family consumes it; later generated families are checked
at expansion. During A6's atomic Type migration, the bootstrap
compiler first builds the new Type using those exact structural signatures;
the rebuilt compiler then rechecks the same sources in CanonicalData mode.
Runtime helper values/layouts are byte-identical across the two checks, and all
accepted stage-1 helper metadata uses only CanonicalData after A6. The sealed
BootstrapLayout encoder/checker remains in the macro implementation so every
future no-snapshot source build can repeat stage 0; the build gate rejects any
token that survives the stage-1 recheck.

Predicates return false for an unknown LayoutId, tag, or arity. In the completed
generator, boundary-safe accessors return `Either DataError a`. Trusted generated
accessors may assume a preceding generated predicate/case dispatch, but misuse
must return DataError or fail through the macro/runtime's fixed bootstrap trap
rather than reading another slot.

Safe-accessor activation is explicitly staged to avoid an Either bootstrap
cycle. A2 reserves the canonical Maybe/Either LayoutIds and neutral descriptors
without activating their runtime APIs. Safe signatures may therefore name the
future Either LayoutId in FoundationTypeExpr.Data. A2 emits trusted
constructors/predicates/accessors plus the neutral
signatures and safe-accessor templates, but exposes them only inside macro
self-tests; it does not emit a compiler-facing Either-returning accessor. In
A4, the macro first expands canonical Either with those trusted helpers, then
enables safe-accessor emission and re-expands/rechecks DataError, Maybe, Either,
and every A2 fixture. After A4 every boundary accessor uses canonical Either;
the trusted forms remain callable only from generated predicate/case bodies.

DataError is dependency-free and lands with define/data. B4 exhaustively maps
its variants to stable Diagnostic codes; no lower data module imports
Diagnostic.

Generated values are the sole runtime representation. A descriptor, manifest,
or RTTI value points to that representation and MUST NOT contain a copied
reflection mirror of each value.

`define/data` MUST live below Foil Type, Subject, Typed Reaver, and all compiler
modules. It may depend only on the Reaver macro/runtime substrate. A clean build
from source with no prebuilt compiler image is a required acceptance test.

### 5.2 Bootstrap and define/foil-schema

Foundational families such as Type are defined with `define/data` directly.
After Type, Subject, and Typed Reaver have bootstrapped,
`define/foil-schema` attaches a second, dependency-neutral typed descriptor to
the same DataDescriptor. The exact descriptor is also the persisted
SchemaTemplate used by manifests and RTTI:

```text
SchemaTemplate {
  definition-id,
  runtime-kind : SchemaRuntimeKind,
  visibility : SchemaVisibility,
  parameters : Row SchemaParameter,
  variants   : Row FoilVariantDescriptor
}

SchemaRuntimeKind =
    CompilerLayout(LayoutId)
  | FoilNominal
  | FoilUnion(members : Row SchemaNominalMember)
  | FoilAlias(target : SchemaTypeExpr)

SchemaNominalMember {
  definition : DefinitionId,
  arguments  : Row SchemaArgument
}

SchemaVisibility = PublicRoot | LocalRoot | ReachablePrivate

SchemaParameter = TypeParameter(name)
                | ConstParameter(name, SchemaTypeExpr)

SchemaArgument =
    SchemaTypeArg(SchemaTypeExpr)
  | SchemaConstArg(declared-type : SchemaTypeExpr,
                   value : SchemaConstExpr)

SchemaConstExpr =
    ConstParameterRef(name)
  | NatConstant(Nat)
  | DefinitionConstant(DefinitionId)

FoilVariantDescriptor {
  runtime-tag : Maybe VariantTag,
  name,
  fields : Row FoilFieldDescriptor
}

FoilFieldDescriptor {
  name,
  visibility,
  type : SchemaTypeExpr
}

SchemaTypeExpr =
    Bottom
  | Natural(refinement : Maybe Nat, rendering : NatRendering)
  | Sum(Row SchemaTypeExpr)
  | ForAllType(name, body : SchemaTypeExpr)
  | ForAllConst(name,
                constraint : SchemaTypeExpr,
                body : SchemaTypeExpr)
  | TypeParameterRef(name)
  | CurrentDefinition(arguments : Row SchemaArgument)
  | CompilerData(LayoutId, Row SchemaTypeExpr)
  | Nominal(DefinitionId, Row SchemaArgument)
  | Function(Row SchemaTypeExpr, SchemaTypeExpr)
  | SelfWrapper(SchemaTypeExpr)
  | Face(name, SchemaTypeExpr)
  | TaggedRow(RowTag, Row SchemaTypeExpr)
  | Array(SchemaTypeExpr)
  | Pin(SchemaTypeExpr)
  | Any
  | Pail
  | TypeWrapper(SchemaTypeExpr)

NatRendering = Number | Boolean | Text

SchemaError =
    WrongArgumentKind(parameter-name)
  | WrongArgumentArity(expected : Nat, actual : Nat)
  | UnboundParameter(parameter-name)
  | DuplicateParameter(parameter-name)
  | ConstDeclaredTypeMismatch(parameter-name)
  | CyclicParameterReference(parameter-name)
  | InvalidCurrentDefinitionArgument
  | InvalidNatRendering(NatRendering)
  | BadTypeNotExportable
  | UnknownSchema(DefinitionId)
```

SchemaTypeExpr is symbolic data, not a Foil Type value. The upper layer
resolves it only after Type and Typed Reaver are available. It contains enough
information to generate generic bindings, constraints, recursive schema
references, field visibility, Foil Types, and RTTI templates.

Elaboration is total and lossless over every exportable canonical Type variant:
Bottom→TBOT; Natural(r, _)→TNAT(r); Sum→TSUM; ForAllType→TQUA;
ForAllConst→TCQUA; TypeParameterRef→TVAR; CurrentDefinition resolves to TDATA
for CompilerLayout and to the current TNOM for a Foil runtime template;
CompilerData→TDATA; Nominal→TNOM; Function→TFUN; SelfWrapper→TSELF;
Face→TFAC; TaggedRow preserves its exact RowTag in TROW; Array→TARR;
Pin→TPIN; Any→TANY; Pail→TPAIL; and TypeWrapper→TTYP. TBAD has no schema
form and is rejected at every export/manifest boundary. The inverse
`schema-type-of` is defined for all of those variants and chooses Number for an
unannotated TNAT. NatRendering does not change Type equality: Boolean and Text
are checked rendering refinements over the exact TNAT refinement and control
only reflected Value/pretty construction. Sum option order, wrappers, row tags,
singleton Nat refinements, and binder scope are never normalized away by this
conversion.

A template paired with DataDescriptor MUST use
CompilerLayout(DataDescriptor.layout-id). Each runtime-tag MUST be Some of the
matching DataDescriptor stable-tag, and field names, field order, and row
cardinalities MUST match exactly. Its parameters MUST be exactly
DataDescriptor.type-parameter-count TypeParameters in order; ConstParameter is
forbidden for CompilerLayout, and CurrentDefinition/CompilerData arguments must
all be SchemaTypeArg. Attachment rejects any mismatch. A concrete
source Foil constructor declaration uses FoilNominal, has exactly one variant
whose runtime-tag is None, and is constructed with
SchemaTemplate.definition-id's active runtime brand. A named union uses
FoilUnion with symbolic applied member
references; the union root is not constructible and its values retain the
selected member's brand. A FoilAlias root is likewise not constructible and its
values retain the fully elaborated target representation. SchemaManifest map
keys and RttiInfo.id MUST equal
SchemaTemplate.definition-id.

CompilerLayout and FoilNominal are deliberately different runtime kinds. A
CompilerLayout value has the exact `[LayoutId, VariantTag, fields...]` layout
from Section 5.1 and is typed as TDATA; it is not a Pail and never receives a
DefinitionBrand. A FoilNominal value is an ordinary Pail whose runtime head is
the active brand for its DefinitionId and whose PLAN application arguments are
the single None-tag variant's fields in declared order. A zero-field value is
the brand Nat itself; a non-empty value is an application spine with that Nat
as `Hd`, never a bracket row `[brand, ...]`. It has no LayoutId or additional
variant-tag head. No helper may guess or convert between these identities.

FoilUnion.members are structurally unique, in declaration order, and each
elaborates one-for-one to an applied NominalRef and resolves to a FoilNominal
template after parameter substitution. Their SchemaArguments explicitly
describe forwarded, dropped, reordered, or fixed type/const parameters.
FoilUnion and FoilAlias
templates have no independent runtime variants; their `variants` row MUST be
empty. Their member/target templates carry the concrete fields. Cycles through
aliases or unions are rejected unless traversal reaches a concrete recursive
nominal field under the normal visited-definition rule.

Template elaboration binds parameters in declared order. A TypeParameter
accepts only SchemaTypeArg. A ConstParameter accepts only SchemaConstArg; its
declared type is elaborated after substituting earlier parameters and MUST equal
the parameter's declared type. A parameter declaration may refer only to
earlier parameters; template fields, union members, and alias targets may refer
to any parameter declared by that template. ConstParameterRef elaborates to
ConstVariable until specialization; NatConstant and DefinitionConstant
elaborate to ConstLiteral of the corresponding ConstValueKey. Nominal arguments
preserve their mixed type/const order and elaborate one-for-one to TypeArgument.
Wrong kind, arity, unbound
reference, duplicate binder, or cyclic parameter substitution is a
SchemaError. SchemaError is dependency-neutral; B4 exhaustively converts it to
Diagnostic.

From a paired DataDescriptor and CompilerLayout SchemaTemplate,
`define/foil-schema` generates:

- the Foil-visible compiler-data TDATA declaration;
- Typed Reaver bindings;
- schema and RTTI templates;
- public manifests; and
- safe constructors exposed to Foil or compile-time transformers.

The upper layer MUST NOT change, wrap, or rebrand the raw compiler-data runtime
representation. `define/foil-schema` is not the constructor generator for
ordinary FoilNominal/Pail values; source nominal declarations use the compiler's
nominal constructor path and FoilNominal templates.
Bootstrap families attach metadata after the fact. Non-bootstrap families MAY
use a combined `define/foil-schema` form that expands to the same lower and
upper layers.

Generated families use the canonical layout above. A layout change from a
legacy family is allowed only when every producer, consumer, persisted
boundary, and test is migrated in the same record-family landing.

### 5.3 Maybe and Either

```text
Maybe[a] = None | Some(a)
```

Compiler APIs MUST use the generated Maybe ADT instead of `Either Unit a`,
zero-as-none, singleton-row-as-some, or family-specific optional helpers.

This compiler-internal Maybe is distinct from any surface Foil `/boot/maybe`
nominal type. Conversions to a legacy boundary representation may occur only in
the named boundary bridge.

`Either[e, a]` in this specification refers to one canonical generated ADT.
Existing surface Foil Either metadata MAY attach to the same neutral descriptor
when its runtime layout agrees. Handwritten `left`, `right`, and predicate/value
helper families and all compiler-internal legacy result/optional shapes are
migrated and deleted in the same A4 landing that activates these canonical
families. Only the exact named external/private bridges below retain another
shape.

While expanding the Either descriptor itself, the macro implementation may use
the Reaver substrate's private expansion result. That value cannot escape the
macro module or appear in compiler APIs, and the completed A4 landing exposes
only generated Either results.

Calls into existing std/Cairn APIs that return legacy `0`/singleton optionals
cross `src/reaver/foil-option-bridge.rvr`, using generated
`maybe-from-legacy` and `maybe-to-legacy`. Compiler public APIs never expose the
legacy shape. Existing raw `("left" ...)`/`("right" ...)` results cross
`src/reaver/foil-result-bridge.rvr`. The Subject and raw exception boundaries live respectively in
`src/reaver/foil-subject-bridge.rvr` and
`src/reaver/foil-unsafe-bridge.rvr`; raw reflection rows live only in
`src/reaver/foil-reflect-bridge.rvr`. These exact module/API boundaries are the
only hygiene allowlists for their representations.

## 6. Canonical compiler contracts

The contracts in this section are final before their record-family migrations
begin. Later features may add schema versions, but MUST NOT introduce competing
canonical shapes.

### 6.1 Diagnostic and Origin

```text
Text = Cord

DiagnosticCode = Path

DiagnosticDatum =
    DatumText(Text)
  | DatumNat(Nat)
  | DatumPath(Path)
  | DatumDefinition(DefinitionId)
  | DatumType(Type)
  | DatumOrigin(Origin)
  | DatumRow(Row DiagnosticDatum)

DiagnosticField {
  name  : Text,
  value : DiagnosticDatum
}

Severity = Error | Warning | Note

Diagnostic {
  code     : DiagnosticCode,
  severity : Severity,
  message  : Text,
  origin   : Maybe Origin,
  context  : Row DiagnosticField,
  children : Row Diagnostic,
  related  : Row RelatedOrigin
}

RelatedOrigin {
  label  : Cord,
  origin : Origin
}

Origin =
    Source(ModuleId, Span)
  | Generated(ModuleId,
              call-site-span,
              generator-definition-id,
              emission-index,
              Maybe generated-span)
  | Synthetic(phase, Maybe ModuleId)

Span {
  line,
  column,
  byte-offset,
  byte-length
}
```

Public parser, compiler, artifact, reflection, and splice boundaries return
`Either Diagnostic a`. Multiple failures use one parent Diagnostic with
ordered children; they do not change the error side to `Row Diagnostic`.
Warnings are returned in `CompileResult`, not on the Left branch.

Consumers MUST branch on stable diagnostic codes and structured context, not
message text. Text and Forge HTML renderers consume the same Diagnostic tree.
DiagnosticCode is a non-empty canonical path declared in one central code
catalogue. Ad hoc message strings are not codes.

Raw parser, evaluator, or PLAN exceptions may cross only the named unsafe
capture bridge, where they are immediately converted to a stable code, Origin,
and context and deeply forced before returning. Lazy exceptions or diagnostic
payloads MUST NOT escape the bridge. Generated diagnostics preserve both
call-site and generator origins through validation, final elaboration,
lowering, artifacts, and formatting. Every Generated primary Origin MUST have
a `related` Source Origin for the generator definition when source metadata is
available.

Diagnostic ordering uses the total key `(origin-class, ModuleId, byte-offset,
emission-index, diagnostic-code, severity, canonical-diagnostic-bytes)`.
`canonical-diagnostic-bytes` is the versioned canonical serialization of the
message, name-sorted context, sorted related origins, and already normalized
child trees; it excludes cache data, pointers, and collection order. Missing
origin fields use a specified zero/sentinel value, and Synthetic origins
additionally sort by phase. This preserves source order within a module while
remaining deterministic across modules and origin kinds. Map, Subject,
pointer, or evaluation iteration order MUST NOT affect it.

Origin-class order is Source, Generated, Synthetic. ModuleId and Path order are
lexicographic generated-field order; phases use a checked-in phase catalogue;
missing ModuleId/span/emission values sort before present values. Normalization
is bottom-up: normalize descendants, compute each complete child key, then sort
the parent row. Byte-identical duplicate children retain their multiplicity;
their mutual permutation is unobservable and no pre-sort ordinal is required.

### 6.2 CompilerEntry

```text
EntryId =
    Declaration(DefinitionId)
  | Instantiation(InstantiationId)

AliasTarget =
    TypeAlias(Type)
  | EntryAlias(EntryId)

CompilerEntry {
  id      : EntryId,
  origin  : Origin,
  payload : EntryPayload
}

EntryPayload =
    Definition(TypedCode, Maybe LoweredEntry)
  | Primitive(signature-id : DefinitionId,
              TypedCode,
              Maybe LoweredEntry)
  | Alias(target : AliasTarget)

LoweredEntry {
  value : RuntimeValue,
  ir    : LoweredIr
}
```

`TypedCode` is the canonical typed compiler AST currently carried inside TC
entries. This specification removes the outer `("TC" ...)` and
`("IR_ENTRY" ...)` storage containers; it does not remove typed compiler code.

Lowering enriches the Definition or Primitive payload of an existing
CompilerEntry. It does not replace the entry or create another canonical entry
type. A transparent alias has a tooling DefinitionId but an Alias payload and
no independent TypedCode/IR. TypeAlias preserves the complete canonical target
Type, including a structural target or an applied NominalRef with all
TypeArguments. EntryAlias preserves the complete target EntryId and its Subject
boundary encoding may remain a navigation binding. Resolution follows aliases
with an active EntryId/DefinitionId set and diagnoses cycles. A nominal
TypeAlias's runtime values retain the target NominalRef.definition; a
structural alias mints no brand. Namespace-only declarations appear in
ModuleView but do not require a value-bearing CompilerEntry.

Builtins, aliases, const-generic materializations, derived accessors, and
ordinary value-bearing declarations all use the generated CompilerEntry API.
A declaration uses `Declaration(id)`. Each materialized generic specialization
uses `Instantiation(InstantiationId)` and therefore coexists with other
specializations of the same declaration. Its nominal runtime brand still
erases to `InstantiationId.definition`.

Subject storage may encode CompilerEntry privately, but only the generated
CompilerEntry API is visible outside the Subject bridge.

### 6.3 CompileRequest and CompileResult

```text
OnlineCompileMode =
    Cold
  | Memory(cache : MemoryCache, provider-revision : ProviderRevision)
  | ArtifactOnline(cache : ArtifactCache)

SourceProviderKey {
  provider-id,
  mapping-version
}

ProviderRevision = Digest

CompileRequestCommon {
  module              : ModuleId,
  source-provider-key : SourceProviderKey,
  substrate           : CompilerSubstrate,
  flags               : CompileFlags,
  limits              : CompileLimits
}

OnlineRequest {
  common : CompileRequestCommon,
  mode   : OnlineCompileMode
}

StrictOfflineRequest {
  common : CompileRequestCommon,
  cache  : ArtifactCache
}

CompileRequest =
    OnlineRequestValue(OnlineRequest)
  | StrictOfflineRequestValue(StrictOfflineRequest)

CompileResult {
  module           : ModuleId,
  source-digest    : SourceDigest,
  unit-view        : ModuleView,
  entries          : OrderedMap EntryId CompilerEntry,
  lore             : Lore,
  warnings         : Row Diagnostic,
  cache-output     : CacheOutput,
  stats            : Maybe CompileStats
}

ProviderSnapshot {
  key              : SourceProviderKey,
  revision         : ProviderRevision,
  root-package     : PackageId,
  allowed-packages : OrderedSet PackageId
}

ImportLocator =
    Relative(logical-path : Path)
  | Package(package : PackageId, logical-path : Path)

ImportRequest {
  importer : ModuleId,
  locator  : ImportLocator
}

SourceUnit {
  module        : ModuleId,
  source-bytes  : Row Nat,
  source-digest : SourceDigest
}

ProviderFault =
    UnknownProvider
  | UnknownModule(ModuleId)
  | InvalidLogicalPath(Path)
  | RealmMismatch(expected : PackageId, actual : PackageId)
  | RevisionChanged(expected : ProviderRevision,
                    actual : ProviderRevision)
  | ReadFailure(ModuleId)

SourceProviderCapability {
  snapshot       : SourceProviderKey
                   -> Either ProviderFault ProviderSnapshot,
  resolve-import : ProviderSnapshot -> ImportRequest
                   -> Either ProviderFault ModuleId,
  read-source    : ProviderSnapshot -> ModuleId
                   -> Either ProviderFault SourceUnit
}

CompileInvocation =
    Online(SourceProviderCapability, OnlineRequest)
  | StrictOffline(StrictOfflineRequest)
```

ProviderFault is dependency-neutral and lands with Diagnostic conversion in
B4. The sealed executable SourceProviderCapability and its compile-engine
integration land later in C3 over that already canonical fault family.

If a source provider cannot inhabit ordinary data, the compiler engine receives
this sealed read-only interface as its sole typed unsafe capability.
CompileRequestCommon stores only its stable provider key; it never stores executable
operations. Source reads and logical resolution occur through the capability,
and B4's unsafe bridge exhaustively converts ProviderFault to Diagnostic.
SourceProviderKey identifies the logical module-to-source mapping contract;
ProviderRevision is a provider-issued digest/epoch proving the complete mapping
and source generation observed by a Memory cache. Neither is a physical file
path or ModuleId.

In modes that consult source, compile-unit lazily obtains at most one live
ProviderSnapshot per request and uses that same value for the entire dependency
graph. It, not a backend, owns import
canonicalization, alias/mount collision rules, graph ordering, and duplicate
handling. The provider may only map an already canonical ImportLocator to a
stable ModuleId and return bytes for that identity. A Relative locator resolves
within `importer.package`; a Package locator resolves to its explicit package.
That package MUST be in allowed-packages, the request root module MUST use
root-package, and every returned module-path MUST be canonical. A provider
cannot install entries, mutate compiler state, or vary behavior by
OnlineCompileMode.

The compiler recomputes SourceDigest from the exact source bytes and rejects a
mismatching reported digest. Every resolved `(ModuleId, SourceDigest)` becomes
an artifact validity fact, and the artifact persists the non-executable
ProviderSnapshot fields used to build that graph.
StrictOffline reconstructs this persisted snapshot fact,
validates it against the artifact key/manifest, and MUST NOT invoke any
SourceProviderCapability operation, including `snapshot`; that invocation
variant contains no capability to call. An online miss or required revalidation
obtains one new live snapshot. Two provider
implementations serving byte-equal logical graphs MUST produce equal semantic
results and diagnostics.

CompileInvocation makes provider/mode consistency unrepresentable: Online
always carries exactly one capability, while StrictOffline carries none and
only an ArtifactCache. StrictOffline selects the artifact-only diagnostics in
Section 9.2. A Memory hit may avoid a source read only when its
ProviderRevision equals the snapshot revision and proves that the provider's
complete logical module mapping and source generation are unchanged; otherwise
it is a miss and revalidates through SourceProviderCapability.

Legacy projections that accept a module Cord use a checked-in workspace
PackageId and canonicalize the logical module name to a path with no empty,
`.` or `..` segments. Physical fixture paths such as `../foil-bad/...` remain a
SourceProvider concern and receive a separate canonical logical test ModuleId.

`CompileResult.entries` and every other map-like semantic field have a
specified canonical sort order. EntryId order is Declaration before
Instantiation, then DefinitionId order, then structural TypeArgument order.
`cache-output` and `stats` are operational and are excluded from semantic
equality.

### 6.4 SchemaManifest and ModuleView

```text
SchemaManifest {
  module  : ModuleId,
  roots   : Row DefinitionId,
  schemas : OrderedMap DefinitionId SchemaTemplate
}

ModuleView {
  module         : ModuleId,
  declarations   : OrderedMap DefinitionId DeclarationView,
  exports        : ExportView,
  resolved       : Row ResolvedImportView,
  schema-manifest: SchemaManifest
}

DeclarationView =
    TypedDeclaration(DefinitionId, Origin, Type, Visibility)
  | AliasDeclaration(DefinitionId, Origin, AliasTarget, Visibility)
  | OpaqueDeclaration(DefinitionId, Text, Origin, Visibility)
```

SchemaManifest is neutral compiler metadata, not a brand-indexed runtime
Registry. Its roots are the local typed nominal declarations and nominal Types
including named unions/aliases, plus the Foil runtime Types of directly visible
imported entries. Its schemas are the flattened transitive DefinitionId closure
reachable from those roots. It contains schema templates only, never unrelated
runtime values or CompilerLayout templates.

The manifest closure is built with the canonical Type traversal, a visited
DefinitionId set, and deterministic DefinitionId sorting. It is retained in
units and artifacts before RTTI activation so a later Registry does not need
raw Subject or hidden dependency storage.

For TypeAlias, closure follows the complete target Type. For EntryAlias, it
follows the resolved target entry's public Type. Alias cycles are diagnosed and
cannot truncate a manifest silently.

ModuleView contains identity, Type/schema, origin, visibility, and export
information suitable for tooling and CompilerContext. DeclarationView MUST NOT
contain arbitrary runtime/compiler values or private Subject storage.

### 6.5 Semantic equality

```text
semantic-view : CompileResult -> CompileSemantics
normalize-diagnostic : Diagnostic -> Diagnostic
```

normalize-diagnostic deeply forces the tree, sorts context fields by name,
sorts related origins and children by the diagnostic ordering contract, and
normalizes generated compiler-only identifiers to their stable semantic forms.
It retains code, severity, message, semantic context, and Origins; it does not
hide a cache-path difference by deleting meaningful diagnostic data.

CompileSemantics includes:

- ModuleId and SourceDigest;
- canonical entry payloads, including aliases and any TypedCode/lowered
  value/IR;
- exports and resolved defining identities;
- the public ModuleView and schema closure;
- lore; and
- normalized warnings.

It excludes cache representation, artifact bytes, profiling, telemetry,
evaluation history, and cache-hit counters. Pins and laws compare by canonical
content identity, never pointer identity or human-readable pin labels.

Before semantic-view is produced, executable values and retained IR are deeply
forced and content-pinned. Pin identity is the canonical content digest of its
unsealed noun. An unavoidable raw law is compared by canonical PLAN
serialization after semantic DefinitionId relocation; a value that cannot be
forced/serialized within CompileLimits is a compilation Diagnostic rather than
an incomparable result.

For unchanged source, dependencies, compiler version, flags, and limits:

```text
semantic-view(cold-miss)
  = semantic-view(memory-miss)
  = semantic-view(memory-hit)
  = semantic-view(artifact-miss)
  = semantic-view(artifact-hit)
```

Failure equivalence means equality of normalized Diagnostic trees.

## 7. Type structure and shared walking

### 7.1 Nominal references and generic arguments

The post-migration nominal representation is exact:

```text
NominalRef {
  definition : DefinitionId,
  arguments  : Row TypeArgument
}

DataTypeRef {
  layout    : LayoutId,
  arguments : Row Type
}

TypeArgument =
    TypeArg(Type)
  | ConstArg(ConstArgument)

ConstArgument {
  declared-type : Type,
  value         : ConstTerm
}

ConstValueKey = NatValue(Nat) | DefinitionValue(DefinitionId)

ConstTerm =
    ConstLiteral(ConstValueKey)
  | ConstVariable(name : Text)

InstantiationId {
  definition : DefinitionId,
  arguments  : Row TypeArgument
}

TNOM {
  nominal : NominalRef
}

RowTag = Structural | NominalRow(DefinitionId) | VariantTag(Text)

Type =
    TBOT
  | TNAT(Maybe Nat)
  | TSUM(Row Type)
  | TQUA(name : Text, body : Type)
  | TCQUA(name : Text, constraint : Type, body : Type)
  | TNOM(NominalRef)
  | TDATA(DataTypeRef)
  | TVAR(name : Text)
  | TFUN(arguments : Row Type, result : Type)
  | TSELF(Type)
  | TFAC(face : Text, value : Type)
  | TROW(RowTag, Row Type)
  | TPIN(Type)
  | TANY
  | TPAIL
  | TTYP(Type)
  | TBAD(Maybe Text)
  | TARR(Type)
```

Canonical Type values contain no `/ty-ap` path encoding and no unit-qualified
Subject path. Parsing/storage adapters decode legacy or surface path syntax to
NominalRef before a Type becomes canonical. TypeArgument equality and ordering
are structural over their generated forms; ConstArg compares both its declared
Type and ConstTerm.

Generic arguments are supplied in declaration binder order. `TQUA(name, body)`
binds `name` in `body`. `TCQUA(name, constraint, body)` does not bind `name` in
its own constraint and binds it only in `body`; all enclosing sibling binders
remain in scope for both constraint and body. Substitution and specialization
MUST preserve these scope rules and reject the wrong argument kind.

Within a TCQUA body, a symbolic const use is
`ConstVariable(TCQUA.name)`. Const substitution replaces only occurrences bound
by that TCQUA, is capture-avoiding, and checks the ConstArgument.declared-type
against the elaborated constraint before installing ConstLiteral. Free or
shadowing-ambiguous ConstVariables are ill-formed in exported Types. TQUA binds
only TVAR and TCQUA binds only ConstVariable; equal printed names across the two
binder kinds do not capture one another. Every
InstantiationId MUST be ground: its Types contain no free TVAR/ConstVariable
and every ConstArg contains ConstLiteral. Its generated constructor rejects a
non-ground argument row.

TDATA arguments are ordinary Type arguments in the paired DataDescriptor's
zero-based parameter order. TDATA is valid only for a known CompilerLayout
LayoutId and fits the `[LayoutId, VariantTag, fields...]` representation
directly. It never lowers through a nominal brand, never accepts ConstArg, and
cannot be used for a FoilNominal source declaration.

TFUN arity is derived from its argument row and is not a separately stored
field. TROW stores semantic RowTag, never a printed-path Cord or physical unit
pin; lowering/RTTI derives the runtime constructor. TSUM normalization
(flattening, sorting, bottom removal, and deduplication) is a separate semantic
operation from generated construction/rebuilding. TBAD is compiler poison with
an optional stable text code and is never a valid exported/runtime Type.

Until V1 brand activation in D3, the independently releasable core uses one
explicit lowering-boundary adapter:

```text
LegacyRuntimeBrand = Nat
LegacyRuntimeBrandMap = OrderedMap DefinitionId LegacyRuntimeBrand

LegacyBrandError =
    MissingDefinition(DefinitionId)
  | DuplicateLegacyBrand(LegacyRuntimeBrand)
  | UnencodableLegacyPath(DefinitionId)

legacy-runtime-brand :
  LegacyRuntimeBrandMap -> DefinitionId
  -> Either LegacyBrandError LegacyRuntimeBrand
```

The resolver builds the map from each defining module's canonical historical
runtime namespace. An import alias or mount reuses the target definition's map
entry; it never derives a brand from the caller-visible path. A nominal
TypeAlias first expands FoilAlias/FoilUnion metadata; construction must select a
concrete FoilNominal member before lookup. An EntryAlias follows its target, and
a structural TypeAlias requests no brand. Only concrete constructor
DefinitionIds occur in the map. The map and its artifact form are
deterministically sorted and collision-checked.

This adapter lives only in `src/reaver/foil-legacy-brand-bridge.rvr` and is the
sole allowed producer of slash/path brands after A6. Canonical Type,
CompilerEntry, ModuleView, and artifact semantic fields store DefinitionId,
never its projection. The old constructors, matching, fitting, and PLAN
execution receive the projection only at their existing runtime ABI boundary.
B4 maps every LegacyBrandError to Diagnostic. D3 replaces all consumers with
encode-brand-v1/registry lookup and deletes the bridge, its persisted map, and
its migratory hygiene entry.

### 7.2 Structural Type interface

The generated Type schema MUST include every Type variant, including `TCQUA`
`TDATA`, and `TTYP`.

```text
TypeChild {
  role  : TypeChildRole,
  value : Type
}

TypeChildRole =
    Plain
  | BinderConstraint(name, binder-kind)
  | BinderBody(name, binder-kind)
  | Argument(index)
  | Return
  | Element
  | Wrapped(wrapper-kind)

FoldedTypeChild[a] {
  role   : TypeChildRole,
  result : a
}

type-kind        : Type -> TypeKind
type-children    : Type -> Row TypeChild
type-rebuild     : Type -> Row TypeChild -> Either DataError Type
type-fold        : All(a) (Type -> Row FoldedTypeChild[a] -> a) -> Type -> a
type-fold-scoped : All(a) TypeVisitor[a] -> Type -> a

TypeVisitor[a] {
  enter-binder,
  leave-binder,
  visit-child,
  visit-const-term,
  finish-node
}
```

These operations are purely structural. They MUST NOT expand a nominal,
substitute a variable, strip a face/self/type wrapper, cross a binder, consult
a Subject/Registry, or normalize the Type.

For every canonical Type:

```text
type-rebuild(t, type-children(t)) = Right(t)
```

`type-rebuild` uses the exact generated layout constructor. It MUST NOT call a
canonicalizing public constructor such as a sum constructor that sorts or
deduplicates children. Normalization is a separate operation.

Required child behavior includes:

- `TSUM`: each option;
- `TQUA`: its body, with binder metadata;
- `TCQUA`: both its constraint Type and body, with the binder applying only
  where specified by the Type semantics;
- `TNOM`: the Type in each TypeArg and the declared Type in each ConstArg;
  type-fold-scoped additionally emits every ConstTerm to visit-const-term under
  the current type/const binder scope, while type-rebuild preserves that scalar
  term exactly;
- `TDATA`: every DataTypeRef argument, in parameter order;
- `TFUN`: every argument and the return Type;
- `TSELF`, `TFAC`, `TROW`, `TPIN`, `TTYP`, and `TARR`: their Type children;
  and
- scalar variants: no children.

### 7.3 Wrapper and binder policy

There is no unconditional `type-spine`. Callers use:

```text
TypeFrame =
    Qua(name)
  | CQua(name, constraint)
  | Face(name)
  | Self
  | TypeValue

SpinePolicy {
  strip-qua,
  strip-cqua,
  strip-face,
  strip-self,
  strip-type-value
}

type-spine  : SpinePolicy -> Type -> TypeSpine
type-respine : Row TypeFrame -> Type -> Type

TypeSpine {
  frames : Row TypeFrame,
  core   : Type
}
```

Frames are ordered outermost to innermost. `type-respine` reapplies them from
innermost to outermost, and for every policy/type pair:

```text
type-respine(type-spine(policy, t).frames,
             type-spine(policy, t).core) = t
```

Spine traversal stops at the first wrapper disabled by policy. A CQua frame
retains its exact constraint Type; callers that transform constraints use the
structural/scoped traversal rather than assuming that transforming only the
spine core transforms the constraint.

Each operation explicitly chooses which frames are transparent. Rendering may
preserve frames that fitting treats as transparent. Binder-sensitive
substitution, well-formedness, free-variable discovery, and type application
remain explicit algorithms, but dispatch through generated exhaustive cases
and receive binder enter/leave events.

Nominal expansion is a separate cycle-aware operation keyed by DefinitionId
and instantiated arguments.

### 7.4 Policy-driven value walker

The reflected `Value` and `Limits` data schemas specified in Section 10.3 are
dependency-neutral traversal contracts. They land with this walker in B5,
before any Registry, Rtti witness, brand activation, or public reflection API.
This permits the final walker shape to land once without pulling the RTTI
runtime into the core bootstrap.

```text
WalkPurpose = ShapeCheck | DeepValidate | ReflectDynamic | ReflectExact

OpaquePolicy = RejectUnexpected | PreserveOpaque
UnresolvedGenericPolicy = RejectUnresolved | EmitUnresolved

SchemaResolver {
  by-definition : ReadOnlyMap DefinitionId SchemaTemplate,
  by-layout     : ReadOnlyMap LayoutId SchemaTemplate
}

RuntimeBrandGeneration = LegacySlashPath | DefinitionBrandV1

RuntimeBrandResolver {
  generation,
  by-definition : OrderedMap DefinitionId Nat,
  by-brand      : OrderedMap Nat DefinitionId
}

WalkResult = ShapeOk | Validated | Reflected(Value)

WalkPolicy {
  purpose,
  limits,
  schema-resolver : SchemaResolver,
  runtime-brands  : RuntimeBrandResolver,
  opaque-policy,
  unresolved-generic-policy
}

walk-value-by-type :
  WalkPolicy -> Type -> RuntimeValue -> Either Diagnostic WalkResult
```

The shared walker owns:

- nominal expansion and generic substitution;
- constructor and arity checks;
- shallow and deep validation policy;
- RefEq-based cycle detection where runtime identity is observable;
- depth, node, row/array, and output limits; and
- reflected `Value` construction.

For TDATA, the walker resolves its template directly through
schema-resolver.by-layout, requires a matching CompilerLayout(LayoutId), and
validates the LayoutId head without consulting runtime-brands. For TNOM and
NominalRow, it first resolves metadata through
schema-resolver.by-definition. FoilAlias elaborates and recurses into its full
target Type. FoilUnion elaborates its applied SchemaNominalMembers and selects
the members whose concrete brand matches the actual Pail head. ShapeCheck may
succeed when that candidate set is non-empty without choosing among erased
generic arguments. DeepValidate and ReflectExact try same-brand candidates in
declared member order against their fully substituted Types. Zero successes
produce the normalized candidate failure tree. DeepValidate succeeds when one
or more candidates validate because validation need not select metadata.
ReflectExact requires exactly one successful candidate; more than one is
`reflect/ambiguous-erased-union`.
ReflectDynamic starts from the concrete by-brand RttiInfo and therefore does
not pretend to recover a union root or erased arguments. Only at a concrete
FoilNominal does the walker resolve
the expected DefinitionId through runtime-brands and compare the head. Alias
and union expansion uses the active DefinitionId/argument set for cycle
detection. Both runtime-brand maps MUST be total inverses over reachable
concrete FoilNominal constructors only; a missing entry or collision is a
Diagnostic, never a fallback to printed-path guessing.

B5 constructs LegacySlashPath from LegacyRuntimeBrandMap. D2 constructs a
DefinitionBrandV1 resolver from the validated Registry and encode-brand-v1;
D3 switches every walker caller to it atomically with runtime brand activation.
RuntimeBrandResolver is immutable data and cannot resolve names through Subject.

Pin and law behavior is purpose-specific:

- ShapeCheck validates only the outer pin/law shape.
- DeepValidate may `Unpin` a data pin and recursively validate its payload; it
  MUST never execute a law. A law is checked only for the expected callable
  shape/arity metadata available without evaluation.
- ReflectDynamic never unpins or traverses pins/laws and emits OpaquePin or
  OpaqueLaw.
- ReflectExact first performs DeepValidate when the exact static Type requires
  it, then emits the same opaque reflected value without exposing the payload.

SchemaResolver is immutable data, not an executable capability. Runtime
identity is tracked on the active recursion stack: encountering the same RefEq
identity on that stack is a cycle; encountering shared identity outside the
active stack is ordinary sharing and is not mislabeled a cycle. All traversals
remain bounded even when identity is unavailable.

SchemaResolver.by-definition keys MUST equal template.definition-id.
SchemaResolver.by-layout contains exactly the reachable CompilerLayout
templates and keys each one by its declared LayoutId; duplicate LayoutIds are
rejected. The two indexes are populated from schema/data manifests, never by
converting or guessing between LayoutId and DefinitionId.

`type-fits`, `type-shape-fits`, and reflection-specific structural walkers are
deleted after their callers move to policies over this walker.

## 8. Primitive catalogue

One logical primitive catalogue is authoritative for every compiler primitive,
but it has a bootstrap-safe lower layer and an implementation upper layer:

```text
PrimitiveSignatureSpec {
  id : DefinitionId,
  schema-type : SchemaTypeExpr,
  canonical-path,
  aliases,
  safety-class,
  version
}

PrimitiveImplementationSpec {
  signature-id,
  implementation
}

SafetyClass = CompileTimePure | RuntimeOnly | CompilerTrusted
```

The signature catalogue depends only on generated data, identity, and
SchemaTypeExpr. It MUST NOT import Typed Reaver, Foil builtins, or executable
primitive implementations. Typed Reaver translates its symbolic signatures to
canonical Type values and generates the trusted prelude from this lower layer.
ForAllType and ForAllConst encode polymorphic primitive binders directly; the
elaborated primitive Type MUST be closed under both TVAR and ConstVariable.
There is no second manual binder/signature row.

The implementation attachment layer imports Typed Reaver and associates each
signature ID with one implementation. Runtime FFI installation and the safe
link universe are generated only after this attachment. This split prevents
`typed-reaver -> primitive implementation -> typed-reaver` bootstrap cycles.

Together the layers generate:

- Typed Reaver's trusted prelude;
- the core Type Subject;
- runtime FFI installation;
- aliases;
- DefinitionIds and reflection metadata; and
- the compile-time-safe link universe.

Manual builtin signature tables and direct `insert-ffi` lists are deleted.
Special implementations, including reversed-argument primitives, remain named
implementations referenced exactly once by the attachment layer. Every
signature MUST have exactly one implementation attachment for each runtime
universe that exposes it; missing or duplicate attachments are bootstrap
diagnostics.

Safety metadata is compiler-produced and unforgeable by transformer source.
Changing an implementation, type, alias, or safety class changes the catalogue
digest used by artifacts.

## 9. Single compilation engine

```text
compile-unit :
  CompileInvocation -> Either Diagnostic CompileResult
```

### 9.1 Import planning and replay policy

Import handling is divided into:

1. deterministic graph planning and validation; and
2. a compile-or-replay policy for each planned unit.

Cold and cached modes share graph semantics, collision rules, mount rules,
identity assignment, result construction, and diagnostic normalization. They
need not perform identical work: a valid artifact hit MUST skip body parsing,
elaboration, lowering, and splice execution.

There is one `resolve-imports` implementation at the semantic layer. Storage
backends supply source/artifact facts through typed interfaces; they do not
reimplement namespace or diagnostic semantics.

Existing public functions such as `compile-mod`, cached variants, and profiling
entry points remain only as thin projections or wrappers over compile-unit.
Profiling MUST NOT change compilation semantics.

### 9.2 Artifacts

Artifacts have an explicit version and contain every semantic field needed for
replay, including lore, origins, entries, exports, resolved identities, module
view, and transitive schema metadata.

Artifact validity includes at least:

- artifact schema and compiler digest;
- ModuleId, SourceDigest, and direct dependency digests;
- PackageId and substrate digest;
- compile flags and limits;
- primitive catalogue digest; and
- for splice modules, generator code, safe-dependency, context, and splice
  policy digests.

In ordinary cache mode, an unsupported or stale artifact is a deterministic
miss followed by rebuild. In explicit offline/artifact-only mode, it is an
`artifact/version-unsupported` or `artifact/stale` Diagnostic. No stale schema
is silently interpreted as current data.

Memory hits SHOULD avoid source reads after validity is established. Artifact
hits MUST have instrumentation proving that body parse, elaboration, lowering,
and splice evaluation did not execute.

## 10. RTTI and reflection

### 10.1 Runtime schemas

```text
Rtti[a] {
  exact-type : Type,
  root       : Maybe DefinitionId,
  witness    : CompilerWitness
}

RttiInfo {
  id              : DefinitionId,
  erased-brand    : DefinitionBrand,
  schema-template : SchemaTemplate
}

Registry {
  by-brand      : OrderedMap DefinitionBrand RttiInfo,
  by-definition : OrderedMap DefinitionId SchemaTemplate
}
```

`Rtti[a]` is a term-level witness for a well-formed, fully instantiated Type.
Polymorphic code receives `Rtti[a]` explicitly. An erased runtime brand cannot
recover generic arguments.

Every RttiInfo.schema-template MUST use FoilNominal and its definition-id MUST
equal RttiInfo.id. CompilerLayout/TDATA templates are available only to
compiler-generated accessors and the safe transformer API; they are not
inserted into either Registry index and cannot be obtained through public
reflection in V1. Registry.by-definition contains reachable FoilNominal,
FoilUnion, and FoilAlias templates. Registry.by-brand contains only concrete
FoilNominal templates, because only those declarations have runtime brands.

Rtti constructors and CompilerWitness are compiler-sealed. User code cannot
construct, update, deserialize, or forge them through generated public schema
constructors. `reflect/rtti[T]` is the only source-level constructor and the
inspection bridge validates its compiler/registry witness before trusting the
exact Type. Tampered or stale witnesses are `reflect/invalid-rtti`.

The public APIs are:

```text
reflect/registry : Registry
reflect/rtti[T]  : Rtti[T]

reflect/brand : Pail -> DefinitionBrand

reflect/lookup :
  Registry -> DefinitionBrand -> Either Diagnostic RttiInfo

reflect/inspect :
  Limits -> Registry -> Pail -> Either Diagnostic Value

reflect/inspect_exact :
  All(a) Limits -> Registry -> Rtti[a] -> a
  -> Either Diagnostic Value

pretty :
  All(a) Limits -> Registry -> Rtti[a] -> a
  -> Either Diagnostic Text

pretty/dynamic :
  Limits -> Registry -> Pail -> Either Diagnostic Text
```

Registry and Limits are explicit. There is no hidden unlimited traversal.
`reflect/registry` is the deterministic registry generated for the current
compiled module. It is a compiler intrinsic expanded to that lexical module's
private registry constant: an imported function continues to use the registry
of the module in which its source occurrence was compiled, not its caller's
registry. Callers may pass another registry explicitly to the other APIs.

### 10.2 Registry closure

SchemaManifest construction and Registry materialization together:

1. start with every typed Foil runtime declaration in the current module and every
   directly visible imported entry's public Type;
2. traverse those Types for nominal, union, and alias DefinitionIds;
3. add each referenced FoilNominal, FoilUnion, or FoilAlias schema to the
   neutral SchemaManifest;
4. traverse fields, union members, alias targets, sum alternatives, generic
   templates, and referenced nominal definitions;
5. stop through a visited DefinitionId set and sort the manifest by
   DefinitionId;
6. validate the persisted manifest when loading it; and
7. copy every retained template to Registry.by-definition; for each
   FoilNominal template only, encode its DefinitionId, construct RttiInfo, and
   add it to Registry.by-brand.

DefinitionId ordering is the lexicographic order of its generated fields and
path segments. Registry.by-definition iterates in DefinitionId order;
Registry.by-brand iterates in ascending numeric DefinitionBrand order.
Injective encoding ensures one brand key maps to exactly one concrete RttiInfo.

Only schema metadata is followed transitively. Unrelated definitions and
runtime values are excluded.

If public schema A references non-visible schema B, B's schema metadata is
included so A remains inspectable through an importer. This does not grant
source-name visibility, value access, or the ability to reference B in source.
Field names and Type/schema structure of such a reachable B are intentionally
visible through reflection and pretty printing; values and unrelated private
declarations are not.
Such an entry is marked ReachablePrivate. It cannot be used as a source lookup
root or returned as a runtime value merely because its schema is present.
Unit and artifact formats therefore retain transitive schema metadata across
module boundaries.

### 10.3 Reflected Value and limits

```text
ReflectedField {
  name  : Maybe Text,
  value : Value
}

TruncationReason = Depth | Nodes | Items | TextBytes

Value =
    Natural(Nat)
  | BooleanValue(Bool)
  | TextValue(Text)
  | ReflectedType(Type)
  | PailValue(Value)
  | OpaqueAny
  | NamedRow(DefinitionId, Text, Row ReflectedField)
  | StructuralRow(Row Value)
  | Variant(Text, Row ReflectedField)
  | ArrayValue(Row Value)
  | OpaquePin
  | OpaqueLaw
  | UnresolvedGeneric(parameter-name, Type)
  | Cycle(cycle-id)
  | Truncated(TruncationReason, omitted-count)

LimitMode = Strict | Truncate

Limits {
  mode,
  max-depth,
  max-nodes,
  max-row-or-array-items,
  max-text-bytes
}
```

Natural(_, Number), Natural(_, Boolean), and Natural(_, Text) map respectively
to Natural, BooleanValue, and TextValue; Boolean additionally rejects a Nat
outside the compiler's canonical Bool encoding. Pail, TypeWrapper, and Any map
to recursively inspected PailValue, ReflectedType, and OpaqueAny. OpaqueAny
never retains or exposes its payload. A zero-field Unit nominal remains a
NamedRow with its declaration name; it is not conflated with an arbitrary Nat.
Additional scalar forms require an explicit Value variant and schema-version
change; they are not encoded in an untyped catch-all payload.

Dynamic inspection substitutes only type arguments established by the value
and registry. A field depending on erased generic information becomes
`UnresolvedGeneric`; it is not guessed. Exact inspection substitutes all
arguments from `Rtti[a]` and deeply validates the value.

In Strict mode, any limit exhaustion is a structured Diagnostic. In Truncate
mode, inspection emits the corresponding deterministic Truncated value and
pretty printing renders it as `…`. An identity is recorded as Cycle only when
it is encountered on the active recursion stack; repeated non-active sharing
is rendered again and remains subject to node limits.

Named rows render as `name{field=value}`, arrays as `[a, b]`, variants as
`.tag(...)`, booleans as `true`/`false`, a unit NamedRow by its schema name,
ReflectedType through the
canonical Type renderer, PailValue as its nested value, OpaqueAny as `#<any>`,
pins/laws as `#<pin>`/`#<law>`, and truncation as `…`.
`web/show_pail` and other handwritten brand cases are deleted after migration.
`Text` is the existing Cord/Nat text representation; it is not Foil's `quip`
aura sum. Web and formatter adapters preserve this exact result type.

## 11. Pure compile-time splices

### 11.1 Transformer ABI

Top-level syntax is:

```foil
# generator-expression
```

The expression resolves to an imported transformer:

```text
Transformer =
  CompilerContext -> Either Diagnostic (Row EmittedDecl)
```

V1 does not require a new module declaration form. Referencing a binding from
`#` causes that binding and its complete callable dependency graph to be
compiled and linked in the safe universe. Code previously compiled against the
ordinary runtime universe cannot later be asserted safe.

### 11.2 Safe universe

A transformer runs in a separately compiled and linked universe containing
only catalogue entries marked `CompileTimePure` plus the explicitly approved
compiler/schema/parser API. Running ordinary code in a nominally pure PLAN
evaluator is insufficient.

Every transitive callable dependency MUST carry compiler-produced safe
provenance. The linker rejects:

- runtime-only or unknown primitives;
- filesystem, environment, clocks, randomness, actors, mutable state, and host
  callbacks;
- raw Subject, cache, compiler-storage, law, or pin capabilities;
- higher-order or dynamic calls whose target cannot be proven safe; and
- artifacts compiled against the ordinary runtime FFI universe.

The proof procedure is:

1. Recompile the transformer and every source module in its dependency closure
   against a global environment containing only PrimitiveSignatureSpecs marked
   CompileTimePure and the approved compiler API. Ordinary runtime artifacts
   are never relabeled or reused as safe code.
2. Give every resulting callable an unforgeable `SafeCallable` witness tied to
   the compiler, safe-catalogue, module, and code digests.
3. Verify canonical TypedCode and lowered IR exhaustively. Every global,
   primitive, captured value, and capability edge must resolve to the safe
   universe. An indirect/higher-order call is accepted only when its callable
   operand has a valid SafeCallable witness or is a locally proven lambda whose
   captures pass the same verifier.
4. Deep-force and seal the verified code before evaluation. Loading a safe
   artifact repeats witness/digest and exhaustive IR verification before use.

An unknown or unverifiable call edge fails closed. Safe provenance is not a
source-level value, cannot be constructed by schema APIs, and is stripped from
transformer-visible data. Tampered safe artifacts are diagnostics, never cache
misses that execute unverified code.

`CompilerContext` is immutable, closed, and serializable. It contains only:

- ModuleId and splice Origin;
- provisional declarations and their public typed views;
- directly visible imported entry views;
- the provisional transitive Registry;
- deterministic fresh-name seed material; and
- limits and compiler version information.

It contains no executable value, raw Subject/storage/cache, provider, callback,
law, or pin.

### 11.3 Evaluation and validation

Each splice receives a byte-equal provisional ModuleView and Registry and runs
in isolation. Its invocation fields differ only by splice Origin and derived
fresh-name seed. Sibling splices cannot observe one another's output.

Fuel, allocation, nesting, emitted-declaration count, serialized output size,
and diagnostic size are deterministic limits. Evaluation, deep forcing,
schema validation, and canonical serialization are all charged before output
leaves the safe evaluator. This prevents a lazy or executable payload from
escaping the boundary.

Output containing laws, pins, imports, nested splices, malformed/foreign schema
values, executable payloads, or unauthorized hygienic references is rejected.
Hygienic DefinitionId references are limited to declarations visible in the
CompilerContext; transitive schema reachability is not a source-visibility
capability.

Fresh names derive from:

```text
(ModuleId,
 splice source ordinal and span,
 generator DefinitionId,
 generator-local counter)
```

They never depend on execution order, randomness, cache state, or sibling
output.

Location-derived fresh names are restricted to non-public hygienic locals and
private temporary declarations that do not mint externally observable nominal
identity. A generated top-level/public declaration MUST provide an explicit
stable local path or call `compiler/stable_decl_name(generator-key,
local-key)`, where both keys are generator-defined stable data independent of
whitespace, call-site byte offsets, and unrelated splice insertion. Duplicate
stable keys are diagnostics. This preserves edit-stable DefinitionIds and
brands for public generated declarations.

### 11.4 Compilation pipeline

Splice-aware compilation is an extension of `compile-unit`, not another engine:

1. Establish the current module's ModuleId from the compilation realm.
2. Parse the module, assign dependency ModuleIds while resolving imports, and
   predeclare every source declaration.
3. Run signature elaboration and build the provisional ModuleView and
   transitive Registry.
4. Typecheck and run every splice against the same provisional context.
5. Deep-force, validate, origin-tag, and canonically serialize every output.
6. Pool source and generated declarations in source-splice/emission order.
7. Diagnose all duplicate DefinitionIds; no declaration wins a collision.
8. Perform whole-module final predeclaration.
9. Build final RTTI, elaborate, validate, lower, and export.

Signature elaboration is distinct from body elaboration. It:

- predeclares all nominal names and DefinitionIds;
- resolves forward Type references to a fixed point;
- checks explicit declaration signatures, nominal field Types, generic
  binders, and const constraints without evaluating declaration bodies; and
- fails the module before any splice runs if a signature is malformed or
  unresolved.

A value declaration without a stable checked signature appears as
`OpaqueDeclaration(id, source-name, origin)` in the provisional ModuleView. A
transformer may emit an ordinary source-name reference for final resolution,
but may not inspect its Type/value or manufacture an exact Rtti witness for it.
Forward-reference and opaque-declaration rules are identical for every sibling
splice.

Generated declarations participate in ordinary final module scope. They may
forward-reference source or generated declarations wherever source
declarations may do so. Deterministic ordering controls serialization and
diagnostic order; it is not a scoping rule.

Generated output may contain declarations only. It cannot add imports or
splices. Schema-generated syntax constructors and `compiler/parse/expr` and
`compiler/parse/decls` are available in the safe universe.

A valid artifact hit for a splice-containing module MUST NOT rerun any
transformer.

## 12. Dependency-safe landing order

Every landing MUST pass its focused tests, hygiene checks, aggregate Foil
tests, and `nix flake check`. A failed, interrupted, timed-out, or emitted
`"ERROR"` run is not a pass.

### Phase A: contracts and bootstrap

#### A1. Inventory and guardrails

- Inventory every compiler record family, positional accessor, Type/value
  walker, compile path, import resolver, builtin table, and unsafe primitive.
- Land hygiene checks with an exact, shrinking legacy allowlist.
- Add test helpers for normalized diagnostics and semantic compile results.
- Record numeric fresh-build, artifact replay, snapshot-size, and PLAN arena
  baselines and accepted regression thresholds.
- Land `doc/typed-foil-compiler-core-checks.md`, mapping every release-gate
  suite to a named flake check or exact checked-in command, timeout, required
  fixtures, and emitted-ERROR scanner. A suite named by this specification is
  not covered merely because some aggregate test happens to import it.
- Change no runtime representation.

**Gate:** the baseline suite passes; each migratory legacy exception has an
owner and deletion landing; and each permanent boundary exception has an owner,
exact allowlist entry, and justification.

#### A2. Dependency-free define/data substrate

- Land neutral descriptors, trusted bootstrap constructors/predicates/accessors,
  safe-accessor templates, updates, exhaustive cases, traversal metadata,
  DataError, and neutral HelperSignature manifests. Do not expose an
  Either-returning boundary accessor yet.
- Reserve the final Maybe/Either LayoutIds and descriptors as neutral data only;
  A4 is their sole runtime/API activation landing.
- Land the dependency-neutral frame-nat/frame-path byte primitives used by the
  reserved bootstrap layout key; A5 reuses these exact primitives for brands.
- Land BootstrapLayout signature elaboration fixtures, but do not migrate
  any production compiler record family or activate canonical Maybe/Either yet.
- Prove the substrate bootstraps with no Type, Subject, or Typed Reaver
  dependency.

**Gate:** only the macro/runtime bootstrap uses generated helpers; every such
call site has an exact typing-exception entry that A3 removes, and no second
production compiler representation has been introduced.

#### A3. Typed Reaver bootstrap capability

- Extend Typed Reaver, against the existing Type boundary, with the local
  definitions, recursion, exhaustive generated cases, compiler record types,
  and trusted bridge signatures required to migrate the Type helper cluster.
- Resolve and check every foundational HelperSignature emitted in A2 using
  BootstrapLayout; expire the untyped generated-helper call-site allowlist
  before A4 begins. Only the sealed stage-0 metadata route remains.
- Add focused negative tests proving unsupported forms still fail closed.
- Do not add schema mirrors or a second trusted primitive table.

**Gate:** the complete Type migration can be expressed with `define/typed` or
schema-generated typed helpers before any Type representation changes.

#### A4. Canonical Maybe and Either

- Land compiler-internal Maybe and canonical Either plus their std/raw result
  bridges and immediately type-check every generated helper.
- Enable canonical Either-returning safe accessors, re-expand every A2
  descriptor/fixture, and confine trusted accessors to generated internals.
- In this same merge landing, migrate every compiler-internal optional/result
  producer and consumer and delete all legacy helpers and ad hoc shapes; retain
  only the exact named boundary bridges.
- Prove the foundational Maybe/Either modules still import no Type, Subject, or
  Typed Reaver implementation module.

**Gate:** no compiler-internal second Maybe/Either representation or deferred
optional-helper allowlist remains.

#### A5. Identity and brand vectors

- Using the typed compiler-record capability from A3, land PackageId, ModuleId,
  DefinitionId, IdentityError, and digest types.
- Migrate module-resolution identity assignment with define/typed helpers only.
- Attach deterministic DefinitionIds to the canonical Maybe/Either families
  and helpers already generated in A4, without changing their layouts.
- Land BrandEncodeError, BrandDecodeError, encode/decode/predicate behavior,
  over A2's framing primitives and golden vectors, but do not yet change
  nominal runtime brands.

**Gate:** identity is alias-, mount-, cache-, content-, process-, and
compile-order independent; duplicate IDs return IdentityError and have no
winner.

#### A6. Canonical Type and structural traversal

- Define the complete Type family with `define/data`, including TCQUA, TDATA,
  and TTYP.
- Land NominalRef, TypeArgument, ConstTerm, ground InstantiationId, DataTypeRef,
  and RowTag as part of that same Type family migration.
- Migrate every Type producer and consumer to generated cases and accessors.
- Land structural children/rebuild, explicit spine policies, and binder events.
- Separate raw rebuilding from Type normalization.
- Re-elaborate every generated helper signature in CanonicalData mode and use
  the rebuilt compiler to recheck the same source tree before accepting the
  migration.
- Reject and discard all stage-0 BootstrapLayoutRef-bearing metadata after that
  successful canonical recheck; retain only the sealed macro/checker bootstrap
  implementation needed by future clean source builds.
- Land the exact legacy-runtime-brand bridge so the pre-RTTI core continues to
  construct, fit, match, and execute historical branded values without storing
  those brands in canonical Type.
- Delete handwritten Type tags, constructors, positional accessors, and
  structurally duplicate traversals.

**Gate:** traversal roundtrips every variant; binder/capture tests pass; TNOM
identity uses DefinitionId rather than import or mount paths; and the legacy
runtime projection is alias/mount independent and collision-checked.

#### A7. define/foil-schema and post-Type Typed Reaver attachment

- Attach Foil/Typed Reaver metadata to the already canonical Type descriptor
  without changing Type values.
- Land the exact SchemaTemplate, mixed SchemaArgument, and SchemaError families
  and their kind/arity/substitution checks.
- Extend Typed Reaver with any compiler schema types that require the canonical
  Type descriptor, without broadening the unsafe bridge.
- Land the combined form for non-bootstrap schemas.

**Gate:** clean bootstrap and schema-expansion tests prove there is no
Type/Subject/Typed Reaver import cycle.

#### A8. Canonical Span and Origin

- Land the final Span and Origin schemas after DefinitionId exists.
- Migrate source-location producers and consumers to those generated families
  and preserve source origin from parsing onward.
- Reserve Generated and Synthetic construction APIs for later compiler phases;
  no Diagnostic representation changes in this landing.
- Delete duplicate span/location wrappers and remove their allowlist entries.

**Gate:** every syntax family can refer to canonical Origin before its own
migration, and generated-origin constructors are deterministic from their
explicit inputs.

### Phase B: canonical compiler families

#### B1. Syntax and declaration families

- Migrate surface syntax and declaration families one atomic family at a time.
- Preserve Span and Origin from parsing onward.
- Migrate parser and elaborator consumers, then delete old tags and adapters.

#### B2. TypedCode family

- Migrate every typed compiler-code/TC AST variant to generated schemas.
- Convert elaboration, Type checking, lowering, relocation, rendering, and
  reference discovery to generated exhaustive cases and accessors.
- Keep the outer legacy `TC`/`IR_ENTRY` storage containers allowlisted until
  C1, but delete handwritten TypedCode tags and positional accessors here.

#### B3. Primitive catalogue

- Land the dependency-neutral signature/safety catalogue, then the
  Typed-Reaver-dependent implementation attachment layer.
- Generate every existing consumer and prove the module graph has no
  Typed-Reaver/implementation bootstrap cycle.
- Include DefinitionId, SchemaTypeExpr, aliases, version, and safety
  classification.
- Delete manual signature, trusted-prelude, and `insert-ffi` registration
  tables.

#### B4. Unified diagnostics

- Land the final Diagnostic schema over the already canonical Origin family,
  the neutral SourceProviderKey, ProviderRevision, and ProviderFault boundary
  families, and the typed unsafe exception-capture bridge.
- Land exhaustive conversions from IdentityError, BrandEncodeError,
  BrandDecodeError, DataError, SchemaError, LegacyBrandError, and ProviderFault
  to stable Diagnostic codes.
- In the same atomic family landing, migrate parsing, import resolution,
  elaboration, lowering, artifacts, Forge/Helm, and formatting.
- Preserve source and generated origins.
- Delete raw diagnostic-row conventions and duplicate location wrappers, then
  remove their hygiene allowlist entries.

#### B5. Shared value walker

- Land the dependency-neutral reflected Value and Limits schemas, the
  policy-driven walker, SchemaResolver, and RuntimeBrandResolver. Initialize
  walker callers with LegacySlashPath; do not expose RTTI APIs yet.
- Migrate shallow boundary checks, deep validation, and future reflection hooks.
- Delete type-fits, type-shape-fits, and duplicate general walkers.

#### B6. Environment and compiler-state families

- Migrate environments, notes, layers, mounts, units, provenance, and
  resolution records one family at a time.
- Land EntryId and AliasTarget before DeclarationView; migrate environment and
  tooling alias records to preserve full Type/EntryId targets.
- Land the neutral SchemaManifest and ModuleView families, including the
  deterministic transitive DefinitionId closure builder, used by compiler
  results and later RTTI registry materialization.
- Keep Cairn/Subject storage details inside their named bridges.
- Do not migrate entries or artifacts until their final schemas below.

### Phase C: entries and one compiler engine

#### C1. Unified CompilerEntry and lowering

- Land CompilerEntry and LoweredEntry over EntryId/AliasTarget from B6.
- Convert elaboration, const materialization, lowering, relocation, Forge,
  Helm, and reference-index consumers.
- Prove that two materialized InstantiationIds of one generic definition remain
  distinct entries while sharing the erased declaration brand.
- Keep only minimal generated-accessor boundary adapters.

**Delete:** `TC` entry containers, `IR_ENTRY`, `ENT`, `make-tc-entry`,
`make-ir-entry`, `entry-parts`, and tag-dependent consumers.

#### C2. Artifacts and caches

- Land final artifact schemas and the stable MemoryCache, ArtifactCache, and
  CacheOutput contracts required by OnlineCompileMode, StrictOfflineRequest,
  and CompileResult.
- Land the non-executable ProviderSnapshot fact schema persisted by
  strict-offline artifacts over the provider key/revision families from B4;
  C3 later attaches the live read-only capability operations.
- Store lore, origins, identities, semantic entries, ModuleView, and
  SchemaManifest dependency data in artifacts.
- Migrate every artifact/cache producer and consumer, version artifacts, and
  define miss/offline rejection behavior.
- Delete old artifact/cache layouts and adapters and remove their allowlist
  entries.

#### C3. CompileRequest and CompileResult

- Land the final CompileRequestCommon, OnlineRequest, StrictOfflineRequest,
  CompileRequest, CompileInvocation, CompileResult, and sealed read-only
  SourceProviderCapability contracts over the cache contracts from C2 and the
  ProviderFault family from B4.
- Migrate every public compiler request producer, projection, and result
  consumer to generated accessors in the same family landing.
- Migrate source resolution/reading to at most one live ProviderSnapshot per
  request (zero for StrictOffline) and reject provider-reported identity,
  revision, realm, or digest mismatches.
- Delete legacy compile-request and compile-result rows and adapters and remove
  their allowlist entries.

#### C4. Single compile-unit engine

- Split deterministic graph planning from compile-or-replay policy.
- Route cold, memory-cached, artifact-cached, profiling, Forge, and Helm callers
  through compile-unit.
- Retain public APIs only as thin projections.
- Delete other engines and import resolvers.

**Core consolidation gate:**

- all semantic and normalized-failure equivalence properties pass;
- cache-hit instrumentation proves skipped work;
- no non-boundary duplicate representation, engine, resolver, Type walker, or
  value walker remains;
- artifact, Forge/Helm, aggregate, snapshot, hygiene, and flake suites pass;
  and
- fresh and artifact performance/arena budgets have no regression beyond the
  accepted threshold.

### Phase D: RTTI release

#### D1. RTTI metadata schemas

- Land Rtti, RttiInfo, Registry, visibility, and sealed-witness schemas over
  the reflected Value and Limits families already landed in B5.
- Land the public signatures but keep reflection and V1-brand construction
  feature-gated until D3.
- Do not switch nominal runtime brands or change match/fitting behavior here.

#### D2. Registry materialization and closure validation

- Consume the SchemaManifest dependency data already persisted across
  unit/artifact boundaries; version artifacts here only if the core manifest
  contract proves insufficient.
- Validate the deterministic DefinitionId closure; materialize all reachable
  Foil runtime templates in Registry.by-definition and only concrete
  FoilNominal constructors in Registry.by-brand, without Subject access.
- Materialize and inverse-check the DefinitionBrandV1 RuntimeBrandResolver, but
  do not activate it in runtime consumers yet.
- Test hidden transitive schemas, cycles, aliases, mounts, and generics.

#### D3. Brand activation and inspection bridge

- Switch nominal runtime brands atomically to encode-brand-v1 now that the
  complete Registry materializer exists.
- Switch every shared-walker caller from the LegacySlashPath resolver to the
  prevalidated DefinitionBrandV1 resolver in this same landing.
- Replace slash-based `branded-cstr?`, TPAIL fitting, match dispatch,
  constructors, and host-side Pail validation with definition-brand-v1?,
  decode, and registry lookup in this same landing.
- Delete foil-legacy-brand-bridge.rvr, its persisted projection map, and its
  migratory hygiene exception in this same landing.
- Invalidate or explicitly convert old branded values and snapshots.
- Implement brand lookup and dynamic/exact inspection through the shared
  walker.
- Confine raw runtime rows to this bridge.
- Test malformed values, unknown brands, unresolved/exact generics, cycles,
  opacity, and every limit.

#### D4. Pretty printing

- Implement typed and dynamic pretty over reflected Value.
- Replace `web/show_pail` and all manual brand dispatch.

**RTTI release gate:** registry closure, reflection, pretty snapshots,
Forge/Helm/web, malformed-input, snapshot-invalidation, hygiene, aggregate, and
flake suites pass. No splice code is required.

### Phase E: independently gated splices

#### E1. Safe transformer universe

- Build the safe linker from the primitive catalogue.
- Define CompilerContext, EmittedDecl, transformer ABI, provenance, and budgets.
- Reject unsafe direct, transitive, higher-order, captured, and lazy escape
  paths.

#### E2. Syntax and output validation

- Add top-level `# expression` and the corresponding SAST form.
- Update every exhaustive SAST consumer in the same landing. Until E3 enables
  execution, the feature-gated compiler handler returns a stable
  `splice/not-enabled` Diagnostic.
- Expose schema constructors and parser helpers in the safe universe.
- Deep-force and validate declaration-only output.
- Implement deterministic fresh names and authorized hygienic references.

#### E3. Single-engine splice pipeline

- Extend compile-unit with provisional predeclaration/registry, isolated
  same-view execution, validated pooling, and the final whole-module pass.
- Produce duplicate diagnostics instead of collision winners.
- Preserve generated origin through every later phase.
- Force splice-containing modules to `Cold` cache policy until E4 lands the
  complete splice validity keys and no-execution replay behavior.

#### E4. Splice artifacts and replay

- Include safe catalogue, generator, transitive dependency, context, limits,
  and output digests in artifact validity.
- Extend semantic equivalence properties to splice success and failure.
- Prove valid hits never rerun transformers.

**Splice release gate:** purity attacks, deterministic replay, sibling
isolation, final-pass forward references, fresh-name stability, collisions,
all limit failures, generated origin, artifact no-execution, snapshot,
hygiene, aggregate, and flake suites pass.

## 13. Acceptance matrix

The following tests are release blockers for their applicable gate.

| Area | Required acceptance |
| --- | --- |
| Bootstrap | Build from source without a prebuilt compiler snapshot; stage-0 BootstrapLayoutRef metadata rechecks to TDATA and no token survives in the stage-1 image/cache/artifact; no schema import cycle |
| Generated data | Layout goldens, malformed tag/arity rejection, accessors, updates, exhaustive cases, descriptor roundtrip |
| Layout ABI | LayoutId collision rejection, exact field slots/cardinality, malformed safe access, Maybe/Either and legacy bridge goldens |
| Identity | Cross-package uniqueness; alias/mount independence; edit stability; rename instability; deterministic generated IDs; brand property and golden tests |
| Physical identity | Source edits change content/unit pins where appropriate without changing unrenamed ModuleId/DefinitionId |
| Type | Exact NominalRef/TypeArgument, ConstTerm, and DataTypeRef layouts; TDATA LayoutId fitting never accepts a nominal brand; every-variant traversal roundtrip; scoped Type/ConstVariable events; TCQUA constraint/body; TQUA/TCQUA capture avoidance and ground InstantiationId rejection; spine roundtrip; recursive/generic TNOM termination |
| Diagnostics | Stable code/datum catalogues; deterministic multi-error ordering; deep-forced lazy exception capture; source/generated/generator origins; cold/cache/artifact equality; shared text/HTML tree |
| Entries | Typed-to-lowered enrichment; structural, applied-generic, nominal, and EntryId aliases preserve complete targets and detect cycles; builtins and accessors; two materializations of one generic coexist under distinct Instantiation EntryIds while erasing to one declaration brand; no legacy tags outside bridges |
| Primitive catalogue | Bootstrap without cycle; signature/implementation one-to-one; equal Types/paths/aliases across trusted prelude, Subject, runtime FFI, safety universe, and reflection metadata |
| Compilation | Generated import graphs; cold/memory/artifact semantic equality for success and failure; lore; recursive types; parallel determinism |
| Source providers | Two backends serving the same logical graph produce equal semantics/diagnostics; revision mismatch revalidates; digest mismatch fails; strict offline makes no provider call |
| Legacy projections | Checked-in PackageId, canonical logical module paths, physical bad-fixture mapping, and equal semantics with compile-unit |
| Cache hits | Instrumentation proves no body parse/elaboration/lowering/splice execution; invalidation by every declared digest |
| Artifacts | Version behavior, deterministic semantic bytes/digests across processes, transitive schema retention, offline diagnostics |
| Brand/Pail | Pre-D3 core constructs/fits/matches/executes and shared-walker validates legacy runtime brands after canonical TNOM/TROW migration; projection is alias/mount independent; V1 decoder/predicate and inverse resolver goldens; atomic walker/adapter/snapshot transition; malformed versus syntactic-unknown brand; host validation |
| Registry | C imports A while A's public schema references hidden B; generic FoilUnion member applications and FoilAlias targets retained in by-definition while only concrete constructors enter by-brand; cyclic/generic closure; comparator goldens; deterministic order; no unrelated values |
| Reflection | Rtti forgery/tampering; exact and erased generics including named union roots whose values carry member brands and same-brand generic-member ambiguity; malformed/unknown values; every exportable Type→SchemaTypeExpr→Type roundtrip and all NatRendering mappings; deep Pin policy; opaque law/pin rendering; active-stack cycles versus sharing; every traversal limit |
| Pretty | Named/structural rows, sums, arrays, opaque values, unresolved generics, cycles, truncation, and web replacement snapshots |
| Splice purity | Direct/transitive I/O, environment, clock, random, actor, mutation, unsafe FFI, captured law/pin, unverifiable higher-order/dynamic call, lazy-output, and safe-artifact tampering attacks |
| Splice signatures | Forward Type references, malformed signatures before execution, opaque unannotated declarations, and sibling-equal provisional views |
| Splice semantics | Same-view siblings, final forward references, declaration-only output, duplicate diagnostics, local fresh-name determinism, public stable-name invariance under whitespace/unrelated splice insertion, generated origins |
| Performance | Fresh, cache-hit, artifact replay, registry size, reflection limits, snapshot size, and PLAN arena budgets |
| Aggregate | Typed Reaver, Foil compiler/integration/execution, cache/artifact, Forge/Helm/web, snapshots, and `nix flake check` |

At minimum, the check manifest MUST explicitly cover the current focused suites
for Type, Subject, environment, relocation, provenance, integration, execution,
rendering, cache/artifacts, Typed Reaver, Helm/Forge/web adapters, and the
aggregate Foil runner. Any such suite absent from `flake.nix` must be added as a
named check or listed with a separate mandatory command before a release gate
can pass.

Test drivers MUST scan output for emitted `"ERROR"` independently of process
exit status. A timeout or interrupted run is recorded as unvalidated or failed,
never passed.

## 14. Completion criteria

The overall specification is complete only when:

- every migrated compiler family has one generated canonical representation;
- no forbidden handwritten tags or positional accessors remain;
- the representation allowlist contains only the six stated boundary classes;
  the unsafe-primitive/raw-exception allowlist contains only
  `foil-unsafe-bridge.rvr`; the typing-hygiene allowlist contains only the
  define/data macro/runtime implementation; and the bootstrap-metadata
  allowlist contains only the sealed BootstrapLayout encoder/checker;
- one Type traversal, one value walker, one import resolver, and one compiler
  engine remain;
- cold, memory, and artifact compilation are semantically equivalent;
- RTTI and pretty printing ship and pass their release gate independently;
- splice purity is transitive and artifact replay does not execute generators;
  and
- all focused, aggregate, hygiene, snapshot, performance, and flake gates pass.
