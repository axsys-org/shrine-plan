// Test-only consumers of the server's checked display list. No Goo layout code.
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';

const [fixturesPath, profilePath, mashRoot] = process.argv.slice(2);
const require = createRequire(path.join(mashRoot, 'tests/integration/package.json'));
const { chromium } = require('@playwright/test');
const fixtures = JSON.parse(await readFile(fixturesPath, 'utf8'));
const profile = JSON.parse(await readFile(path.join(profilePath, 'profile.json'), 'utf8'));
const css = await readFile(path.join(profilePath, 'profile.css'), 'utf8');
const escape = (value) => String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const near = (actual, expected, context, tolerance = 0.12) => assert.ok(Math.abs(actual - expected) <= tolerance, `${context}: ${actual} != ${expected}`);
const browser = await chromium.launch({ headless: true });
try {
  // The page receives fully rendered HTML. Scripts are disabled throughout.
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 1000, height: 1400 } });
  let document = '';
  await context.route('https://goo-profile.test/**', async (route) => {
    const leaf = new URL(route.request().url()).pathname.slice(1);
    if (!leaf) return route.fulfill({ body: document, contentType: 'text/html' });
    assert.match(leaf, /^(profile\.css|goo-[A-Za-z0-9]+\.ttf)$/);
    return route.fulfill({ body: await readFile(path.join(profilePath, leaf)), contentType: leaf.endsWith('.ttf') ? 'font/ttf' : 'text/css' });
  });
  const page = await context.newPage();
  let boxes = 0, lines = 0;
  for (const fixture of fixtures) {
    const display = fixture.display;
    assert.deepEqual(display.profile, { id: profile.id, version: profile.version, revision: profile.revision });
    document = `<!doctype html><link rel="stylesheet" href="/profile.css"><style>body{margin:17px}</style>${fixture.html}`;
    await page.goto('https://goo-profile.test/');
    await page.evaluate(async () => { await document.fonts.ready; });
    const measured = await page.evaluate(() => {
      const surface = document.querySelector('.goo-surface');
      const origin = surface.getBoundingClientRect();
      const box = (rect) => ({ x: rect.x - origin.x, y: rect.y - origin.y, width: rect.width, height: rect.height });
      return { surface: box(origin), nodes: [...surface.querySelectorAll('[data-node]')].map((node) => ({
        id: node.dataset.node, box: box(node.getBoundingClientRect()),
        rawLine: (() => {
          if (!node.hasAttribute('data-leaf') || node.tagName === 'INPUT' || node.querySelector('.goo-ascii-line') || !node.textContent) return null;
          const range = document.createRange(); range.selectNodeContents(node);
          return { rects: range.getClientRects().length, box: box(range.getBoundingClientRect()) };
        })(),
        font: { family: getComputedStyle(node).fontFamily.replaceAll('"', ''), weight: Number(getComputedStyle(node).fontWeight), size: parseFloat(getComputedStyle(node).fontSize), leading: parseFloat(getComputedStyle(node).lineHeight) },
        lines: [...node.querySelectorAll(':scope > .goo-ascii-line')].map((line) => {
          const range = document.createRange(); range.selectNodeContents(line);
          const marker = document.createElement('span');
          marker.style.cssText = 'display:inline-block;width:0;height:0;padding:0;border:0;vertical-align:baseline';
          line.append(marker);
          const baseline = marker.getBoundingClientRect().y - origin.y;
          marker.remove();
          return { text: line.textContent, baseline, line: box(line.getBoundingClientRect()), ink: box(range.getBoundingClientRect()) };
        }),
      })) };
    });
    near(measured.surface.width, display.width, `${fixture.name} surface width`);
    near(measured.surface.height, display.height, `${fixture.name} surface height`);
    assert.equal(measured.nodes.length, display.nodes.length);
    for (const expected of display.nodes) {
      const actual = measured.nodes.find((node) => node.id === expected.id);
      assert.ok(actual, `${fixture.name}/${expected.id} missing from SSR`);
      for (const key of ['x', 'y', 'width', 'height']) near(actual.box[key], expected.box[key], `${fixture.name}/${expected.id}/${key}`);
      boxes++;
      if (expected.kind !== 'group') {
        assert.equal(actual.font.family, expected.textStyle.family);
        assert.equal(actual.font.weight, expected.textStyle.weight);
        near(actual.font.size, expected.textStyle.fontSize, `${expected.id} font size`);
        near(actual.font.leading, expected.textStyle.lineHeight, `${expected.id} line height`);
      }
      if (actual.rawLine && expected.lines.length) {
        assert.equal(actual.rawLine.rects, 1, `${fixture.name}/${expected.id} must not browser-wrap`);
        near(actual.rawLine.box.x, expected.lines[0].textX, `${fixture.name}/${expected.id} primitive text x`);
        near(actual.rawLine.box.width, expected.lines[0].box.width, `${fixture.name}/${expected.id} primitive text advance`, 0.25);
      }
      // Native inputs/avatar/control text need no wrapping; explicit lines cover
      // the text and code paths where server/browser drift would change layout.
      if (actual.lines.length) {
        assert.equal(actual.lines.length, expected.lines.length);
        for (const [i, line] of actual.lines.entries()) {
          const planned = expected.lines[i];
          assert.equal(line.text, planned.text);
          near(line.line.y, planned.box.y, `${fixture.name}/${expected.id}/line ${i} y`);
          // Native HTML rounds font ascent/descent and half-leading to pixels.
          // Keep Goo's portable fractional baseline; do not encode one engine's
          // raster rounding in the profile. Box checks remain strict.
          near(line.baseline, planned.baseline, `${fixture.name}/${expected.id}/line ${i} baseline`, 1.5);
          near(line.line.height, planned.box.height, `${fixture.name}/${expected.id}/line ${i} height`);
          near(line.ink.x, planned.box.x, `${fixture.name}/${expected.id}/line ${i} x`);
          near(line.ink.width, planned.box.width, `${fixture.name}/${expected.id}/line ${i} advance`, 0.25);
          lines++;
        }
      }
    }
    // A second, deliberately small consumer: SVG uses only resolved coordinates,
    // font references and baselines. It knows nothing of rows, gaps or wrapping.
    const shapes = display.nodes.flatMap((node) => {
      const b = node.box, s = node.textStyle;
      return [`<rect x="${b.x}" y="${b.y}" width="${b.width}" height="${b.height}" fill="none" stroke="#d8e2cd"/>`,
        ...node.lines.map((line) => {
          assert.equal(typeof line.baseline, 'number', 'display must resolve the text baseline');
          const rtl = display.context.direction === 'rtl';
          const textX = line.textX + (rtl ? line.box.width - line.prefixAdvance : 0);
          return `<text direction="${display.context.direction}" text-anchor="${rtl ? 'end' : 'start'}" x="${textX}" y="${line.baseline}" font-family="${escape(s.family)}" font-size="${s.fontSize}" font-weight="${s.weight}" font-style="${escape(s.style)}" letter-spacing="${s.letterSpacing}" xml:space="preserve">${escape(line.text)}</text>`;
        })];
    }).join('');
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${display.width}" height="${Math.max(display.height, 1)}"><style>${css.replaceAll('&', '&amp;').replaceAll('<', '&lt;')} text{font-kerning:none;font-variant-ligatures:none;font-feature-settings:"kern" 0,"liga" 0,"clig" 0;font-synthesis:none}</style>${shapes}</svg>`;
    await writeFile(path.join(path.dirname(fixturesPath), `${fixture.name}.svg`), svg);
    document = `<!doctype html><link rel="stylesheet" href="/profile.css">${svg}`;
    await page.goto('https://goo-profile.test/');
    await page.evaluate(async () => { await document.fonts.ready; });
    const advances = await page.locator('text').evaluateAll((elements) => elements.map((element) => element.getComputedTextLength()));
    const expectedLines = display.nodes.flatMap((node) => node.lines);
    for (const [i, advance] of advances.entries()) near(advance, expectedLines[i].box.width - expectedLines[i].prefixAdvance, `${fixture.name}/SVG line ${i} advance`, 0.25);
  }
  console.log(`Chromium SSR (scripts disabled): ${fixtures.length} fixtures, ${boxes} boxes, ${lines} explicit lines; SVG consumer advances match.`);
  await context.close();
} finally {
  await browser.close();
}
