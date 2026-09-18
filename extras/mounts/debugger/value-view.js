import {button} from './icons.js';
import {declaredTemplate} from './declarations.js';
import {VALUE_WINDOW_BYTES, valueWindowURL, parseValueChunk, renderValueWindow} from './values.js';

const openValues = new Set();
const pending = [];
let active = 0;
const MAX_RESPONSE_BYTES = 196608;
const decimalLabel = value => BigInt(value).toLocaleString('en-US');

// Exact reads have no eager prefetch or retained full-value cache. A user's
// explicit reads share two slots; cancelling a queued read removes it at once.
function pump() {
  while (active < 2 && pending.length) {
    const item = pending.shift();
    item.signal.removeEventListener('abort', item.cancel);
    if (item.signal.aborted) { item.reject(item.signal.reason); continue; }
    active++;
    readChunk(item.request, item.signal).then(item.resolve, item.reject).finally(() => { active--; pump(); });
  }
}
function enqueue(request, signal) {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted();
    const item = {request, signal, resolve, reject};
    item.cancel = () => {
      const index = pending.indexOf(item);
      if (index !== -1) pending.splice(index, 1);
      reject(signal.reason);
    };
    signal.addEventListener('abort', item.cancel, {once: true});
    pending.push(item); pump();
  });
}
async function readChunk(request, signal) {
  const response = await fetch(request.url, {signal, redirect: 'error', cache: 'no-store', credentials: 'same-origin',
    headers: {Accept: 'application/json'}});
  if (!response.ok) {
    const reasons = {404: 'This version or slot is no longer available.', 409: 'This version is not available yet.',
      410: 'The record is deleted at this version.', 416: 'This byte window is unavailable.',
      422: 'The runtime cannot inspect this representation.'};
    await response.body?.cancel().catch(() => {});
    throw new Error(reasons[response.status] || 'The runtime could not read this value.');
  }
  if (!/^application\/json(?:\s*;|$)/i.test(response.headers.get('content-type') || '')) {
    await response.body?.cancel().catch(() => {});
    throw new Error('The runtime did not return value data.');
  }
  const reader = response.body?.getReader();
  if (!reader) throw new Error('The runtime returned no value data.');
  let length = 0;
  const chunks = [];
  try {
    while (true) {
      signal.throwIfAborted();
      const result = await reader.read();
      if (result.done) break;
      length += result.value.length;
      if (length > MAX_RESPONSE_BYTES) throw new Error('The runtime exceeded the bounded value response.');
      chunks.push(result.value);
    }
  } catch (error) { await reader.cancel().catch(() => {}); throw error; }
  finally { reader.releaseLock(); }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  let json;
  try { json = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes)); }
  catch { throw new Error('The runtime returned invalid value data.'); }
  return parseValueChunk(json, request);
}

export function cancelValueInspections(scope = null) {
  for (const view of [...openValues]) if (!scope || scope.contains(view.pail)) view.close(false);
}
const removalObserver = new MutationObserver(() => {
  for (const view of [...openValues]) if (!view.pail.isConnected) view.close(false);
});
document.addEventListener('debug:navigation-start', () => cancelValueInspections());

function summary(metadata) {
  if (!metadata || metadata.state === 'unknown') return 'Completeness unknown';
  if (metadata.state === 'complete') return 'Complete' + (metadata.bytes !== null ? ' · ' + decimalLabel(metadata.bytes) + ' bytes' : '');
  if (metadata.state === 'opaque') return 'Summary · exact inspection unavailable';
  if (metadata.reason === 'byte-limit' && metadata.previewBytes !== null && metadata.bytes !== null) {
    return 'Preview · first ' + decimalLabel(metadata.previewBytes) + ' of ' + decimalLabel(metadata.bytes) + ' bytes';
  }
  if (metadata.reason === 'numeric-summary') return 'Numeric summary' + (metadata.bytes !== null ? ' · ' + decimalLabel(metadata.bytes) + ' bytes' : '');
  if (metadata.reason === 'non-text-bytes') return 'Non-text bytes' + (metadata.bytes !== null ? ' · ' + decimalLabel(metadata.bytes) + ' bytes' : '');
  return 'Preview · exact inspection ' + (metadata.url ? 'available' : 'unavailable');
}

/** Namespace read orchestration stays here; sh-pail owns the reusable value,
 * status and action anatomy. A read never replaces the original preview. */
const boundValues = new WeakSet();
export function attachValueInspection(pail, slot, {unknownContext = null} = {}) {
  if (!pail || boundValues.has(pail)) return;
  boundValues.add(pail);
  const metadata = slot.fidelity;
  pail.dataset.valueState = metadata?.state || 'unknown';
  if ((!metadata || metadata.state === 'unknown') && unknownContext instanceof Element &&
      unknownContext.ownerDocument === pail.ownerDocument && unknownContext.id && unknownContext.textContent.trim()) {
    // The note and pail share the document's light DOM. This is a static,
    // explicitly scoped description, not a cross-shadow ID or fidelity claim.
    pail.setAttribute('aria-describedby', unknownContext.id);
    return;
  }
  const status = declaredTemplate('value-status');
  status.slot = 'status'; status.className = 'wb-value-status';
  status.textContent = summary(metadata);
  if (!metadata || metadata.state === 'unknown') status.title = 'This runtime does not report whether its displayed value is complete.';
  pail.append(status);
  if (!metadata?.url) return;

  let controller = null, generation = 0, window = null, opened = false, recordEpoch = null;
  const declaredArea = declaredTemplate('value-window');
  const area = declaredArea;
  area.className = 'wb-full-value wb-code-scroll mash-scroll-quiet';
  area.setAttribute('orientation', 'vertical'); area.setAttribute('mode', 'scrolling');
  area.setAttribute('size', 'medium');
  area.setAttribute('label', 'Exact value bytes for ' + slot.key);
  area.style.setProperty('--wb-code-limit', '18rem');
  const pre = area.querySelector('pre');
  const inspect = button('Inspect value', 'inspect', () => load('0', inspect), 'Inspect value');
  const earlier = button('Earlier bytes', 'back', () => load(String(BigInt(window.start) > VALUE_WINDOW_BYTES ? BigInt(window.start) - VALUE_WINDOW_BYTES : 0n), earlier), 'Earlier');
  const next = button('Next bytes', 'forward', () => load(window.end, next), 'Next');
  const closeButton = button('Close value', 'close', () => close(true), 'Close');
  earlier.hidden = next.hidden = closeButton.hidden = true;
  for (const control of [inspect, earlier, next, closeButton]) {
    // Do not inherit the workbench's older text-button geometry override.
    // Mash's pail/action recipe owns compact type, wrapping and touch targets.
    control.classList.remove('wb-button');
    control.slot = 'actions'; pail.append(control);
  }
  const view = {pail, close};

  async function close(restoreFocus) {
    generation++; controller?.abort(); controller = null; opened = false; window = null; recordEpoch = null;
    const run = generation;
    area.remove(); pre.textContent = '';
    earlier.hidden = next.hidden = closeButton.hidden = true;
    inspect.hidden = false; inspect.disabled = false;
    status.textContent = summary(metadata); delete status.dataset.failed;
    openValues.delete(view);
    if (!openValues.size) removalObserver.disconnect();
    if (restoreFocus) {
      await inspect.updateComplete;
      if (run === generation && pail.isConnected) inspect.focus();
    }
  }
  function controls(loading) {
    inspect.hidden = Boolean(window);
    inspect.disabled = loading;
    earlier.hidden = next.hidden = !window;
    earlier.disabled = loading || !window || window.start === '0';
    next.disabled = loading || !window || window.end === metadata.bytes;
    closeButton.hidden = !opened;
  }
  async function load(start, origin) {
    if (controller) return;
    const focused = document.activeElement === origin;
    const run = ++generation;
    controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(20000)]);
    opened = true; openValues.add(view);
    removalObserver.observe(document.body, {childList: true, subtree: true});
    status.textContent = 'Reading value bytes…'; delete status.dataset.failed; controls(true);
    try {
      const request = valueWindowURL(metadata, start);
      const chunk = await enqueue(request, signal);
      signal.throwIfAborted();
      if (run !== generation || !pail.isConnected) return;
      if (recordEpoch !== null && recordEpoch !== chunk.recordEpoch) throw new Error('The value assertion changed between byte windows.');
      recordEpoch = chunk.recordEpoch;
      const result = renderValueWindow(chunk, request);
      window = result;
      pre.textContent = result.text;
      area.dataset.format = result.format;
      if (!area.isConnected) pail.insertBefore(area, status);
      const position = metadata.bytes === '0' ? (metadata.representation === 'natural-le-bytes' ? 'Zero · 0 bytes' : 'Empty text · 0 bytes') :
        'Bytes ' + decimalLabel(result.start) + '–' + decimalLabel(String(BigInt(result.end) - 1n)) + ' of ' + decimalLabel(metadata.bytes);
      status.textContent = position + ' · ' + (result.format === 'utf8' ? 'UTF-8' : metadata.representation === 'natural-le-bytes' ? 'Hex · little-endian natural' : 'Hex · non-text bytes');
      status.title = 'Version ' + metadata.epoch + '. Byte positions start at zero. UTF-8 characters belong to the window containing their first byte.';
      await area.updateComplete;
      if (run === generation) area.scrollViewportTo({top: 0, left: 0, behavior: 'instant'});
    } catch (error) {
      if (run !== generation || !pail.isConnected) return;
      status.textContent = 'Read failed. ' + (error.name === 'TimeoutError' ? 'Value read timed out.' : error.message) + ' Try again.';
      status.dataset.failed = 'true';
    } finally {
      if (run === generation) {
        controller = null; controls(false);
        // A disabled initiating button may have lost focus to body. Restore only
        // in that case; never pull focus back from somewhere the user moved it.
        if (focused && (document.activeElement === document.body || document.activeElement === origin)) {
          if (origin === inspect && window) {
            await area.updateComplete;
            if (run === generation && pail.isConnected) area.viewportElement.focus();
          } else {
            const target = !origin.hidden && !origin.disabled ? origin : closeButton;
            await target.updateComplete;
            if (run === generation && pail.isConnected) target.focus();
          }
        }
      }
    }
  }
  pail.addEventListener('keydown', event => {
    if (event.key === 'Escape' && opened && !event.defaultPrevented) { event.preventDefault(); event.stopPropagation(); close(true); }
  });
}
