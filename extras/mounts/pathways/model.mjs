// Pure graph and notebook logic shared by the UI and its regression checks.
export const ATLAS = "redox-folate-clock-v1";
export const STATES = ["unknown", "present", "absent"];
export const DIRECTIONS = ["unspecified", "decreased", "increased", "timing"];
const require = (ok, message) => {
  if (!ok) throw new Error(message);
};
const object = (x) => x && typeof x === "object" && !Array.isArray(x);
const keys = (x, names) =>
  object(x) &&
  Object.keys(x).length === names.length &&
  names.every((k) => Object.hasOwn(x, k));
const text = (x, max) =>
  typeof x === "string" && new TextEncoder().encode(x).length <= max;
const unique = (xs) => new Set(xs).size === xs.length;
export function validateAtlas(a) {
  require(a.schema === 1 && a.id === ATLAS, "Unsupported atlas version.");
  for (const key of [
    "sources",
    "nodes",
    "edges",
    "observations",
    "hypotheses",
  ]) {
    require(Array.isArray(a[key]) &&
      unique(a[key].map((x) => x.id)), `Duplicate or missing ${key}.`);
  }
  const refs = new Set(a.sources.map((x) => x.id)),
    nodes = new Set(a.nodes.map((x) => x.id)),
    obs = new Set(a.observations.map((x) => x.id));
  for (const source of a.sources)
    require(/^https:\/\//.test(source.url) &&
      source.scope &&
      source.accessed, "Source needs provenance.");
  for (const item of [...a.nodes, ...a.edges, ...a.hypotheses])
    require(item.sources?.length &&
      item.sources.every((x) => refs.has(x)), `Missing source: ${item.id}`);
  for (const n of a.nodes)
    require(Number.isFinite(n.x) &&
      Number.isFinite(n.y), "Invalid map position.");
  for (const e of a.edges)
    require(nodes.has(e.source) &&
      nodes.has(e.target) &&
      [
        "biochemical",
        "experimental",
        "context",
        "association",
        "null",
      ].includes(e.kind), "Invalid edge.");
  for (const h of a.hypotheses)
    require(h.targets.every((x) => nodes.has(x)) &&
      h.observations.every((x) => obs.has(x)) &&
      h.limits, "Invalid hypothesis.");
  return a;
}
export function newCase(id) {
  return {
    id,
    title: "Untitled case",
    observations: [],
    hypotheses: [],
    custom: {
      statement: "",
      targets: [],
      direction: "unspecified",
      rationale: "",
    },
    notes: "",
  };
}
export function validateCases(cases, a) {
  require(Array.isArray(cases) &&
    cases.length <= 32 &&
    unique(cases.map((x) => x?.id)), "Use at most 32 cases with unique IDs.");
  const strings = (xs, max, allowed) =>
    Array.isArray(xs) &&
    xs.length <= max &&
    unique(xs) &&
    xs.every((x) => text(x, 80) && x.length && (!allowed || allowed.has(x)));
  const nodeIDs = new Set(a.nodes.map((n) => n.id)),
    hypothesisIDs = new Set(a.hypotheses.map((h) => h.id)),
    observationIDs = new Set(a.observations.map((o) => o.id));
  for (const c of cases) {
    require(keys(c, [
      "id",
      "title",
      "observations",
      "hypotheses",
      "custom",
      "notes",
    ]) &&
      text(c.id, 80) &&
      c.id.length &&
      text(c.title, 160) &&
      text(c.notes, 8000), "Invalid case fields.");
    require(strings(
      c.hypotheses,
      16,
      hypothesisIDs,
    ), "Unknown or duplicate hypothesis.");
    require(Array.isArray(c.observations) &&
      c.observations.length <= 64 &&
      unique(c.observations.map((o) => o?.id)), "Invalid observations.");
    for (const o of c.observations)
      require(keys(o, ["id", "state", "note"]) &&
        observationIDs.has(o.id) &&
        STATES.includes(o.state) &&
        text(o.note, 1000), "Invalid observation or atlas mismatch.");
    const h = c.custom;
    require(keys(h, ["statement", "targets", "direction", "rationale"]) &&
      text(h.statement, 500) &&
      text(h.rationale, 4000) &&
      strings(h.targets, 32, nodeIDs) &&
      DIRECTIONS.includes(h.direction), "Invalid custom hypothesis.");
    require(!h.targets.length ||
      h.statement
        .length, "Give your custom hypothesis a statement before selecting its targets.");
  }
  require(new TextEncoder().encode(JSON.stringify(cases)).length <
    190000, "Notebook is too large. Export or split the cases.");
  return cases;
}
export function observationsFor(c, hypothesis) {
  const related = new Set(hypothesis.observations);
  return {
    present: c.observations.filter(
      (o) => related.has(o.id) && o.state === "present",
    ),
    absent: c.observations.filter(
      (o) => related.has(o.id) && o.state === "absent",
    ),
    unmapped: c.observations.filter(
      (o) => !related.has(o.id) && o.state === "present",
    ),
  };
}
export function implications(a, c, depth = 1) {
  const roots = new Map();
  for (const h of a.hypotheses.filter((h) => c.hypotheses.includes(h.id))) {
    for (const id of h.targets)
      roots.set(id, [
        ...(roots.get(id) || []),
        { title: h.title, direction: h.direction, kind: "preset assumption" },
      ]);
  }
  if (c.custom.statement.trim())
    for (const id of c.custom.targets)
      roots.set(id, [
        ...(roots.get(id) || []),
        {
          title: c.custom.statement,
          direction: c.custom.direction,
          kind: "user hypothesis",
        },
      ]);
  const paths = new Map([...roots.keys()].map((id) => [id, []]));
  let frontier = [...roots.keys()];
  // Only curated biochemical connections participate. No signs or probabilities
  // propagate; research associations, null results, and clock-context links stop here.
  for (let step = 0; step < Math.max(0, Math.min(2, depth)); step++) {
    const next = [];
    for (const from of frontier)
      for (const e of a.edges.filter(
        (e) =>
          e.kind === "biochemical" && (e.source === from || e.target === from),
      )) {
        const to = e.source === from ? e.target : e.source;
        if (!paths.has(to)) {
          paths.set(to, [...paths.get(from), e.id]);
          next.push(to);
        }
      }
    frontier = next;
  }
  return { roots, paths };
}
export function importCases(value, a) {
  require(keys(value, ["schema", "atlas", "cases"]) &&
    value.schema === 1 &&
    value.atlas ===
      a.id, "This file uses a different notebook or atlas format.");
  return validateCases(value.cases, a);
}
