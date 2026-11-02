import {
  validateAtlas,
  validateCases,
  newCase,
  observationsFor,
  implications,
  importCases,
} from "./model.mjs";
const $ = (id) => document.getElementById(id);
const el = (tag, text, cls) => {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
};
const svg = (tag, attrs = {}) => {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
};
const clone = (x) => structuredClone(x);
let atlas,
  cases = [],
  current = "",
  revision = "0",
  dirty = false,
  edits = 0,
  saving = false,
  selected = { kind: "node", id: "folate" },
  camera = { x: 0, y: 0, w: 1390, h: 800 };
const uuid = () => crypto.randomUUID();
const caseNow = () => cases.find((c) => c.id === current);
function status(message, error = false) {
  $("status").textContent = message;
  $("status").classList.toggle("error", error);
}
function changed() {
  dirty = true;
  edits++;
  $("save").disabled = saving;
  status("Unsaved changes");
}
function casesList() {
  const select = $("case-select");
  select.replaceChildren();
  for (const c of cases) {
    const o = el("option", c.title || "Untitled case");
    o.value = c.id;
    select.append(o);
  }
  select.value = current;
}
function sourceList(ids) {
  const box = el("div");
  for (const id of new Set(ids)) {
    const s = atlas.sources.find((s) => s.id === id);
    if (!s) continue;
    const row = el("div", undefined, "source"),
      a = el("a", s.title + " ↗");
    a.href = s.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    row.append(
      a,
      el("small", s.kind + " · checked " + s.accessed),
      el("p", s.scope),
    );
    box.append(row);
  }
  return box;
}
function observationWidgets() {
  const box = $("observations");
  box.replaceChildren();
  const c = caseNow();
  for (const o of atlas.observations) {
    let saved = c.observations.find((x) => x.id === o.id);
    const row = el("div", undefined, "observation"),
      top = el("div"),
      label = el("label", o.label),
      input = el("select");
    input.id = "obs-" + o.id;
    label.htmlFor = input.id;
    for (const state of ["unknown", "present", "absent"]) {
      const option = el("option", state[0].toUpperCase() + state.slice(1));
      option.value = state;
      input.append(option);
    }
    input.value = saved?.state || "unknown";
    const note = el("input");
    note.placeholder =
      o.kind === "laboratory"
        ? "Analyte, value, units, date, assay…"
        : "Timing / context…";
    note.maxLength = 1000;
    note.value = saved?.note || "";
    note.setAttribute("aria-label", o.label + " notes");
    const update = () => {
      let entry = c.observations.find((x) => x.id === o.id);
      if (!entry) {
        entry = { id: o.id, state: "unknown", note: "" };
        c.observations.push(entry);
      }
      entry.state = input.value;
      entry.note = note.value;
      changed();
      renderHypotheses();
      renderInspector();
    };
    input.addEventListener("change", update);
    note.addEventListener("input", update);
    top.append(label, input);
    row.append(top, note);
    box.append(row);
  }
}
function renderHypotheses() {
  const box = $("hypotheses"),
    c = caseNow();
  box.replaceChildren();
  for (const h of atlas.hypotheses) {
    const label = el(
        "label",
        undefined,
        "hypothesis" + (c.hypotheses.includes(h.id) ? " active" : ""),
      ),
      head = el("div"),
      check = el("input");
    check.type = "checkbox";
    check.checked = c.hypotheses.includes(h.id);
    check.dataset.hypothesis = h.id;
    check.addEventListener("change", () => {
      c.hypotheses = check.checked
        ? [...c.hypotheses, h.id]
        : c.hypotheses.filter((id) => id !== h.id);
      selected = { kind: "hypothesis", id: h.id };
      changed();
      renderHypotheses();
      renderMap();
      renderInspector();
    });
    head.append(check, el("strong", h.title));
    const links = observationsFor(c, h);
    label.append(
      head,
      el("p", h.summary),
      el(
        "small",
        `${links.present.length} present clues · ${links.absent.length} absent clues · ${links.unmapped.length} present observations unmapped`,
      ),
    );
    box.append(label);
  }
}
function renderCustom() {
  const c = caseNow();
  $("custom-statement").value = c.custom.statement;
  $("custom-direction").value = c.custom.direction;
  $("custom-rationale").value = c.custom.rationale;
  const box = $("custom-targets");
  box.replaceChildren();
  for (const n of atlas.nodes.filter((n) => n.id !== "adhd")) {
    const label = el("label"),
      check = el("input");
    check.type = "checkbox";
    check.checked = c.custom.targets.includes(n.id);
    check.setAttribute("aria-label", "Assume effect on " + n.label);
    check.addEventListener("change", () => {
      if (check.checked && !c.custom.statement.trim()) {
        check.checked = false;
        $("custom-statement").focus();
        status("Write a hypothesis statement before choosing targets.", true);
        return;
      }
      c.custom.targets = check.checked
        ? [...c.custom.targets, n.id]
        : c.custom.targets.filter((id) => id !== n.id);
      changed();
      renderMap();
      renderInspector();
    });
    label.append(check, document.createTextNode(n.label));
    box.append(label);
  }
}
function loadCase() {
  const c = caseNow();
  casesList();
  $("case-title").value = c.title;
  $("case-notes").value = c.notes;
  observationWidgets();
  renderCustom();
  renderHypotheses();
  renderMap();
  renderInspector();
}
function cameraApply() {
  $("map").setAttribute(
    "viewBox",
    `${camera.x} ${camera.y} ${camera.w} ${camera.h}`,
  );
}
function zoom(factor) {
  const w = Math.max(450, Math.min(2400, camera.w * factor)),
    h = (w * 800) / 1390;
  camera = {
    x: camera.x + (camera.w - w) / 2,
    y: camera.y + (camera.h - h) / 2,
    w,
    h,
  };
  cameraApply();
}
function edgeGeometry(e) {
  const special = {
    "folate-adhd": { d: "M 220 130 V 30 H 1340 V 700 H 1300", x: 800, y: 22 },
    "methionine-comt": { d: "M 550 210 V 280 H 1180 V 390", x: 910, y: 268 },
    "methionine-melatonin": {
      d: "M 580 210 V 245 H 700 V 575 H 550 V 660",
      x: 700,
      y: 555,
    },
    "clock-sleep": { d: "M 220 740 V 780 H 870 V 740", x: 545, y: 772 },
  };
  if (special[e.id]) return special[e.id];
  const a = atlas.nodes.find((n) => n.id === e.source),
    b = atlas.nodes.find((n) => n.id === e.target);
  let x1 = a.x + 120,
    y1 = a.y + 40,
    x2 = b.x + 120,
    y2 = b.y + 40;
  const dx = x2 - x1,
    dy = y2 - y1;
  if (Math.abs(dx) > Math.abs(dy)) {
    x1 += Math.sign(dx) * 120;
    x2 -= Math.sign(dx) * 120;
    const m = (x1 + x2) / 2;
    return {
      d: `M ${x1} ${y1} C ${m} ${y1} ${m} ${y2} ${x2} ${y2}`,
      x: m,
      y: (y1 + y2) / 2 - 10,
    };
  }
  y1 += Math.sign(dy) * 40;
  y2 -= Math.sign(dy) * 40;
  const m = (y1 + y2) / 2;
  return {
    d: `M ${x1} ${y1} C ${x1} ${m} ${x2} ${m} ${x2} ${y2}`,
    x: (x1 + x2) / 2 + 9,
    y: m,
  };
}
function choose(kind, id, keyboard = false) {
  selected = { kind, id };
  renderMap();
  renderInspector();
  if (keyboard)
    document.querySelector(`[data-${kind}="${CSS.escape(id)}"]`)?.focus();
}
function renderMap() {
  if (!atlas || !caseNow()) return;
  const g = $("graph");
  g.replaceChildren();
  const c = caseNow(),
    trace = implications(atlas, c, Number($("depth").value)),
    q = $("search").value.trim().toLowerCase();
  for (const [text, y] of [
    ["ONE-CARBON TRANSFER & SULFUR", 90],
    ["REDUCING POWER & CATECHOLAMINES", 350],
    ["CELLULAR TIME & CLINICAL CONTEXT", 620],
  ]) {
    const t = svg("text", { x: 100, y, class: "group-label" });
    t.textContent = text;
    g.append(t);
  }
  for (const e of atlas.edges) {
    if (e.kind !== "biochemical" && !$("research").checked) continue;
    const geometry = edgeGeometry(e),
      group = svg("g", {
        class:
          "edge-group" +
          (selected.kind === "edge" && selected.id === e.id ? " selected" : ""),
        role: "button",
        tabindex: "0",
        "data-edge": e.id,
        "aria-label": `${e.label}: ${e.kind} link`,
      });
    const active = [...trace.paths.values()].some((path) =>
      path.includes(e.id),
    );
    const path = svg("path", {
      d: geometry.d,
      class:
        "edge" +
        (e.kind !== "biochemical" ? " research" : "") +
        (e.kind === "null" ? " null" : "") +
        (active ? " active" : "") +
        (selected.kind === "edge" && selected.id === e.id ? " selected" : ""),
      "marker-end": e.kind === "biochemical" ? "url(#arrow)" : "",
    });
    const hit = svg("path", { d: geometry.d, class: "edge-hit" }),
      text = svg("text", {
        x: geometry.x,
        y: geometry.y,
        class: "edge-label",
        "text-anchor": "middle",
      });
    text.textContent = e.label;
    group.append(path, hit, text);
    group.addEventListener("click", () => choose("edge", e.id));
    group.addEventListener("keydown", (event) => {
      if (["Enter", " "].includes(event.key)) {
        event.preventDefault();
        choose("edge", e.id, true);
      }
    });
    g.append(group);
  }
  for (const n of atlas.nodes) {
    const match =
      !q || [n.label, ...n.terms].join(" ").toLowerCase().includes(q);
    let cls = "node";
    if (trace.roots.has(n.id)) cls += " assumed";
    else if (trace.paths.has(n.id)) cls += " related";
    if (selected.kind === "node" && selected.id === n.id) cls += " selected";
    if (!match) cls += " dim";
    const group = svg("g", {
        class: cls,
        transform: `translate(${n.x} ${n.y})`,
        role: "button",
        tabindex: "0",
        "aria-label": n.label,
        "data-node": n.id,
      }),
      rect = svg("rect", { width: 240, height: 80 });
    const title = svg("text", { x: 14, y: 29, class: "label" });
    title.textContent = n.label;
    const sub = svg("text", { x: 14, y: 49, class: "sub" });
    sub.textContent = n.group.toUpperCase();
    const badge = svg("text", { x: 14, y: 68, class: "badge" });
    badge.textContent = trace.roots.has(n.id)
      ? "ASSUMED · " + trace.roots.get(n.id).length + " hypothesis/es"
      : trace.paths.has(n.id)
        ? "CONNECTED · effect unspecified"
        : "";
    group.append(rect, title, sub, badge);
    group.addEventListener("click", () => choose("node", n.id));
    group.addEventListener("keydown", (event) => {
      if (["Enter", " "].includes(event.key)) {
        event.preventDefault();
        choose("node", n.id, true);
      }
    });
    g.append(group);
  }
  $("coverage").textContent = trace.roots.size
    ? `${trace.roots.size} directly implicated by your assumptions · ${trace.paths.size - trace.roots.size} biochemical neighbors · downstream effects remain unspecified.`
    : "Choose a hypothesis below. Hover or select a connection for its evidence; observations alone never activate a mechanism.";
}
function renderInspector() {
  if (!atlas || !caseNow()) return;
  const box = $("inspector");
  box.replaceChildren();
  const c = caseNow(),
    trace = implications(atlas, c, Number($("depth").value));
  if (selected.kind === "hypothesis") {
    const h = atlas.hypotheses.find((h) => h.id === selected.id);
    box.append(
      el("span", "WORKING ASSUMPTION", "tag"),
      el("h2", h.title),
      el("p", h.summary),
      el("p", h.limits, "limits"),
    );
    const links = observationsFor(c, h);
    const names = (xs) =>
      xs
        .map((o) => atlas.observations.find((x) => x.id === o.id).label)
        .join(", ");
    box.append(
      el("h3", "Observations remain distinct"),
      el(
        "p",
        "Present compatible clues: " +
          (names(links.present) || "none recorded") +
          ".",
      ),
      el(
        "p",
        "Absent compatible clues: " +
          (names(links.absent) || "none recorded") +
          ". Absence is not exclusion.",
      ),
      el(
        "p",
        "Present observations not mapped here: " +
          (names(links.unmapped) || "none recorded") +
          ".",
      ),
    );
    box.append(el("h3", "Questions to challenge it"));
    const list = el("ul");
    for (const q of h.questions) list.append(el("li", q));
    box.append(list, el("h3", "Evidence & limits"), sourceList(h.sources));
    return;
  }
  if (selected.kind === "edge") {
    const e = atlas.edges.find((e) => e.id === selected.id);
    box.append(
      el("span", e.kind.toUpperCase() + " CONNECTION", "tag"),
      el("h2", e.label),
      el(
        "p",
        `${atlas.nodes.find((n) => n.id === e.source).label} ${e.kind === "biochemical" ? "→" : "↔"} ${atlas.nodes.find((n) => n.id === e.target).label}`,
      ),
      el("p", e.note, "limits"),
      sourceList(e.sources),
    );
    return;
  }
  const n = atlas.nodes.find((n) => n.id === selected.id);
  box.append(
    el("span", n.group.toUpperCase(), "tag"),
    el("h2", n.label),
    el("p", n.summary),
    el("p", n.compartment, "hint"),
  );
  if (trace.roots.has(n.id)) {
    box.append(el("h3", "Directly assumed"));
    for (const root of trace.roots.get(n.id))
      box.append(el("p", `${root.title}: ${root.direction} (${root.kind}).`));
  } else if (trace.paths.has(n.id)) {
    box.append(
      el("h3", "Why this is connected"),
      el(
        "p",
        "Topology provides context, not a prediction of impaired function.",
        "limits",
      ),
    );
    const list = el("ol");
    for (const id of trace.paths.get(n.id)) {
      const e = atlas.edges.find((e) => e.id === id),
        item = el("li");
      const b = el("button", e.label);
      b.addEventListener("click", () => choose("edge", e.id));
      item.append(b);
      list.append(item);
    }
    box.append(list);
  } else
    box.append(
      el("p", "No active hypothesis directly implicates this process.", "hint"),
    );
  box.append(
    el("h3", "Terms"),
    el("p", n.terms.join(" · ")),
    el("h3", "Source evidence"),
    sourceList(n.sources),
  );
}
async function fetchJSON(url, options) {
  const response = await fetch(url, { cache: "no-store", ...options });
  if (!response.ok)
    throw Error(
      `Request failed (${response.status}): ${(await response.text()).slice(0, 180)}`,
    );
  return response.json();
}
function receive(doc) {
  if (doc.atlas !== atlas.id || !/^\d+$/.test(doc.revision))
    throw Error("Unexpected namespace document.");
  validateCases(doc.cases, atlas);
  revision = doc.revision;
  cases = doc.cases;
  dirty = false;
  if (!cases.length) {
    cases = [newCase(uuid())];
    dirty = true;
  }
  if (!cases.some((c) => c.id === current)) current = cases[0].id;
  loadCase();
  $("save").disabled = !dirty;
  status(
    dirty
      ? "New case · not saved"
      : `Saved in namespace · revision ${revision}`,
  );
}
async function save() {
  if (saving) return;
  try {
    validateCases(cases, atlas);
    saving = true;
    $("save").disabled = true;
    const receipt = uuid(),
      snapshot = clone(cases),
      serial = edits;
    status("Saving to namespace…");
    const acknowledgement = await fetch("/pathways/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        atlas: atlas.id,
        revision,
        receipt,
        cases: snapshot,
      }),
    });
    if (!acknowledgement.ok)
      throw Error(`Save rejected (${acknowledgement.status}).`);
    await acknowledgement.text();
    const doc = await fetchJSON("/pathways/state");
    if (doc.receipt !== receipt)
      throw Error(
        "Save conflict: a newer revision exists. Export your draft, then reload saved cases.",
      );
    revision = doc.revision;
    dirty = edits !== serial;
    status(
      dirty
        ? "Saved snapshot; newer edits are unsaved."
        : `Saved in namespace · revision ${revision}`,
    );
  } catch (error) {
    status(error.message, true);
  } finally {
    saving = false;
    $("save").disabled = !dirty;
  }
}
function attach() {
  $("save").addEventListener("click", save);
  $("new").addEventListener("click", () => {
    if (cases.length >= 32) {
      status("Maximum 32 cases. Export or remove a case first.", true);
      return;
    }
    const c = newCase(uuid());
    cases.push(c);
    current = c.id;
    changed();
    loadCase();
    $("case-title").focus();
  });
  $("case-select").addEventListener("change", () => {
    current = $("case-select").value;
    loadCase();
  });
  $("case-title").addEventListener("input", () => {
    caseNow().title = $("case-title").value;
    changed();
    casesList();
  });
  $("case-notes").addEventListener("input", () => {
    caseNow().notes = $("case-notes").value;
    changed();
  });
  $("delete").addEventListener("click", () => {
    if (
      !confirm("Remove this case from the draft? Save to commit the removal.")
    )
      return;
    cases = cases.filter((c) => c.id !== current);
    if (!cases.length) cases = [newCase(uuid())];
    current = cases[0].id;
    changed();
    loadCase();
  });
  $("example").addEventListener("click", () => {
    if (cases.length >= 32) {
      status("Maximum 32 cases.", true);
      return;
    }
    const c = newCase(uuid());
    c.title = "Example: attention & delayed timing";
    c.observations = [
      {
        id: "inattention",
        state: "present",
        note: "Illustrative example only",
      },
      {
        id: "late_sleep",
        state: "present",
        note: "Later sleep onset than desired",
      },
      {
        id: "hard_waking",
        state: "present",
        note: "On required early-wake days",
      },
    ];
    c.hypotheses = ["circadian_delay"];
    c.notes =
      "Synthetic example. Compare a timing contribution with other explanations; do not infer etiology from shared symptoms.";
    cases.push(c);
    current = c.id;
    selected = { kind: "hypothesis", id: "circadian_delay" };
    changed();
    loadCase();
  });
  for (const [id, key] of [
    ["custom-statement", "statement"],
    ["custom-direction", "direction"],
    ["custom-rationale", "rationale"],
  ])
    $(id).addEventListener(
      id === "custom-direction" ? "change" : "input",
      () => {
        caseNow().custom[key] = $(id).value;
        changed();
        renderMap();
        renderInspector();
      },
    );
  $("search").addEventListener("input", renderMap);
  $("research").addEventListener("change", renderMap);
  $("depth").addEventListener("change", () => {
    renderMap();
    renderInspector();
  });
  $("zoom-in").addEventListener("click", () => zoom(0.8));
  $("zoom-out").addEventListener("click", () => zoom(1.25));
  $("fit").addEventListener("click", () => {
    camera = { x: 0, y: 0, w: 1390, h: 800 };
    cameraApply();
  });
  let drag;
  $("map").addEventListener("pointerdown", (e) => {
    if (e.target.closest("[role=button]")) return;
    drag = { x: e.clientX, y: e.clientY, ox: camera.x, oy: camera.y };
    $("map").setPointerCapture(e.pointerId);
  });
  $("map").addEventListener("pointermove", (e) => {
    if (!drag) return;
    const rect = $("map").getBoundingClientRect(),
      scale = Math.min(rect.width / camera.w, rect.height / camera.h);
    camera.x = drag.ox - (e.clientX - drag.x) / scale;
    camera.y = drag.oy - (e.clientY - drag.y) / scale;
    cameraApply();
  });
  for (const name of ["pointerup", "pointercancel"])
    $("map").addEventListener(name, () => {
      drag = null;
    });
  $("map").addEventListener(
    "wheel",
    (e) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      zoom(e.deltaY > 0 ? 1.1 : 0.9);
    },
    { passive: false },
  );
  $("reload").addEventListener("click", async () => {
    if (
      dirty &&
      !confirm("Discard unsaved edits and load the namespace revision?")
    )
      return;
    try {
      receive(await fetchJSON("/pathways/state"));
    } catch (error) {
      status(error.message, true);
    }
  });
  $("export").addEventListener("click", () => {
    const blob = new Blob(
        [JSON.stringify({ schema: 1, atlas: atlas.id, cases }, null, 2)],
        { type: "application/json" },
      ),
      url = URL.createObjectURL(blob),
      link = el("a");
    link.href = url;
    link.download = "pathways-cases.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  $("import").addEventListener("click", () => $("import-file").click());
  $("import-file").addEventListener("change", async () => {
    try {
      const file = $("import-file").files[0];
      if (!file) return;
      if (file.size > 200000) throw Error("File is too large.");
      const incoming = importCases(JSON.parse(await file.text()), atlas);
      if (cases.length + incoming.length > 32)
        throw Error("Import would exceed 32 cases.");
      const copies = incoming.map((c) => ({ ...clone(c), id: uuid() }));
      cases.push(...copies);
      if (copies.length) current = copies[0].id;
      changed();
      loadCase();
      status("Imported as new drafts. Save cases to commit.");
    } catch (error) {
      status(error.message, true);
    } finally {
      $("import-file").value = "";
    }
  });
  window.addEventListener("beforeunload", (e) => {
    if (dirty) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
}
try {
  atlas = validateAtlas(await fetchJSON("/pathways/atlas.json"));
  receive(await fetchJSON("/pathways/state"));
  attach();
  document.body.dataset.ready = "true";
} catch (error) {
  status(error.message, true);
  $("inspector").replaceChildren(
    el("h2", "Unable to load the notebook"),
    el("p", "Check the local Eden server, then reload the page."),
  );
}
