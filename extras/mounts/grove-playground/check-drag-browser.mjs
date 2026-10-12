// Real pointer input and bound Goo actions against a running Eden namespace.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
const [base, mash, out = "/tmp/grove-drag-browser"] = process.argv.slice(2);
if (!base || !mash)
  throw new Error("usage: check-drag-browser.mjs URL MASH_ROOT [OUTPUT]");
const engines = createRequire(resolve(mash, "tests/integration/package.json"))(
  "@playwright/test",
);
await mkdir(out, { recursive: true });
const results = [];
for (const name of (process.env.BROWSERS || "chromium,firefox,webkit").split(
  ",",
)) {
  const browser = await engines[name].launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1600, height: 1100 },
  });
  page.setDefaultTimeout(90000);
  const errors = [],
    moves = [],
    checks = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (new URL(r.url()).pathname !== "/goo/act") return;
    for (const value of new URLSearchParams(r.postData() || "").values()) {
      try {
        const v = JSON.parse(value);
        if (v.kind === "move-nodes") moves.push(v);
      } catch {}
    }
  });
  await page.addInitScript(() => {
    window.forbiddenMeasurements = [];
    const forbidden = (el) =>
      el?.matches?.("goo-patch-node,goo-patch-port,[data-patch-label]") ||
      el?.closest?.("goo-patch-node,goo-patch-port,[data-patch-label]");
    for (const key of ["getBoundingClientRect", "getClientRects"]) {
      const original = Element.prototype[key];
      Element.prototype[key] = function (...args) {
        if (forbidden(this)) window.forbiddenMeasurements.push(key);
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
            if (forbidden(this)) window.forbiddenMeasurements.push(key);
            return d.get.call(this);
          },
        });
    }
  });
  const ready = () =>
    page.waitForFunction(
      () => {
        const p = document.querySelector("goo-patch");
        return (
          p?.editable &&
          !p.pending.size &&
          p.installedScene.header.layoutRev.endsWith(":spline-v3")
        );
      },
      undefined,
      { timeout: 180000 },
    );
  const scene = () =>
    page.locator("goo-patch").evaluate((p) => p.installedScene);
  const state = async () =>
    (await page.request.get(base + "/grove-playground/state")).json();
  const bodyPoint = () =>
    page.locator("goo-patch").evaluate((p) => {
      const r = p.installedScene.nodes.find((n) => n.key === "3").rect;
      const c = p.getCamera(),
        m = p.mapping();
      return {
        x: m.left + (c.tx + (r.x + r.width / 2) * c.scale) * m.sx,
        y: m.top + (c.ty + (r.y + r.height / 2) * c.scale) * m.sy,
      };
    });
  const check = (text) => {
    checks.push(text);
    console.log(name, text);
  };
  try {
    await page.goto(base + "/grove-playground");
    await ready();
    const editor = page
      .locator(
        '.goo-native[data-inspector-mode="properties"] input[data-input-slot$="/value"]',
      )
      .first();
    const initial = await scene(),
      semantics = await state(),
      before = moves.length;
    let p = await bodyPoint();
    await page.mouse.click(p.x, p.y);
    assert.equal(moves.length, before, "click selects without moving");
    assert.equal(
      await page
        .locator('goo-patch-node[data-key="3"] [data-patch-select]')
        .evaluate((el) => getComputedStyle(el).cursor),
      "grab",
    );
    await ready();
    await page.waitForFunction(() => {
      const scope = document.querySelector(
        '.goo-native[data-inspector-mode="properties"]',
      );
      return scope?.dataset.renderKey && !scope.dataset.loadingKey;
    });
    await editor.fill("Preserve during card drag");
    await editor.evaluate((el) => {
      window.dragEditor = el;
      el.setSelectionRange(2, 8);
    });
    p = await bodyPoint();
    await page.mouse.move(p.x, p.y);
    await page.mouse.down();
    await page.mouse.move(p.x + 95, p.y + 45, { steps: 8 });
    // Painting is rAF-scheduled; WebKit can deliver all mouse steps before it.
    await page.waitForFunction(() => {
      const el = document.querySelector("goo-patch");
      return el.gestures.draft?.phase === "move-nodes" && el.origins.has("3");
    });
    await page.mouse.up();
    await page.waitForFunction(
      (old) => {
        const n = document
          .querySelector("goo-patch")
          ?.installedScene.nodes.find((n) => n.key === "3");
        return n && (n.rect.x !== old.x || n.rect.y !== old.y);
      },
      initial.nodes.find((n) => n.key === "3").rect,
    );
    await ready();
    assert.equal(moves.length - before, 1, "one authoritative move per drop");
    const saved = await scene(),
      after = await state();
    for (const key of ["source", "revision", "ready", "published"])
      assert.deepEqual(after[key], semantics[key]);
    assert.equal(await editor.inputValue(), "Preserve during card drag");
    assert(await editor.evaluate((el) => el === window.dragEditor));
    assert.deepEqual(
      await editor.evaluate((el) => [el.selectionStart, el.selectionEnd]),
      [2, 8],
    );
    check(
      "whole-card click/drag; one saved move; rerouted curves; preserved input and semantic revision",
    );
    p = await bodyPoint();
    await page.mouse.move(p.x, p.y);
    await page.mouse.down();
    await page.mouse.move(p.x + 80, p.y - 35, { steps: 6 });
    await page.keyboard.press("Escape");
    await page.mouse.up();
    assert.equal(moves.length - before, 1);
    assert.deepEqual((await scene()).nodes, saved.nodes);
    assert(
      await page
        .locator("goo-patch")
        .evaluate((el) => !el.gestures.draft && !el.origins.size),
    );
    check("Escape cancels card drag without saving");
    await page.reload();
    await ready();
    assert.deepEqual((await scene()).nodes, saved.nodes);
    assert.deepEqual((await scene()).connections, saved.connections);
    check("browser reload restores saved card placement and curves");
    await page
      .getByRole("button", { name: "Move example right", exact: true })
      .press("Enter");
    await page.waitForFunction(
      (x) =>
        document
          .querySelector("goo-patch")
          ?.installedScene.nodes.find((n) => n.key === "3").rect.x !== x,
      saved.nodes.find((n) => n.key === "3").rect.x,
    );
    await ready();
    assert.equal(moves.length - before, 2);
    assert.deepEqual(
      await page.evaluate(() => window.forbiddenMeasurements),
      [],
    );
    assert.deepEqual(errors, []);
    check(
      "keyboard movement remains available; no node/port/label measurements or browser errors",
    );
    // Keep the zero axes in the viewport, using the existing camera API only.
    // Every card/port coordinate below comes from the authoritative scene.
    for (const destination of [{ x: -180, y: -160 }, { x: -340, y: -320 }, { x: 60, y: 320 }]) {
      await page.locator("goo-patch").evaluate((p) => p.setCamera({ scale: 0.65, tx: 500, ty: 350 }));
      const beforeMove = (await scene()).nodes.find((n) => n.key === "3").rect;
      const start = await bodyPoint();
      const end = await page.locator("goo-patch").evaluate((p, d) => {
        const r = p.installedScene.nodes.find((n) => n.key === "3").rect;
        const c = p.getCamera(), m = p.mapping();
        return { x: m.left + (c.tx + (d.x + r.width / 2) * c.scale) * m.sx,
          y: m.top + (c.ty + (d.y + r.height / 2) * c.scale) * m.sy };
      }, destination);
      await page.mouse.move(start.x, start.y);
      await page.mouse.down();
      await page.mouse.move(end.x, end.y, { steps: 12 });
      await page.waitForFunction(() => document.querySelector("goo-patch").origins.has("3"));
      await page.mouse.up();
      await page.waitForFunction((old) => {
        const r = document.querySelector("goo-patch").installedScene.nodes.find((n) => n.key === "3").rect;
        return r.x !== old.x || r.y !== old.y;
      }, beforeMove);
      await ready();
      const savedSigned = await scene(), r = savedSigned.nodes.find((n) => n.key === "3").rect;
      assert(Math.abs(r.x - destination.x) <= 1 && Math.abs(r.y - destination.y) <= 1,
        `saved drop ${JSON.stringify(r)} must match ${JSON.stringify(destination)}`);
      for (const n of savedSigned.nodes) {
        assert(n.rect.x >= savedSigned.extent.x && n.rect.y >= savedSigned.extent.y);
        assert(n.rect.x + n.rect.width <= savedSigned.extent.x + savedSigned.extent.width);
        assert(n.rect.y + n.rect.height <= savedSigned.extent.y + savedSigned.extent.height);
      }
      for (const key of ["source", "revision", "ready", "published"])
        assert.deepEqual((await state())[key], semantics[key]);
      await page.reload();
      await ready();
      assert.deepEqual((await scene()).nodes, savedSigned.nodes);
      assert.deepEqual((await scene()).connections, savedSigned.connections);
      check(`drag to (${destination.x}, ${destination.y}), reroute and reload preserve signed placement and semantics`);
    }
    const current = await scene();
    const rejection = page.waitForResponse((r) => new URL(r.url()).pathname === "/goo/act" &&
      r.request().postData()?.includes("move-nodes"));
    await page.locator("goo-patch").evaluate((p) => {
      const n = p.installedScene.nodes.find((n) => n.key === "3"),
        target = { kind: "node", node: n.key, lifetime: n.lifetime },
        capture = p.capture("move-nodes", [target]);
      p.submit({ kind: "move-nodes", nodes: [{ target, baseOrigin: { x: 0, y: 0 },
        proposedOrigin: { x: -50, y: -50 } }] }, capture, p.basis, crypto.randomUUID());
    });
    const rejected = await rejection, detail = await rejected.json();
    assert(!rejected.ok(), JSON.stringify(detail));
    assert.match(detail.error, /Placement changed during movement/);
    await page.waitForFunction(() => !document.querySelector("goo-patch").pending.size);
    assert.deepEqual((await scene()).nodes, current.nodes);
    check("stale movement reports the actual rejection reason and preserves saved positions");
    assert.deepEqual(await page.evaluate(() => window.forbiddenMeasurements), []);
    assert.deepEqual(errors, []);
    await page.screenshot({ path: resolve(out, name + ".png") });
    results.push({ engine: name, version: browser.version(), checks });
  } catch (error) {
    console.error(name, error);
    console.error(
      await page
        .locator("goo-patch")
        .evaluate((p) => ({
          editable: p.editable,
          phase: p.gestures.draft?.phase,
          origins: [...p.origins],
          camera: p.getCamera(),
          mapping: p.mapping(),
          selection: p.selection,
        })),
    );
    await page.screenshot({ path: resolve(out, name + "-failure.png") });
    throw error;
  } finally {
    await browser.close();
  }
}
await writeFile(
  resolve(out, "results.json"),
  JSON.stringify(results, null, 2) + "\n",
);
