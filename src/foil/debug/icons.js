// Application intent mapped to Mash's existing semantic icon registry.
// No application SVG overrides or external icon sources are installed.
import {declaredTemplate} from './declarations.js';
export const iconNames = Object.freeze({
  record: 'object.document',
  subtree: 'object.layers',
  history: 'object.clock',
  activity: 'object.terminal',
  sidebar: 'navigation.panel-left',
  roots: 'object.folder',
  inspector: 'navigation.panel-right',
  inspect: 'object.code',
  bookmark: 'object.bookmark',
  branch: 'object.tree',
  run: 'action.play',
  live: 'action.refresh',
  arrow: 'navigation.forward',
  close: 'action.dismiss',
  search: 'action.search',
  clock: 'object.clock',
  chevron: 'navigation.disclosure',
  back: 'navigation.chevron-left',
  forward: 'navigation.disclosure',
  edit: 'action.edit',
  more: 'navigation.more.horizontal',
  settings: 'action.settings',
  error: 'status.error',
  warning: 'status.warning',
});

export function icon(name) {
  const sourceName = iconNames[name];
  if (!sourceName) throw new TypeError('Unknown debugger icon: ' + name);
  const element = declaredTemplate('icon');
  element.classList.add('wb-icon');
  element.setAttribute('name', sourceName);
  element.setAttribute('size', 'small');
  element.setAttribute('aria-hidden', 'true');
  element.dataset.iconSource = 'Mash';
  return element;
}

export function button(label, glyph, action, text = '') {
  const authored = declaredTemplate('button');
  const button = authored;
  button.setAttribute('type', 'button');
  button.setAttribute('size', text ? 'small' : 'compact');
  button.setAttribute('variant', 'ghost');
  button.setAttribute('tone', 'neutral');
  button.setAttribute('aria-label', label);
  // Empty title blocks inherited native hints; icon help belongs to ui-tooltip.
  button.title = '';
  button.className = text ? 'wb-button' : 'wb-icon-button';
  if (!text) button.setAttribute('icon-only', '');
  else { button.removeAttribute('icon-only'); button.setAttribute('touch-target', ''); }
  const prefix = button.querySelector('ui-icon');
  prefix.setAttribute('name', iconNames[glyph]);
  if (text) prefix.slot = 'prefix';

  if (text) { const span = button.querySelector('span'); span.hidden = false; span.textContent = text;  }
  if (action) button.addEventListener('click', action);
  return button;
}
