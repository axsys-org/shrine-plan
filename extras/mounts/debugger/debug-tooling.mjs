import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';

export const root = fileURLToPath(new URL('.', import.meta.url));
export const outputRoot = resolve(process.env.DEBUG_OUTPUT_ROOT || resolve(root, '.check/debug-assets/foil'));
export function mashRoot() {
  const path = process.env.MASH_ROOT || process.env.MASH_NIX_ROOT;
  if (!path) throw new Error('Run x/eden, enter nix develop .#debugger, or set MASH_ROOT to an explicit Mash checkout.');
  return resolve(path);
}
export function isNixMash() {
  return Boolean(process.env.MASH_NIX_ROOT) && mashRoot() === resolve(process.env.MASH_NIX_ROOT);
}
export function mashRequire() { return createRequire(resolve(mashRoot(), 'apps/catalog/package.json')); }
export function esbuild() { return mashRequire()('esbuild'); }
export function playwright() {
  // Resolve the test package through its declared workspace dependency, not a
  // pnpm-internal path or a package accidentally hoisted into the parent repo.
  const require = createRequire(resolve(mashRoot(), 'tests/visual/package.json'));
  return require('@playwright/test');
}
export function mashDependency(lock) {
  const input = lock.nodes?.[lock.root]?.inputs?.mash;
  const locked = typeof input === 'string' && lock.nodes?.[input]?.locked;
  if (locked?.type !== 'git' || typeof locked.url !== 'string' || !locked.url ||
      !/^[a-f0-9]{40}$/.test(locked.rev || '')) {
    throw new Error('Pin the Mash Git input to a commit in flake.lock.');
  }
  return {repository:locked.url, revision:locked.rev};
}
export function validateMashRevision(dependency, revision, dirty, release) {
  if (revision !== dependency.revision) throw new Error(`Mash revision does not match flake.lock: expected ${dependency.revision}, got ${revision}.`);
  if (release && dirty) throw new Error('Release blocked: Mash checkout is dirty.');
}
export function validateNixMash(dependency, manifest, path, release) {
  if (!/^\/nix\/store\/[a-z0-9]{32}-[^/]+$/.test(path)) throw new Error('MASH_NIX_ROOT must be an immutable Nix store workspace.');
  if (manifest.version !== 1 || manifest.repository !== dependency.repository ||
      manifest.packageManager !== dependency.packageManager ||
      typeof manifest.dirty !== 'boolean' || !/^[a-f0-9]{64}$/.test(manifest.sourceSha256 || '')) {
    throw new Error('Invalid Mash Nix build provenance.');
  }
  validateMashRevision(dependency, manifest.revision, manifest.dirty, release);
}
export async function mashProvenance(release = false) {
  const checkout = mashRoot();
  const dependency = mashDependency(JSON.parse(await readFile(resolve(root, '../../flake.lock'), 'utf8')));
  if (isNixMash()) {
    const manifest = JSON.parse(await readFile(resolve(checkout, 'mash-nix.json'), 'utf8'));
    const workspace = JSON.parse(await readFile(resolve(checkout, 'package.json'), 'utf8'));
    validateNixMash({...dependency, packageManager:workspace.packageManager}, manifest, checkout, release);
    return {...manifest, storePath:checkout};
  }
  const git = (...args) => execFileSync('git', ['-C', checkout, ...args], {encoding:'utf8'}).trim();
  const revision = git('rev-parse', 'HEAD');
  const dirty = Boolean(git('status', '--porcelain', '--untracked-files=normal'));
  validateMashRevision(dependency, revision, dirty, release);
  const manifest = JSON.parse(await readFile(resolve(checkout, 'package.json'), 'utf8'));
  const pinned = JSON.parse(git('show', `${dependency.revision}:package.json`));
  if (manifest.packageManager !== pinned.packageManager) throw new Error('Mash package manager does not match the commit pinned in flake.lock.');
  const ui = JSON.parse(await readFile(resolve(checkout, 'packages/components/package.json'), 'utf8'));
  if (!ui.exports?.['./icon/lucide']) throw new Error('Debugger requires Mash with the semantic Lucide icon pack.');
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
