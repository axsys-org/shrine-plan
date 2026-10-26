# Shrine: worlds assembled through discovery

Ian's statement of what the views are built toward, 2026-10-25. Where this and an implementation choice differ, this
wins; HANDOFF.md carries the order of work.

## The central idea

Independent agents gather arbitrary pieces of information; Shrine reveals how those pieces connect, before anyone has
fully understood, digested or organized them. The "as a world" view in the explorer is the central experience, and it
is also how agents discover relationships, see what is missing, and decide what to research next.

An agent does not need to understand the whole namespace, organize every discovery, or design a hierarchy before the
information is useful. Agents discover, preserve at names, and let the reference and overlay machinery show how the
pieces fit.

## 1. Agents independently discover pieces

A request ("investigate Verisk, McKenzie, their products, founders, and the wider catastrophe-modelling connections")
is dispatched to independent investigations: acquisitions, people, products; over existing worlds, the web, existing
records. Each may find a record, a reference, an existing view, a source document, a domain, an endpoint, or an
ambiguous subject not yet identified. They do not return summaries to the main agent; they contribute to the
namespace, with ownership and provenance intact.

## 2. Preserve the discovered structure, not just extracted facts

Established relations are slots naming other things, across worlds. But agents also find what is not yet understood
well enough to be a fact: sources, endpoints, domains, hyperlinks, mentions, extracted topics, uncertain identity
candidates. These are kept as observations, not discarded, because they are routes toward further discovery. A topic
such as "catastrophe modelling" can become a named subject when there is reason to treat it independently; it is not
invented as a placeholder to complete a hierarchy. Preserve discoverability without pretending an observed
association is an established fact.

## 3. Shrine reveals how the pieces connect

The reference machinery finds paths between contributions: forward through outgoing references, backward through
incoming ones, down through stored children at x/y/z, sideways through relationships and shared identities, across
worlds through authorized remote names, and through sources, mentions, domains and topics where supported. This is a
graph of connections, not a new storage hierarchy. The operation that matters is finding how arbitrary named
observations connect, whichever agent, source or world they came from.

## 4. The overlay turns the connections into the world view

From any vantage, the general "as a world" definition produces the navigable tree: acquisitions holding McKenzie
holding its founder holding his education, products holding the flood model and what mentions it, sources and where
they were published, connected research topics. No sub-agent built the hierarchy; the kernel exposes structural and
referential connections and named Foil computations decide how to traverse, group and display them. The tree is a
reproducible perspective over the records, never copied primary data.

## 5. Show the route of connection

Given several names (Verisk, Forbes McKenzie, the flood model), possibly from different worlds and cares, Shrine looks
for the connecting paths and exposes them as a view: the inputs, what connects them, the established paths, and what
is unresolved. The agent observes the relationship without pulling every record between them into its context. If
the inputs are not connected, Shrine returns the disconnected regions and possible evidence-backed discovery routes;
it never fabricates a connection.

## 6. The assembled structure is the agent's research signal

The composed working world shows not only connections but where observation would be valuable: connected (reuse),
uncertain (inspect evidence, judge identity), missing (search existing sources and views, then the web). A new domain
may connect unrelated sources; a mention may suggest a relation worth investigating; a shared identifier may
establish identity; a new topic may connect several articles; a new reference may shorten a long path. The signals:
digest this source, investigate this identity, follow this connection, reuse this view, create this missing
computation. Shrine's indexes, dependencies, candidates and views expose them; the agent does not invent them by
free-form reasoning. A missing connection is not a missing fact, and semantic proximity is not identity.

## 7. Views compose into more useful views

"As a world" gives general connected reach; a task view selects the useful portion (catastrophe view, exposure view,
investment view). The agent reuses existing computations first and builds missing intermediates only as needed. Each
view is another named, navigable structure later agents consume. The aim is not many views; it is useful perspectives
emerging cheaply from existing knowledge.

## 8. The agent's context stays small

The main agent observes a compact description: the task, how many subjects connected, how many views are reusable,
how many paths were newly found, what remains (an ambiguous identity, an undigested report, a missing relation), and
the next operations. The full structure stays in Shrine.

## 9. The loop

Ask or provide data; inspect the existing world; select relevant names and views; dispatch focused research when
needed (own world, other worlds, the web); seed discoveries (names, sources, references, mentions, topics,
judgements); find connections; compose the world view and show the routes; observe; if sufficient, present; if gaps
remain, research, digest, resolve, compose, and go round; persist reusable work; the next agent starts further ahead.

## The principle

Agents are free to discover arbitrary names and sources. Shrine is responsible for revealing the structural,
referential and identity routes by which those discoveries form a connected perspective. The composed view is both
the user's result and the agent's observation surface for deciding what work is still valuable. The objective is not
a large graph built by explicit planning; it is conditions under which independent research naturally contributes to
one increasingly connected computational environment.

In one sentence: agents discover pieces of reality independently; Shrine reveals how those pieces fit together,
exposes the gaps between them, and makes every newly established connection reusable for future work.

## The guard

Optimize for useful, evidence-supported connection paths, not the largest number of references or the shortest graph
distance; otherwise the world view fills with incidental web mentions and misleading identity matches. The aim is the
richness of the original explorer tree with enough structural clarity that a person or an agent can see why any two
things appear connected.

---

# Part two: connection first

Ian, later the same night. Shrine constructs the connected virtual namespace *before* it decides what to digest,
research or connect. The initial goal is not a perfectly understood graph; it is to take everything an agent has
encountered and reveal how much structure is already present in partially understood information.

1. **Start with disparate observations**: user-selected names across worlds, existing views, web fetches, undigested
   sources, mentions and topics. Some are already connected by references; others share an identifier, a domain, a
   hyperlink, a topic or a mention. Do not dispatch agents to interpret everything first; assemble the observable
   connectivity.
2. **Build a preliminary virtual namespace** from it: connected components, each an island tied together by some
   observable route, the view preserving the difference between an established reference and a tentative
   association. Two records sharing a topic is visible without Shrine claiming they are one entity.
3. **Present the actual routes, including weak ones**: same-entity, acquisitions, mentioned-in with domain and
   mentions, topics with undigested reports, and the unconnected with "no established route". The structure of the
   evidence is exposed before its contents are interpreted.
4. **The islands are the work**: Shrine exposes gaps between components relevant to the requested perspective; a
   sub-agent gets a specific objective (does this report describe McKenzie's product? establish the connection only
   if supported). One justified relation can join two regions. Not every island is a problem; prioritize bridges
   relevant to the perspective, never connect indiscriminately.
5. **Repeat as the world changes**: collect, connect, identify components (connected: reuse; weakly linked: inspect
   evidence, digest; isolated: search for bridges), establish, recompute, compose. An agent must not re-fetch a page
   merely because it is undigested: if the contents are preserved, interpret them; re-fetch for absence,
   incompleteness or freshness.
6. **Two views, one machinery.** *As a world*: established knowledge, navigable. *Connection workspace*: that plus raw
   sources, domains, endpoint links, mentions, candidate identities, tentative topics, disconnected components, and
   reusable computations. Same cells, same references; the difference is the treatment of uncertainty and the
   purpose. A reference path can be known; a topic similarity is tentative; the page and the agent must see which.

**The principle:** before interpreting everything it encounters, Shrine assembles the largest useful, evidence-labelled
virtual namespace possible from existing names, references, views, source metadata, web structure, mentions and
candidate connections. The connected components expose opportunities for reuse, targeted digestion, identity
resolution, further research and new view composition. The agent does not discover knowledge in order to build the
initial view; it builds the initial view to discover which knowledge is worth discovering. Collect, connect what is
connectable, inspect the resulting world, investigate meaningful gaps, strengthen connections, compose better views.

---

# Part three: the meter

The view at one standing is the **intersection**: what meets at the thing you stand on, the records across worlds that
are the same thing, the facts and routes that converge there. The view from several standings is the **union**: what
any of them can reach, plus the routes between them; its size is the sum of the neighbourhoods less their overlap.

Every justified connection does two things at once: it grows what one standing reaches and it shortens the route
between standings. So over time the single view grows and the combined view shrinks, until they are the same picture
and combining standings adds nothing. The ratio, union over intersection, is the progress meter: large where the
knowledge is still islands with long routes between them (research worth doing), one where things are woven
(done). Only established edges count toward it; tentative edges are drawn but never shrink the world until a
digestion or a judgement turns one into a slot, or mentions would collapse everything into one blob and the meter
would lie.

Two unions, same index, different scopes: the "in N worlds" block on a record is a union of what the worlds say
about one thing; the multi-standing view is a union of what several things can reach.

The **grey zone** sits between the two numbers: reach that exists but does not count yet. Three kinds, all already
records, none established edges: undigested content (texts with a source and a mention index, pointing at names
without relating them); web identity (a domain, an endpoint, a site: enough to say two texts came from the same
place); topic tags (phrases several texts share, meta on the undigested, a thing in its own right only when there is
reason, never a placeholder). They are drawn, labelled tentative, closed beyond the subject, and excluded from the
numbers; they are also the raw material of the connect step. The grey is tissue running through the established
graph, not a region beside it: a route can be three solid hops, a mention, two solid hops, and the one grey segment
makes it tentative end to end. So a route has a quality, not only a length: how many hops are established and where
the soft ones sit. That is the pointer the connect step follows: digest that text, judge that domain, and the route
hardens with nothing else changing. Tentative edges stay visible for exactly this reason; without them islands look
like islands, with them you can see they already touch through evidence nobody has read.

## Part four: the contract

```
graph_overlay( standings | observations ) -> namespace
```

- standings: paths at x | y | z, from this node, another node (read by name), or a view.
- observations: web fetches with identity (url, endpoint, domain) and extracted meta/content (regions, mentions,
  topics), any of it undigested.
- namespace: one computed tree at a name, in which connected = reachable by established routes, drawn as folders,
  attributed per hop; tentative = joined only through a text, a domain, a topic or a name match: drawn, labelled,
  closed beyond the subject, not counted; islands = no route, usually the raw web fetches, sometimes a standing itself.
- the agent, on the result, may: inspect (open a branch, read a text, follow a route); add (a record, a slot, a
  judgement with its evidence); bridge (apply an existing view or define a new one over an established route of any
  length); fetch (search or fetch more, which lands as a new observation); digest (turn a stored text into records,
  which hardens a grey hop). Then recompute: the same overlay, with more established reach and a smaller union.

Three properties fixed by this: pure and reproducible (a function of names and the index at an epoch; nothing it draws
is written back); why-per-edge (every hop says who asserted it and how strongly: a slot, a judgement, a mention); the
non-connective case is normal (a fresh fetch is an island by construction; mentions give it tentative edges; digestion
and judgement give it established ones; islands are the intake, not failures).

State against it: the single-standing form is the `as_world` cell; the reverse index and identity closure exist;
tentative versus established is partly there (mentions are a labelled folder) but not yet a property on every edge;
multiple standings and the web-identity vertices are the next cell, `graph_workspace`.
