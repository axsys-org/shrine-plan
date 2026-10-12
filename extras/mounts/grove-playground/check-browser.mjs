// Real namespace/compiler/action integration. No intercepted domain responses.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
const [base, mash, out = "/tmp/grove-playground-browser"] =
  process.argv.slice(2);
if (!base || !mash)
  throw new Error("usage: check-browser.mjs URL MASH_ROOT [OUTPUT]");
const require = createRequire(resolve(mash, "tests/integration/package.json"));
const engines = require("@playwright/test"),
  results = [];
await mkdir(out, { recursive: true });
for (const name of (process.env.BROWSERS || "chromium,firefox,webkit").split(
  ",",
)) {
  const browser = await engines[name].launch({ headless: true }),
    page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
  page.setDefaultTimeout(60000);
  const errors = [],
    checks = [];
  let lastAction;
  page.on("pageerror", (e) => errors.push(e.message));
  if (process.env.DEBUG_FRAMES) {
    page.on("framenavigated", (f) => console.log("FRAME", f.url()));
    page.on("requestfailed", (r) =>
      console.log("REQUEST FAILED", r.url(), r.failure()),
    );
  }
  await page.addInitScript(() => {
    window.forbiddenMeasurements = [];
    const forbidden = (el) =>
      el?.matches?.("goo-patch-node,goo-patch-port,[data-patch-label]") ||
      el?.closest?.("goo-patch-node,goo-patch-port,[data-patch-label]");
    for (const key of ["getBoundingClientRect", "getClientRects"]) {
      const original = Element.prototype[key];
      Element.prototype[key] = function (...args) {
        if (forbidden(this))
          window.forbiddenMeasurements.push(key + ":" + this.tagName);
        return original.apply(this, args);
      };
    }
    for (const key of [
      "offsetWidth",
      "offsetHeight",
      "clientWidth",
      "clientHeight",
      "scrollWidth",
      "scrollHeight",
    ]) {
      const proto = Object.getOwnPropertyDescriptor(HTMLElement.prototype, key)
        ? HTMLElement.prototype
        : Element.prototype;
      const d = Object.getOwnPropertyDescriptor(proto, key);
      if (d?.get)
        Object.defineProperty(proto, key, {
          ...d,
          get() {
            if (forbidden(this))
              window.forbiddenMeasurements.push(key + ":" + this.tagName);
            return d.get.call(this);
          },
        });
    }
  });
  const state = async () => {
    const r = await page.request.get(base + "/grove-playground/state");
    assert.equal(r.status(), 200);
    return r.json();
  };
  const form = (label) =>
    page
      .locator(".goo-native")
      .filter({ has: page.getByRole("button", { name: label, exact: true }) });
  const input = (label, key) =>
    form(label).locator(`input[data-input-slot$="/${key}"]`);
  const modes = {
    "Create node": "create",
    "Save properties": "properties",
    "Delete node": "properties",
    "Collapse / expand view": "properties",
    "Connect relationship": "links",
    "Disconnect relationship": "links",
    "Reorder child": "links",
    "Save sample field": "links",
    "Publish revision": "publish",
  };
  async function revealForm(label) {
    if (!(await page.locator(".inspector-heading").isVisible()))
      await page.locator('[data-workspace="properties"]').click();
    await page
      .locator('.inspector-tabs [data-mode="' + modes[label] + '"]')
      .click();
  }
  async function chooseNode(id) {
    const library = page.locator('[data-workspace="library"]');
    if ((await library.getAttribute("aria-pressed")) !== "true")
      await library.click();
    await page
      .locator('#playground-outline button[data-id="' + id + '"]')
      .click();
    await library.click();
  }

  async function submit(label, values = {}, semantic = true) {
    console.log(name, "submit", label);
    await revealForm(label);
    await page.waitForFunction(
      () => !document.querySelector(".goo-native[data-loading-key]"),
    );
    const before = await state();
    const sequence = await page
      .locator("goo-patch")
      .evaluate((el) => el.installedScene.header.viewSeq);
    for (const [key, value] of Object.entries(values))
      await input(label, key).fill(String(value));
    const action = page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/goo/act",
    );
    await form(label).getByRole("button", { name: label, exact: true }).click();
    const response = await action;
    lastAction = response.request().postData();
    const body = await response.json();
    assert.equal(response.status(), 200, JSON.stringify(body));
    await page.waitForFunction(
      (seq) =>
        document.querySelector("goo-patch")?.installedScene.header.viewSeq >
        seq,
      sequence,
    );
    await page.waitForFunction(
      () =>
        !document
          .querySelector(".goo-view-host")
          ?.querySelector('[aria-busy="true"]'),
    );
    if (semantic)
      await page.waitForFunction(
        (rev) =>
          document
            .querySelector(".playground-status")
            ?.textContent.startsWith(`Draft ${Number(rev) + 1} `),
        before.revision,
      );
    await page.waitForFunction(
      () => !document.querySelector(".goo-native[data-loading-key]"),
    );
    const settled = await state();
    console.log(
      name,
      "settled",
      label,
      settled.revision,
      settled.ready,
      settled.published,
    );
    return settled;
  }
  const ready = async () => {
    await page.waitForFunction(
      () => document.querySelector("goo-patch")?.installedScene,
      undefined,
      { timeout: 180000 },
    );
    await page.waitForFunction(() =>
      document
        .querySelector(".playground-status")
        ?.textContent.startsWith("Draft "),
    );
  };
  const revealPreview = async () => {
    const button = page.locator("[data-workspace=preview]");
    if ((await button.getAttribute("aria-pressed")) !== "true")
      await button.click();
  };
  const previewText = () =>
    page.frameLocator("#playground-preview iframe").locator("body");
  try {
    await page.goto(base + "/grove-playground");
    await ready();
    let s = await state();
    assert.equal(s.ready, s.revision, s.message);
    await page
      .frameLocator("#playground-preview iframe")
      .getByRole("button", { name: "Inspect a presentation", exact: true })
      .waitFor();
    checks.push("real initial compilation and installation");
    const sample = s.nodes.find((n) => n.id === "3");
    const value = `Grove ${name} ${Date.now()}`;
    await page
      .getByRole("button", { name: "Select " + sample.name, exact: true })
      .click();
    await page
      .locator(".inspector-heading h2")
      .filter({ hasText: sample.name })
      .waitFor();
    await page.waitForFunction(
      (id) =>
        [
          ...document.querySelectorAll(
            '.goo-native[data-inspector-mode="properties"] input[data-input-slot$="/id"]',
          ),
        ].some((input) => input.value === id),
      sample.id,
    );
    assert.equal(await input("Save properties", "id").inputValue(), sample.id);
    assert.equal(
      await input("Save properties", "name").inputValue(),
      sample.name,
    );
    assert.equal(
      await input("Save properties", "value").inputValue(),
      sample.value,
    );
    s = await submit("Save properties", {
      id: 3,
      name: sample.name,
      value,
      slot: sample.slot,
    });
    assert.equal(s.ready, s.revision, s.message);
    await revealPreview();
    await page.locator("#playground-preview iframe").scrollIntoViewIfNeeded();
    await previewText()
      .filter({ hasText: value })
      .waitFor({ state: "attached", timeout: 120000 });
    checks.push("bound sample edit automatically updates compiled preview");
    const duplicate = await page.request.post(base + "/goo/act", {
      form: Object.fromEntries(new URLSearchParams(lastAction)),
    });
    assert.equal(duplicate.status(), 200);
    assert.equal((await state()).revision, s.revision);
    checks.push("duplicate invocation is applied only once");
    // Preview retains the ordinary inspection entrypoint.
    await revealPreview();
    await page.locator("#playground-preview iframe").scrollIntoViewIfNeeded();
    const live = page.frameLocator("#playground-preview iframe");
    await live
      .getByRole("button", { name: "Inspect a presentation", exact: true })
      .click();
    await live
      .locator(
        '.goo-view-host .preview[data-view$="/preview/summary"] .goo-surface',
      )
      .click();
    const inspection = live.getByRole("complementary", {
      name: "Presentation inspection",
    });
    await inspection
      .getByRole("status")
      .filter({ hasText: "Captured observation." })
      .waitFor();
    const observed = await inspection.innerText();
    assert(observed.includes(s.preview));
    assert(observed.includes("/preview/summary"));
    assert(observed.toLowerCase().includes("layout"));
    await inspection.getByRole("button", { name: "Close inspection" }).click();
    checks.push("inspect actual compiled recipe, subject and resolved layout");
    const success = s.ready;
    const roleField = s.edges.find(
      (e) => e.source === "2" && e.port === "field" && e.target === "1",
    );
    s = await submit("Disconnect relationship", { id: roleField.id });
    assert.equal(s.ready, success);
    assert.notEqual(s.revision, s.ready);
    assert(s.message);
    assert.equal(s.diagnosticNode, "5");
    await revealPreview();
    await page.locator("#playground-preview iframe").scrollIntoViewIfNeeded();
    await previewText()
      .filter({ hasText: value })
      .waitFor({ state: "attached", timeout: 120000 });
    checks.push(
      "compiler diagnostics map to component; failed build retains last preview",
    );
    s = await submit("Connect relationship", {
      left: 2,
      port: "field",
      right: 1,
    });
    assert.equal(s.ready, s.revision, s.message);
    // Rename identity-bearing slot, preserving all relationship identities.
    const edges = s.edges;
    await chooseNode("1");
    s = await submit("Save properties", {
      id: 1,
      name: name + "Title",
      value: "",
      slot: "",
    });
    assert.equal(s.ready, s.revision, s.message);
    assert.deepEqual(s.edges, edges);
    checks.push("rename preserves identities and recompiles receiver bindings");
    // Publish only the explicitly selected compiled revision.
    s = await submit("Publish revision", { revision: s.ready }, false);
    assert.equal(s.published, s.ready);
    const published = s.published;
    const publishedPath = s.preview.replace("/preview/", "/published/");
    const publishedResponse = await page.request.get(
      base + "/views" + publishedPath,
    );
    assert.equal(publishedResponse.status(), 200);
    assert((await publishedResponse.text()).includes(value));
    checks.push("explicit real publication and separate installed target");
    const stale = published;
    s = await submit("Save properties", {
      id: 3,
      name: sample.name,
      value: value + " edited",
      slot: sample.slot,
    });
    assert.equal(s.published, published);
    assert.equal(s.ready, s.revision);
    const publishedAfter = await page.request.get(
      base + "/views" + publishedPath,
    );
    assert(!(await publishedAfter.text()).includes(value + " edited"));
    // Stale explicit revision must be rejected by server admission/action code.
    await revealForm("Publish revision");
    await input("Publish revision", "revision").fill(stale);
    const rejected = page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/goo/act",
    );
    await form("Publish revision")
      .getByRole("button", { name: "Publish revision", exact: true })
      .click();
    const rejection = await (await rejected).json();
    assert(rejection.error, JSON.stringify(rejection));
    assert.equal((await state()).published, published);
    checks.push(
      "stale publication rejected; preview edits leave publication isolated",
    );
    // Dynamic occurrence creation, literal configuration, child ordering and deletion via ordinary forms.
    s = await submit("Create node", { tag: "text", name: "caption_" + name });
    const child = s.nodes.at(-1);
    s = await submit("Save properties", {
      id: child.id,
      name: child.name,
      value: "Visual child " + name,
      slot: "/sys/slot/label",
    });
    const compatibility = page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/goo/patch-query",
    );
    await page.getByRole("button", { name: "4 child", exact: true }).click();
    const queryResponse = await compatibility;
    assert.equal(queryResponse.status(), 200);
    const answer = await queryResponse.json();
    assert.equal(
      answer.candidates.find((c) => c.target.node === child.id).status,
      "allowed",
    );
    await page
      .getByRole("button", { name: child.id + " ref", exact: true })
      .click();
    await page.waitForFunction(
      (rev) =>
        document
          .querySelector(".playground-status")
          ?.textContent.startsWith(`Draft ${Number(rev) + 1} `),
      s.revision,
    );
    await page.waitForFunction(
      () => document.querySelector("goo-patch")?.pending.size === 0,
    );
    s = await state();
    assert.equal(s.ready, s.revision, s.message);
    const expired = await page.request.post(base + "/goo/patch-query", {
      form: Object.fromEntries(
        new URLSearchParams(queryResponse.request().postData()),
      ),
    });
    assert.equal(expired.status(), 409);
    checks.push(
      "server-backed compatibility, no-drag port connection and stale query rejection",
    );
    const childEdge = s.edges.find(
      (e) => e.target === child.id && e.port === "child",
    );
    s = await submit("Reorder child", { id: childEdge.id, index: 0 });
    assert.equal(
      s.edges.filter((e) => e.source === "4" && e.port === "child")[0].id,
      childEdge.id,
    );
    checks.push(
      "dynamic creation, configuration, containment and ordered child connections",
    );
    let programRevision = s.revision;
    await submit("Collapse / expand view", { id: 4 }, false);
    await page.waitForFunction(
      () =>
        document.querySelector("goo-patch")?.installedScene.nodes.length === 3,
    );
    await submit("Collapse / expand view", { id: 4 }, false);
    await page.waitForFunction(
      () =>
        document.querySelector("goo-patch")?.installedScene.nodes.length === 5,
    );
    assert.equal((await state()).revision, programRevision);
    // Reconnect through the shared connection controls, preserving edge identity.
    const sameEdge = s.edges.find((e) => e.source === "3" && e.port === "on");
    const beforeReconnect = (await state()).revision;
    await revealForm("Connect relationship");
    const reconciling = page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/goo/patch-query",
    );
    await page
      .getByRole("button", {
        name: "Reconnect " + sameEdge.id + " to",
        exact: true,
      })
      .click();
    const reconnectAdvice = await (await reconciling).json();
    assert.equal(
      reconnectAdvice.candidates.find(
        (c) => c.target.node === "2" && c.target.port === "ref",
      ).status,
      "allowed",
    );
    await page.getByRole("button", { name: "2 ref", exact: true }).click();
    await page.waitForFunction(
      (rev) =>
        document
          .querySelector(".playground-status")
          ?.textContent.startsWith(`Draft ${Number(rev) + 1} `),
      beforeReconnect,
    );
    await page.waitForFunction(
      () => document.querySelector("goo-patch")?.pending.size === 0,
    );
    s = await state();
    assert(s.edges.some((e) => e.id === sameEdge.id));
    checks.push("keyboard reconnect preserves relationship identity");
    programRevision = s.revision;
    // Dirty input and synthetic composition survive a server projection caused by keyboard movement.
    await revealForm("Save properties");
    const editor = input("Save properties", "value");
    await editor.fill("Unsaved composition draft");
    await editor.evaluate((el) => {
      window.savedEditor = el;
      el.focus();
      el.setSelectionRange(3, 9);
      el.dispatchEvent(
        new CompositionEvent("compositionstart", {
          bubbles: true,
          data: "draft",
        }),
      );
    });
    const origin = await page
      .locator("goo-patch")
      .evaluate(
        (el) => el.installedScene.nodes.find((n) => n.key === "3").rect.x,
      );
    const moved = page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/goo/act",
    );
    // Focusing the always-visible handle reveals its keyboard movement controls.
    await page
      .getByRole("button", { name: "Move example", exact: true })
      .focus();
    await page
      .getByRole("button", {
        name: "Move example right",
        exact: true,
      })
      .click();
    assert.equal((await moved).status(), 200);
    assert(await editor.evaluate((el) => el === window.savedEditor));
    assert.equal(await editor.inputValue(), "Unsaved composition draft");
    assert.deepEqual(
      await editor.evaluate((el) => [el.selectionStart, el.selectionEnd]),
      [3, 9],
    );
    await editor.evaluate((el) =>
      el.dispatchEvent(
        new CompositionEvent("compositionend", {
          bubbles: true,
          data: "draft",
        }),
      ),
    );
    await page.waitForFunction(
      (x) =>
        document
          .querySelector("goo-patch")
          ?.installedScene.nodes.find((n) => n.key === "3").rect.x > x,
      origin,
    );
    assert.equal((await state()).revision, programRevision);
    checks.push(
      "no-drag movement, dirty input/caret and synthetic composition preservation",
    );
    const x = await page
      .locator("goo-patch")
      .evaluate(
        (el) => el.installedScene.nodes.find((n) => n.key === "3").rect.x,
      );
    // Test source export and persisted namespace state on browser reload.
    await page.locator("[data-workspace=source]").click();
    const download = page.waitForEvent("download");
    await page.getByRole("link", { name: "Export Grove ↗" }).click();
    assert.equal((await download).suggestedFilename(), "playground.grove");
    assert.deepEqual(
      await page.evaluate(() => window.forbiddenMeasurements),
      [],
    );
    await page.reload();
    await ready();
    assert.equal((await state()).revision, programRevision);
    assert.equal(
      await page
        .locator("goo-patch")
        .evaluate(
          (el) => el.installedScene.nodes.find((n) => n.key === "3").rect.x,
        ),
      x,
    );
    checks.push("read-only source export and reload restoration");
    await submit("Disconnect relationship", { id: childEdge.id });
    s = await submit("Delete node", { id: child.id });
    assert.equal(s.nodes.length, 5);
    assert.equal(s.ready, s.revision, s.message);
    // A server-backed creation picker finishes the original captured action.
    await page.locator("goo-patch").scrollIntoViewIfNeeded();
    const points = await page.locator("goo-patch").evaluate((el) => {
      const rect = el.getBoundingClientRect(),
        camera = el.getCamera(),
        node = el.installedScene.nodes.find((n) => n.key === "4"),
        port = node.ports.find((p) => p.key === "child");
      const client = (p) => ({
        x: rect.left + camera.tx + p.x * camera.scale,
        y: rect.top + camera.ty + p.y * camera.scale,
      });
      return {
        from: client({
          x: node.rect.x + port.anchor.x,
          y: node.rect.y + port.anchor.y,
        }),
        to: client({ x: 370, y: 550 }),
      };
    });
    const previous = s.revision;
    await page.mouse.move(points.from.x, points.from.y);
    await page.mouse.down();
    await page.mouse.move(points.to.x, points.to.y, { steps: 5 });
    await page.mouse.up();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Create text", exact: true })
      .click();
    await page.waitForFunction(
      (rev) =>
        document
          .querySelector(".playground-status")
          ?.textContent.startsWith(`Draft ${Number(rev) + 1} `),
      previous,
    );
    await page.waitForFunction(
      () => document.querySelector("goo-patch")?.pending.size === 0,
    );
    s = await state();
    const created = s.nodes.at(-1),
      createdEdge = s.edges.find(
        (e) =>
          e.source === "4" && e.target === created.id && e.port === "child",
      );
    assert.equal(created.kind, "text");
    assert(createdEdge);
    assert.equal(s.ready, s.revision, s.message);
    await submit("Disconnect relationship", { id: createdEdge.id });
    await submit("Delete node", { id: created.id });
    checks.push("real creation picker creates and connects atomically");
    assert.deepEqual(
      await page.evaluate(() => window.forbiddenMeasurements),
      [],
    );
    assert.deepEqual(errors, []);
    checks.push("no node/port/label geometry reads");
    await page.screenshot({
      path: resolve(out, name + ".png"),
      fullPage: true,
    });
    results.push({
      engine: name,
      version: browser.version(),
      checks,
      passed: true,
    });
    console.log(JSON.stringify(results.at(-1)));
    await writeFile(
      resolve(out, "results.json"),
      JSON.stringify(results, null, 2) + "\n",
    );
  } catch (error) {
    await page
      .screenshot({
        path: resolve(out, name + "-failure.png"),
        fullPage: true,
        timeout: 10000,
      })
      .catch(() => {});
    console.error("PAGE ERRORS", errors);
    console.error(
      "PREVIEW",
      await previewText()
        .textContent()
        .catch((e) => e.message),
    );
    console.error(
      "NATIVE",
      await page.locator(".goo-native").evaluateAll((nodes) =>
        nodes.map((n) => ({
          loading: n.dataset.loadingKey,
          render: n.dataset.renderKey,
          text: n.textContent.slice(0, 100),
        })),
      ),
    );
    console.error("STATE", await state());
    console.error(await page.locator("body").innerText());
    throw error;
  } finally {
    await browser.close();
  }
}
await writeFile(
  resolve(out, "results.json"),
  JSON.stringify(results, null, 2) + "\n",
);
