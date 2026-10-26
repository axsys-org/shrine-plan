Imagine five completely independent organizations using Shrine. None agreed on a schema. None organized their information the same way.

A property investment firm wants to understand whether it should buy an apartment building in Miami.

Here's what makes Shrine potentially extraordinary.

## 1. What actually exists in each world

These are the only canonical records. Each world owns its own names.

```
WORLD 0x11 — PROPERTY INVESTOR
─────────────────────────────────────────────────
/0x11/user/properties/100_biscayne
  address: 100 Biscayne Boulevard, Miami
  asking_price: $42,000,000
  insured_by → /0x12/user/carriers/atlas

/0x11/user/deals/miami_2027
  target → /0x11/user/properties/100_biscayne


WORLD 0x12 — INSURANCE ANALYST
─────────────────────────────────────────────────
/0x12/user/carriers/atlas
  name: Atlas Insurance
  catastrophe_model → /0x13/user/models/flood_v4

/0x12/user/claims/claim_884
  property → /0x11/user/properties/100_biscayne
  cause: Flood
  amount: $1,800,000


WORLD 0x13 — CLIMATE RESEARCHER
─────────────────────────────────────────────────
/0x13/user/models/flood_v4
  name: Coastal Flood Model v4
  projects → /0x13/user/zones/ae_104

/0x13/user/zones/ae_104
  flood_risk: High
  contains → /0x11/user/properties/100_biscayne


WORLD 0x14 — CONSTRUCTION ENGINEER
─────────────────────────────────────────────────
/0x14/user/materials/panel_7
  name: MarineShield Exterior Panel
  suitable_for → /0x13/user/zones/ae_104
  supplier → /0x15/user/vendors/coastal_supply


WORLD 0x15 — SUPPLIER RESEARCHER
─────────────────────────────────────────────────
/0x15/user/vendors/coastal_supply
  name: Coastal Supply
  lead_time_days: 90
  price_per_panel: $185
```

All fictional example data.

Notice the important part: the insurance analyst doesn't need to place their claims inside the investor's property tree.

The claim simply points to the investor's building.

And the construction engineer doesn't need to copy the climate researcher's flood zone.

They reference its name.

## 2. Open the property as a world

The investor opens:

`/0x11/user/properties/100_biscayne`

Then selects As a World.

100 Biscayne Boulevard

Composed view · 5 worlds

```
100 Biscayne Boulevard                        [0x11]
│
├── Price: $42,000,000                        [0x11]
│
├── Insurance
│   └── Atlas Insurance                      [0x12]
│       └── Catastrophe Model
│           └── Coastal Flood Model v4       [0x13]
│               └── Projected Zones
│                   └── Zone AE-104           [0x13]
│
├── Claims Against This Property
│   └── Claim #884                           [0x12]
│       ├── Cause: Flood
│       └── Amount: $1,800,000
│
└── Located In Flood Zone
    └── Zone AE-104                           [0x13]
        │
        └── Suitable Materials
            └── MarineShield Panel            [0x14]
                └── Supplier
                    └── Coastal Supply         [0x15]
                        ├── Lead Time: 90 days
                        └── Price: $185/panel
```

Nobody created that complete hierarchy.

It came from following relationships forward and backward across the worlds.

The building has no stored `claims` child, but an insurance claim points at the building. Shrine's reverse-reference machinery makes it discoverable.

The material isn't inside the flood zone either. It merely says it's suitable for that zone.

Yet it becomes reachable from the property.

That's one level of power.

## 3. Now another agent takes this entire computed view as input

The investor asks:

"Show me the flood-related concerns and possible mitigation options for this acquisition."

An agent defines a reusable Foil computation, conceptually:

```
/0x11/user/views/acquisition_flood_review

  input:
    /0x11/user/properties/100_biscayne
    care: composed

  computation:
    gather related claims
    follow flood zones
    follow mitigation materials
    follow suppliers
    organize findings by concern
```

Reading that cell produces:

```
ACQUISITION FLOOD REVIEW
│
├── Asset
│   └── 100 Biscayne Boulevard
│
├── Evidence of Flood Exposure
│   ├── Flood Zone AE-104                     [0x13]
│   │   └── Risk: High
│   │
│   └── Historical Claim #884                [0x12]
│       └── $1,800,000 flood claim
│
├── Potential Mitigation
│   └── MarineShield Panel                   [0x14]
│       └── Coastal Supply                   [0x15]
│           ├── $185/panel
│           └── 90-day lead time
│
└── Questions To Investigate
    ├── Does the flood model apply to this structure?
    ├── Is the claim correctly associated with the asset?
    └── How many panels would remediation require?
```

The questions are derived from a named review policy; any model-authored assessment would be recorded separately with its evidence.

And here's the crucial step:

Another computation can enter any branch of this result.

It doesn't receive an enormous JSON document and parse it. It reads a navigable computed namespace.

## 4. Compose that view with an investment decision model

Now the investor has another cell:

```
/0x11/user/views/investment_decision

  inputs:
    acquisition_flood_review
    acquisition_price
    financing_terms
    expected_rental_income
```

It produces another hierarchy:

```
INVESTMENT DECISION
│
├── Building: 100 Biscayne Boulevard
│
├── Acquisition
│   └── Asking Price: $42,000,000
│
├── Risk Review                           ← computed view
│   ├── Flood Exposure
│   │   └── High
│   ├── Historical Flood Claim
│   │   └── $1,800,000
│   └── Potential Mitigation
│       └── MarineShield Panel
│
├── Financial Analysis                     ← another cell
│   ├── Financing
│   ├── Operating Income
│   └── Estimated Remediation Cost
│
└── Decision
    └── Pending additional evidence
```

That entire investment decision is itself an addressable view.

It can be pinned, navigated, referenced, and used by another computation.

You now have:

```
Raw records from five independent worlds
                   │
                   ▼
          Composed property view
                   │
                   ▼
           Flood exposure view
                   │
                   ▼
         Investment decision view
                   │
                   ▼
           Portfolio-level view
                   │
                   ▼
         Company-wide risk view
```

Each view becomes part of a larger computation without becoming new primary data.

## 5. The really wild part: a stranger changes one fact

Tomorrow, the supplier researcher changes:

```
/0x15/user/vendors/coastal_supply

lead_time_days: 90 → 180
```

Think through what happens.

The investor did not edit their property. The insurance analyst did nothing. The climate researcher did nothing.

Yet the relevant live computation can change:

```
PROPERTY INVESTMENT VIEW
│
├── Potential Mitigation
│   └── Coastal Supply
│       └── Lead Time: 180 days     ← updated
│
└── Investment Decision
    └── Remediation schedule requires review
```

No global synchronization of everybody's databases is necessary.

The view knows which facts it depends on. When the supplier's record changes, the relevant live views can be invalidated and recomputed. Historical pinned views retain their earlier dependencies.

And an unrelated change, such as the supplier updating its office phone number, shouldn't force the entire investment calculation to recompute if that slot isn't a dependency.

## 6. And an agent can enter at any point

Imagine an agent whose context contains only:

```
TASK:
  Review acquisition risk for 100 Biscayne.

CURRENT:
  /0x11/user/views/investment_decision

OBSERVABLE BRANCHES:
  acquisition
  risk_review
  financial_analysis
  decision
```

It can inspect:

```
read("risk_review/flood_exposure", care=y)
```

Then:

```
read("risk_review/potential_mitigation", care=z)
```

Then investigate an uncertain claim.

It doesn't have to fetch the five worlds, rebuild their relationships, load all their source documents, or reconstruct the investment analysis.

It enters a persistent structure that already knows how to produce those answers.

## What I think is the true power

The impressive thing isn't that five worlds made a big tree.

A graph database can traverse relationships. A federated query engine can combine databases. A workflow engine can chain calculations.

The distinctive ambition for Shrine is to make all of those capabilities share one persistent, named, versioned, composable interface.

A stranger publishes a fact.

Another stranger's record references it.

A third person defines a perspective over their combined knowledge.

A fourth person builds a computation over that perspective.

A fifth agent enters the resulting computed hierarchy and continues the work.

Nobody has to own the entire network, agree on one database schema, or duplicate every piece of information.

The world isn't just storing what everyone knows. It's accumulating structures through which everyone can compute with what others know.

And critically, this is a picture of what the completed cell/overlay and peer machinery could support—not a claim that Shrine currently implements all of it.