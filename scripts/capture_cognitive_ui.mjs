import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright-core";

const root = path.resolve(import.meta.dirname, "..");
const token = fs.readFileSync(path.join(root, "data", "portal.token"), "ascii").trim();
const outputDirectory = path.join(root, "data", "captures");
const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
fs.mkdirSync(outputDirectory, { recursive: true });

const browser = await chromium.launch({
  executablePath: edgePath,
  headless: true,
  args: ["--use-angle=swiftshader", "--enable-webgl", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});

const reports = [];
for (const target of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "mobile", width: 390, height: 844 },
]) {
  const context = await browser.newContext({
    viewport: { width: target.width, height: target.height },
    deviceScaleFactor: 1,
    reducedMotion: "no-preference",
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400 && !response.url().endsWith("/favicon.ico")) {
      errors.push(`${response.status()} ${response.url()}`);
    }
  });
  page.on("requestfailed", (request) => {
    const reason = request.failure()?.errorText || "request failed";
    if (!reason.includes("ERR_ABORTED")) errors.push(`${reason} ${request.url()}`);
  });

  await page.goto(`http://127.0.0.1:8765/?access_token=${encodeURIComponent(token)}`, {
    waitUntil: "domcontentloaded",
    timeout: 45000,
  });
  await page.waitForSelector("body[data-backend='online']", { timeout: 45000 });
  await page.waitForSelector("#aurisCore[data-pixel-check='nonblank']", { timeout: 45000 });

  const layout = await page.evaluate(() => {
    const visible = [...document.querySelectorAll("body *")].filter((element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    });
    const viewportOverflow = visible
      .filter((element) => {
        if (element.id === "wakeToggle") return false;
        if (element.closest(".core-atmosphere")) return false;
        let parent = element.parentElement;
        while (parent) {
          const overflowX = getComputedStyle(parent).overflowX;
          if (["auto", "scroll"].includes(overflowX) && parent.scrollWidth > parent.clientWidth) {
            return false;
          }
          parent = parent.parentElement;
        }
        const rect = element.getBoundingClientRect();
        return rect.left < -2 || rect.right > innerWidth + 2;
      })
      .slice(0, 20)
      .map((element) => ({
        tag: element.tagName,
        id: element.id,
        className: String(element.className),
        left: Math.round(element.getBoundingClientRect().left),
        right: Math.round(element.getBoundingClientRect().right),
      }));
    const canvas = document.querySelector("#aurisCore");
    const dockControls = ["#voiceButton", ".wake-control", ".execute-control", "#dockStop"]
      .map((selector) => document.querySelector(selector))
      .filter(Boolean)
      .map((element) => ({
        text: element.textContent.trim(),
        width: Math.round(element.getBoundingClientRect().width),
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
        clipped: element.scrollWidth > element.clientWidth + 1,
      }));
    return {
      backend: document.body.dataset.backend,
      renderer: canvas?.dataset.renderer,
      pixelCheck: canvas?.dataset.pixelCheck,
      projection: canvas?.dataset.viewMode,
      viewportOverflow,
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: innerWidth,
      dockControls,
    };
  });

  const screenshot = path.join(outputDirectory, `auris-0.8.34-${target.name}.png`);
  await page.screenshot({ path: screenshot, fullPage: false });
  const firstFrame = await page.locator("#aurisCore").screenshot();
  await page.waitForTimeout(450);
  const secondFrame = await page.locator("#aurisCore").screenshot();
  const moving = !firstFrame.equals(secondFrame);
  const modes = [];
  for (const mode of ["2d", "schematic", "3d"]) {
    await page.locator(`button[data-core-view='${mode}']`).evaluate((button) => button.click());
    modes.push(await page.locator("#aurisCore").getAttribute("data-view-mode"));
  }
  reports.push({ ...target, screenshot, errors: [...errors], layout, moving, modes });
  await context.close();
}

await browser.close();
const ok = reports.every((report) => (
    !report.errors.length
    && report.layout.pixelCheck === "nonblank"
    && report.layout.viewportOverflow.length === 0
    && report.layout.documentWidth === report.layout.viewportWidth
    && report.layout.dockControls.every((control) => !control.clipped)
    && report.moving && report.modes.join() === "2d,schematic,3d"
  ));
console.log(JSON.stringify({ ok, reports }, null, 2));
if (!ok) process.exitCode = 1;
