// Real namespace/compiler/action integration. No intercepted domain responses.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
const [base, mash, out = "/tmp/grove-layout-browser"] = process.argv.slice(2);
if (!base || !mash)
  throw new Error("usage: check-layout-browser.mjs URL MASH_ROOT [OUTPUT]");
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

  await page.addInitScript(() => {
    window.previewReasons = [];
    customElements.whenDefined("goo-patch").then(() => {
      const proto = customElements.get("goo-patch").prototype,
        original = proto.beginNodeMovePreview;
      proto.beginNodeMovePreview = function (...args) {
        const result = original.apply(this, args);
        result?.signal.addEventListener("abort", () => {
          window.previewReasons.push(result.signal.reason);
          console.info("PREVIEW_ABORT", result.signal.reason);
        });
        return result;
      };
    });
  });
  page.on("console", (message) => {
    if (message.text().includes("PREVIEW_ABORT"))
      console.log(name, message.text());
  });
  const running = async () => {
    await page.waitForFunction(
      () =>
        document.querySelector(".layout-status")?.textContent !==
        "Loading layout engine…",
    );
    assert.match(
      await page.locator(".layout-status").textContent(),
      /^Arranging visible cards/,
    );
  };
  const scene = () =>
    page.locator("goo-patch").evaluate((el) => el.installedScene);
  const assertCurves = async (snapshot) => {
    if (snapshot.header.layoutRev.endsWith(":spline-v3")) {
      assert(
        snapshot.connections.every(
          (edge) =>
            edge.segments[0].commands[0].op === "M" &&
            edge.segments[0].commands.slice(1).every((c) => c.op === "C"),
        ),
      );
      return; // Obstacle clearance and rounded SVG are covered by check-routing-browser.mjs.
    }
    const nodes = new Map(snapshot.nodes.map((n) => [n.key, n]));
    for (const edge of snapshot.connections) {
      const segment = edge.segments[0];
      assert.equal(edge.segments.length, 1);
      assert.deepEqual(
        segment.commands.map((c) => c.op),
        ["M", "C"],
      );
      const [move, curve] = segment.commands;
      const anchor = (endpoint) => {
        const node = nodes.get(endpoint.port.node);
        const port = node.ports.find((p) => p.key === endpoint.port.port);
        return {
          x: node.rect.x + port.anchor.x,
          y: node.rect.y + port.anchor.y,
        };
      };
      assert.deepEqual(move.to, anchor(edge.endpoints[0]));
      assert.deepEqual(curve.to, anchor(edge.endpoints[1]));
      assert.deepEqual(curve.c1, { x: move.to.x + 80, y: move.to.y });
      assert.deepEqual(curve.c2, { x: curve.to.x - 80, y: curve.to.y });
      const midpoint = {
        x: (move.to.x + 3 * curve.c1.x + 3 * curve.c2.x + curve.to.x) / 8,
        y: (move.to.y + 3 * curve.c1.y + 3 * curve.c2.y + curve.to.y) / 8,
      };
      const label = edge.labels[0].rect;
      assert(Math.abs(label.x + label.width / 2 - midpoint.x) <= 0.5);
      assert(Math.abs(label.y + label.height / 2 - midpoint.y) <= 0.5);
    }
    const paths = await page
      .locator("goo-patch")
      .evaluate((el) =>
        [...el.shadowRoot.querySelectorAll("g[data-key] path[data-key]")].map(
          (p) => p.getAttribute("d"),
        ),
      );
    assert.equal(paths.length, snapshot.connections.length);
    assert(paths.every((d) => d.includes("C") && !d.includes("L")));
  };
  const routingIdle = () =>
    page.waitForFunction(
      () => {
        const scene = document.querySelector("goo-patch")?.installedScene;
        return (
          !scene?.connections.length ||
          scene.header.layoutRev.endsWith(":spline-v3")
        );
      },
      undefined,
      { timeout: 90000 },
    );
  const ready = async () => {
    await page.waitForFunction(
      () => document.querySelector("goo-patch")?.editable,
      undefined,
      { timeout: 180000 },
    );
    await page.waitForFunction(() =>
      document
        .querySelector(".playground-status")
        ?.textContent.startsWith("Draft "),
    );
    await routingIdle();
  };
  const actions = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/goo/act")
      if (
        ![...new URLSearchParams(request.postData())].some(([key, value]) => {
          if (!key.startsWith("input:")) return false;
          try {
            return !!JSON.parse(value).routes;
          } catch {
            return false;
          }
        })
      )
        actions.push(request.postData());
  });
  const arrange = () => {
    console.log(name, "arrange");
    return page
      .getByRole("button", { name: "Arrange", exact: true })
      .press("Enter");
  };
  const settled = async () => {
    await page
      .getByRole("status")
      .filter({ hasText: "Layout saved." })
      .waitFor({ timeout: 60000 });
    await page.waitForFunction(
      () => document.querySelector("goo-patch")?.pending.size === 0,
    );
    await routingIdle();
  };
  try {
    await page.goto(base + "/grove-playground");
    await ready();
    await page.locator('[data-workspace="library"]').click();
    await page.getByRole("button", { name: "Show all", exact: true }).click();
    await page.waitForFunction(
      () =>
        document.querySelector("goo-patch")?.installedScene.nodes.length === 4,
    );
    await page.locator('[data-workspace="library"]').click();
    await routingIdle();
    actions.length = 0;
    const initial = await state();
    // A CDN failure is local and leaves the graph editable. No domain response is mocked.
    await page.route("https://esm.sh/**", (route) => route.abort());
    await arrange();
    await page
      .locator(".layout-status")
      .filter({ hasText: "Arrange unavailable:" })
      .waitFor();
    assert.equal(actions.length, 0);
    assert.equal(
      await page.locator("goo-patch").evaluate((el) => el.previewingNodeMove),
      false,
    );
    await page.unroute("https://esm.sh/**");
    await page.reload();
    await ready();
    checks.push("CDN failure releases captured preview and saves nothing");
    const original = await scene();
    await assertCurves(original);
    // Exercise cancellation during the actual D3 animation, rather than cancelling only loading.
    await arrange();
    await running();
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await page
      .locator(".layout-status")
      .filter({ hasText: "Arrangement cancelled." })
      .waitFor();
    assert.equal(actions.length, 0);
    assert.deepEqual((await scene()).nodes, original.nodes);
    assert.equal(
      await page.locator("goo-patch").evaluate((el) => el.origins.size),
      0,
    );
    checks.push("Cancel restores authoritative positions without submitting");
    // Keep a dirty native input and caret through animation and accepted server projection.
    await page
      .getByRole("button", { name: "Select example", exact: true })
      .click();
    const editor = page
      .locator(
        '.goo-native[data-inspector-mode="properties"] input[data-input-slot$="/value"]',
      )
      .first();
    await editor.fill("Keep this unsaved edit");
    await editor.evaluate((el) => {
      window.layoutEditor = el;
      el.setSelectionRange(2, 7);
    });
    await arrange();
    await page.waitForFunction(
      () => document.querySelector("goo-patch")?.origins.size > 0,
    );
    assert.deepEqual((await scene()).nodes, original.nodes);
    await settled();
    assert.equal(actions.length, 1);
    const arranged = await scene(),
      after = await state();
    await assertCurves(arranged);
    checks.push(
      "server-authored connection geometry survives arrangement (routed geometry has its own gate)",
    );
    assert.notDeepEqual(
      arranged.nodes.map((n) => n.rect),
      original.nodes.map((n) => n.rect),
    );
    assert.deepEqual(
      arranged.nodes.map((n) => [n.key, n.lifetime]),
      original.nodes.map((n) => [n.key, n.lifetime]),
    );
    for (const key of ["source", "revision", "ready", "published"])
      assert.deepEqual(after[key], initial[key], key);
    assert(await editor.evaluate((el) => el === window.layoutEditor));
    assert.equal(await editor.inputValue(), "Keep this unsaved edit");
    assert.deepEqual(
      await editor.evaluate((el) => [el.selectionStart, el.selectionEnd]),
      [2, 7],
    );
    for (let i = 0; i < arranged.nodes.length; i++)
      for (let j = i + 1; j < arranged.nodes.length; j++) {
        const a = arranged.nodes[i].rect,
          b = arranged.nodes[j].rect;
        assert(
          a.x + a.width <= b.x ||
            b.x + b.width <= a.x ||
            a.y + a.height <= b.y ||
            b.y + b.height <= a.y,
          "overlapping final cards",
        );
      }
    checks.push(
      "real D3 animation; one admitted batch; no overlaps; stable identities and dirty inputs; no recompilation",
    );
    // Replay the actual submitted operation through Goo's receipt ledger.
    const duplicate = await page.request.post(base + "/goo/act", {
      form: Object.fromEntries(new URLSearchParams(actions[0])),
    });
    assert.equal(duplicate.status(), 200);
    assert.equal((await state()).revision, initial.revision);
    await page.reload();
    await ready();
    assert.deepEqual(
      (await scene()).nodes.map((n) => n.rect),
      arranged.nodes.map((n) => n.rect),
    );
    await assertCurves(await scene());
    checks.push("duplicate submission and reload preserve saved layout");
    // Hold only the optional engine download while a real filter action changes
    // the scene. This avoids racing a 1.5-second animation against server latency.
    let releaseEngine, engineRequested, engineHandled;
    const engineGate = new Promise((resolve) => {
      releaseEngine = resolve;
    });
    const requestSeen = new Promise((resolve) => {
      engineRequested = resolve;
    });
    const continued = new Promise((resolve) => {
      engineHandled = resolve;
    });
    await page.route("https://esm.sh/**", async (route) => {
      engineRequested();
      await engineGate;
      await route.continue();
      engineHandled();
    });
    await page.locator('[data-workspace="library"]').click();
    await arrange();
    await requestSeen;
    await page
      .getByRole("checkbox", { name: "Show role cards", exact: true })
      .click();
    await page
      .locator(".layout-status")
      .filter({ hasText: "Graph changed; arrangement cancelled." })
      .waitFor();
    await page.waitForFunction(
      () =>
        document.querySelector("goo-patch")?.installedScene.nodes.length === 3,
    );
    releaseEngine();
    await continued;
    await page.unroute("https://esm.sh/**");
    const hidden = await scene();
    await page.emulateMedia({ reducedMotion: "reduce" });
    const beforeActions = actions.length;
    await arrange();
    await settled();
    assert.equal(actions.length, beforeActions + 1);
    assert.equal((await scene()).nodes.length, hidden.nodes.length);
    await page.getByRole("button", { name: "Show all", exact: true }).click();
    await page.waitForFunction(
      () =>
        document.querySelector("goo-patch")?.installedScene.nodes.length === 4,
    );
    assert.deepEqual(
      (await scene()).nodes.find((n) => n.key === "2").rect,
      arranged.nodes.find((n) => n.key === "2").rect,
    );
    checks.push(
      "new projection cancels; reduced-motion arrangement saves visible cards only and retains hidden placement",
    );
    assert.deepEqual(
      await page.evaluate(() => window.forbiddenMeasurements),
      [],
    );
    assert.deepEqual(errors, []);
    checks.push("no node, port or label measurement; no browser errors");
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
    console.error(
      "PREVIEW REASONS",
      await page.evaluate(() => window.previewReasons),
    );
    console.error(await page.locator(".layout-status").textContent());
    throw error;
  } finally {
    await browser.close();
  }
}
