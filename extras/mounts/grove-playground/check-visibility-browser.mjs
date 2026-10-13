// Real namespace/compiler/action integration. No intercepted domain responses.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
const [base, mash, out = "/tmp/grove-visibility-browser"] =
  process.argv.slice(2);
if (!base || !mash)
  throw new Error("usage: check-visibility-browser.mjs URL MASH_ROOT [OUTPUT]");
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

  const scene = () =>
    page.locator("goo-patch").evaluate((el) => el.installedScene);
  const settled = () => page.waitForFunction(() => {
    const p = document.querySelector("goo-patch");
    return p?.editable && !p.pending.size &&
      (!p.installedScene.connections.length || p.installedScene.header.layoutRev.endsWith(":spline-v3"));
  }, undefined, { timeout: 90000 });
  const ready = async () => {
    await page.waitForFunction(
      () => document.querySelector("goo-patch")?.installedScene,
      undefined,
      { timeout: 180000 },
    );
    await page.locator('[data-workspace="library"]').click();
    await page
      .getByRole("checkbox", { name: "Show role cards", exact: true })
      .waitFor();
    await page.waitForFunction(
      () => !document.querySelector(".filter-kinds input")?.disabled,
    );
  };
  async function change(action, expected, accepted = async () => {}) {
    await settled();
    console.log(name, "visibility", expected.join(",") || "show all");
    await page.waitForFunction(() => !document.querySelector(".filter-kinds input")?.disabled);
    const before = (await scene()).header.viewSeq;
    const response = page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/goo/act",
    );
    await action();
    const result = await response;
    const body = await result.json();
    assert.equal(result.status(), 200, JSON.stringify(body));
    assert(!body.error, JSON.stringify(body));
    await accepted();
    await page.waitForFunction(
      (seq) =>
        document.querySelector("goo-patch")?.installedScene.header.viewSeq >
        seq,
      before,
    );
    await page.waitForFunction(
      (kinds) =>
        [...document.querySelectorAll(".filter-kinds input")].every(
          (i) => !i.disabled && i.checked === !kinds.includes(i.dataset.kind),
        ),
      expected,
    );
    assert.deepEqual(
      (await state()).hiddenKinds.slice().sort(),
      expected.slice().sort(),
    );
  }
  try {
    await page.goto(base + "/grove-playground");
    await ready();
    let initial = await state();
    if (initial.hiddenKinds.length)
      await change(
        () =>
          page.getByRole("button", { name: "Show all", exact: true }).click(),
        [],
      );
    initial = await state();
    await settled();
    const original = await scene();
    const slots = initial.nodes.filter((n) => n.kind === "slot");
    assert(slots.length, "real slot definitions retained");
    assert(initial.palette.includes("slot"), "slot creation remains available");
    for (const slot of slots) {
      assert(!original.nodes.some((n) => n.key === slot.id));
      assert.equal(await page.locator(`#playground-outline button[data-id="${slot.id}"]`).count(), 1);
    }
    assert(original.nodes.every((n) => n.ports.every((p) => !["field", "for"].includes(p.key))));
    assert(original.connections.every((e) => e.endpoints.every((ep) => original.nodes.some((n) => n.key === ep.port.node))));
    checks.push("slots retained in library and palette, absent from canvas with all slot-only wires and ports");
    const camera = await page
      .locator("goo-patch")
      .evaluate((el) => el.getCamera());
    const role = initial.nodes.find((n) => n.kind === "role");
    await page
      .locator(`#playground-outline button[data-id="${role.id}"]`)
      .click();
    const editor = page
      .locator(
        '.goo-native[data-inspector-mode="properties"] input[data-input-slot$="/value"]',
      )
      .first();
    await page.waitForFunction(() => {
      const scope = document.querySelector('.goo-native[data-inspector-mode="properties"]');
      return scope?.dataset.renderKey && !scope.dataset.loadingKey;
    });
    await editor.fill("Unsaved visibility draft");
    // Opening Properties resizes panes and refreshes the other bound forms.
    await page.waitForFunction(() => !document.querySelector(".filter-kinds input")?.disabled);
    await editor.evaluate((el) => {
      window.savedEditor = el;
      el.setSelectionRange(2, 7);
      el.dispatchEvent(
        new CompositionEvent("compositionstart", {
          bubbles: true,
          data: "draft",
        }),
      );
    });
    const box = page.getByRole("checkbox", {
      name: "Show role cards",
      exact: true,
    });
    await change(
      async () => {
        await box.focus();
        await page.keyboard.press("Space");
      },
      ["role"],
      async () => {
        assert(await editor.evaluate((el) => el === window.savedEditor));
        assert.equal(await editor.inputValue(), "Unsaved visibility draft");
        assert.deepEqual(
          await editor.evaluate((el) => [el.selectionStart, el.selectionEnd]),
          [2, 7],
        );
        // Goo defers applying the projection while a native composition is active.
        await editor.evaluate((el) =>
          el.dispatchEvent(
            new CompositionEvent("compositionend", {
              bubbles: true,
              data: "draft",
            }),
          ),
        );
      },
    );
    const hidden = await scene();
    assert.equal(hidden.nodes.length, original.nodes.length - 1);
    assert(!hidden.nodes.some((n) => n.key === role.id));
    const expectedEdges = original.connections.filter(
      (e) => e.endpoints.every((ep) => ep.port.node !== role.id),
    );
    assert.equal(hidden.connections.length, expectedEdges.length);
    assert.equal(
      await page.locator(`goo-patch-node[data-key="${role.id}"]`).count(),
      0,
    );
    assert.equal(
      await page
        .locator(`#playground-outline button[data-id="${role.id}"]`)
        .count(),
      0,
    );
    assert.equal(
      await page
        .locator("goo-patch")
        .evaluate(
          (el, id) =>
            el.index.region({ kind: "node", node: id, lifetime: "node:" + id }),
          role.id,
        ),
      null,
    );
    assert.equal(
      await page.locator("body").getAttribute("data-inspector"),
      "closed",
    );
    assert(await editor.evaluate((el) => el === window.savedEditor));
    assert.equal(await editor.inputValue(), "Unsaved visibility draft");
    assert.deepEqual(
      await editor.evaluate((el) => [el.selectionStart, el.selectionEnd]),
      [2, 7],
    );
    await editor.evaluate((el) =>
      el.dispatchEvent(
        new CompositionEvent("compositionend", {
          bubbles: true,
          data: "draft",
        }),
      ),
    );
    checks.push(
      "keyboard kind toggle filters actual scene, wires, hit regions and outline; hidden selection closes inspector",
    );
    checks.push(
      "dirty native input, caret and synthetic composition preserved",
    );
    const after = await state();
    for (const key of [
      "revision",
      "ready",
      "published",
      "source",
      "nodes",
      "edges",
      "preview",
    ])
      assert.deepEqual(after[key], initial[key], key);
    assert.deepEqual(
      await page.locator("goo-patch").evaluate((el) => el.getCamera()),
      camera,
    );
    checks.push(
      "source, program revision, preview, publication and camera unchanged",
    );
    // Real server compatibility provider no longer offers the hidden role.
    await page.locator('[data-workspace="library"]').click();
    const query = page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/goo/patch-query",
    );
    await page.getByRole("button", { name: "4 on", exact: true }).click();
    const advice = await (await query).json();
    assert(!advice.candidates.some((c) => c.target.node === role.id));
    await page.keyboard.press("Escape");
    checks.push("real compatibility advice excludes hidden targets");
    await page.reload();
    await ready();
    assert(!(await box.isChecked()));
    assert(!(await scene()).nodes.some((n) => n.key === role.id));
    checks.push("saved kind preferences and filtered scene restored on reload");
    await change(
      () => page.getByRole("button", { name: "Hide all", exact: true }).click(),
      initial.cardKinds.map((kind) => kind.key),
    );
    assert.equal((await scene()).nodes.length, 0);
    assert.equal((await scene()).connections.length, 0);
    await change(
      () => page.getByRole("button", { name: "Show all", exact: true }).click(),
      [],
    );
    assert.deepEqual(
      initial.cardKinds.map((kind) => kind.key),
      ["role", "sample", "view"],
    );
    assert.equal(await page.locator(".filter-kinds input").count(), 3);
    assert.equal(
      await page.locator(".playground-palette button").count(),
      initial.palette.length,
    );
    await change(
      () =>
        page
          .getByRole("checkbox", {
            name: "Show View / pane cards",
            exact: true,
          })
          .click(),
      ["view"],
    );
    const declarations = initial.nodes.filter(
      (node) => node.cardKind !== "view",
    );
    assert.deepEqual(
      (await scene()).nodes.map((node) => node.key),
      declarations.filter((node) => node.kind !== "slot").map((node) => node.id),
    );
    assert.equal(
      await page.locator("#playground-outline button").count(),
      declarations.length,
    );
    for (const key of ["revision", "ready", "source"])
      assert.deepEqual((await state())[key], initial[key]);
    await change(
      () =>
        page
          .getByRole("checkbox", {
            name: "Show View / pane cards",
            exact: true,
          })
          .click(),
      [],
    );
    checks.push(
      "three card categories; View / pane hides views and constructors together while creation palette remains intact",
    );
    const restored = await scene();
    assert.deepEqual(
      restored.nodes.map((n) => [n.key, n.lifetime, n.rect]),
      original.nodes.map((n) => [n.key, n.lifetime, n.rect]),
    );
    assert.deepEqual(restored.connections.map((e) => [e.key, e.lifetime, e.topologyRef, e.endpoints]),
      original.connections.map((e) => [e.key, e.lifetime, e.topologyRef, e.endpoints]));
    checks.push(
      "bulk hide/show restores identical identities, positions and connections",
    );
    assert.deepEqual(
      await page.evaluate(() => window.forbiddenMeasurements),
      [],
    );
    assert.deepEqual(errors, []);
    checks.push("no node/port/label measurement or browser errors");
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
      .screenshot({ path: resolve(out, name + "-failure.png"), fullPage: true })
      .catch(() => {});
    console.error("PAGE ERRORS", errors);
    console.error("STATE", await state());
    throw error;
  } finally {
    await browser.close();
  }
}
