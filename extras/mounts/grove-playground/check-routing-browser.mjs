// Real namespace/compiler/action integration. No intercepted domain responses.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
const [base, mash, out = "/tmp/grove-routing-browser"] = process.argv.slice(2);
if (!base || !mash)
  throw new Error("usage: check-routing-browser.mjs URL MASH_ROOT [OUTPUT]");
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
  checks.push = (...items) => {
    console.log(name, ...items);
    return Array.prototype.push.apply(checks, items);
  };
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

  const actions = [];
  page.on("request", (r) => {
    if (new URL(r.url()).pathname === "/goo/act") actions.push(r.postData());
  });
  const scene = () =>
    page.locator("goo-patch").evaluate((el) => el.installedScene);
  const ready = () =>
    page.waitForFunction(
      () => document.querySelector("goo-patch")?.editable,
      undefined,
      { timeout: 180000 },
    );
  const routed = async () => {
    await page.waitForFunction(
      () =>
        document
          .querySelector("goo-patch")
          ?.installedScene?.header.layoutRev.endsWith(":spline-v3"),
      undefined,
      { timeout: 90000 },
    );
    await page.waitForFunction(() => {
      const scope = document.querySelector(
        '.goo-native[data-inspector-mode="routing"]',
      );
      return (
        !!scope?.dataset.renderKey &&
        !scope.dataset.loadingKey &&
        !!scope.querySelector("button") &&
        !scope.querySelector("button").disabled
      );
    });
  };
  function checkRoutes(snapshot) {
    assert(snapshot.header.layoutRev.endsWith(":spline-v3"));
    for (const e of snapshot.connections) {
      const cmds = e.segments[0].commands;
      const anchors = e.endpoints.map((ep) => {
        const n = snapshot.nodes.find((n) => n.key === ep.port.node),
          p = n.ports.find((p) => p.key === ep.port.port);
        return { x: n.rect.x + p.anchor.x, y: n.rect.y + p.anchor.y };
      });
      assert.deepEqual(cmds[0].to, anchors[0]);
      assert.deepEqual(cmds.at(-1).to, anchors[1]);
      assert(cmds.slice(1).every((c) => c.op === "C"));
      assert(cmds.every((c) => ["M", "C"].includes(c.op)));
      for (const c of cmds) for (const p of [c.to, c.c1, c.c2].filter(Boolean)) {
        const r = snapshot.extent;
        assert(p.x >= r.x && p.x <= r.x+r.width && p.y >= r.y && p.y <= r.y+r.height,
          "Fit contains the full spline hull");
      }
      for (let i = 1; i < cmds.length - 1; i++) {
        const knot = cmds[i].to,
          incoming = cmds[i].c2,
          outgoing = cmds[i + 1].c1;
        assert.equal(
          knot.x - incoming.x,
          outgoing.x - knot.x,
          "continuous x tangent",
        );
        assert.equal(
          knot.y - incoming.y,
          outgoing.y - knot.y,
          "continuous y tangent",
        );
      }
      assert.equal(cmds[1].c1.y, anchors[0].y, "horizontal exit tangent");
      assert(cmds[1].c1.x >= anchors[0].x, "outward exit tangent");
      assert.equal(cmds.at(-1).c2.y, anchors[1].y, "horizontal entry tangent");
      assert(cmds.at(-1).c2.x <= anchors[1].x, "inward entry tangent");
      const samples = [cmds[0].to];
      let previous = cmds[0].to;
      for (const c of cmds.slice(1)) {
        for (let i = 1; i < 40; i++) {
          const t = i / 40,
            u = 1 - t,
            p =
              c.op === "L"
                ? {
                    x: previous.x * u + c.to.x * t,
                    y: previous.y * u + c.to.y * t,
                  }
                : {
                    x:
                      u ** 3 * previous.x +
                      3 * u * u * t * c.c1.x +
                      3 * u * t * t * c.c2.x +
                      t ** 3 * c.to.x,
                    y:
                      u ** 3 * previous.y +
                      3 * u * u * t * c.c1.y +
                      3 * u * t * t * c.c2.y +
                      t ** 3 * c.to.y,
                  };
          samples.push(p);
          for (const n of snapshot.nodes) {
            const r = n.rect;
            assert(
              !(
                p.x > r.x &&
                p.x < r.x + r.width &&
                p.y > r.y &&
                p.y < r.y + r.height
              ),
              `spline ${e.key} crosses card ${n.key}`,
            );
          }
        }
        samples.push(c.to);
        previous = c.to;
      }
      const cross = (a, b, c) => (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
      for (let i=1; i<samples.length; i++) {
        for (let j=i+2; j<samples.length; j++) {
          const a=samples[i-1], b=samples[i], c=samples[j-1], d=samples[j];
          assert(!(cross(a,b,c)*cross(a,b,d)<0 && cross(c,d,a)*cross(c,d,b)<0),
            `spline ${e.key} has a self-crossing loop`);
        }
      }
    }
  }
  const routingProposal = (body) => {
    for (const [key, value] of new URLSearchParams(body))
      if (key.startsWith("input:")) {
        try {
          const p = JSON.parse(value);
          if (p.routes) return p;
        } catch {}
      }
  };
  try {
    await page.goto(base + "/grove-playground");
    await ready();
    await routed();
    const initial = await state(),
      original = await scene();
    checkRoutes(original);
    await writeFile(resolve(out, name + "-initial-scene.json"), JSON.stringify(original, null, 2));
    assert(
      original.connections.some((e) =>
        e.segments[0].commands.some((c) => c.op === "C"),
      ),
    );
    const paths = await page
      .locator("goo-patch")
      .evaluate((el) =>
        [...el.shadowRoot.querySelectorAll("g[data-key] path[data-key]")].map(
          (p) => p.getAttribute("d"),
        ),
      );
    assert.equal(paths.length, original.connections.length);
    assert(paths.every((p) => p.includes("C") && !p.includes("L")));
    checks.push(
      "actual CDN WASM worker; admitted smooth cubic splines avoid cards and meet exact ports",
    );
    await page
      .getByRole("button", { name: "Select example", exact: true })
      .click();
    const editor = page
      .locator(
        '.goo-native[data-inspector-mode="properties"] input[data-input-slot$="/value"]',
      )
      .first();
    await editor.fill("Keep routing input");
    await editor.evaluate((el) => {
      window.routingEditor = el;
      el.setSelectionRange(2, 7);
    });
    actions.length = 0;
    await page
      .getByRole("button", { name: "Arrange", exact: true })
      .press("Enter");
    await page
      .locator(".layout-status")
      .filter({ hasText: "Layout saved." })
      .waitFor();
    await page.waitForFunction(
      (old) =>
        document.querySelector("goo-patch").installedScene.header.layoutRev !==
        old,
      original.header.layoutRev,
    );
    await routed();
    const arranged = await scene();
    checkRoutes(arranged);
    await writeFile(resolve(out, name + "-arranged-scene.json"), JSON.stringify(arranged, null, 2));
    assert.notDeepEqual(
      arranged.nodes.map((n) => n.rect),
      original.nodes.map((n) => n.rect),
    );
    const routes = actions.filter(routingProposal);
    assert.equal(routes.length, 1);
    const guides = routingProposal(routes[0]).routes;
    const guideLegs = guides.reduce((n, r) => n+r.points.length-1, 0);
    const curveSpans = arranged.connections.reduce((n, e) => n+e.segments[0].commands.length-1, 0);
    assert(curveSpans < guideLegs, "whole-cable fitting discards redundant routing knots");
    console.log(name, { guideLegs, curveSpans });
    assert.equal(actions.length, 2);
    const after = await state();
    for (const key of ["source", "revision", "ready", "published"])
      assert.deepEqual(after[key], initial[key], key);
    assert.equal(await editor.inputValue(), "Keep routing input");
    assert(await editor.evaluate((el) => el === window.routingEditor));
    assert.deepEqual(
      await editor.evaluate((el) => [el.selectionStart, el.selectionEnd]),
      [2, 7],
    );
    checks.push(
      "keyboard Arrange then one routing save; unchanged semantics and preserved native input/caret",
    );
    if (process.env.GEOMETRY_ONLY) {
      await page.reload();
      await ready();
      await routed();
      const restored = await scene();
      checkRoutes(restored);
      assert.deepEqual(restored.connections, arranged.connections);
      const extent = restored.extent;
      for (const edge of restored.connections)
        for (const c of edge.segments[0].commands)
          for (const p of [c.to, c.c1, c.c2].filter(Boolean)) {
            assert(
              p.x >= extent.x &&
                p.x <= extent.x + extent.width &&
                p.y >= extent.y &&
                p.y <= extent.y + extent.height,
              "Fit contains the full spline hull",
            );
          }
      assert.deepEqual(
        await page.evaluate(() => window.forbiddenMeasurements),
        [],
      );
      assert.deepEqual(errors, []);
      checks.push(
        "reload retains smooth splines; Fit contains control hulls; no geometry measurements or browser errors",
      );
      await page.screenshot({ path: resolve(out, name + ".png") });
      results.push({ engine: name, version: browser.version(), checks });
      continue;
    }
    const duplicate = await page.request.post(base + "/goo/act", {
      form: Object.fromEntries(new URLSearchParams(routes[0])),
    });
    assert.equal(duplicate.status(), 200);
    await page.reload();
    await ready();
    await routed();
    assert.deepEqual((await scene()).connections, arranged.connections);
    assert.deepEqual((await scene()).nodes, arranged.nodes);
    checks.push("duplicate receipt and browser reload retain saved routes");
    // Use the real bound action to submit a stale proposal, not a mocked domain response.
    const stale = { ...routingProposal(routes[0]), basis: "retired-basis" };
    const responsePromise = page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/goo/act",
    );
    await page.evaluate((proposal) => {
      const scope = document.querySelector(
          '.goo-native[data-inspector-mode="routing"]',
        ),
        input = scope.querySelector("input");
      input.value = JSON.stringify(proposal);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      scope.querySelector("button").click();
    }, stale);
    const rejected = await responsePromise;
    assert((await rejected.json()).error);
    await routed();
    assert.deepEqual((await scene()).connections, arranged.connections);
    checks.push(
      "server rejects stale routing basis without replacing the successful scene",
    );
    await page.locator('[data-workspace="library"]').click();
    await page
      .getByRole("checkbox", { name: "Show role cards", exact: true })
      .press("Space");
    await page.waitForFunction(
      () =>
        document.querySelector("goo-patch").installedScene.nodes.length === 3,
    );
    await routed();
    const filtered = await scene();
    checkRoutes(filtered);
    assert(!filtered.nodes.some((n) => n.key === "2"));
    await page
      .getByRole("checkbox", { name: "Show role cards", exact: true })
      .press("Space");
    await page.waitForFunction(
      () =>
        document.querySelector("goo-patch").installedScene.nodes.length === 4,
    );
    await routed();
    checkRoutes(await scene());
    await page.locator('[data-workspace="library"]').click();
    checks.push(
      "visibility projections reroute only live connections and restore identities",
    );
    // Hold only the optional CDN module. Cancellation must not submit geometry.
    let releaseDownload, sawDownload;
    const downloadGate = new Promise((resolve) => {
      releaseDownload = resolve;
    });
    const downloadSeen = new Promise((resolve) => {
      sawDownload = resolve;
    });
    const cdn = "https://cdn.jsdelivr.net/npm/libavoid-js@*/**";
    await page.context().route(cdn, async (route) => {
      sawDownload();
      await downloadGate;
      try {
        await route.continue();
      } catch {
        /* The cancelled worker owns this request. */
      }
    });
    await page
      .getByRole("button", { name: "Arrange", exact: true })
      .press("Enter");
    let downloadDeadline;
    await Promise.race([
      downloadSeen,
      new Promise((_, reject) => {
        downloadDeadline = setTimeout(
          () => reject(new Error("Routing worker did not request the CDN")),
          60000,
        );
      }),
    ]);
    clearTimeout(downloadDeadline);
    const beforeCancel = actions.filter(routingProposal).length;
    await page
      .getByRole("button", { name: "Cancel routing", exact: true })
      .press("Enter");
    await page
      .locator(".routing-status")
      .filter({ hasText: "Routing cancelled." })
      .waitFor();
    releaseDownload();
    await page.context().unroute(cdn);
    assert.equal(actions.filter(routingProposal).length, beforeCancel);
    assert(!(await scene()).header.layoutRev.endsWith(":spline-v3"));
    checks.push(
      "Cancel terminates an in-flight worker download without saving routes",
    );
    await page.context().route(cdn, (route) => route.abort());
    await page
      .getByRole("button", { name: "Route edges", exact: true })
      .press("Enter");
    await page
      .locator(".routing-status")
      .filter({ hasText: "Routing unavailable:" })
      .waitFor();
    assert(!(await scene()).header.layoutRev.endsWith(":spline-v3"));
    assert(await page.locator("goo-patch").evaluate((el) => el.editable));
    await page
      .context()
      .unroute("https://cdn.jsdelivr.net/npm/libavoid-js@*/**");
    await page.evaluate(() =>
      document.dispatchEvent(
        new CompositionEvent("compositionstart", {
          bubbles: true,
          data: "test",
        }),
      ),
    );
    const count = actions.length;
    await page
      .getByRole("button", { name: "Route edges", exact: true })
      .press("Enter");
    await page.waitForTimeout(500);
    assert.equal(actions.length, count);
    assert(!(await scene()).header.layoutRev.endsWith(":spline-v3"));
    await page.evaluate(() =>
      document.dispatchEvent(
        new CompositionEvent("compositionend", { bubbles: true, data: "test" }),
      ),
    );
    await routed();
    checkRoutes(await scene());
    checks.push(
      "CDN failure retains usable fallback; keyboard retry waits for synthetic composition end",
    );
    assert.deepEqual(
      await page.evaluate(() => window.forbiddenMeasurements),
      [],
    );
    assert.deepEqual(errors, []);
    checks.push("no card/port/label DOM geometry reads or browser errors");
    await page.screenshot({ path: resolve(out, name + ".png") });
    results.push({ engine: name, version: browser.version(), checks });
    console.log(name, JSON.stringify(checks));
  } catch (error) {
    console.error(name, error);
    await page.screenshot({ path: resolve(out, name + "-failure.png") });
    console.error(
      "STATUS",
      await page.locator(".routing-status").textContent({ timeout: 1000 }).catch(() => "not mounted"),
    );
    console.error("ERRORS", errors);
    throw error;
  } finally {
    await browser.close();
  }
}
await writeFile(
  resolve(out, "results.json"),
  JSON.stringify(results, null, 2) + "\n",
);
