// goo dev server client.
//
// Sends the source to POST /lower on every edit and swaps in the rendered
// passes, the diagnostics and the output. Polls GET /version so a server
// restart (e.g. ghcid reloading the passes) re-runs the lowering, and an
// edit to this file or app.css reloads the page.

const $ = (sel) => document.querySelector(sel);
const source = $("#source");
const passes = $("#passes");
const diags = $("#diags");
const preview = $("#preview");
const status = $("#compile-status");
const exampleSel = $("#example");
const viewPathInput = $("#view-path");
const customViewPathInput = $("#custom-view-path");
const dirtyMark = $("#dirty");

// Browser storage is a convenience only: keep going if it is unavailable.
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } },
};

// State ---------------------------------------------------------------------

let example = source.dataset.example || exampleSel.value || "";
let savedText = source.value;   // what is on disk for `example`

{
  const storedExample = store.get("goo.v2.example");
  const storedSource = store.get("goo.v2.source");
  const storedSaved = store.get("goo.v2.saved");
  if (!new URLSearchParams(location.search).has("example") && storedExample !== null && storedSource !== null &&
      [...exampleSel.options].some((o) => o.value === storedExample)) {
    example = storedExample;
    exampleSel.value = storedExample;
    source.value = storedSource;
    savedText = storedSaved ?? storedSource;
  }
}

function setStatus(text, kind) {
  status.textContent = text;
  const tone = { ok: "bg-selected text-accent", warn: "bg-amber-50 text-amber-800", err: "bg-red-50 text-danger", down: "bg-red-50 text-danger" };
  status.className = `status ml-auto text-xs px-2 py-1 rounded-full ${kind || ""} ${tone[kind] || "bg-canvas text-muted"}`;
}

function updateDirty() {
  const dirty = source.value !== savedText;
  dirtyMark.textContent = dirty ? `${example || "untitled"} • unsaved` : example;
  store.set("goo.v2.source", source.value);
  store.set("goo.v2.example", example);
  store.set("goo.v2.saved", savedText);
}

// The view is compilation context, so changing it does not dirty the source.
const savedViewPath = new URLSearchParams(location.search).get("view") || store.get("goo.view-path");
const retiredThemeViews = (viewPathInput.dataset.retiredViewPaths || "").split(/\s+/).filter(Boolean);
if (savedViewPath && !retiredThemeViews.includes(savedViewPath)) {
  if ([...viewPathInput.options].some((option) => option.value === savedViewPath)) {
    viewPathInput.value = savedViewPath;
  } else {
    viewPathInput.value = "custom";
    customViewPathInput.value = savedViewPath;
  }
} else if (savedViewPath) {
  store.set("goo.view-path", viewPathInput.value);
}
customViewPathInput.hidden = viewPathInput.value !== "custom";
function currentViewPath() {
  return viewPathInput.value === "custom" ? customViewPathInput.value.trim() : viewPathInput.value;
}
viewPathInput.addEventListener("change", () => {
  customViewPathInput.hidden = viewPathInput.value !== "custom";
  if (!customViewPathInput.hidden) customViewPathInput.focus();
  store.set("goo.view-path", currentViewPath());
  clearTimeout(timer);
  lower();
});

// Lowering ------------------------------------------------------------------

let seq = 0;
let lastScroll = 0;
let stopRendering = () => {};
let measurementSeq = 0;
let outputSeq = 0;
const budgetInput = $("#budget"), uniformInput = $("#uniform-edges");
for (const input of [budgetInput, uniformInput]) input.addEventListener("change", () => lower());

async function lower() {
  const id = ++seq;
  stopRendering();
  ++measurementSeq;
  let data;
  try {
    const query = new URLSearchParams({view:currentViewPath(), uniform:uniformInput.checked?'1':'0'});
    if (budgetInput.value !== 'auto') query.set('budget', budgetInput.value);
    const res = await fetch(`/lower?${query}`, {
      method: "POST",
      headers: { "content-type": "text/plain; charset=utf-8" },
      body: source.value,
    });
    if (!res.ok) {
      const message = await res.text();
      if (id === seq) {
        setStatus(message || `HTTP ${res.status}`, "err");
        passes.replaceChildren();
        diags.replaceChildren();
        preview.srcdoc = "";
      }
      return;
    }
    data = await res.json();
  } catch (e) {
    if (id === seq) setStatus("server unreachable", "down");
    return;
  }
  if (id !== seq) return; // a newer request is in flight

  // Keep each card open or closed as the user left it; new cards use the
  // server's default.
  const wasOpen = new Map(
    [...passes.querySelectorAll("details.pass")].map((d) => [d.dataset.pass, d.open]));
  passes.innerHTML = data.passes;
  for (const d of passes.querySelectorAll("details.pass")) {
    if (wasOpen.has(d.dataset.pass)) d.open = wasOpen.get(d.dataset.pass);
  }
  diags.innerHTML = data.diagnostics;

  try { lastScroll = preview.contentWindow.scrollY; } catch { /* ignore */ }
  outputSeq = id;
  preview.srcdoc = data.output;

  if (data.crashed) setStatus(`pass ${data.crashed} crashed`, "err");
  else if (data.errors) setStatus(plural(data.errors, "error"), "err");
  else if (data.warnings) setStatus(plural(data.warnings, "warning"), "warn");
  else setStatus("ok", "ok");
}

preview.addEventListener("load", async () => {
  const doc = preview.contentDocument, compileId = outputSeq;
  if (compileId !== seq) return;
  stopRendering();
  try {
    const stop = await GooReference.renderDocument(doc, async result => {
      if (compileId !== seq || doc !== preview.contentDocument) return;
      const revision = ++measurementSeq;
      if (result.error) { setStatus(result.error, "err"); return; }
      try {
        const res = await fetch('/rendered', {method:'POST', headers:{'content-type':'application/json'},body:JSON.stringify(result)});
        if (!res.ok) throw Error(`measurement display: HTTP ${res.status}`);
        const data = await res.json();
        if (compileId !== seq || revision !== measurementSeq || doc !== preview.contentDocument) return;
        const names = ['measurement','metric','layout','adjacency-trace'];
        const open = new Map([...passes.querySelectorAll('details.pass')].map(d=>[d.dataset.pass,d.open]));
        for (const name of names) passes.querySelector(`[data-pass="${name}"]`)?.remove();
        passes.insertAdjacentHTML('beforeend', data.passes);
        for (const d of passes.querySelectorAll('details.pass')) if (open.has(d.dataset.pass)) d.open=open.get(d.dataset.pass);
        setStatus('ok', 'ok');
      } catch (e) { if (compileId === seq) setStatus(e.message, 'err'); }
    });
    if (compileId !== seq || doc !== preview.contentDocument) stop(); else stopRendering=stop;
    preview.contentWindow.scrollTo(0, lastScroll);
  } catch (e) { if (compileId === seq) setStatus(e.message, 'err'); }
});

function plural(n, word) { return `${n} ${word}${n === 1 ? "" : "s"}`; }

let timer;
customViewPathInput.addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    store.set("goo.view-path", currentViewPath());
    lower();
  }, 180);
});
source.addEventListener("input", () => {
  updateDirty();
  clearTimeout(timer);
  timer = setTimeout(lower, 120);
});

// Editor keys ---------------------------------------------------------------

const INDENT = "    ";

// execCommand keeps the browser's undo stack intact; fall back if missing.
function insert(text) {
  if (!document.execCommand("insertText", false, text)) {
    source.setRangeText(text, source.selectionStart, source.selectionEnd, "end");
    source.dispatchEvent(new Event("input"));
  }
}

function lineStart(pos) { return source.value.lastIndexOf("\n", pos - 1) + 1; }

function selectedLines() {
  const v = source.value;
  const start = lineStart(source.selectionStart);
  let end = v.indexOf("\n", Math.max(source.selectionEnd - 1, source.selectionStart));
  if (end === -1) end = v.length;
  return { start, end };
}

source.addEventListener("keydown", (e) => {
  if (e.key === "Tab") {
    e.preventDefault();
    const multi = source.value.slice(source.selectionStart, source.selectionEnd).includes("\n");
    if (!multi && !e.shiftKey) { insert(INDENT); return; }
    const { start, end } = selectedLines();
    const block = source.value.slice(start, end);
    const lines = block.split("\n");
    const out = e.shiftKey
      ? lines.map((l) => l.replace(/^ {1,4}/, ""))
      : lines.map((l) => (l ? INDENT + l : l));
    source.setSelectionRange(start, end);
    insert(out.join("\n"));
    source.setSelectionRange(start, start + out.join("\n").length);
  } else if (e.key === "Enter" && !e.metaKey && !e.ctrlKey) {
    e.preventDefault();
    const pos = source.selectionStart;
    const line = source.value.slice(lineStart(pos), pos);
    let indent = line.match(/^ */)[0];
    if (/\{\s*$/.test(line)) indent += INDENT;
    insert("\n" + indent);
  } else if ((e.metaKey || e.ctrlKey) && e.key === "s") {
    e.preventDefault();
    save(example);
  }
});

document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "s" && e.target !== source) {
    e.preventDefault();
    save(example);
  }
});

// Diagnostics jump to the source ---------------------------------------------

document.addEventListener("click", (e) => {
  const item = e.target.closest(".diag[data-line]");
  if (!item) return;
  const line = +item.dataset.line;
  const col = +item.dataset.col;
  const lines = source.value.split("\n");
  let offset = 0;
  for (let i = 0; i < line - 1 && i < lines.length; i++) offset += lines[i].length + 1;
  offset += Math.max(0, col - 1);
  const word = source.value.slice(offset).match(/^\S*/)[0];
  source.focus();
  source.setSelectionRange(offset, offset + word.length);
  const lh = parseFloat(getComputedStyle(source).lineHeight) || 20;
  source.scrollTop = Math.max(0, (line - 4) * lh);
});

// Examples ------------------------------------------------------------------

exampleSel.addEventListener("change", async () => {
  const name = exampleSel.value;
  if (source.value !== savedText && !confirm(`Discard unsaved changes to ${example}?`)) {
    exampleSel.value = example;
    return;
  }
  const res = await fetch(`/examples/${encodeURIComponent(name)}`, { cache: "no-store" });
  if (!res.ok) { setStatus(`could not load ${name}`, "err"); return; }
  example = name;
  source.value = await res.text();
  savedText = source.value;
  source.scrollTop = 0;
  updateDirty();
  lower();
});

async function save(name) {
  if (!name) return saveAs();
  const res = await fetch(`/examples/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "content-type": "text/plain; charset=utf-8" },
    body: source.value,
  });
  if (!res.ok) { setStatus(`save failed: ${await res.text()}`, "err"); return; }
  example = name;
  savedText = source.value;
  if (![...exampleSel.options].some((o) => o.value === name)) {
    const opt = new Option(name, name);
    const after = [...exampleSel.options].find((o) => o.value > name);
    exampleSel.add(opt, after || null);
  }
  exampleSel.value = name;
  updateDirty();
  setStatus(`saved examples/${name}.goo`, "ok");
}

async function saveAs() {
  const name = prompt("Save as examples/NAME.goo. Letters, digits, - and _ only.", "");
  if (!name) return;
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(name)) { setStatus("invalid example name", "err"); return; }
  save(name);
}

$("#save").addEventListener("click", () => save(example));
$("#save-as").addEventListener("click", saveAs);

// Lowering pane controls ------------------------------------------------------

function bindToggle(id, className, invert) {
  const box = $("#" + id);
  const stored = store.get("goo." + id);
  if (stored !== null) box.checked = stored === "1";
  const apply = () => {
    passes.classList.toggle(className, invert ? !box.checked : box.checked);
    store.set("goo." + id, box.checked ? "1" : "0");
  };
  box.addEventListener("change", apply);
  apply();
}
bindToggle("changes-only", "changes-only", false);
bindToggle("show-removed", "hide-removed", true);

$("#toggle-all").addEventListener("click", (e) => {
  const cards = [...passes.querySelectorAll("details.pass")];
  const anyOpen = cards.some((d) => d.open);
  for (const d of cards) d.open = !anyOpen;
  e.target.textContent = anyOpen ? "Expand all" : "Collapse all";
});

// Output width presets -------------------------------------------------------

for (const btn of document.querySelectorAll("[data-width]")) {
  btn.addEventListener("click", () => {
    for (const b of document.querySelectorAll("[data-width]")) b.classList.toggle("on", b === btn);
    preview.style.width = btn.dataset.width;
    preview.classList.toggle("preview-constrained", btn.dataset.width !== "100%");
    store.set("goo.width", btn.dataset.width);
  });
}
{
  const w = store.get("goo.width");
  const btn = w && document.querySelector(`[data-width="${w}"]`);
  if (btn) btn.click();
}

// Server restarts and asset edits --------------------------------------------

let version = null;

async function poll() {
  try {
    const res = await fetch("/version", { cache: "no-store" });
    const v = await res.json();
    if (version && v.assets !== version.assets) { location.reload(); return; }
    if (version && v.boot !== version.boot) lower();
    else if (!version || status.classList.contains("down")) lower();
    version = v;
  } catch {
    setStatus("server unreachable", "down");
  }
}

setInterval(poll, 1000);
updateDirty();
poll();
