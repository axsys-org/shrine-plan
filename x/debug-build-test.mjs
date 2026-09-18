import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {esbuild,root,mashRoot,isNixMash,mashDependency,mashProvenance,validateMashRevision,validateNixMash} from './debug-tooling.mjs';

const revision = 'a'.repeat(40), pinned = {revision};
assert.throws(() => validateMashRevision(pinned, 'b'.repeat(40), false, true), /does not match/);
assert.throws(() => validateMashRevision(pinned, 'b'.repeat(40), false, false), /does not match flake.lock/);
assert.throws(() => validateMashRevision(pinned, revision, true, true), /dirty/);
assert.doesNotThrow(() => validateMashRevision(pinned, revision, false, true));
assert.doesNotThrow(() => validateMashRevision(pinned, revision, true, false));
const lock = JSON.parse(await readFile(resolve(root,'flake.lock'),'utf8'));
const declared = mashDependency(lock);
// Resolve the root input mapping: Nix may rename the dependency's node.
const fixture = locked => ({root:'app', nodes:{app:{inputs:{mash:'mash_2'}}, mash_2:{locked}}});
const locked = {type:'git', url:'https://example.com/mash.git', rev:revision};
assert.deepEqual(mashDependency(fixture(locked)), {repository:locked.url, revision});
for (const invalid of [{}, {root:'missing', nodes:{}}, fixture({...locked, rev:null}), fixture({...locked, rev:'main'}), fixture({...locked, url:null})]) {
  assert.throws(() => mashDependency(invalid), /Pin the Mash Git input/);
}
const dependency = {...pinned, repository:'https://github.com/axsys-org/mash.git', packageManager:'pnpm@10.33.0'};
const storePath = '/nix/store/' + 'a'.repeat(32) + '-mash-workspace-0.0.0';
const nixManifest = {...dependency, version:1, dirty:false, sourceSha256:'b'.repeat(64)};
assert.doesNotThrow(() => validateNixMash(dependency, nixManifest, storePath, true));
assert.throws(() => validateNixMash(dependency, nixManifest, '/tmp/mash', false), /immutable Nix store/);
assert.throws(() => validateNixMash(dependency, {...nixManifest, revision:'c'.repeat(40)}, storePath, false), /does not match/);
assert.throws(() => validateNixMash(dependency, {...nixManifest, dirty:true}, storePath, true), /dirty/);
for (const changed of [{version:2}, {repository:'wrong'}, {packageManager:'pnpm@9'}, {sourceSha256:'bad'}, {dirty:null}]) {
  assert.throws(() => validateNixMash(dependency, {...nixManifest,...changed}, storePath, false), /Invalid Mash Nix/);
}
if (isNixMash()) {
  const provenance = await mashProvenance(true);
  assert.equal(provenance.revision, declared.revision);
  assert.equal(provenance.repository, declared.repository);
  const workspace = JSON.parse(await readFile(resolve(mashRoot(),'package.json'),'utf8'));
  assert.equal(provenance.packageManager, workspace.packageManager);
  assert.equal(provenance.storePath, mashRoot());
  assert.ok((await readFile(resolve(mashRoot(),'apps/catalog/dist/mash.js'))).length > 0);
}
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
assert.match(debuggerHost, /grove_app\/document/);
assert.doesNotMatch(debuggerHost, /href=|script\[src=|components\.dip/);
const app = await readFile(resolve(root, 'src/grove/debugger/application.grove'), 'utf8');
assert.match(app, /inspection =\s+@role/);
const instance = await readFile(resolve(root, 'src/grove/debugger/instance.grove'), 'utf8');
assert.match(instance, /"\/page" =\s+@tree/);
assert.match(instance, /tack: '@\/y\/%\/input/);
const registry = await readFile(resolve(mashRoot(),'packages/components/src/icon/lucide-icons.generated.ts'),'utf8');
const names = new Set([...registry.matchAll(/^\s+"([^"]+)": \{/gm)].map(match=>match[1]));
const icons = await readFile(resolve(root,'src/foil/debug/icons.js'),'utf8');
assert.doesNotMatch(icons, /registerIcon|createElementNS|shrine-icons|<svg\b/);
const aliases = [...icons.matchAll(/^\s+\w+: '([^']+)'/gm)].map(match=>match[1]);
assert.ok(aliases.length > 20);
for (const name of aliases) assert.ok(names.has(name),'Stock Mash icon: ' + name);
// Grove owns static glyphs and read-descriptor glyphs, not just browser aliases.
for (const file of ['debugger.grove', 'debugger/chrome.grove', 'debugger/model.grove', 'debugger/document.grove']) {
  const source = await readFile(resolve(root,'src/grove',file),'utf8');
  for (const [name] of source.matchAll(/\b(?:action|object|navigation|status)\.[a-z.-]+\b/g)) {
    assert.ok(names.has(name), 'Stock Mash Lucide icon in ' + file + ': ' + name);
  }
}
const registration = await readFile(resolve(mashRoot(),'packages/components/src/icon/register.ts'),'utf8');
assert.match(registration, /installLucideIcons\(\)/, 'Mash installs the pack; the application does not');
assert.doesNotMatch(registration, /installCarbonIcons/);
console.log('DEBUGGER-BUILD-BOUNDARY-PASS');
