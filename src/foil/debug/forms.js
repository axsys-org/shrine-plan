import {legacyElement} from './legacy.js';
// Sew server-authored controls into Mash without replacing their form/value
// owners. This module adds presentation only: no listeners, submission, data
// coercion or generated explanation. Repeated enhancement is a no-op.
const textInputs = new Set(['text', 'search', 'email', 'password', 'tel', 'url', 'number']);

function editing(control) {
  return control.matches(':focus-within') || control.getRootNode().activeElement === control;
}

function ownsVisibleLabel(control) {
  if (control.closest('ui-field, ui-input-group, label') || control.hasAttribute('slot') ||
      control.hasAttribute('aria-labelledby') || control.hasAttribute('aria-describedby') ||
      control.hasAttribute('aria-description')) return true;
  return [...control.getRootNode().querySelectorAll('label')].some(label =>
    label.control === control || (control.id && label.htmlFor === control.id));
}

export function enhanceForms(section) {
  if (!__DEBUG_LEGACY__) return; // Native forms are wholly declared by Grove/Mash.
  for (const form of section?.querySelectorAll('form') || []) {
    // Explicit control sizes and authored contexts remain authoritative.
    form.dataset.mashSize ||= 'small';
    for (const control of form.querySelectorAll('ui-button, ui-input, ui-input-group')) {
      control.setAttribute('touch-target', '');
    }
    for (const input of form.querySelectorAll('ui-input')) {
      const label = input.getAttribute('label');
      if (!label?.trim() || ownsVisibleLabel(input) || editing(input)) continue;
      const field = legacyElement('ui-field');
      field.setAttribute('label', label);
      // UIField owns required propagation. Configure before connection so it
      // cannot erase native validation, including before custom-element upgrade.
      field.toggleAttribute('required', 'required' in input ? input.required : input.hasAttribute('required'));
      field.dataset.debugFormField = '';
      input.before(field);
      input.setAttribute('slot', 'control');
      field.append(input);
    }
    for (const input of form.querySelectorAll('input')) {
      if (!textInputs.has(input.type) || input.hasAttribute('slot') ||
          input.closest('ui-field, ui-input-group') || editing(input)) continue;
      // Grove's native label and input keep their relationship, node identity,
      // values, hidden siblings and form ownership. Do not put a native group
      // inside UIField: that composition does not currently forward its label.
      const group = legacyElement('ui-input-group');
      group.setAttribute('typography', 'code');
      group.setAttribute('touch-target', '');
      group.dataset.debugFormNative = '';
      input.before(group);
      input.setAttribute('slot', 'control');
      group.append(input);
    }
  }
}
