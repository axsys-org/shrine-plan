import {legacyElement} from './legacy.js';
// Target-local cases are distinct from sovereign epochs and shape counters.
// The runtime's /h contract has dense data cases 1..N for each target/care.
// Render only one five-case window; no namespace read occurs until a link opens.
import {button, icon} from './icons.js';

const WINDOW = 5n;
const node = (tag, className = '', text = '') => {
  const element = legacyElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
};
function counter(value) {
  if (typeof value === 'number' && (!Number.isSafeInteger(value) || value < 0)) return null;
  return /^(0|[1-9][0-9]*)$/.test(String(value)) ? String(value) : null;
}
function casePath(path, care, number) {
  const segments = path.split('/').filter(Boolean);
  return '/h/' + care + '/' + number + '/' + segments.length + (segments.length ? '/' + segments.join('/') : '');
}

const boundInspectors = new WeakSet();
/** Bind exact navigation state to Grove's case-window declaration. */
export function bindCaseInspector(panel, {navigate}) {
  if (boundInspectors.has(panel)) return;
  boundInspectors.add(panel);
  for (const item of panel.querySelectorAll('[data-case-total]')) {
    const raw = counter(item.dataset.caseTotal);
    if (raw === null || BigInt(raw) <= WINDOW) continue;
    const total = BigInt(raw), path = panel.dataset.path, care = item.dataset.care;
    let end = total;
    const links = item.querySelector('.wb-case-links');
    const template = item.querySelector('template[data-case-link]');
    const older = item.querySelector('[data-case-older]');
    const newer = item.querySelector('[data-case-newer]');
    const range = item.querySelector('.wb-case-range');
    const form = item.querySelector('.wb-case-jump');
    const input = form.querySelector('input'), group = form.querySelector('ui-input-group');
    const render = () => {
      const start = end > WINDOW ? end - WINDOW + 1n : 1n;
      const rows = [];
      for (let index = start; index <= end; index++) {
        const row = template.content.firstElementChild.cloneNode(true);
        row.href = '/debug' + casePath(path, care, index);
        row.textContent = String(index);
        row.setAttribute('aria-label', care + ' case ' + index + ' of ' + path);
        row.toggleAttribute('data-latest', index === total);
        rows.push(row);
      }
      links.replaceChildren(...rows);
      older.disabled = start === 1n; newer.disabled = end === total;
      range.textContent = start + '–' + end + ' of ' + total;
    };
    older.addEventListener('click', () => { end -= WINDOW; render(); });
    newer.addEventListener('click', () => { end = end + WINDOW > total ? total : end + WINDOW; render(); });
    input.addEventListener('input', () => { input.setCustomValidity(''); input.removeAttribute('aria-invalid'); group.invalid = false; });
    input.addEventListener('invalid', () => { input.setAttribute('aria-invalid', 'true'); group.invalid = true; });
    form.addEventListener('submit', event => {
      event.preventDefault(); event.stopPropagation();
      if (!/^[1-9][0-9]*$/.test(input.value) || BigInt(input.value) > total) {
        input.setCustomValidity('Enter a case from 1 to ' + total + '.'); input.reportValidity(); return;
      }
      navigate(casePath(path, care, input.value));
    });
  }
}

export function caseInspector(view, {link, navigate}) {
  const section = node('section', 'wb-cases');
  section.setAttribute('aria-label', 'Cases and version');
  const title = node('h2', 'wb-section-title', 'Cases');
  section.append(title);
  const accordion = node('ui-accordion');
  accordion.setAttribute('mode', 'multiple');
  accordion.setAttribute('variant', 'quiet');
  accordion.setAttribute('size', 'compact');
  for (const care of ['x', 'y', 'z']) {
    const data = counter(view.version?.[care + '_data']);
    const shape = counter(view.version?.[care + '_shape']);
    const item = node('ui-accordion-item');
    item.dataset.care = care;
    item.setAttribute('value', care);
    item.setAttribute('title', care + ' cases');
    item.setAttribute('heading-level', '3');
    item.setAttribute('open', '');
    const suffix = node('span', 'wb-case-counters', (data ?? '—') + ' data · ' + (shape ?? '—') + ' shape');
    suffix.slot = 'suffix';
    suffix.title = '/' + care + '_data: ' + (data ?? 'not reported') + '; /' + care + '_shape: ' + (shape ?? 'not reported');
    const disclosure = icon('chevron'); disclosure.slot = 'disclosure';
    item.append(disclosure, suffix);
    accordion.append(item);
    if (data === null || data === '0') {
      item.append(node('p', 'wb-context-note', data === null ? 'Not reported.' : 'No cases.'));
      continue;
    }
    const total = BigInt(data);
    let end = total;
    const links = node('nav', 'wb-case-links');
    links.setAttribute('aria-label', care + ' case history');
    const pager = node('div', 'wb-case-pager');
    const range = node('span', 'wb-case-range');
    range.setAttribute('role', 'status');
    const older = button('Older ' + care + ' cases', 'back', () => { end -= WINDOW; render(); });
    const newer = button('Newer ' + care + ' cases', 'forward', () => { end = end + WINDOW > total ? total : end + WINDOW; render(); });
    pager.append(older, range, newer);
    function render() {
      const start = end > WINDOW ? end - WINDOW + 1n : 1n;
      links.replaceChildren();
      for (let index = start; index <= end; index++) {
        const anchor = link(casePath(view.path, care, index), String(index), 'wb-case-link');
        anchor.setAttribute('aria-label', care + ' case ' + index + ' of ' + view.path);
        if (index === total) {
          anchor.dataset.latest = 'true';
          anchor.title = 'Latest ' + care + ' data case';
        }
        links.append(anchor);
      }
      older.disabled = start === 1n;
      newer.disabled = end === total;
      range.textContent = start + '–' + end + ' of ' + total;
    }
    item.append(links);
    if (total > WINDOW) {
      const form = node('form', 'wb-case-jump');
      form.dataset.debugNavigation = 'case';
      const group = node('ui-input-group');
      group.setAttribute('size', 'small');
      group.setAttribute('typography', 'code');
      group.setAttribute('touch-target', '');
      const input = node('input');
      input.slot = 'control'; input.type = 'text'; input.inputMode = 'numeric';
      // An untouched navigation input is not an error. Empty input is checked
      // when submitted; Mash can then expose its native custom validity.
      input.pattern = '[1-9][0-9]*'; input.placeholder = 'Case number';
      input.setAttribute('aria-label', 'Open ' + care + ' case');
      input.addEventListener('input', () => {
        input.setCustomValidity(''); input.removeAttribute('aria-invalid'); group.invalid = false;
      });
      input.addEventListener('invalid', () => { input.setAttribute('aria-invalid', 'true'); group.invalid = true; });
      const submit = button('Open ' + care + ' case', 'arrow');
      submit.setAttribute('type', 'submit');
      group.append(input); form.append(group, submit);
      form.addEventListener('submit', event => {
        event.preventDefault();
        // This is navigation, never an operation handled by the document form listener.
        event.stopPropagation();
        const value = input.value;
        if (!/^[1-9][0-9]*$/.test(value) || BigInt(value) > total) {
          input.setCustomValidity('Enter a case from 1 to ' + total + '.');
          input.reportValidity(); return;
        }
        navigate(casePath(view.path, care, value));
      });
      item.append(pager, form);
    }
    render();
  }
  section.append(accordion);
  const version = node('section', 'wb-version');
  version.setAttribute('aria-label', 'Version metadata');
  version.append(node('h2', 'wb-section-title', 'Version'));
  for (const name of ['state', 'first', 'now', 'block', 'top']) {
    if (view.version?.[name] === undefined) continue;
    const row = node('div', 'wb-meta-row');
    row.append(node('code', '', '/' + name), node('code', '', String(view.version[name])));
    version.append(row);
  }
  if (version.children.length === 1) version.append(node('p', 'wb-context-note', 'Version metadata not reported.'));
  section.append(version);
  return section;
}
