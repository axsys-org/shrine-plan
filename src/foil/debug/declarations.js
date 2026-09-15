/** Clone only a namespace-authored template. No tag/layout fallback in v1. */
export const LEGACY_UI = typeof __DEBUG_LEGACY__ !== 'undefined' && __DEBUG_LEGACY__;
export function isDeclared() {
  return !LEGACY_UI || Boolean(document.querySelector('[data-grove-contract="debugger/v1"]'));
}
export function declaredTemplate(name) {
  if (!isDeclared()) return null;
  const template = document.getElementById('debug-template-' + name);
  if (!(template instanceof HTMLTemplateElement) || !template.content.firstElementChild) {
    throw new Error('Missing Grove debugger declaration: ' + name);
  }
  return template.content.firstElementChild.cloneNode(true);
}
