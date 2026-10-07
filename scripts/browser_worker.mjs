import { createHash } from "node:crypto";
import { lookup } from "node:dns/promises";
import { isIP } from "node:net";
import { createInterface } from "node:readline";
import { chromium } from "playwright-core";

const EDGE_PATH = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const PROFILE_PATH = new URL("../data/browser-profile/", import.meta.url).pathname.replace(/^\/(\w:)/, "$1");
const FIXTURE_URL = "http://127.0.0.1:8765/browser-acceptance.html";
const BLOCKED_CONTROL = /\b(?:buy|purchase|checkout|pay|place order|transfer|send|publish|post|submit application|delete|remove|password|security|sign in|log in|book|reserve)\b/i;
const SENSITIVE_VALUE = /\b(?:password|passcode|api key|private key|secret|security code|credit card|card number|cvv|token)\b/i;
const SENSITIVE_URL_KEY = /^(?:access_token|api_key|apikey|auth|key|password|secret|token)$/i;

let context;
let page;

function emit(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

function clean(value, limit = 240) {
  return String(value ?? "").replace(/\s+/g, " ").trim().slice(0, limit);
}

function exactText(value, limit, label) {
  if (typeof value !== "string" || value.length < 1 || value.length > limit || value !== value.trim() || /[\u0000-\u001f\u007f]/.test(value)) {
    throw new Error(`The approved ${label} is outside the exact-text policy.`);
  }
  return value;
}

function safeUrl(rawUrl) {
  try {
    const url = new URL(rawUrl);
    url.username = "";
    url.password = "";
    for (const [key, value] of [...url.searchParams.entries()]) {
      url.searchParams.set(key, `sha256:${createHash("sha256").update(value).digest("hex").slice(0, 16)}`);
    }
    url.hash = "";
    return url.toString();
  } catch {
    return "";
  }
}

function isPrivateIPv4(hostname) {
  const parts = hostname.split(".").map(Number);
  if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) return false;
  return parts[0] === 10 || parts[0] === 127 || (parts[0] === 169 && parts[1] === 254) ||
    (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) || (parts[0] === 192 && parts[1] === 168);
}

function isPrivateAddress(hostname) {
  const host = hostname.replace(/^\[|\]$/g, "").toLowerCase();
  if (isPrivateIPv4(host)) return true;
  if (isIP(host) !== 6) return false;
  if (["::", "::1"].includes(host) || host.startsWith("fc") || host.startsWith("fd")) return true;
  if (host.startsWith("::ffff:")) return isPrivateIPv4(host.slice(7));
  const first = Number.parseInt(host.split(":")[0] || "0", 16);
  return first < 0x2000 || first > 0x3fff;
}

async function allowedUrl(rawUrl) {
  let url;
  try { url = new URL(rawUrl); } catch { return false; }
  const fixture = new URL(FIXTURE_URL);
  if (url.origin === fixture.origin && [fixture.pathname, "/browser-acceptance.css"].includes(url.pathname)) return true;
  if (!["http:", "https:"].includes(url.protocol)) return false;
  if (url.username || url.password || [...url.searchParams.keys()].some((key) => SENSITIVE_URL_KEY.test(key)) || /(?:^|[&#])(?:access_token|api_key|apikey|auth|key|password|secret|token)=/i.test(url.hash.slice(1))) return false;
  const host = url.hostname.replace(/^\[|\]$/g, "").toLowerCase();
  if (["localhost", "0.0.0.0"].includes(host) || host.endsWith(".local") || isPrivateAddress(host)) return false;
  try {
    const addresses = await lookup(host, { all: true, verbatim: true });
    return addresses.length > 0 && addresses.every(({ address }) => !isPrivateAddress(address));
  } catch {
    return false;
  }
}

async function ensurePage() {
  if (!page || page.isClosed()) page = await context.newPage();
  return page;
}

async function pageState(activePage) {
  const status = await activePage.getByRole("status").allTextContents().catch(() => []);
  const alerts = await activePage.getByRole("alert").allTextContents().catch(() => []);
  const body = clean(await activePage.locator("body").innerText({ timeout: 3000 }).catch(() => ""), 12000);
  return {
    url: safeUrl(activePage.url()),
    url_query_values: "sha256_redacted",
    title: clean(await activePage.title().catch(() => ""), 160),
    status: status.map((item) => clean(item, 300)).filter(Boolean).slice(0, 5),
    alerts: alerts.map((item) => clean(item, 300)).filter(Boolean).slice(0, 5),
    body_digest: createHash("sha256").update(body).digest("hex"),
  };
}

async function inspect(activePage) {
  const headings = await activePage.getByRole("heading").allTextContents().catch(() => []);
  const roles = ["button", "link", "textbox", "checkbox", "radio", "combobox", "tab"];
  const controls = [];
  for (const role of roles) {
    const locator = activePage.getByRole(role);
    const count = Math.min(await locator.count(), 20);
    for (let index = 0; index < count && controls.length < 50; index += 1) {
      const item = locator.nth(index);
      if (!(await item.isVisible().catch(() => false))) continue;
      const name = clean(
        (await item.getAttribute("aria-label")) ||
        (await item.getAttribute("placeholder")) ||
        (await item.innerText().catch(() => "")),
        120,
      );
      if (name) controls.push({ role, name });
    }
  }
  return {
    ...(await pageState(activePage)),
    headings: headings.map((item) => clean(item, 160)).filter(Boolean).slice(0, 20),
    controls,
    content_trust: "untrusted_web_content",
  };
}

async function exactFillLocator(activePage, name) {
  const candidates = [
    activePage.getByLabel(name, { exact: true }),
    activePage.getByPlaceholder(name, { exact: true }),
    activePage.getByRole("textbox", { name, exact: true }),
  ];
  for (const candidate of candidates) {
    const count = await candidate.count();
    if (count > 1) throw new Error("The exact visible field name is ambiguous.");
    if (count === 1 && await candidate.isVisible().catch(() => false)) return candidate;
  }
  throw new Error("The exact visible field name did not resolve uniquely.");
}

async function exactClickLocator(activePage, name) {
  if (BLOCKED_CONTROL.test(name)) throw new Error("That browser control is outside the bounded interaction policy.");
  const roles = ["button", "link", "checkbox", "radio", "tab", "menuitem"];
  const matches = [];
  for (const role of roles) {
    const candidate = activePage.getByRole(role, { name, exact: true });
    if (await candidate.count() === 1 && await candidate.isVisible().catch(() => false)) matches.push(candidate);
  }
  if (matches.length !== 1) throw new Error("The exact visible control name did not resolve uniquely.");
  return matches[0];
}

async function performNavigate(activePage, rawUrl) {
  if (!await allowedUrl(rawUrl)) throw new Error("The browser URL is outside the network policy.");
  const response = await activePage.goto(rawUrl, { waitUntil: "domcontentloaded", timeout: 20000 });
  if (!await allowedUrl(activePage.url())) throw new Error("The browser redirected outside the network policy.");
  const status = response?.status() ?? null;
  return { ok: Boolean(response && status >= 200 && status < 400), http_status: status, page: await inspect(activePage) };
}

async function performFill(activePage, rawName, rawValue) {
  const name = exactText(rawName, 120, "field name");
  const value = exactText(rawValue, 500, "field value");
  if (SENSITIVE_VALUE.test(value)) throw new Error("The field value is outside the bounded interaction policy.");
  const locator = await exactFillLocator(activePage, name);
  if ((await locator.getAttribute("type"))?.toLowerCase() === "password") throw new Error("AURIS will not fill password fields.");
  await locator.fill(value, { timeout: 8000 });
  const observed = await locator.inputValue();
  return {
    ok: observed === value,
    observed_length: observed.length,
    value_sha256: createHash("sha256").update(value).digest("hex"),
    page: await inspect(activePage),
  };
}

async function performClick(activePage, rawName) {
  const name = exactText(rawName, 120, "control name");
  const locator = await exactClickLocator(activePage, name);
  const before = await pageState(activePage);
  await locator.click({ timeout: 8000 });
  await activePage.waitForTimeout(250);
  const after = await pageState(activePage);
  const changed = before.url !== after.url || before.title !== after.title || before.body_digest !== after.body_digest || JSON.stringify(before.status) !== JSON.stringify(after.status) || JSON.stringify(before.alerts) !== JSON.stringify(after.alerts);
  return { ok: changed, state_changed: changed, before, page: await inspect(activePage) };
}

async function validateWorkflowSteps(rawSteps) {
  if (!Array.isArray(rawSteps) || rawSteps.length < 3 || rawSteps.length > 5) throw new Error("A browser mission must contain three to five exact steps.");
  const steps = [];
  const fieldNames = new Set();
  for (let index = 0; index < rawSteps.length; index += 1) {
    const raw = rawSteps[index];
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("The browser mission step schema is invalid.");
    const expectedKind = index === 0 ? "navigate" : index === rawSteps.length - 1 ? "click" : "fill";
    if (raw.kind !== expectedKind) throw new Error("The browser mission step order is invalid.");
    if (expectedKind === "navigate") {
      if (Object.keys(raw).sort().join(",") !== "accessible_name,kind,url" || !await allowedUrl(raw.url)) throw new Error("The browser mission navigation is outside policy.");
      steps.push({ kind: "navigate", url: raw.url });
    } else if (expectedKind === "fill") {
      if (Object.keys(raw).sort().join(",") !== "accessible_name,kind,url,value") throw new Error("The browser mission field schema is invalid.");
      const name = exactText(raw.accessible_name, 120, "field name");
      const value = exactText(raw.value, 500, "field value");
      if (raw.url !== "" || SENSITIVE_VALUE.test(value) || fieldNames.has(name.toLowerCase())) throw new Error("The browser mission field is outside policy.");
      fieldNames.add(name.toLowerCase());
      steps.push({ kind: "fill", accessible_name: name, value });
    } else {
      if (Object.keys(raw).sort().join(",") !== "accessible_name,kind,url") throw new Error("The browser mission control schema is invalid.");
      const name = exactText(raw.accessible_name, 120, "control name");
      if (raw.url !== "" || BLOCKED_CONTROL.test(name)) throw new Error("The browser mission control is outside policy.");
      steps.push({ kind: "click", accessible_name: name });
    }
  }
  return steps;
}

function checkpoint(result, step, index) {
  const page = result.page || {};
  const evidence = {
    index: index + 1,
    kind: step.kind,
    ok: Boolean(result.ok),
    page: { url: page.url || "", title: page.title || "", body_digest: page.body_digest || "" },
  };
  for (const key of ["http_status", "observed_length", "value_sha256", "state_changed", "before"]) {
    if (key in result) evidence[key] = result[key];
  }
  if (step.accessible_name) evidence.accessible_name = step.accessible_name;
  return evidence;
}

async function performWorkflow(activePage, rawSteps) {
  const steps = await validateWorkflowSteps(rawSteps);
  const results = [];
  for (let index = 0; index < steps.length; index += 1) {
    const step = steps[index];
    try {
      const result = step.kind === "navigate"
        ? await performNavigate(activePage, step.url)
        : step.kind === "fill"
          ? await performFill(activePage, step.accessible_name, step.value)
          : await performClick(activePage, step.accessible_name);
      results.push(checkpoint(result, step, index));
      if (!result.ok) {
        return { ok: false, completed_steps: index, failed_step: index + 1, steps: results, page: result.page, error: "A browser mission checkpoint was not verified." };
      }
    } catch (error) {
      return { ok: false, completed_steps: index, failed_step: index + 1, steps: results, page: await inspect(activePage), error: clean(error?.message || error, 300) };
    }
  }
  return { ok: true, completed_steps: steps.length, failed_step: null, steps: results, page: await inspect(activePage) };
}

async function handle(request) {
  const keys = Object.keys(request).sort().join(",");
  if (request.operation === "shutdown" && keys === "operation") return { shutdown: true };
  if (!["click", "fill", "inspect", "navigate", "workflow"].includes(request.operation)) throw new Error("Unsupported browser operation.");
  const activePage = await ensurePage();
  if (request.operation === "navigate") {
    if (keys !== "operation,request_id,url") throw new Error("The navigate request schema is invalid.");
    return { request_id: request.request_id, operation: "navigate", ...await performNavigate(activePage, request.url) };
  }
  if (request.operation === "inspect") {
    if (keys !== "operation,request_id") throw new Error("The inspect request schema is invalid.");
    return { ok: true, request_id: request.request_id, operation: "inspect", page: await inspect(activePage) };
  }
  if (request.operation === "fill") {
    if (keys !== "accessible_name,operation,request_id,value") throw new Error("The fill request schema is invalid.");
    return { request_id: request.request_id, operation: "fill", ...await performFill(activePage, request.accessible_name, request.value) };
  }
  if (request.operation === "workflow") {
    if (keys !== "operation,request_id,steps") throw new Error("The browser mission request schema is invalid.");
    return { request_id: request.request_id, operation: "workflow", ...await performWorkflow(activePage, request.steps) };
  }
  if (keys !== "accessible_name,operation,request_id") throw new Error("The click request schema is invalid.");
  return { request_id: request.request_id, operation: "click", ...await performClick(activePage, request.accessible_name) };
}

async function run() {
  context = await chromium.launchPersistentContext(PROFILE_PATH, {
    executablePath: EDGE_PATH,
    headless: false,
    chromiumSandbox: true,
    acceptDownloads: false,
    viewport: { width: 1280, height: 820 },
    args: ["--no-first-run", "--disable-features=msEdgeSidebarV2"],
  });
  context.on("dialog", (dialog) => dialog.dismiss().catch(() => {}));
  context.on("page", (newPage) => { page = newPage; });
  await context.route("**/*", async (route) => {
    if (await allowedUrl(route.request().url())) await route.continue(); else await route.abort("blockedbyclient");
  });
  page = context.pages()[0] || await context.newPage();
  emit({ type: "ready", provider: "playwright_edge", pid: process.pid, profile: "isolated_auris_profile" });
  const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
  for await (const line of lines) {
    let request;
    try {
      request = JSON.parse(line);
      const response = await handle(request);
      if (response.shutdown) break;
      emit(response);
    } catch (error) {
      emit({ ok: false, request_id: request?.request_id || "", error: clean(error?.message || error, 300) });
    }
  }
  await context.close();
}

run().catch((error) => {
  emit({ type: "startup_error", error: clean(error?.message || error, 300) });
  process.exitCode = 1;
});
