import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  validateAtlas,
  validateCases,
  newCase,
  implications,
  observationsFor,
  importCases,
} from "./model.mjs";
const atlas = validateAtlas(
  JSON.parse(await readFile(new URL("./atlas.json", import.meta.url))),
);
const server = await readFile(new URL("./main.foil", import.meta.url), "utf8");
for (const [declaration, collection] of [
  ["node_ids", "nodes"],
  ["observation_ids", "observations"],
  ["hypothesis_ids", "hypotheses"],
]) {
  const section = server.split(`  + ${declaration}\n`)[1].split("\n  + ")[0];
  assert.deepEqual(
    [...section.matchAll(/"([a-z_]+)"/g)].map((m) => m[1]),
    atlas[collection].map((x) => x.id),
    "Server and atlas identifiers must agree",
  );
}
const c = newCase("test");
c.observations = [
  { id: "inattention", state: "present", note: "" },
  { id: "late_sleep", state: "absent", note: "" },
];
assert.equal(
  implications(atlas, c, 2).paths.size,
  0,
  "Symptoms must never imply a biochemical defect",
);
c.hypotheses = ["redox_limit"];
const redox = implications(atlas, c, 2);
assert(redox.roots.has("gsr") && redox.roots.has("nadph"));
assert(redox.paths.has("ppp"));
assert(
  !redox.paths.has("adhd") && !redox.paths.has("clock"),
  "Association and purified-system links must not propagate",
);
assert.equal(implications(atlas, c, 0).paths.size, 2);
const clues = observationsFor(
  c,
  atlas.hypotheses.find((h) => h.id === "circadian_delay"),
);
assert.equal(clues.present.length, 0);
assert.equal(clues.absent.length, 1);
assert.equal(clues.unmapped.length, 1);
c.custom = {
  statement: "A counterfactual",
  targets: ["comt"],
  direction: "increased",
  rationale: "Unverified",
};
const custom = implications(atlas, c, 1);
assert.equal(custom.roots.get("comt")[0].kind, "user hypothesis");
assert(
  !custom.roots.has("folate"),
  "Connected nodes never become assumed effects",
);
validateCases([c], atlas);
assert.deepEqual(
  importCases({ schema: 1, atlas: atlas.id, cases: [c] }, atlas),
  [c],
);
assert.throws(() => validateCases([c, c], atlas));
assert.throws(() =>
  validateCases([{ ...c, hypotheses: ["not-in-atlas"] }], atlas),
);
assert.throws(() => validateCases([{ ...c, notes: 123 }], atlas));
assert.throws(() =>
  importCases({ schema: 1, atlas: "wrong", cases: [c] }, atlas),
);
assert.throws(() =>
  validateCases([{ ...c, custom: { ...c.custom, statement: "" } }], atlas),
);
assert.throws(() =>
  validateAtlas({ ...atlas, edges: [{ ...atlas.edges[0], sources: [] }] }),
);
assert(
  atlas.edges.some(
    (e) => e.kind === "null" && e.sources.includes("folate_trial"),
  ),
  "Keep negative findings visible",
);
console.log(
  "PATHWAYS-MODEL-PASS: provenance, bounded context, absent observations, custom hypotheses, import validation",
);
