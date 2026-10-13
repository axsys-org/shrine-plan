import { LIBAVOID_JS, LIBAVOID_WASM, routeScene } from "./routing.js";
self.onmessage = async ({ data }) => {
  try {
    const { AvoidLib } = await import(LIBAVOID_JS);
    await AvoidLib.load(LIBAVOID_WASM);
    self.postMessage({
      ok: true,
      proposal: routeScene(data, AvoidLib.getInstance()),
    });
  } catch (error) {
    self.postMessage({ ok: false, error: String(error?.message || error) });
  }
};
