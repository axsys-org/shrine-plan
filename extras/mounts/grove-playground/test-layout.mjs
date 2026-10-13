import { test } from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { createLayout } from "./layout.js";
if (!process.env.D3_FORCE_MODULE)
  throw new Error(
    "Set D3_FORCE_MODULE to the verified d3-force@3.0.0 ESM bundle.",
  );
const d3 = await import(pathToFileURL(process.env.D3_FORCE_MODULE));
function scene(count) {
  return {
    nodes: Array.from({ length: count }, (_, i) => ({
      key: String(i),
      lifetime: "node:" + i,
      rect: {
        x: 40,
        y: 40,
        width: 240 + (i % 3) * 40,
        height: 208 + (i % 5) * 10,
      },
    })),
    connections: Array.from({ length: Math.max(0, count - 1) }, (_, i) => ({
      endpoints: [
        { port: { node: String(i) } },
        { port: { node: String(i + 1) } },
      ],
    })),
  };
}
function run(input) {
  const layout = createLayout(input, d3);
  while (!layout.done) layout.step();
  return layout.finish();
}
for (const count of [1, 5, 32, 128])
  test(`bounded layout for ${count} overlapping rectangles`, () => {
    const input = scene(count),
      before = structuredClone(input),
      positions = run(input);
    assert.deepEqual(input, before);
    assert.equal(positions.length, count);
    const byId = new Map(input.nodes.map((node) => [node.key, node]));
    for (let i = 0; i < count; i++) {
      const a = positions[i],
        ar = byId.get(a.target.node).rect;
      assert(
        Number.isSafeInteger(a.origin.x) &&
          a.origin.x >= 0 &&
          a.origin.x <= 100000,
      );
      assert(
        Number.isSafeInteger(a.origin.y) &&
          a.origin.y >= 0 &&
          a.origin.y <= 100000,
      );
      for (let j = i + 1; j < count; j++) {
        const b = positions[j],
          br = byId.get(b.target.node).rect;
        assert(
          a.origin.x + ar.width <= b.origin.x ||
            b.origin.x + br.width <= a.origin.x ||
            a.origin.y + ar.height <= b.origin.y ||
            b.origin.y + br.height <= a.origin.y,
          `overlap ${a.target.node}/${b.target.node}`,
        );
      }
    }
  });
test("same snapshot produces repeatable positions", () =>
  assert.deepEqual(run(scene(12)), run(scene(12))));
test("empty and over-limit scenes fail without a simulation", () => {
  assert.throws(() => createLayout(scene(0), d3));
  assert.throws(() => createLayout(scene(129), d3));
});
