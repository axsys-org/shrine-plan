// Target-local cases are distinct from sovereign epochs and shape counters.
// The runtime's /h contract has dense data cases 1..N for each target/care.
// Render only one five-case window; no namespace read occurs until a link opens.

const WINDOW = 5n;
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
