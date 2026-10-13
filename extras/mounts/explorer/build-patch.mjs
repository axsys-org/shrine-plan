import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {readFile,mkdir,access,writeFile} from 'node:fs/promises';
const out=process.argv[2];
// Explicit development selection; default remains the pinned production workspace.
const development=process.env.GOO_PATCH_MASH_ROOT;
const mash=development||process.env.MASH_NIX_ROOT;
if(!mash)throw new Error('Build patch components in the Extras Nix shell, or explicitly set GOO_PATCH_MASH_ROOT for development.');
if(!development){
 const lock=JSON.parse(await readFile(new URL('../../flake.lock',import.meta.url),'utf8'));
 const pinned=lock.nodes[lock.nodes[lock.root].inputs.mash].locked.rev;
 const provenance=JSON.parse(await readFile(resolve(mash,'mash-nix.json'),'utf8'));
 if(provenance.revision!==pinned||provenance.dirty||!mash.startsWith('/nix/store/'))throw new Error('Mash revision mismatch');
}
const require=createRequire(resolve(mash,'apps/catalog/package.json'));
const {build}=require('esbuild');await mkdir(out,{recursive:true});
const base=resolve(mash,'packages/shrine-components/dist/patch');
try { await access(resolve(base,'register.js')); } catch {
 if(development)throw new Error('Build @mash/shrine before starting the patch demo.');
 await writeFile(resolve(out,'goo-patch-components.js'),'/* Pinned Mash does not yet publish Goo patch components. */\n');
 console.error('Pinned Mash has no patch renderer; patch panes require the development build until the package pin is updated.');
 process.exit(0);
}
await build({stdin:{contents:`import ${JSON.stringify(resolve(base,'register.js'))};\nimport * as adapter from ${JSON.stringify(resolve(base,'integration/goo-adapter.js'))};\nglobalThis.GooPatchComponents=adapter;`,resolveDir:mash,loader:'js'},bundle:true,format:'iife',target:'es2022',outfile:resolve(out,'goo-patch-components.js'),logLevel:'info'});
console.error(development?'Goo patch development assets from '+mash:'Goo patch assets from pinned Mash');
