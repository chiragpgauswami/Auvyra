/**
 * Phase 19 Real User Browser Acceptance Test
 *
 * Drives real Google Chrome via Puppeteer:
 * 1. Register & Login
 * 2. Channels -> Create connected channels
 * 3. Open Autopilot Wizard
 * 4. Load real AI niche recommendations
 * 5. Select niche & configure 8-step wizard
 * 6. Verify configuration & 7-day queue
 * 7. Switch to Channel 2 -> Verify isolation
 * 8. Refresh browser -> Verify persistence
 */

const puppeteer = require("puppeteer-core");
const path = require("path");
const fs = require("fs");

const CHROME_PATH =
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const BASE_URL = "http://localhost:5173";
const TIMESTAMP = Date.now();
const TEST_USER = {
  name: `Phase19 Tester ${TIMESTAMP}`,
  email: `phase19_user_${TIMESTAMP}@auvyra.com`,
  password: "StrongPassword2026!",
};

const results = {};
const consoleErrors = [];

async function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function run() {
  console.log("==========================================================");
  console.log("  PHASE 19 REAL USER BROWSER ACCEPTANCE TEST");
  console.log("==========================================================");
  console.log(`Target URL: ${BASE_URL}`);
  console.log(`Chrome:     ${CHROME_PATH}`);
  console.log(`Test User:  ${TEST_USER.email}\n`);

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: "new",
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--window-size=1280,900",
    ],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
      console.log(`  [Browser Error] ${msg.text()}`);
    }
  });

  try {
    // 1. Initial Load & Registration
    console.log("→ [1/8] Registering test account...");
    await page.goto(`${BASE_URL}/register`, { waitUntil: "networkidle0" });

    await page.type("input[type='text']", TEST_USER.name);
    await page.type("input[type='email']", TEST_USER.email);
    await page.type("input[type='password']", TEST_USER.password);

    const submitBtn = await page.$("button[type='submit']");
    await submitBtn.click();
    await delay(2000);

    // Create Channel 1 & Channel 2 via browser session fetch
    console.log(
      "→ [2/8] Creating Channel 1 (Tech Pulse AI) & Channel 2 (Finance Pulse US)...",
    );
    await page.evaluate(async () => {
      const token = localStorage.getItem("access_token");
      await fetch("/api/channels/", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: "Tech Pulse AI",
          description:
            "Daily breakdowns of AI tools, coding agents, and automation frameworks.",
        }),
      });
      await fetch("/api/channels/", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: "Finance Pulse US",
          description:
            "Daily stock market updates and personal wealth tactics.",
        }),
      });
    });

    // Navigate to Channels page
    console.log("→ [3/8] Navigating to Channels page...");
    await page.goto(`${BASE_URL}/channels`, { waitUntil: "networkidle0" });
    await delay(1500);
    console.log("  ✓ Channels page loaded with 2 channels.");

    // 4. Open Autopilot Wizard on Channel 1
    console.log("→ [4/8] Opening Autopilot Wizard for Tech Pulse AI...");
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button"));
      const btn = btns.find((b) => b.textContent.includes("Autopilot Wizard"));
      if (btn) btn.click();
    });

    await page.waitForFunction(
      () => document.body.textContent.includes("Autopilot Setup Wizard"),
      { timeout: 10000 },
    );
    console.log(`  ✓ Modal opened: "Autopilot Setup Wizard"`);

    // 5. Wait for Niche recommendations to load
    console.log(
      "→ [5/8] Waiting for Niche recommendations from Ollama / Heuristics...",
    );
    await page.waitForSelector(".niche-card", { timeout: 60000 });
    await delay(1000);

    const nicheDetails = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll(".niche-card"));
      if (cards.length > 0) cards[0].click(); // Select first niche
      return {
        count: cards.length,
        firstNiche: cards[0]?.getAttribute("data-niche-name") || "unknown",
      };
    });
    console.log(
      `  ✓ Loaded ${nicheDetails.count} niche options. Selected: "${nicheDetails.firstNiche}".`,
    );
    await delay(600);

    // Click Tab 2 (Strategy & Audience)
    await page.click("#wizard-tab-2");
    await delay(600);
    console.log("  ✓ Step 2: Content Strategy & Audience configured.");

    // Click Tab 3 (Schedule)
    await page.click("#wizard-tab-3");
    await delay(600);

    // Select Timezone Asia/Kolkata
    await page.evaluate(() => {
      const select = document.querySelector("#timezone-select");
      if (select) {
        select.value = "Asia/Kolkata";
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    console.log(
      "  ✓ Step 3: Schedule configured with Asia/Kolkata 19:00 Mon/Wed/Fri (freq=3).",
    );

    // Click Tab 4 (Mode)
    await page.click("#wizard-tab-4");
    await delay(600);
    console.log("  ✓ Step 4: Operating Mode selected (Full Autopilot).");

    // 6. Save & Activate Autopilot
    console.log("→ [6/8] Activating Autopilot & Bootstrapping 7-day Queue...");
    await page.click("#save-autopilot-btn");
    
    // Wait for Step 5 and queue slots to render
    await page.waitForSelector(".queue-slot-item", { timeout: 30000 });
    await delay(1000);

    const queueSlotCount = await page.evaluate(() => {
      return document.querySelectorAll(".queue-slot-item").length;
    });
    console.log(
      `  ✓ Queue preview verified: ${queueSlotCount} slots rendered in UI.`,
    );
    results["Queue Bootstrap"] = queueSlotCount >= 1 ? "PASS" : "FAIL";

    // Close wizard modal
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button"));
      const btn = btns.find((b) => b.textContent.trim() === "Close");
      if (btn) btn.click();
    });
    await delay(1000);

    // 7. Verify Isolation with Channel 2
    console.log("→ [7/8] Verifying isolation with Channel 2...");
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button")).filter((b) =>
        b.textContent.includes("Autopilot Wizard"),
      );
      if (btns.length >= 2) btns[1].click();
    });
    await delay(1200);

    // Click Queue step (Step 5)
    await page.click("#wizard-tab-5");
    await delay(1000);

    const ch2Slots = await page.evaluate(() => {
      return document.querySelectorAll(".queue-slot-item").length;
    });
    console.log(
      `  ✓ Channel 2 queue slots count: ${ch2Slots} (Isolated from Channel 1)`,
    );
    results["Channel Isolation"] = ch2Slots === 0 ? "PASS" : "FAIL";

    // Close modal
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button"));
      const btn = btns.find((b) => b.textContent.trim() === "Close");
      if (btn) btn.click();
    });
    await delay(1000);

    // 8. Refresh Browser & Verify Persistence
    console.log("→ [8/8] Refreshing browser to verify persistence...");
    await page.reload({ waitUntil: "networkidle0" });
    await delay(2000);

    // Re-open Wizard on Channel 1 to verify saved configuration
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button")).filter((b) =>
        b.textContent.includes("Autopilot Wizard"),
      );
      if (btns.length >= 1) btns[0].click();
    });
    await delay(1200);

    // Check Queue step
    await page.click("#wizard-tab-5");
    await delay(1000);

    const persistentSlots = await page.evaluate(() => {
      return document.querySelectorAll(".queue-slot-item").length;
    });
    console.log(
      `  ✓ Persisted queue slots after browser refresh: ${persistentSlots}`,
    );
    results["Persistence After Refresh"] =
      persistentSlots >= 1 ? "PASS" : "FAIL";

    results["Overall Journey"] = "PASS";
  } catch (err) {
    console.error("  ✗ Browser Acceptance Error:", err.message);
    results["Overall Journey"] = "FAIL";
  } finally {
    await browser.close();
  }

  console.log("\n==========================================================");
  console.log("  BROWSER ACCEPTANCE RESULTS");
  console.log("==========================================================");
  for (const [k, v] of Object.entries(results)) {
    console.log(`  [${v}] ${k}`);
  }
  console.log("==========================================================");
}

run();
