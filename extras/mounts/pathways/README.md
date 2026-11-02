# Pathways

A browser research notebook for redox pathways, folate/one-carbon cycling,
circadian timing and ADHD-related literature. Run from the core checkout:

```sh
x/eden --mount pathways --wire-port 8679
```

Open **http://127.0.0.1:8130/pathways**. No Explorer dependency, asset build,
external API credentials, or network requests are needed at runtime. Reference
links open their original publishers when selected.

## Explore a case

1. Name a case and record observations as **present**, **absent**, or **unknown**.
   Lab observations have space for analyte, units, date, assay and compartment;
   a symptom is not converted to a biochemical measurement.
2. Select one or more working hypotheses. Coral nodes are the processes that
   hypothesis explicitly assumes are affected. Green nodes are biochemical
   neighbors, with **no inferred direction, magnitude or probability**.
3. Click a process or a connection for its sources, evidence type, limitations,
   and the connection explaining its highlight. Search by process or gene name.
   Pan the map, use the zoom buttons, or Ctrl/Command-scroll to zoom.
4. Enable or hide research links. Dashed links include in-vitro experiments,
   cross-scale context, clinical associations and null findings. They never
   participate in biochemical neighbor expansion.
5. Use **Build your own hypothesis** for a statement, directly affected
   processes, assumed direction, reasoning and potential falsifiers. These are
   explicitly user assumptions, not new sourced facts.
6. **Save cases** commits to Shrine. **Export** downloads all current cases,
   including unsaved drafts. **Import** validates an export and appends new
   copies; it does not overwrite existing case IDs.

The timing example is synthetic. No symptoms are prefilled for a personal case.
Observation links are qualitative prompts, not a differential diagnosis, score,
likelihood, treatment recommendation, or inference from common genetic variants.
The map is a curated pilot (12 processes/contexts, 15 links), not a reaction-level
recreation of the full Roche charts or a comprehensive account of ADHD biology.

## Evidence and scope

`atlas.json` contains every node, edge, hypothesis and source, including source
URLs, access dates, evidence categories and limits. It is a hand-authored
schematic based on Reactome annotations and linked research papers, not a bulk
Reactome import. Multiple compartments and scales are explicitly labeled.

- Solid connections are biochemical substrate/cofactor relationships. Walking
  them in either direction supplies context, not a kinetic simulation.
- Purified-protein redox/clock results are marked **experimental**. They are not
  evidence of a human symptom mechanism.
- Clinical study links retain population and design limitations. The redox
  case-control study's higher erythrocyte GSH result and the null methylfolate
  adjunct trial are included rather than translated into a deficiency narrative.
- The ADHD context includes genetic architecture and NIMH background. No
  molecular mechanism is inferred merely from inattention or an ADHD label.
- The pilot does not encode treatment doses, supplement protocols or diagnostic
  thresholds. It supports research organization and hypothesis comparison.

Roche's retired wall charts inspired the overview; no Roche artwork or dataset
is copied. Reactome data are CC0 per https://reactome.org/license. Summaries and
map layout here are original; each scientific claim links back to its source.

## Namespace and persistence

Foil module: `apps/pathways/main`.

- `/<node>/app/pathways/notebook`: `/sys/content` holds a typed
  `pathways/document` (revision, receipt, validated JSON cases).
- `/<node>/app/pathways/save`: declared operation applied with `writ/warp`.
- `GET /pathways/state`: reads one live supervisor snapshot.
- `POST /pathways/save`: validates the document, submits an expected-revision
  write, and acknowledges the commit. The client then reads state and checks its unique
  receipt; a stale revision is a no-op and leaves the browser draft intact.

Browser reloads preserve saved cases. **A new Eden process starts a fresh
namespace**; export/import is the durable file handoff for this development
launcher. Drafts stay in page memory and are not saved to localStorage. Nothing
is sent to an external service. Do not put identifying health information into
a shared development instance.

`x/reload-mount pathways` republishes source and assets; reload the browser to
use updated assets. Activation is not rerun and existing notebooks are not
migrated. Restart Eden for changes to the installed save operation or HTTP plan.

## Checks

```sh
x/check pathways
node extras/mounts/pathways/check-model.mjs
x/eden --mount pathways --node 0x2a --check
# With a running instance and a Playwright installation:
node extras/mounts/pathways/check-browser.mjs http://127.0.0.1:8130 /path/to/node_modules/@playwright/test/package.json
```

`host.py` is registered for `x/eden --check`: asset delivery, namespace
read-after-write, stale writes and malformed documents. The browser check covers
observations, map selection, hypotheses, saves/reload, concurrent-tab conflicts,
export/import, keyboard access and a narrow viewport. It restores the original
notebook after its run. `check-model.mjs` verifies source references, expansion
boundaries, absent observations and import validation.

The gate also verifies that the server's versioned identifier lists match the
atlas. Update those lists in `main.foil` when adding processes or hypotheses.

Extend the atlas by adding referenced nodes/edges/hypotheses in `atlas.json`.
Keep source and edge evidence types explicit; do not encode a clinical
association as a biochemical edge. Changing atlas semantics or identifiers
requires a new atlas ID plus an explicit case migration, not a silent rewrite.
