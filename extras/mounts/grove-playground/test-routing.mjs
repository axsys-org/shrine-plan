import assert from "node:assert/strict";
import test from "node:test";
import { pathToFileURL } from "node:url";
import { routeScene } from "./routing.js";
// Use the actual pinned npm package, not a stand-in router.
const { AvoidLib } = await import(pathToFileURL(process.env.LIBAVOID_MODULE));
await AvoidLib.load(process.env.LIBAVOID_WASM);
const A = AvoidLib.getInstance();
const node = (key, x, y) => ({
  key,
  lifetime: "n:" + key,
  rect: { x, y, width: 240, height: 208 },
  ports: [
    { key: "ref", anchor: { x: 0, y: 40 }, outward: { x: -1, y: 0 } },
    { key: "out", anchor: { x: 240, y: 80 }, outward: { x: 1, y: 0 } },
  ],
});
const edge = (key, from, to) => ({
  key,
  lifetime: "e:" + key,
  topologyRef: "t:" + key,
  endpoints: [
    { port: { node: from, port: "out" } },
    { port: { node: to, port: "ref" } },
  ],
});
const scene = {
  header: { layoutRev: "test" },
  nodes: [node("a", 40, 40), node("b", 700, 40), node("obstacle", 370, 0)],
  connections: [edge("edge", "a", "b")],
};
function valid(scene, proposal) {
  for (const route of proposal.routes) {
    const e = scene.connections.find((e) => e.key === route.key),
      p = route.points;
    assert.equal(route.topologyRef, e.topologyRef);
    assert.equal(route.lifetime, e.lifetime);
    e.endpoints.forEach((ep, i) => {
      const n = scene.nodes.find((n) => n.key === ep.port.node),
        port = n.ports.find((p) => p.key === ep.port.port);
      assert.deepEqual(p.at(i ? -1 : 0), {
        x: n.rect.x + port.anchor.x,
        y: n.rect.y + port.anchor.y,
      });
    });
    assert(p[1].x - p[0].x >= 12);
    assert(p.at(-1).x - p.at(-2).x >= 12);
    for (let i = 1; i < p.length; i++) {
      const a = p[i - 1],
        b = p[i];
      assert(a.x === b.x || a.y === b.y);
      assert.notDeepEqual(a, b);
      for (const n of scene.nodes) {
        if (
          (i === 1 && n.key === e.endpoints[0].port.node) ||
          (i === p.length - 1 && n.key === e.endpoints[1].port.node)
        )
          continue;
        const r = n.rect,
          x = r.x - 12,
          y = r.y - 12,
          w = r.width + 24,
          h = r.height + 24;
        const hit =
          a.y === b.y
            ? a.y > y &&
              a.y < y + h &&
              Math.max(a.x, b.x) > x &&
              Math.min(a.x, b.x) < x + w
            : a.x > x &&
              a.x < x + w &&
              Math.max(a.y, b.y) > y &&
              Math.min(a.y, b.y) < y + h;
        assert(!hit, `route ${route.key} crosses ${n.key}`);
      }
    }
  }
}
test("actual WASM avoids an intervening card with signed coordinates", () => {
  const result = routeScene(scene, A);
  valid(scene, result);
  assert(result.routes[0].points.some((p) => p.y < 0));
});
test("backward connections leave and enter their specified port sides", () => {
  const s = { ...scene, connections: [edge("back", "b", "a")] };
  valid(s, routeScene(s, A));
});
test("shared pins and parallel connections are routed", () => {
  const s = {
    ...scene,
    connections: [
      edge("one", "a", "b"),
      edge("two", "a", "b"),
      edge("three", "b", "a"),
    ],
  };
  valid(s, routeScene(s, A));
});
test("input order does not change routing and server snapshots remain immutable", () => {
  const before = JSON.stringify(scene),
    r = routeScene(scene, A);
  assert.deepEqual(
    routeScene({ ...scene, nodes: [...scene.nodes].reverse() }, A),
    r,
  );
  assert.equal(JSON.stringify(scene), before);
});
test("repeated router cleanup and bounded populations", () => {
  for (let i = 0; i < 10; i++) valid(scene, routeScene(scene, A));
  assert.throws(
    () => routeScene({ ...scene, nodes: Array(129).fill(scene.nodes[0]) }, A),
    /size bound/,
  );
  assert.throws(
    () =>
      routeScene(
        { ...scene, connections: Array(513).fill(scene.connections[0]) },
        A,
      ),
    /size bound/,
  );
});
test("missing endpoint fails without mutating the graph", () => {
  assert.throws(
    () =>
      routeScene({ ...scene, connections: [edge("bad", "a", "missing")] }, A),
    /unavailable/,
  );
  valid(scene, routeScene(scene, A));
});

test("saved route versions are normalized when upgrading to splines", () => {
  for (const suffix of [":avoid-v1", ":spline-v2", ":spline-v3"]) {
    const upgraded = routeScene(
      { ...scene, header: { layoutRev: "test" + suffix } },
      A,
    );
    assert.equal(upgraded.basis, "test");
    valid(scene, upgraded);
  }
});

test("signed card geometry and endpoints route across both zero axes", () => {
  const shifted = { ...scene, nodes: scene.nodes.map((n) => ({ ...n,
    rect: { ...n.rect, x: n.rect.x - 800, y: n.rect.y - 400 } })) };
  const proposal = routeScene(shifted, A);
  valid(shifted, proposal);
  assert(proposal.routes[0].points.some((p) => p.x < 0 && p.y < 0));
});
