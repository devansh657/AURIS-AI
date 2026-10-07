import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import { chromium } from "playwright-core";

const root = path.resolve(import.meta.dirname, "..");
const token = fs.readFileSync(path.join(root, "data", "portal.token"), "ascii").trim();
const browser = await chromium.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
  args: ["--use-angle=swiftshader", "--enable-webgl", "--enable-unsafe-swiftshader"],
});
const reports = [];
try {
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(`http://127.0.0.1:8765/?access_token=${encodeURIComponent(token)}`);
    await page.waitForSelector("body[data-backend='online']", { timeout: 45000 });
    await page.locator(".nav-item[data-view='engineering']").click();
    await page.waitForFunction(() => [...document.querySelectorAll("#engineeringMetrics > div")]
      .some((element) => element.querySelector("span")?.textContent === "CODEX" && element.querySelector("strong")?.textContent === "READY"));
    const option = page.locator("#projectSelect option").filter({ hasText: "Codex Bridge Acceptance 20261002135623" });
    const projectId = await option.getAttribute("value");
    await page.selectOption("#projectSelect", projectId);
    await page.waitForFunction((selected) => document.querySelector("#engineeringMetrics").dataset.projectId === selected, projectId);
    const screenshot = path.join(root, "data", "captures", `auris-0.8.34-coding-${viewport.width}.png`);
    await page.screenshot({ path: screenshot });
    await page.locator("#codexProjectMission").click();
    await page.locator("#commandInput").waitFor({ state: "visible" });
    assert.match(await page.inputValue("#commandInput"), /Use Codex to implement/);
    const layout = await page.evaluate(() => {
      const left = document.querySelector(".core-hud.top-left").getBoundingClientRect();
      const right = document.querySelector(".core-hud.top-right").getBoundingClientRect();
      return {
      viewportWidth: innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      commandWidth: document.querySelector("#commandInput").getBoundingClientRect().width,
      hudOverlap: left.width > 0 && left.right > right.left,
      clippedActions: [...document.querySelectorAll("[data-view-panel='engineering'] .workspace-actions button")]
        .filter((element) => element.scrollWidth > element.clientWidth + 1).map((element) => element.textContent),
      };
    });
    assert.equal(layout.documentWidth, layout.viewportWidth);
    assert.deepEqual(layout.clippedActions, []);
    assert.ok(layout.commandWidth >= 300, "The coding brief field is too narrow.");
    assert.equal(layout.hudOverlap, false, "Neural status labels overlap.");
    assert.deepEqual(errors, []);
    const commandScreenshot = screenshot.replace(".png", "-command.png");
    await page.screenshot({ path: commandScreenshot });
    reports.push({ viewport, layout, errors, screenshot, commandScreenshot });
    await page.close();
  }
} finally {
  await browser.close();
}
console.log(JSON.stringify({ ok: true, reports }, null, 2));
