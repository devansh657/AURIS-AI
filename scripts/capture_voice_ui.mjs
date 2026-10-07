import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright-core";

const root = path.resolve(import.meta.dirname, "..");
const token = fs.readFileSync(path.join(root, "data", "portal.token"), "ascii").trim();
const output = path.join(root, "data", "captures");
fs.mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", headless: true,
  args: ["--use-angle=swiftshader", "--enable-webgl", "--enable-unsafe-swiftshader"] });
const reports = [];
try {
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    let releaseProjects;
    const projectGate = new Promise((resolve) => { releaseProjects = resolve; });
    await page.route("**/api/projects", async (route) => { await projectGate; await route.continue(); });
    const started = Date.now();
    await page.goto(`http://127.0.0.1:8765/?access_token=${encodeURIComponent(token)}`);
    try {
      await page.waitForSelector("body[data-backend='online']", { timeout: 45000 });
    } catch (error) {
      console.log(JSON.stringify({ viewport, errors, startup: await page.evaluate(() => ({backend:document.body.dataset.backend, messages:document.querySelector("#messages")?.textContent})) }));
      throw error;
    }
    const readyBeforeOptionalData = await page.locator("#voiceButton").isEnabled();
    const readyMs = Date.now() - started;
    releaseProjects();
    await page.locator(".nav-item[data-view='activity']").evaluate((button) => button.click());
    const actualScreenshot = path.join(output, `auris-0.8.34-voice-live-${viewport.width}.png`);
    await page.screenshot({ path: actualScreenshot });
    // Explicit UI fixtures test long labels and states, not microphone accuracy or PC execution.
    const voiceData = await (await page.request.get("http://127.0.0.1:8765/api/voice/status")).json();
    const statusData = await (await page.request.get("http://127.0.0.1:8765/api/status")).json();
    const fixtureTurns = [
        { turn_id: "layout-fixture-1", source: "push_to_talk", heard: "Create a folder called AURIS acceptance reports on my Desktop and prepare the project documentation", outcome: "partially_completed", failure_stage: "execution", input_provider: "local_whisper_stream", capture_ms: 2700, decode_ms: 350, command_ms: 690, first_audio_ms: 520, recognition_to_audio_ms: 1210, task_type: "computer_operation", verification: "partial", speech_state: "completed", decoder_score: .82, actions: [{kind: "create_folder", ok: true, signed: true, nonce_claimed: true}] },
        { turn_id: "layout-fixture-2", source: "wake", heard: "[private or sensitive transcript hidden]", outcome: "awaiting_approval", failure_stage: null, input_provider: "local_whisper_stream", capture_ms: 3000, decode_ms: 400, command_ms: 390, first_audio_ms: null, recognition_to_audio_ms: null, task_type: "coding", verification: "not_reported", speech_state: "not_requested", actions: [] },
    ];
    voiceData.voice.recent_turns = fixtureTurns;
    statusData.status.voice.recent_turns = fixtureTurns;
    await page.route("**/api/voice/status", (route) => route.fulfill({ json: voiceData }));
    await page.route("**/api/status", (route) => route.fulfill({ json: statusData }));
    const tasks = [
      {task_id:"fixture-1", objective:"Layout fixture: generated reply", state:"completed", task_type:"general_assistance"},
      {task_id:"fixture-2", objective:"Layout fixture: partial task", state:"partially_completed", task_type:"computer_operation"},
      {task_id:"fixture-3", objective:"Layout fixture: pending approval", state:"awaiting_approval", task_type:"coding"},
    ].map((task) => ({...task, risk_level:"read_only", result:{verification_report:{status:"verified"}}}));
    await page.route("**/api/tasks?*", (route) => route.fulfill({json:{ok:true, tasks}}));
    await page.waitForSelector("#voiceTurnsView details[data-turn='layout-fixture-1']", { timeout: 15000 });
    await page.waitForFunction(() => document.querySelector("#tasksView")?.textContent.includes("Layout fixture"), { timeout: 15000 });
    const labels = await page.locator("#tasksView .verification-status").allTextContents();
    await page.locator("#voiceTurnsView details").evaluateAll((items) => items.forEach((item) => { item.open = true; }));
    const layout = await page.evaluate(() => {
      const panel = document.querySelector("#voiceTurnsView");
      const visible = [...panel.querySelectorAll("*")].filter((node) => node.getBoundingClientRect().width > 0);
      return { documentWidth: document.documentElement.scrollWidth, viewportWidth: innerWidth,
        overflow: visible.filter((node) => { const r = node.getBoundingClientRect(); return r.left < 0 || r.right > innerWidth + 1; }).map((node) => node.tagName),
        decoderLabelCorrect: panel.textContent.includes("UNCALIBRATED") && !panel.textContent.includes("82%"),
        expandedDetails: panel.querySelectorAll("details[open]").length,
        privateHidden: panel.textContent.includes("[private or sensitive transcript hidden]") };
    });
    const fixtureScreenshot = path.join(output, `auris-0.8.34-voice-layout-fixture-${viewport.width}.png`);
    await page.screenshot({ path: fixtureScreenshot });
    reports.push({ viewport, actualScreenshot, fixtureScreenshot, fixtureOnly: true, readyBeforeOptionalData, readyMs, labels, layout, errors });
    await context.close();
  }
} finally {
  await browser.close();
}
const ok = reports.every((r) => r.readyBeforeOptionalData && !r.errors.length && !r.layout.overflow.length && r.layout.documentWidth === r.layout.viewportWidth
  && r.layout.expandedDetails === 2 && r.layout.decoderLabelCorrect && r.layout.privateHidden && r.labels.join() === "REPLY GENERATED,PARTIAL,AWAITING APPROVAL");
console.log(JSON.stringify({ ok, reports }, null, 2));
if (!ok) process.exitCode = 1;
