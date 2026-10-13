// Geometry only. libavoid gets copies of the server-resolved rectangles and ports.
export const LIBAVOID_VERSION = "0.5.0-beta.5";
export const LIBAVOID_JS = `https://cdn.jsdelivr.net/npm/libavoid-js@${LIBAVOID_VERSION}/dist/index.js`;
export const LIBAVOID_WASM = `https://cdn.jsdelivr.net/npm/libavoid-js@${LIBAVOID_VERSION}/dist/libavoid.wasm`;
export const ROUTED_SUFFIX = ":spline-v3";
export function routeScene(scene, A) {
  if (scene.nodes.length > 128 || scene.connections.length > 512)
    throw new Error("Routing graph exceeds its size bound.");
  const router = new A.Router(A.RouterFlag.OrthogonalRouting.value);
  const values = [],
    shapes = new Map(),
    connectors = [];
  const own = (value) => (values.push(value), value);
  const point = (x, y) => own(new A.Point(x, y));
  try {
    router.setRoutingParameter(A.RoutingParameter.shapeBufferDistance, 12);
    router.setRoutingParameter(A.RoutingParameter.segmentPenalty, 40);
    router.setRoutingParameter(A.RoutingParameter.idealNudgingDistance, 8);
    router.setRoutingOption(
      A.RoutingOption.nudgeOrthogonalSegmentsConnectedToShapes,
      false,
    );
    router.setRoutingOption(
      A.RoutingOption.nudgeSharedPathsWithCommonEndPoint,
      true,
    );
    for (const [i, node] of [...scene.nodes]
      .sort((a, b) => a.key.localeCompare(b.key))
      .entries()) {
      const r = node.rect;
      const rect = own(
        new A.Rectangle(point(r.x, r.y), point(r.x + r.width, r.y + r.height)),
      );
      const shape = new A.ShapeRef(router, rect, i + 1);
      const pins = new Map();
      for (const [j, port] of node.ports.entries()) {
        // libavoid ConnDirFlag bitmask: up=1, down=2, left=4, right=8.
        const n = port.outward;
        const direction = n.x > 0.5 ? 8 : n.x < -0.5 ? 4 : n.y > 0.5 ? 2 : 1;
        const pin = new A.ShapeConnectionPin(
          shape,
          j + 1,
          port.anchor.x,
          port.anchor.y,
          false,
          0,
          direction,
        );
        pin.setExclusive(false); // Multiple Grove relationships may share a reference socket.
        pins.set(port.key, j + 1);
      }
      shapes.set(node.key, { shape, pins });
    }
    for (const [i, edge] of [...scene.connections]
      .sort((a, b) => a.key.localeCompare(b.key))
      .entries()) {
      if (edge.endpoints.length !== 2)
        throw new Error("Playground routing requires two endpoints.");
      const end = (endpoint) => {
        const held = shapes.get(endpoint.port.node),
          pin = held?.pins.get(endpoint.port.port);
        if (!held || !pin) throw new Error("Routing endpoint is unavailable.");
        return own(new A.ConnEnd(held.shape, pin));
      };
      const connector = new A.ConnRef(
        router,
        end(edge.endpoints[0]),
        end(edge.endpoints[1]),
        scene.nodes.length + i + 1,
      );
      connector.setRoutingType(A.ConnType.ConnType_Orthogonal);
      connectors.push({ edge, connector });
    }
    router.processTransaction();
    let total = 0;
    const routes = connectors.map(({ edge, connector }) => {
      const line = connector.displayRoute(),
        points = [];
      for (let i = 0; i < line.size(); i++) {
        const p = line.at(i),
          q = { x: Math.round(p.x), y: Math.round(p.y) };
        p.delete();
        if (
          !Number.isFinite(q.x) ||
          !Number.isFinite(q.y) ||
          Math.abs(q.x) > 100000 ||
          Math.abs(q.y) > 100000
        )
          throw new Error("Route exceeds coordinate bounds.");
        if (
          !points.length ||
          q.x !== points.at(-1).x ||
          q.y !== points.at(-1).y
        )
          points.push(q);
      }
      line.delete();
      // Remove collinear intermediates after integer rounding.
      for (let i = 1; i < points.length - 1;) {
        const a = points[i - 1],
          b = points[i],
          c = points[i + 1];
        if (
          (a.x === b.x && b.x === c.x && (b.y - a.y) * (c.y - b.y) >= 0) ||
          (a.y === b.y && b.y === c.y && (b.x - a.x) * (c.x - b.x) >= 0)
        )
          points.splice(i, 1);
        else i++;
      }
      if (
        points.length < 2 ||
        points.length > 128 ||
        (total += points.length) > 8192
      )
        throw new Error("Route exceeds its bend bound.");
      return {
        key: edge.key,
        lifetime: edge.lifetime,
        topologyRef: edge.topologyRef,
        points,
      };
    });
    return {
      basis: scene.header.layoutRev.replace(/:(?:avoid-v1|spline-v2|spline-v3)$/, ""),
      routes,
    };
  } finally {
    // The router owns connectors, shapes, and pins. Value wrappers are separate copies.
    router.delete();
    for (const value of values.reverse()) value.delete();
  }
}
