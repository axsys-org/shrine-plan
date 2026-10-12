// Optional placement assistant. Input geometry comes from SceneSnapshot, never DOM measurement.
export const ENGINE_URL =
  "https://esm.sh/d3-force@3.0.0/es2022/d3-force.bundle.mjs";
let engine;
export function loadEngine() {
  return (engine ||= import(ENGINE_URL).catch((error) => {
    engine = undefined;
    throw error;
  }));
}
const GAP = 48;
const overlaps = (a, b) =>
  Math.abs(a.x - b.x) < (a.width + b.width) / 2 + GAP &&
  Math.abs(a.y - b.y) < (a.height + b.height) / 2 + GAP;

export function createLayout(scene, d3) {
  // D3 mutates its inputs: never give it authoritative scene records.
  const nodes = scene.nodes
    .map((node) => ({
      id: node.key,
      target: { kind: "node", node: node.key, lifetime: node.lifetime },
      width: node.rect.width,
      height: node.rect.height,
      x: node.rect.x + node.rect.width / 2,
      y: node.rect.y + node.rect.height / 2,
      vx: 0,
      vy: 0,
    }))
    .sort((a, b) => a.id.localeCompare(b.id));
  if (!nodes.length || nodes.length > 128)
    throw new Error("Arrange supports 1–128 visible cards.");
  const ids = new Set(nodes.map((node) => node.id));
  const links = scene.connections.flatMap((edge) => {
    const a = edge.endpoints[0]?.port.node;
    return edge.endpoints.slice(1).flatMap((endpoint) => {
      const b = endpoint.port.node;
      return a && a !== b && ids.has(a) && ids.has(b)
        ? [{ source: a, target: b }]
        : [];
    });
  });
  const cx = nodes.reduce((sum, n) => sum + n.x, 0) / nodes.length;
  const cy = nodes.reduce((sum, n) => sum + n.y, 0) / nodes.length;
  // Rectangle collisions use supplied widths/heights, including a readable gutter.
  function rectangles() {
    for (let i = 0; i < nodes.length; i++)
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i],
          b = nodes[j];
        const dx = b.x + b.vx - (a.x + a.vx),
          dy = b.y + b.vy - (a.y + a.vy);
        const ox = (a.width + b.width) / 2 + GAP - Math.abs(dx),
          oy = (a.height + b.height) / 2 + GAP - Math.abs(dy);
        if (ox <= 0 || oy <= 0) continue;
        if (ox < oy) {
          const push = (dx < 0 ? -1 : 1) * ox * 0.45;
          a.vx -= push;
          b.vx += push;
        } else {
          const push = (dy < 0 ? -1 : 1) * oy * 0.45;
          a.vy -= push;
          b.vy += push;
        }
      }
  }
  const simulation = d3
    .forceSimulation(nodes)
    .stop()
    .force(
      "links",
      d3
        .forceLink(links)
        .id((n) => n.id)
        .distance((link) => (link.source.width + link.target.width) / 2 + 150)
        .strength(0.16),
    )
    .force("charge", d3.forceManyBody().strength(-1100))
    .force("x", d3.forceX(cx).strength(0.012))
    .force("y", d3.forceY(cy).strength(0.018))
    .force("rectangles", rectangles)
    .velocityDecay(0.45)
    .alphaDecay(1 - Math.pow(0.001, 1 / 180));
  let ticks = 0;
  function positions() {
    const minX = Math.min(...nodes.map((n) => n.x - n.width / 2));
    const minY = Math.min(...nodes.map((n) => n.y - n.height / 2));
    const dx = Math.max(0, 40 - minX),
      dy = Math.max(0, 40 - minY);
    return nodes.map((n) => {
      const x = Math.round(n.x - n.width / 2 + dx),
        y = Math.round(n.y - n.height / 2 + dy);
      if (
        !Number.isFinite(x) ||
        !Number.isFinite(y) ||
        x < 0 ||
        y < 0 ||
        x > 100000 ||
        y > 100000
      )
        throw new Error("Calculated layout exceeds the playground bounds.");
      return { target: n.target, origin: { x, y } };
    });
  }
  return {
    step(count = 2) {
      simulation.tick(Math.min(count, 180 - ticks));
      ticks = Math.min(180, ticks + count);
      return positions();
    },
    get done() {
      return ticks >= 180;
    },
    finish() {
      // Deterministic final clearance handles any residual overlap after the bounded simulation.
      for (let i = 1; i < nodes.length; i++) {
        const node = nodes[i],
          prior = nodes.slice(0, i);
        let attempts = 0,
          hit;
        while (
          (hit = prior.find((other) => overlaps(node, other))) &&
          attempts++ < nodes.length * 4
        ) {
          const dx = node.x - hit.x,
            dy = node.y - hit.y;
          const ox = (node.width + hit.width) / 2 + GAP - Math.abs(dx) + 2;
          const oy = (node.height + hit.height) / 2 + GAP - Math.abs(dy) + 2;
          if (ox < oy) node.x += (dx < 0 ? -1 : 1) * ox;
          else node.y += (dy < 0 ? -1 : 1) * oy;
        }
        if (prior.some((other) => overlaps(node, other)))
          node.x =
            Math.max(...prior.map((other) => other.x + other.width / 2)) +
            GAP +
            node.width / 2 +
            2;
      }
      simulation.stop();
      return positions();
    },
    stop() {
      simulation.stop();
    },
  };
}

export function abortable(promise, signal, timeout = 15000) {
  return new Promise((resolve, reject) => {
    const abort = () => finish(reject, new Error("Arrangement cancelled."));
    const timer = setTimeout(
      () =>
        finish(
          reject,
          new Error("Layout engine did not load. Try Arrange again."),
        ),
      timeout,
    );
    function finish(fn, value) {
      clearTimeout(timer);
      signal.removeEventListener("abort", abort);
      fn(value);
    }
    if (signal.aborted) {
      abort();
      return;
    }
    signal.addEventListener("abort", abort, { once: true });
    promise.then(
      (value) => finish(resolve, value),
      (error) => finish(reject, error),
    );
  });
}
