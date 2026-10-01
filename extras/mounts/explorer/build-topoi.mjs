import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {readFile,mkdir} from 'node:fs/promises';
const mash=process.env.MASH_NIX_ROOT;
if(!mash) throw new Error('Build topoi in the Extras Nix shell with the pinned Mash workspace.');
const lock=JSON.parse(await readFile(new URL('../../flake.lock',import.meta.url),'utf8'));
const pinned=lock.nodes[lock.nodes[lock.root].inputs.mash].locked.rev;
const provenance=JSON.parse(await readFile(resolve(mash,'mash-nix.json'),'utf8'));
if(provenance.revision!==pinned) throw new Error('Mash revision mismatch');
const require=createRequire(resolve(mash,'apps/catalog/package.json'));
const {build}=require('esbuild');
const out=process.argv[2]; await mkdir(out,{recursive:true});
await build({stdin:{contents:`import ${JSON.stringify(resolve(mash,'packages/components/dist/goo-tree/register.js'))};\nimport ${JSON.stringify(resolve(mash,'packages/components/src/goo-tree/theme.css'))};\nimport ${JSON.stringify(resolve(mash,'packages/components/dist/goo-tidy-tree/register.js'))};`,resolveDir:mash,loader:'ts'},
 bundle:true,format:'iife',target:'es2022',outfile:resolve(out,'goo-topoi-components.js'),logLevel:'info'});
