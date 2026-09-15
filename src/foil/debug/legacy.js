/** Compatibility-only factory. The native build erases the DOM constructor. */
export function legacyElement(tag) {
  if (!__DEBUG_LEGACY__) throw new Error('Legacy UI construction is disabled in the Grove debugger: ' + tag);
  return document.createElement(tag);
}
