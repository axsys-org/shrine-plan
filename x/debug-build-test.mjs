import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {esbuild,root,mashRoot,validateMashRevision} from './debug-tooling.mjs';

const revision = 'a'.repeat(40), pinned = {revision};
assert.throws(() => validateMashRevision({revision:null}, revision, false, true), /pin the paired/);
assert.throws(() => validateMashRevision(pinned, 'b'.repeat(40), false, true), /does not match/);
assert.throws(() => validateMashRevision(pinned, revision, true, true), /dirty/);
assert.doesNotThrow(() => validateMashRevision(pinned, revision, false, true));
assert.doesNotThrow(() => validateMashRevision({revision:null}, revision, true, false));
const {outputFiles:[{text}]} = await esbuild().build({
  entryPoints:[root + '/src/foil/debug/native.js'],
  bundle:true,write:false,format:'iife',target:'es2022',minifySyntax:true,
});
assert.doesNotMatch(text, /\bcreateElement(?:NS)?\s*\(/);
assert.doesNotMatch(text, /__DEBUG_LEGACY__|legacyElement|enhanceForms/);
assert.doesNotMatch(text, /beginStylesheetHandoff|__DEBUG_STYLE_|createTooltips/);
const host = await readFile(resolve(root, 'src/foil/web.foil'), 'utf8');
const debuggerHost = host.slice(host.indexOf('+  debugger\n'), host.indexOf('+  zoo\n'));
assert.doesNotMatch(debuggerHost, /debug_model\/|web_style\/css|page_with_bundle/);
assert.match(debuggerHost, /weft\/page_with_assets/);
const registry = await readFile(resolve(mashRoot(),'packages/components/src/icon/carbon-icons.generated.ts'),'utf8');
const names = new Set([...registry.matchAll(/^\s+"([^"]+)": \{/gm)].map(match=>match[1]));
const icons = await readFile(resolve(root,'src/foil/debug/icons.js'),'utf8');
assert.doesNotMatch(icons, /registerIcon|createElementNS|shrine-icons|<svg\b/);
const aliases = [...icons.matchAll(/^\s+\w+: '([^']+)'/gm)].map(match=>match[1]);
assert.ok(aliases.length > 20);
for (const name of aliases) assert.ok(names.has(name),'Stock Mash icon: ' + name);
console.log('DEBUGGER-BUILD-BOUNDARY-PASS');
