// Bundle browser sources into the two asset names the running HTTP foot serves.
// This updates UI assets only; it does not restart or mutate the namespace.
import { resolve, dirname, delimiter } from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { readFile, writeFile, mkdir, rename } from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {root, outputRoot, mashRoot, mashProvenance, esbuild} from './debug-tooling.mjs';
const legacy = process.argv.includes('--legacy');
const provenance = await mashProvenance(process.argv.includes('--release'));
// Build actual workspace sources every time. No ignored/prebuilt input is
// accepted as evidence of which Mash revision this application contains.
const mash = mashRoot();
const pnpm = process.env.PNPM || 'pnpm';
const env = process.env.PNPM ? {...process.env, PATH:dirname(resolve(pnpm)) + delimiter + process.env.PATH} : process.env;
const pnpmVersion = execFileSync(pnpm, ['--version'], {cwd:mash, encoding:'utf8',env}).trim();
if ('pnpm@' + pnpmVersion !== provenance.packageManager) throw new Error('Use ' + provenance.packageManager + '; found pnpm@' + pnpmVersion + '. Set PNPM to its executable if needed.');
// Dependency installation is explicit: pnpm install --frozen-lockfile in Mash.
// A build must not replace an existing checkout's node_modules/store layout.
execFileSync(pnpm, ['run', 'build'], {cwd:mash, stdio:'inherit',env});
execFileSync(pnpm, ['--filter', '@mash/catalog', 'run', 'build:iife'], {cwd:mash, stdio:'inherit',env});
const {build} = esbuild();
const outputs = new Map();

// Match the JS enhancement to the CSS that was built with it. A link existing
// (or a different cached build loading) is not proof that replacement is ready.
function withReadiness(source, name) {
  const footer = new RegExp('\\n/\\* shrine-debug stylesheet readiness \\*/\\n:root \\{ --shrine-debug-' + name + '-ready: asset-[a-f0-9]{16}; \\}\\n?$');
  const css = source.replace(footer, '');
  const version = 'asset-' + createHash('sha256').update(css).digest('hex').slice(0, 16);
  return { version, css: css + '\n/* shrine-debug stylesheet readiness */\n:root { --shrine-debug-' + name + '-ready: ' + version + '; }\n' };
}

let componentCSS;

// --components is accepted for old callers; components are now always built.
{
  async function recipe(path, stack = []) {
    if (stack.includes(path)) throw new Error('Cyclic component CSS import: ' + path);
    let text = await readFile(path, 'utf8');
    for (const match of [...text.matchAll(/@import\s+"(\.\/[^"\n]+)"\s*;/g)]) {
      const imported = await recipe(resolve(path, '..', match[1]), [...stack, path]);
      text = text.replace(match[0], imported);
    }
    return text;
  }
  const css = await Promise.all(['components', 'shrine-components'].map(packageName =>
    recipe(resolve(mash, 'packages', packageName, 'src/catalogue/mash.css'))));
  componentCSS = css.join('\n');
  outputs.set(resolve(outputRoot, '.debug-assets/mash.js'), await readFile(resolve(mash, 'apps/catalog/dist/mash.js')));
}
const components = withReadiness(componentCSS, 'components');
const compiledCSS = await build({ entryPoints: [resolve(root, 'src/foil/debug/styles.css')], outfile: resolve(root, 'src/foil/debug.css'), bundle: true, write: false, target: 'es2022', logLevel: 'info' });
const app = withReadiness(compiledCSS.outputFiles[0].text, 'app');
const compiledJS = await build({
  entryPoints: [resolve(root, 'src/foil/debug/' + (legacy ? 'workbench.js' : 'native.js'))], outfile: resolve(root, 'src/foil/debug.js'),
  bundle: true, write: false, format: 'iife', target: 'es2022', logLevel: 'info', minifySyntax:true, treeShaking:true,
  define: { __DEBUG_LEGACY__: String(legacy), __DEBUG_STYLE_APP__: JSON.stringify(app.version), __DEBUG_STYLE_COMPONENTS__: JSON.stringify(components.version) },
});
if (!legacy && /\bcreateElement(?:NS)?\s*\(/.test(compiledJS.outputFiles[0].text)) {
  throw new Error('Native application bundle contains a DOM factory; declare its UI in Grove.');
}
outputs.set(resolve(outputRoot, '.debug-assets/components.css'), components.css);
outputs.set(resolve(outputRoot, 'debug.css'), app.css);
outputs.set(resolve(outputRoot, 'debug.js'), compiledJS.outputFiles[0].contents);
outputs.set(resolve(outputRoot, 'style.css'), await readFile(resolve(root, 'src/foil/style.css')));
const after = await mashProvenance(process.argv.includes('--release'));
if (after.sourceSha256 !== provenance.sourceSha256 || after.revision !== provenance.revision) throw new Error('Mash source changed during build; rerun.');
outputs.set(resolve(outputRoot, 'build.json'), JSON.stringify({mode:legacy ? 'legacy-compatibility' : 'grove', mash:provenance,
  assets:Object.fromEntries([...outputs].map(([path,body]) => [path.slice(outputRoot.length+1),createHash('sha256').update(body).digest('hex')]))}, null,2)+'\n');

// Prepare all outputs before replacing any. Each replacement is atomic; mixed
// asset requests during a build retain legacy styling through the version gate.
await mkdir(resolve(outputRoot, '.debug-assets'), { recursive: true });
for (const [path, contents] of outputs) {
  const temporary = path + '.' + randomUUID() + '.tmp';
  await writeFile(temporary, contents);
  await rename(temporary, path);
}
console.log('Debugger assets:', outputRoot, '\nStyles:', app.version, components.version);
