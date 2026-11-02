import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { mkdir } from "node:fs/promises";
const [base, playwrightPackage, out = "/tmp/pathways-browser"] =
  process.argv.slice(2);
if (!base || !playwrightPackage)
  throw Error(
    "Usage: check-browser.mjs URL /path/to/@playwright/test/package.json [OUTPUT]",
  );
const { chromium } = createRequire(resolve(playwrightPackage))(
  "@playwright/test",
);
await mkdir(out, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1560, height: 1080 },
  acceptDownloads: true,
});
const page = await context.newPage(),
  errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("dialog", (d) => d.accept());
page.setDefaultTimeout(25000);
const endpoint = base + "/pathways",
  initial = await (await fetch(endpoint + "/state")).json();
const ready = (p) =>
  p.waitForFunction(() => document.body.dataset.ready === "true");
const saved = (p) =>
  p
    .locator("#status")
    .filter({ hasText: /^Saved in namespace/ })
    .waitFor();
try {
  await page.goto(endpoint);
  await ready(page);
  assert.equal(await page.locator("[data-node]").count(), 12);
  assert.equal(await page.locator(".node.assumed").count(), 0);
  await page.locator("#case-title").fill("Browser check");
  await page.locator("#obs-inattention").selectOption("present");
  assert.equal(
    await page.locator(".node.assumed").count(),
    0,
    "Symptoms do not trigger assumptions",
  );
  await page.locator("#obs-late_sleep").selectOption("absent");
  await page.locator('[data-hypothesis="circadian_delay"]').check();
  assert.match(
    await page.locator("#inspector").innerText(),
    /Absent compatible clues: Late sleep onset/,
  );
  assert.match(
    await page.locator("#inspector").innerText(),
    /not mapped here: Inattention/,
  );
  await page.locator('[data-hypothesis="circadian_delay"]').uncheck();
  await page.locator('[data-hypothesis="redox_limit"]').check();
  assert.equal(await page.locator(".node.assumed").count(), 2);
  assert(
    !(await page.locator('[data-node="adhd"]').getAttribute("class")).includes(
      "related",
    ),
  );
  await page.locator('[data-node="gsr"]').click();
  assert.match(
    await page.locator("#inspector").innerText(),
    /Glutathione reductase uses NADPH/,
  );
  assert(await page.locator('#inspector a[href*="R-HSA-71682"]').count());
  await page.locator("#research").uncheck();
  assert.equal(await page.locator(".edge.research").count(), 0);
  await page.locator("#research").check();
  await page.locator("#custom-section summary").click();
  await page
    .locator("#custom-statement")
    .fill("Could a timing shift explain the pattern?");
  await page.locator("#custom-direction").selectOption("timing");
  await page
    .getByLabel("Assume effect on Circadian clock", { exact: true })
    .check();
  await page
    .locator("#custom-rationale")
    .fill("User hypothesis; would reconsider if timing is stable.");
  await page
    .locator("#case-notes")
    .fill("<script>not executable</script> — context kept as text");
  await page.locator("#save").click();
  await saved(page);
  const stored = await (await fetch(endpoint + "/state")).json();
  assert.equal(stored.cases.at(-1).custom.direction, "timing");
  await page.reload();
  await ready(page);
  await page.locator("#case-select").selectOption(stored.cases.at(-1).id);
  assert.equal(
    await page.locator("#case-notes").inputValue(),
    "<script>not executable</script> — context kept as text",
  );
  assert.equal(await page.locator("#obs-late_sleep").inputValue(), "absent");
  assert.equal(await page.locator(".node.assumed").count(), 3);
  await page.locator('[data-node="folate"]').focus();
  await page.keyboard.press("Enter");
  assert.match(await page.locator("#inspector h2").innerText(), /Folate cycle/);
  assert.equal(
    await page
      .locator('[data-node="folate"]')
      .evaluate((e) => e === document.activeElement),
    true,
  );
  await page.locator('[data-edge="folate-adhd"]').focus();
  await page.keyboard.press("Enter");
  assert.match(await page.locator("#inspector").innerText(), /NULL CONNECTION/);
  assert.equal(
    await page
      .locator('[data-edge="folate-adhd"]')
      .evaluate((e) => e === document.activeElement),
    true,
  );
  // Another tab edits the same saved revision. Neither writer may silently win twice.
  const other = await context.newPage();
  other.on("dialog", (d) => d.accept());
  await other.goto(endpoint);
  await ready(other);
  await page.locator("#case-notes").fill("First tab wins");
  await page.locator("#save").click();
  await saved(page);
  await other.locator("#case-notes").fill("Second tab keeps its draft");
  await other.locator("#save").click();
  await other.locator("#status").filter({ hasText: "Save conflict" }).waitFor();
  assert.equal(
    await other.locator("#case-notes").inputValue(),
    "Second tab keeps its draft",
  );
  assert.equal(
    (await (await fetch(endpoint + "/state")).json()).cases.at(-1).notes,
    "First tab wins",
  );
  await other.close();
  const downloadPromise = page.waitForEvent("download");
  await page.locator("#export").click();
  const download = await downloadPromise;
  const path = resolve(out, "export.json");
  await download.saveAs(path);
  const count = await page.locator("#case-select option").count();
  await page.locator("#import-file").setInputFiles(path);
  await page
    .locator("#status")
    .filter({ hasText: "Imported as new drafts" })
    .waitFor();
  assert.equal(await page.locator("#case-select option").count(), count * 2);
  await page.locator("#save").click();
  await saved(page);
  await page.locator("#case-title").fill("Redox / one-carbon research");
  await page.locator("#save").click();
  await saved(page);
  await page.locator('[data-node="gsr"]').click();
  await page.screenshot({ path: resolve(out, "desktop.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
    "No horizontal overflow on mobile",
  );
  await page.screenshot({ path: resolve(out, "mobile.png"), fullPage: true });
  assert.deepEqual(errors, []);
  console.log(
    "PATHWAYS-BROWSER-PASS: map, evidence, assumptions, namespace save/reload, absent observations, concurrent tabs, import/export, keyboard, mobile",
  );
} catch (error) {
  await page.screenshot({ path: resolve(out, "failure.png"), fullPage: true });
  throw error;
} finally {
  const current = await (await fetch(endpoint + "/state")).json();
  await fetch(endpoint + "/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      atlas: initial.atlas,
      revision: current.revision,
      receipt: "browser-check-restore-" + Date.now(),
      cases: initial.cases,
    }),
  });
  await browser.close();
}
