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

export function button(label, glyph, action, text = '') {
  const button = declaredTemplate('button');
  button.setAttribute('size', text ? 'small' : 'compact');
  button.setAttribute('aria-label', label);
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
