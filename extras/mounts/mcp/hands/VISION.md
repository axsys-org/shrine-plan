# Shrine: how the world discovers, organizes, and connects itself

This is the specification the hands are built against, as written by Ian (2026-10-23). Where an implementation
choice conflicts with it, this document wins. ONTOLOGY.md records the structural scheme that serves it; SYNC.md the
networking design.

The system begins with a simple principle: information should be encountered once, understood in context, given a
durable place, and made available wherever it becomes relevant.

The purpose is not to collect pages, fill databases, or build a universal hierarchy. It is to let independently
maintained worlds grow into a connected body of knowledge without surrendering their independence.

A person should be able to give the system a website, a document, a question, a collection of records, or access to
another world. The system should progressively discover what is there, recognize what already exists, preserve what is
new, and make its relationships navigable.

An agent should experience the resulting knowledge as a world it can move through, not a pile of search results that
it must reconstruct on every encounter.

## 1. Discovery begins with what the agent already knows

When asked about something, the agent first looks within the world it can already see: the subject's existing record,
its immediate contents, and the connections already known. It does not immediately search the internet, does not
reread documents already organized, and does not assume that a fact missing from one folder is unknown. It follows
names, relationships and existing sources outward from the subject, reading only what the question needs. Records may
come from several independently maintained worlds; it follows them as one connected structure. When the existing world
is insufficient, it expands the search.

## 2. Search extends from the known into the unknown

It searches names and descriptions in accessible worlds, follows references and back-references, inspects attached
sources, and only then searches the public web (search engines for candidates; Firecrawl, when available, to retrieve
readable content and follow pages within a site). Each discovery gives possible new names and relationships. Discovering
a page is not establishing its contents as truth: the original source, the statements it makes, and the agent's
interpretation are kept distinct. Disagreeing sources are both preserved with their origins. Search expands observation;
it is not permission to overwrite what is known. The agent stops when it has sufficient evidence or must present the
remaining uncertainty.

## 3. Encountered information becomes part of a durable world

A useful page remains identifiable as a source: address, retrieval time, content, relationship to its site, and its
exact retrieved version as distinct from the current one. The agent then understands it in relation to what it knows,
creating structured knowledge where that improves understanding, reuse or navigation, and keeping text as text where
that serves better. No fixed universal ontology. Every interpretation stays traceable to the material it came from.

## 4. Naming is reconciliation, not automatic creation

Before making a record, the agent asks whether the thing exists, searching names, aliases, sources, descriptions and
relationships for identifying evidence, not textual similarity alone. A supported match reuses the record; an
inconclusive one preserves uncertainty; only something genuinely new gets a new record, in its owning world. The aim is
recognizing that different names refer to the same thing while preserving who made that judgment and why.

## 5. Records remain where they belong; relationships travel

Each independently owned record keeps its place. Worlds' records are never inserted into one another; the relationships
are preserved (`acquired_by`, `founded`), meaningful by context, not by a fixed definition. A record becomes discoverable
from many places without being copied. This is how independent worlds form a network.

## 6. The network can be experienced as a hierarchy

A relationship may appear as a folder, a child or a navigable path, drawing from several worlds, without any change of
ownership. The same records can be seen from Verisk's perspective or from Forbes's; both views are valid at once. What
is stored is separate from how it is presented, so organization can evolve without costly undoing.

## 7. The user can organize the world deliberately

The user can create folders, save relationships, choose groupings and establish views. A real record is where
information is maintained; a saved arrangement expresses a user's preference; a computed arrangement expresses discovered
relationships. All three appear together. The agent respects the user's arrangements: it adds, suggests and offers
views, but never casually destroys or silently reinterprets deliberate organization.

## 8. Synchronization is an opportunity to understand

Synchronizing a site, collection or namespace discovers what changed and what it means: later syncs concentrate on
differences. For each new or changed page: does it introduce something unknown, describe something known, assert a
relationship, correct or contradict an assertion, hold information worth separating, or give a better source? Arrival is
separated from interpretation: content is preserved first, then organized progressively through durable pending work.

## 9. Work waiting to be done is itself part of the namespace

Outstanding work is named records (a sync, its source, its observations, its work items with status), not an agent's
private instructions. Any authorized agent can resume it; the user can inspect it; it is not repeated needlessly. A task's
identity is grounded in what is examined, which version, and what kind of understanding is produced, so completed work is
recognized and work made necessary by a new version is distinguished. Attempted is distinct from completed.

## 10. Understanding proceeds from small observations

Each piece of work begins with the smallest useful observation and grows only as the task requires. A rich network makes
observation more precise, never forces an agent to load an ever-expanding graph. The agent can request a subject, its
nearby relationships, its immediate contents, or a deeper connected view.

## 11. Agents work on the same world without one shared conversation

Agents cooperate through the namespace: they observe records and pending work, produce conclusions, commit supported
changes, and discover each other's results through the same names and indexes. Before committing a new record an agent
checks that an equivalent identity has not been established, and reconsiders against newer state when a competing
change landed. Work has clear ownership while executing, a visible result when complete, and a recoverable state if
execution stops.

## 12. The system maintains connections as information changes

A change affects exactly the relationships and views that depend on it, not everything that mentions the record. A
remote record is never imported whole. References answer in both directions, across worlds, without copying remote
records into local primary storage. Only permitted, visible sources participate. A disconnected peer never makes the
local world unusable; previously observed relationships are kept and distinguished from currently verified ones.

## 13. New worlds expand the possible connections

A newly accessible world's mentions are resolved against existing names; the relationships the evidence supports are
established. The network becomes richer; nothing is copied; each world keeps its records, naming decisions and authority.
Union through recognized relationships, not forced agreement. Worlds may disagree or organize differently without
migration; they need only enough shared addressing for relationships to be traversable.

## 14. The agent continuously improves the organization of what it knows

Unresolved names, undecomposed text, references to unencountered things, and apparent duplicates are made observable, as
opportunities, not errors. The agent judges which to pursue; improvements are durable so future agents do not repeat the
work. Organization is an ongoing consequence of using the world.

## 15. The agent can act through the arrangement it sees

Working through a computed hierarchy is as natural as through a stored one. An addition under a computed view is directed
to the owning record (with permission), not written as a copy. Placing a company under a factual view (acquisitions) may
assert a relationship; placing it in a research collection only states a preference. When the meaning is clear the
action becomes the canonical change; when several readings are plausible the user decides.

## 16. Every conclusion retains its origin

Every relationship can explain itself: its supporting assertion, its source, and whether it came from a primary source,
a secondary report, a user assertion or an agent interpretation. Derived relationships stay reproducible. Disagreements
(a founding year of 1988 against 1989) are preserved with their origins; a preferred answer may be presented when
justified, never by destroying conflicting information.

## 17. Synchronization should converge without demanding identical worlds

Worlds recognize the names they share, exchange permitted changes and refresh the relationships that depend on them. No
peer stores everything. A disconnected world keeps its records and reconciles on return. Conclusions stay identifiable as
drawn from particular observations even when newer observations revise them.

## 18. The complete cycle

Encounter (search worlds, follow relationships, retrieve permitted sources), Understand (interpret, identify, reconcile,
separate evidence from judgment), Preserve (keep sources, commit records and assertions, keep histories), Connect
(recognize relationships, including across peers), Present (construct arrangements for the current perspective),
Reconsider (new observations, unfinished work, corrections, peer changes). Each stage leaves durable results.

## 19. What the system ultimately becomes

Discovery, understanding, durable organization and navigation in one continuous environment. It becomes more useful as
it gains information because new information increases the number of meaningful ways existing information can be
reached, understood and used.

There is no need for one universal hierarchy, one universal vocabulary, or one authority that organizes the entire
world. There must instead be durable names, independent ownership, discoverable relationships, and the freedom to
construct coherent perspectives over them. The agent's role is to continually improve the connections between what is
encountered and what is already known. The user remains free to organize, question, correct and navigate through their
own perspective. The world does not become unified because everything moves into the same place. It becomes unified
because things can find, recognize, and relate to one another without needing to move at all.
