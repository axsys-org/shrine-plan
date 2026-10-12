/* Playground chrome. Model, compatibility, compilation and mutation policy are server-owned; Arrange proposes local placement. */
(() => {
  "use strict";
  const main = document.querySelector("main[data-target]");
  if (!main) return;
  main.dataset.view ||=
    main.dataset.target.split("/").slice(0, 2).join("/") +
    "/gov/grove_playground/editor";
  let snapshot,
    selected,
    refreshSeq = 0,
    previewRevision = "",
    timer;
  document.body.classList.add("playground-app");
  document.body.dataset.inspector = "closed";
  document.body.dataset.library = "closed";
  document.body.dataset.dock = "preview";
  const header = document.querySelector("body>header");
  header.innerHTML =
    '<a class="brand" href="/grove-playground" aria-label="Grove playground"><svg viewBox="0 0 32 32" aria-hidden="true"><path d="M8 8h16v16H8zM0 16h8m16 0h8M16 0v8m0 16v8"/><circle cx="16" cy="16" r="3"/></svg><strong>grove</strong><span>PLAYGROUND</span></a><nav aria-label="Workspace"><button type="button" data-workspace="library">＋ Add / browse</button><button type="button" data-arrange title="Arrange visible cards and save their positions">Arrange</button><button type="button" data-cancel-arrange hidden>Cancel</button><button type="button" data-route>Route edges</button><button type="button" data-cancel-routing hidden>Cancel routing</button><button type="button" data-workspace="properties">Properties</button><button type="button" data-workspace="preview">Preview</button><button type="button" data-workspace="source">Source</button><button type="button" data-workspace="publish" class="publish-shortcut">Publish ↗</button></nav>';
  const inspector = document.createElement("aside");
  inspector.className = "inspector-heading";
  inspector.setAttribute("aria-label", "Inspector controls");
  inspector.innerHTML =
    '<div><span class="eyebrow">INSPECTOR</span><button type="button" aria-label="Close inspector" data-close-inspector>×</button></div><h2>Select a node</h2><nav class="inspector-tabs" aria-label="Inspector sections"><button type="button" data-mode="properties">Properties</button><button type="button" data-mode="links">Connections</button><button type="button" data-mode="create">Create</button><button type="button" data-mode="publish">Publish</button></nav>';
  document.body.append(inspector);
  function showInspector(mode) {
    document.body.dataset.inspector = mode;
    if (mode !== "closed") document.body.dataset.dock = "closed";
    for (const b of inspector.querySelectorAll("[data-mode]"))
      b.setAttribute("aria-pressed", String(b.dataset.mode === mode));
    syncChrome();
  }
  function toggleDock(mode) {
    const opening = document.body.dataset.dock !== mode;
    showInspector("closed");
    document.body.dataset.dock = opening ? mode : "closed";
    syncChrome();
  }
  header.addEventListener("click", (event) => {
    const key = event.target.closest("[data-workspace]")?.dataset.workspace;
    if (!key) return;
    if (key === "library")
      document.body.dataset.library =
        document.body.dataset.library === "open" ? "closed" : "open";
    else if (key === "properties" || key === "publish")
      showInspector(document.body.dataset.inspector === key ? "closed" : key);
    else toggleDock(key);
    syncChrome();
  });
  inspector.addEventListener("click", (event) => {
    const mode = event.target.closest("[data-mode]")?.dataset.mode;
    if (mode) showInspector(mode);
    if (event.target.closest("[data-close-inspector]")) showInspector("closed");
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key !== "Escape" ||
      document.querySelector("dialog[open]") ||
      event.target.closest("input,textarea,select,[contenteditable=true]")
    )
      return;
    showInspector("closed");
    document.body.dataset.library = "closed";
    syncChrome();
  });
  const modeFor = {
    "Create node": "create",
    "Save properties": "properties",
    "Delete node": "properties",
    "Collapse / expand view": "properties",
    "Connect relationship": "links",
    "Disconnect relationship": "links",
    "Reorder child": "links",
    "Save sample field": "links",
    "Publish revision": "publish",
    "Set card visibility": "visibility",
    "Save routing": "routing",
  };
  function syncChrome() {
    for (const [label, mode] of Object.entries(modeFor)) {
      const native = form(label);
      if (native && native.dataset.inspectorMode !== mode)
        native.dataset.inspectorMode = mode;
    }
    for (const b of header.querySelectorAll("[data-workspace]")) {
      const key = b.dataset.workspace,
        active =
          key === "library"
            ? document.body.dataset.library === "open"
            : key === "properties" || key === "publish"
              ? document.body.dataset.inspector === key
              : document.body.dataset.dock === key;
      const value = String(active);
      if (b.getAttribute("aria-pressed") !== value)
        b.setAttribute("aria-pressed", value);
    }
    for (const node of main.querySelectorAll("goo-patch-node")) {
      const record = snapshot?.nodes.find((n) => n.id === node.dataset.key);
      if (record && node.dataset.kind !== record.cardKind)
        node.dataset.kind = record.cardKind;
      for (const port of node.querySelectorAll("goo-patch-port")) {
        const button = port.querySelector("button");
        if (button && button.dataset.caption !== port.dataset.key)
          button.dataset.caption = port.dataset.key;
      }
    }
    syncFilters();
    scheduleRouting();
  }

  const status = document.createElement("p");
  status.className = "playground-status";
  status.setAttribute("role", "status");
  main.before(status);
  const palette = document.createElement("nav");
  palette.className = "playground-palette";
  palette.setAttribute("aria-label", "Create declaration or component");
  main.before(palette);
  palette.dataset.title = "ADD TO GROVE";
  const outline = document.createElement("nav");
  outline.id = "playground-outline";
  outline.setAttribute("aria-label", "Draft nodes");
  main.before(outline);
  outline.dataset.title = "IN THIS GROVE";
  const library = document.createElement("aside");
  library.className = "playground-library";
  library.setAttribute("aria-label", "Node library");
  const filters = document.createElement("fieldset");
  filters.className = "playground-filters";
  filters.innerHTML =
    '<legend>SHOW CARD KINDS</legend><div class="filter-actions"><button type="button" data-visibility="show">Show all</button><button type="button" data-visibility="hide">Hide all</button></div><div class="filter-kinds"></div><p>Saved canvas preference. Hidden cards still compile.</p>';
  filters.addEventListener("change", (event) => {
    const input = event.target.closest("input[data-kind]");
    if (input)
      setKindVisibility(input.dataset.kind, input.checked ? "show" : "hide");
  });
  filters.addEventListener("click", (event) => {
    const button = event.target.closest("[data-visibility]");
    if (button) setKindVisibility("*", button.dataset.visibility);
  });
  library.append(filters, palette, outline);
  document.body.append(library);
  function syncFilters() {
    if (!snapshot) return;
    const native = form("Set card visibility");
    const button = native?.querySelector("button");
    const disabled =
      !native?.dataset.renderKey ||
      !!native.dataset.loadingKey ||
      !button ||
      button.disabled;
    for (const control of filters.querySelectorAll("input,button"))
      control.disabled = disabled;
    for (const input of filters.querySelectorAll("input[data-kind]")) {
      input.checked = !snapshot.hiddenKinds.includes(input.dataset.kind);
      input.nextElementSibling.textContent = `${snapshot.cardKinds.find((kind) => kind.key === input.dataset.kind).label} · ${snapshot.nodes.filter((node) => node.cardKind === input.dataset.kind).length}`;
    }
  }
  function setKindVisibility(tag, value) {
    // Use the ordinary bound Goo action; the server owns the filtered projection.
    if (!fill("Set card visibility", { tag, value })) return;
    form("Set card visibility").querySelector("button").click();
    syncFilters();
  }
  const edges = document.createElement("div");
  edges.className = "playground-edges";
  edges.setAttribute("aria-label", "Relationships");
  main.after(edges);
  const preview = document.querySelector("#playground-preview"),
    source = document.querySelector("#playground-source");
  preview.innerHTML =
    '<div class="dock-heading"><h2><span class="live-dot"></span> Live preview</h2><button type="button" data-close-dock aria-label="Close preview">×</button></div><label>Sample <select aria-label="Preview sample"></select></label><p></p><iframe title="Compiled Goo preview"></iframe>';
  source.innerHTML =
    '<div class="dock-heading"><h2>Generated Grove</h2><button type="button" data-close-dock aria-label="Close source">×</button></div><a download="playground.grove">Export Grove ↗</a><pre></pre>';
  for (const panel of [preview, source])
    panel.querySelector("[data-close-dock]").onclick = () => {
      document.body.dataset.dock = "closed";
      syncChrome();
    };
  let exportURL, lastOfferedRevision;
  const samplePicker = preview.querySelector("select");
  samplePicker.onchange = () => renderPreview(snapshot);
  function renderPreview(data) {
    const target = samplePicker.value || data.preview,
      key = data.ready + ":" + target;
    if (data.ready !== "0" && key !== previewRevision) {
      previewRevision = key;
      // A compiled revision owns its preview document and inspection observations.
      // Replace it atomically; same-URL iframe reloads retain stale frame contexts in Firefox.
      const frame = document.createElement("iframe");
      frame.title = "Compiled Goo preview";
      frame.src = "/views" + target;
      frame.addEventListener("load", () => {
        const doc = frame.contentDocument;
        if (!doc) return;
        doc.documentElement.classList.add("playground-embedded");
        const style = doc.createElement("link");
        style.rel = "stylesheet";
        style.href = "/grove-playground/style.css";
        style.addEventListener("load", () => {
          frame.dataset.ready = "true";
        });
        style.addEventListener("error", () => {
          frame.dataset.ready = "true";
        });
        doc.head.append(style);
      });
      preview.querySelector("iframe").replaceWith(frame);
    }
  }
  function offerRevision(revision) {
    const field = form("Publish revision")?.querySelector("input");
    if (!field) return;
    if (field.value !== "" && field.value !== lastOfferedRevision) return;
    if (field.value !== revision) fill("Publish revision", { revision });
    lastOfferedRevision = revision;
  }
  const buttons = () => [...main.querySelectorAll("button")];
  const pendingFills = new Map();
  function form(label) {
    const button = buttons().find((b) => b.textContent.trim() === label);
    return button?.closest(".goo-native");
  }
  function fill(label, values) {
    pendingFills.set(label, values);
    return applyFill(label);
  }
  function applyFill(label) {
    const scope = form(label);
    // Closed panels may still contain unbound SSR. Fill only after Goo has
    // admitted the pane-sized presentation and attached its input capture.
    if (!scope?.dataset.renderKey || scope.dataset.loadingKey) return false;
    const values = pendingFills.get(label);
    if (!values) return false;
    for (const input of scope.querySelectorAll("input[data-input-slot]")) {
      const key = input.dataset.inputSlot.split("/").at(-1);
      if (Object.hasOwn(values, key)) {
        input.value = String(values[key]);
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }
    pendingFills.delete(label);
    return true;
  }
  function choose(id) {
    const node = snapshot?.nodes.find((n) => n.id === id);
    if (!node) return;
    selected = id;
    inspector.querySelector("h2").textContent = node.name || node.kind;
    showInspector("properties");
    fill("Save properties", node);
    for (const label of ["Delete node", "Collapse / expand view"])
      fill(label, { id });
    for (const b of outline.querySelectorAll("button"))
      b.setAttribute("aria-pressed", String(b.dataset.id === id));
  }
  async function refresh() {
    const seq = ++refreshSeq;
    const response = await fetch("/grove-playground/state", {
      cache: "no-store",
    });
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    if (seq !== refreshSeq) return;
    snapshot = data;
    if (!filters.querySelector("input")) {
      for (const kind of data.cardKinds) {
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.dataset.kind = kind.key;
        input.setAttribute("aria-label", `Show ${kind.label} cards`);
        label.append(input, document.createElement("span"));
        filters.querySelector(".filter-kinds").append(label);
      }
    }
    // Slots stay editable in the library, but are never canvas occurrences.
    const visible = (node) => node.kind === "slot" || !data.hiddenKinds.includes(node.cardKind);
    const visibleIds = new Set(
      data.nodes.filter(visible).map((node) => node.id),
    );
    if (selected && !visibleIds.has(selected)) {
      selected = undefined;
      inspector.querySelector("h2").textContent = "Select a node";
      showInspector("closed");
    }
    status.textContent = `Draft ${data.revision} · preview ${data.ready} · published ${data.published} · ${data.message}${data.line !== "0" ? " (generated line " + data.line + ")" : ""}`;
    source.querySelector("pre").textContent = data.source;
    if (exportURL) URL.revokeObjectURL(exportURL);
    exportURL = URL.createObjectURL(
      new Blob([data.source], { type: "text/plain" }),
    );
    source.querySelector("a").href = exportURL;
    offerRevision(data.ready);
    if (!palette.children.length)
      for (const kind of data.palette) {
        const button = document.createElement("button");
        button.textContent = kind;
        button.dataset.kind = kind;
        button.type = "button";
        button.onclick = () => {
          showInspector("create");
          inspector.querySelector("h2").textContent = "New " + kind;
          fill("Create node", { tag: kind, name: "" });
          form("Create node")?.querySelector("input")?.focus();
        };
        palette.append(button);
      }
    outline.replaceChildren(
      ...data.nodes.filter(visible).map((node) => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.id = node.id;
        button.dataset.error = String(data.diagnosticNode === node.id);
        button.textContent = node.name;
        button.dataset.kind = data.cardKinds.find(
          (kind) => kind.key === node.cardKind,
        )?.label || node.cardKind;
        button.title = `${node.kind} · ${node.id}`;
        button.setAttribute("aria-pressed", String(selected === node.id));
        button.onclick = () => choose(node.id);
        return button;
      }),
    );
    const title = document.createElement("h2");
    title.textContent = "Relationships";
    edges.replaceChildren(
      title,
      ...data.edges
        .filter(
          (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target),
        )
        .map((edge) => {
          const button = document.createElement("button");
          button.type = "button";
          button.textContent = `${data.nodes.find((n) => n.id === edge.source)?.name || edge.source} .${edge.port} → ${data.nodes.find((n) => n.id === edge.target)?.name || edge.target}`;
          button.onclick = () => {
            showInspector("links");
            fill("Disconnect relationship", { id: edge.id });
            fill("Reorder child", { id: edge.id, index: "0" });
            fill("Save sample field", { id: edge.id, value: edge.value });
          };
          return button;
        }),
    );
    preview.querySelector("p").textContent =
      data.ready === data.revision
        ? "Current compiled draft"
        : `Showing last successful revision ${data.ready}`;
    const chosen = samplePicker.value;
    samplePicker.replaceChildren(
      ...(data.previewTargets || [data.preview]).filter(Boolean).map((path) => {
        const option = document.createElement("option");
        option.value = path;
        option.textContent = path.split("/").at(-1);
        return option;
      }),
    );
    if ([...samplePicker.options].some((option) => option.value === chosen))
      samplePicker.value = chosen;
    renderPreview(data);
    syncChrome();
  }
  const schedule = () => {
    clearTimeout(timer);
    timer = setTimeout(
      () => refresh().catch((e) => (status.textContent = e.message)),
      80,
    );
  };
  main.addEventListener("goo-patch-selection-accepted", (event) => {
    const target = event.detail.find((t) => t.kind === "node");
    if (target) choose(target.node);
  });
  main.addEventListener("goo-patch-query-result", (event) => {
    const { request, result } = event.detail;
    if (request.kind !== "create-picker" || !result.pickerHTML) return;
    const surface = event.target;
    if (!surface.gestures.hasChoice(request.queryId)) return;
    const dialog = document.createElement("dialog"),
      body = document.createElement("div");
    // This is server-prepared native menu HTML. Choices finish the original captured binding.
    GooActions.prepareMount(
      body,
      { html: result.pickerHTML, controls: [] },
      false,
      false,
    ).commit();
    const cancel = document.createElement("button");
    cancel.textContent = "Cancel";
    cancel.type = "button";
    let chosen = false;
    body.addEventListener("click", (e) => {
      const button = e.target.closest("[data-patch-choice]");
      if (!button) return;
      chosen = true;
      surface.gestures.acceptChoice(
        request.queryId,
        button.dataset.patchChoice,
      );
      dialog.close();
    });
    cancel.onclick = () => dialog.close();
    dialog.append(body, cancel);
    document.body.append(dialog);
    dialog.addEventListener("close", () => {
      if (!chosen) surface.cancelGesture("picker-cancel");
      dialog.remove();
    });
    dialog.showModal();
  });
  // Accepted outcomes are emitted by the shared Goo action runtime, after admission.
  globalThis.GooActions.subscribeOutcomes((receipt) => {
    if (receipt.outcome === "accepted") schedule();
    else syncFilters();
  });
  const observer = new MutationObserver(() => {
    for (const label of pendingFills.keys()) applyFill(label);
    if (form("Publish revision") && snapshot) offerRevision(snapshot.ready);
    syncChrome();
  });
  observer.observe(main, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["disabled", "data-render-key", "data-loading-key"],
  });
  window.addEventListener("pagehide", () => {
    observer.disconnect();
    clearTimeout(timer);
    if (exportURL) URL.revokeObjectURL(exportURL);
  });
  const arrange = header.querySelector("[data-arrange]");
  const cancelArrange = header.querySelector("[data-cancel-arrange]");
  const layoutStatus = document.createElement("span");
  layoutStatus.className = "layout-status";
  layoutStatus.setAttribute("role", "status");
  layoutStatus.setAttribute("aria-live", "polite");
  header.append(layoutStatus);
  let layoutRun, layoutOperation;
  function layoutMessage(message) {
    layoutStatus.textContent = message;
  }
  function layoutControls() {
    arrange.disabled = !!layoutRun || !!layoutOperation || routingBusy();
    cancelArrange.hidden = !layoutRun;
  }
  function cancelLayout(reason = "cancelled") {
    layoutRun?.preview.cancel(reason);
  }
  cancelArrange.onclick = () => cancelLayout();
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && layoutRun) {
      event.preventDefault();
      cancelLayout();
    }
  });
  main.addEventListener("pointerdown", () => cancelLayout("interaction"), {
    capture: true,
  });
  main.addEventListener(
    "input",
    (event) => {
      // Goo also dispatches synthetic input while prefilling bound forms.
      if (event.isTrusted) cancelLayout("input");
    },
    { capture: true },
  );
  document.addEventListener(
    "compositionstart",
    () => cancelLayout("composition"),
    { capture: true },
  );
  window.addEventListener("pagehide", () => cancelLayout("pagehide"));
  main.addEventListener("goo-patch-diagnostic", (event) => {
    if (layoutOperation && event.detail.code === "outcome-unknown")
      layoutMessage(
        "Save outcome unknown; reconciling. Do not arrange again yet.",
      );
  });
  GooActions.subscribeOutcomes((receipt) => {
    if (!layoutOperation || receipt.operationId !== layoutOperation) return;
    if (receipt.outcome === "unknown") {
      layoutMessage(
        "Save outcome unknown; reconciling. Do not arrange again yet.",
      );
      return;
    }
    layoutMessage(
      receipt.outcome === "accepted"
        ? "Layout saved."
        : "Layout rejected; restored saved positions.",
    );
    layoutOperation = undefined;
    layoutControls();
  });
  arrange.onclick = async () => {
    if (layoutRun || layoutOperation || routingBusy()) return;
    cancelRouting("Arrangement started", false);
    const surface = main.querySelector("goo-patch"),
      scene = surface?.installedScene;
    if (!scene || scene.nodes.length < 2) {
      layoutMessage("Show at least two cards to arrange.");
      return;
    }
    const targets = scene.nodes.map((node) => ({
      kind: "node",
      node: node.key,
      lifetime: node.lifetime,
    }));
    const preview = surface.beginNodeMovePreview?.(targets);
    if (!preview) {
      layoutMessage(
        "Finish the current edit or pending operation, then arrange.",
      );
      return;
    }
    const run = { preview, frame: 0, simulation: undefined };
    layoutRun = run;
    layoutControls();
    layoutMessage("Loading layout engine…");
    preview.signal.addEventListener(
      "abort",
      () => {
        cancelAnimationFrame(run.frame);
        run.simulation?.stop();
        if (layoutRun === run) layoutRun = undefined;
        if (preview.signal.reason !== "submitted") {
          layoutMessage(
            preview.signal.reason === "unchanged"
              ? "Layout already settled."
              : ["projection-changed", "stale-preview"].includes(
                    preview.signal.reason,
                  )
                ? "Graph changed; arrangement cancelled."
                : "Arrangement cancelled.",
          );
        }
        layoutControls();
      },
      { once: true },
    );
    try {
      const helpers = await import("/grove-playground/layout.js");
      if (preview.signal.aborted) return;
      const engine = await helpers.abortable(
        helpers.loadEngine(),
        preview.signal,
      );
      if (preview.signal.aborted) return;
      const simulation = helpers.createLayout(scene, engine);
      run.simulation = simulation;
      const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
      const started = performance.now();
      layoutMessage(
        reduced ? "Calculating layout…" : "Arranging visible cards…",
      );
      const step = () => {
        if (preview.signal.aborted) return;
        try {
          const positions = simulation.step(reduced ? 24 : 2);
          if (!reduced && !preview.update(positions)) return;
          if (simulation.done || performance.now() - started > 5000) {
            if (!preview.update(simulation.finish())) return;
            layoutMessage("Saving layout…");
            // No await between final preview and submission. The captured binding owns the save.
            layoutOperation = preview.commit() || undefined;
            layoutControls();
          } else run.frame = requestAnimationFrame(step);
        } catch (error) {
          preview.cancel("failed");
          layoutMessage(`Arrange failed: ${error.message}`);
        }
      };
      run.frame = requestAnimationFrame(step);
    } catch (error) {
      if (!preview.signal.aborted) {
        preview.cancel("failed");
        layoutMessage(`Arrange unavailable: ${error.message}`);
      }
    }
  };
  // Routing remains an ordinary bound Goo form action. The worker only proposes
  // geometry; the server validates it and builds the authoritative SceneSnapshot.
  const routeButton = header.querySelector("[data-route]");
  const cancelRouteButton = header.querySelector("[data-cancel-routing]");
  const routingStatus = document.createElement("span");
  routingStatus.className = "routing-status";
  routingStatus.setAttribute("role", "status");
  routingStatus.setAttribute("aria-live", "polite");
  header.append(routingStatus);
  let routeJob,
    routingTimer,
    routeDisposed = false,
    routingComposing = false;
  const routeAttempts = new Set();
  let lastRoutedKey;
  function routingBusy() {
    return !!(
      routeJob?.operation ||
      form("Save routing")?.querySelector("button")?.disabled
    );
  }
  function routingControls() {
    routeButton.disabled =
      !!routeJob || !!layoutRun || !!layoutOperation || routingBusy();
    cancelRouteButton.hidden = !routeJob || !!routeJob.operation;
    layoutControls();
  }
  function cancelRouting(message, attempted = true) {
    if (!routeJob || routeJob.operation) return;
    if (!attempted) routeAttempts.delete(routeJob.key);
    routeJob.worker?.terminate();
    clearTimeout(routeJob.timeout);
    routeJob = undefined;
    routingStatus.textContent = message;
    routingControls();
  }
  function scheduleRouting() {
    if (routeDisposed) return;
    clearTimeout(routingTimer);
    routingTimer = setTimeout(routeTick, 80);
  }
  function routeTick() {
    const surface = main.querySelector("goo-patch"),
      scene = surface?.installedScene;
    if (!scene || !surface.editable || document.hidden) return;
    const basis = scene.header.layoutRev.replace(
      /:(?:avoid-v1|spline-v2|spline-v3)$/,
      "",
    );
    const key = JSON.stringify([
      scene.header.surface,
      scene.header.encounter,
      basis,
    ]);
    if (routeJob && routeJob.key !== key && !routeJob.operation)
      cancelRouting("Graph changed; routing cancelled.");
    if (scene.header.layoutRev.endsWith(":spline-v3")) {
      if (routeJob && !routeJob.operation) cancelRouting("");
      lastRoutedKey = key;
      if (!routeJob) routingStatus.textContent = "Edges routed.";
      routingControls();
      return;
    }
    if (lastRoutedKey === key) {
      routeAttempts.delete(key);
      lastRoutedKey = undefined;
    }
    if (
      layoutRun ||
      layoutOperation ||
      surface.pending.size ||
      surface.gestures.draft ||
      surface.previewingNodeMove ||
      routingComposing
    ) {
      if (routeJob && !routeJob.operation)
        cancelRouting("Routing paused during editing.", false);
      routingControls();
      routingTimer = setTimeout(routeTick, 250);
      return;
    }
    if (routeJob?.proposal && !routeJob.operation) {
      const scope = form("Save routing"),
        button = scope?.querySelector("button");
      if (
        !scope?.dataset.renderKey ||
        scope.dataset.loadingKey ||
        !button ||
        button.disabled
      ) {
        routingTimer = setTimeout(routeTick, 250);
        return;
      }
      if (
        !fill("Save routing", { operation: JSON.stringify(routeJob.proposal) })
      )
        return;
      delete button.dataset.gooInvocation;
      button.click();
      routeJob.operation = button.dataset.gooInvocation;
      if (!routeJob.operation) {
        cancelRouting(
          "Routing save could not start. Use Route edges to retry.",
        );
        return;
      }
      routingStatus.textContent = "Saving routes…";
      routingControls();
      return;
    }
    if (routeJob || routeAttempts.has(key) || !scene.connections.length) {
      routingControls();
      return;
    }
    const scope = form("Save routing");
    if (
      !scope?.dataset.renderKey ||
      scope.dataset.loadingKey ||
      scope.querySelector("button")?.disabled
    ) {
      routingTimer = setTimeout(routeTick, 250);
      return;
    }
    routeAttempts.add(key);
    if (routeAttempts.size > 64)
      routeAttempts.delete(routeAttempts.values().next().value);
    let worker;
    try {
      worker = new Worker("/grove-playground/routing-worker.js", {
        type: "module",
      });
    } catch (error) {
      routingStatus.textContent = `Routing unavailable: ${error.message}. Use Route edges to retry.`;
      routingControls();
      return;
    }
    const job = { key, worker };
    routeJob = job;
    routingStatus.textContent = "Routing edges…";
    routingControls();
    const fail = (message) => {
      if (routeJob !== job) return;
      cancelRouting(
        `Routing unavailable: ${message}. Use Route edges to retry.`,
      );
    };
    job.timeout = setTimeout(
      () => fail("calculation or download timed out"),
      20000,
    );
    job.worker.onerror = (event) => {
      event.preventDefault();
      fail(event.message || "worker failed");
    };
    job.worker.onmessage = ({ data }) => {
      if (routeJob !== job) return;
      clearTimeout(job.timeout);
      job.worker.terminate();
      job.worker = undefined;
      if (!data.ok) {
        fail(data.error);
        return;
      }
      job.proposal = data.proposal;
      scheduleRouting();
    };
    job.worker.postMessage(scene);
  }
  routeButton.onclick = () => {
    const scene = main.querySelector("goo-patch")?.installedScene;
    if (!scene || routeJob) return;
    if (scene.header.layoutRev.endsWith(":spline-v3")) {
      routingStatus.textContent = "Edges already routed.";
      return;
    }
    routeAttempts.delete(
      JSON.stringify([
        scene.header.surface,
        scene.header.encounter,
        scene.header.layoutRev.replace(/:(?:avoid-v1|spline-v2|spline-v3)$/, ""),
      ]),
    );
    scheduleRouting();
  };
  cancelRouteButton.onclick = () => cancelRouting("Routing cancelled.");
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && routeJob && !routeJob.operation) {
      event.preventDefault();
      cancelRouting("Routing cancelled.");
    }
  });
  document.addEventListener(
    "compositionstart",
    () => {
      routingComposing = true;
      cancelRouting("Routing paused during composition.", false);
    },
    { capture: true },
  );
  document.addEventListener(
    "compositionend",
    () => {
      routingComposing = false;
      scheduleRouting();
    },
    { capture: true },
  );
  main.addEventListener(
    "pointerdown",
    () => cancelRouting("Routing paused during interaction.", false),
    { capture: true },
  );
  document.addEventListener("pointerup", scheduleRouting, { capture: true });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) cancelRouting("Routing paused.", false);
    else scheduleRouting();
  });
  GooActions.subscribeOutcomes((receipt) => {
    if (!routeJob?.operation || routeJob.operation !== receipt.operationId)
      return;
    if (receipt.outcome === "unknown") {
      routingStatus.textContent =
        "Routing save outcome unknown; awaiting reconciliation.";
      return;
    }
    routingStatus.textContent =
      receipt.outcome === "accepted"
        ? "Routes saved."
        : "Routing rejected; existing edges retained. Use Route edges to retry.";
    routeJob = undefined;
    routingControls();
    scheduleRouting();
  });
  window.addEventListener("pagehide", () => {
    routeDisposed = true;
    clearTimeout(routingTimer);
    routeJob?.worker?.terminate();
    clearTimeout(routeJob?.timeout);
  });
  schedule();
})();
