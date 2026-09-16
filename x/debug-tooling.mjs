import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';

export const root = fileURLToPath(new URL('..', import.meta.url));
export const outputRoot = resolve(process.env.DEBUG_OUTPUT_ROOT || resolve(root, '.check/debug-assets/foil'));
export function mashRoot() {
  if (!process.env.MASH_ROOT) throw new Error('Set MASH_ROOT to an explicit Mash checkout; see doc/debugger-pr.md.');
  return resolve(process.env.MASH_ROOT);
}
export function mashRequire() { return createRequire(resolve(mashRoot(), 'apps/catalog/package.json')); }
export function esbuild() { return mashRequire()('esbuild'); }
export function playwright() {
  // Resolve the test package through its declared workspace dependency, not a
  // pnpm-internal path or a package accidentally hoisted into the parent repo.
  const require = createRequire(resolve(mashRoot(), 'tests/visual/package.json'));
  return require('@playwright/test');
}
export function validateMashRevision(dependency, revision, dirty, release) {
  if (release && !/^[a-f0-9]{40}$/.test(dependency.revision || '')) throw new Error('Release blocked: pin the paired Mash commit in debug-dependencies.json.');
  if (dependency.revision && revision !== dependency.revision) throw new Error('Mash revision does not match debug-dependencies.json.');
  if (release && dirty) throw new Error('Release blocked: Mash checkout is dirty.');
}
export async function mashProvenance(release = false) {
  const checkout = mashRoot();
  const dependency = JSON.parse(await readFile(resolve(root, 'debug-dependencies.json'), 'utf8')).mash;
  const git = (...args) => execFileSync('git', ['-C', checkout, ...args], {encoding:'utf8'}).trim();
  const revision = git('rev-parse', 'HEAD');
  const dirty = Boolean(git('status', '--porcelain', '--untracked-files=normal'));
  validateMashRevision(dependency, revision, dirty, release);
  const manifest = JSON.parse(await readFile(resolve(checkout, 'package.json'), 'utf8'));
  if (manifest.packageManager !== dependency.packageManager) throw new Error('Mash package manager does not match the declared dependency.');
  const hash = createHash('sha256');
  const inputs = git('ls-files', '-co', '--exclude-standard').split('\n').filter(p =>
    p === 'pnpm-lock.yaml' || p === 'pnpm-workspace.yaml' || p.endsWith('package.json') ||
    /^(packages\/|apps\/catalog\/src\/mash.iife|apps\/catalog\/vite)/.test(p));
  for (const path of [...new Set(inputs)].sort()) {
    // A tracked deletion is an input too, not a missing-file build failure.
    hash.update(path + '\0');
    try { hash.update(await readFile(resolve(checkout,path))); }
    catch (error) { if (error.code !== 'ENOENT') throw error; hash.update('<deleted>'); }
  }
  return {repository:dependency.repository, revision, dirty, sourceSha256:hash.digest('hex'), packageManager:manifest.packageManager};
}
