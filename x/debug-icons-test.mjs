// Pure icon/component contracts. No browser, runtime, or namespace requests.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { icon, iconNames, button } from '../src/foil/debug/icons.js';

const mashRoot = process.env.MASH_ROOT || fileURLToPath(new URL('../../mash/', import.meta.url));
const registry = readFileSync(resolve(mashRoot, 'packages/components/src/icon/carbon-icons.generated.ts'), 'utf8');
const stockNames = new Set([...registry.matchAll(/^\s+"([^"]+)": \{/gm)].map(match => match[1]));
assert.ok(stockNames.size > 0, 'read Mash’s actual semantic registry');
const source = readFileSync(new URL('../src/foil/debug/icons.js', import.meta.url), 'utf8');
assert.doesNotMatch(source, /registerIcon|createElementNS|shrine-icons|<svg\b/, 'no custom icon sources or registration');
const workbench = readFileSync(new URL('../src/foil/debug/workbench.js', import.meta.url), 'utf8');
assert.doesNotMatch(workbench, /\b(?:readSnapshot|caseNumber|care)\b|wb-(?:version|history|case|pin|compare)/,
  'the live-record view has no scope/history/case architecture');
assert.doesNotMatch(workbench, /\bfetch\s*\(/, 'the workbench renders parsed live documents without independent namespace reads');

globalThis.Mash = { registerIcon() { throw new Error('application icon overrides are forbidden'); } };
globalThis.document = {
  createElement(localName) {
    return {
      localName, attributes: {}, children: [], dataset: {}, classes: new Set(),
      get classList() { return { add: name => this.classes.add(name) }; },
      setAttribute(name, value) { this.attributes[name] = value; },
      append(...children) { this.children.push(...children); },
      addEventListener() {},
    };
  },
};

for (const [name, sourceName] of Object.entries(iconNames)) {
  assert.ok(stockNames.has(sourceName), sourceName + ' must exist in the stock Mash registry');
  const element = icon(name);
  assert.equal(element.localName, 'ui-icon');
  assert.equal(element.attributes.name, sourceName);
  assert.equal(element.attributes['aria-hidden'], 'true');
  assert.equal(element.attributes.size, 'small');
  assert.equal(element.classes.has('wb-icon'), true);
  assert.equal(element.dataset.iconSource, 'Mash');
  assert.equal(element.children.length, 0, 'the component owns rendering, not an authored SVG layer');
}
assert.throws(() => icon('unmapped-handdrawn-icon'), /Unknown debugger icon/);
const host = button('Open operations', 'run', null, 'Run');
assert.equal(host.localName, 'ui-button');
assert.equal(host.attributes['aria-label'], 'Open operations');
assert.equal(host.children[0].localName, 'ui-icon');
assert.equal(host.children[0].attributes.name, 'action.play');
assert.equal(host.children[1].textContent, 'Run');
assert.equal(host.attributes['icon-only'], undefined, 'text actions retain their label layout');
const iconAction = button('Refresh', 'live');
assert.equal(iconAction.attributes['icon-only'], '', 'Mash owns the icon-only control axis');
assert.equal(iconAction.attributes.size, 'compact');
console.log('PASS: all ' + Object.keys(iconNames).length + ' aliases use stock Mash icons; no custom glyphs, overrides, or scope/history workbench remain.');
