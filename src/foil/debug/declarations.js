/** Clone only a namespace-authored template. No tag/layout fallback. */
export function declaredTemplate(name) {
  const template = document.getElementById('debug-template-' + name);
  if (!(template instanceof HTMLTemplateElement) || !template.content.firstElementChild) {
    throw new Error('Missing Grove debugger declaration: ' + name);
  }
  return template.content.firstElementChild.cloneNode(true);
}
