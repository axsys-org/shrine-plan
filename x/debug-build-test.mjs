import assert from 'node:assert/strict';
import {esbuild,root,validateMashRevision} from './debug-tooling.mjs';

const revision = 'a'.repeat(40), pinned = {revision};
assert.throws(() => validateMashRevision({revision:null}, revision, false, true), /pin the paired/);
assert.throws(() => validateMashRevision(pinned, 'b'.repeat(40), false, true), /does not match/);
assert.throws(() => validateMashRevision(pinned, revision, true, true), /dirty/);
assert.doesNotThrow(() => validateMashRevision(pinned, revision, false, true));
assert.doesNotThrow(() => validateMashRevision({revision:null}, revision, true, false));
for (const legacy of [false,true]) {
  const {outputFiles:[{text}]} = await esbuild().build({
    entryPoints:[root + '/src/foil/debug/' + (legacy ? 'workbench.js' : 'native.js')],
    bundle:true,write:false,format:'iife',target:'es2022',minifySyntax:true,
    define:{__DEBUG_LEGACY__:String(legacy)},
  });
  assert.equal(/\bcreateElement(?:NS)?\s*\(/.test(text),legacy);
}
console.log('DEBUGGER-BUILD-BOUNDARY-PASS');
