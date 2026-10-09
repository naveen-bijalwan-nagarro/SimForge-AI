import { test, expect } from "@playwright/test";
import path from "node:path";

async function adminLab(page) {
  await page.goto("/");
  await page.getByRole("button", { name: "admin", exact: true }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByRole("button", { name: "Scenario Lab", exact: true }).click();
  await expect(page.getByLabel("Scenario description")).toBeVisible();
}

function pdf(text) {
  const stream = `BT /F1 12 Tf 20 700 Td (${text}) Tj ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}\nendstream`,
  ];
  let data = "%PDF-1.4\n",
    offsets = [0];
  for (let i = 0; i < objects.length; i++) {
    offsets.push(Buffer.byteLength(data));
    data += `${i + 1} 0 obj\n${objects[i]}\nendobj\n`;
  }
  const xref = Buffer.byteLength(data);
  data += `xref\n0 6\n0000000000 65535 f \n${offsets
    .slice(1)
    .map((n) => String(n).padStart(10, "0") + " 00000 n \n")
    .join("")}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(data);
}

test("multiple PDFs feed only selected references; archive is reversible and learner data survives", async ({
  page,
  browser,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/api/authoring/status*", (route) =>
    route.fulfill({
      json: {
        enabled: true,
        installed: true,
        authenticated: true,
        ready: true,
        reason: "Mocked local connection for UI test",
        mode: "Read-only draft",
        model: "test",
      },
    }),
  );
  await adminLab(page);
  const sources = page.getByRole("region", {
    name: "Scenario reference documents",
  });
  await page.getByLabel("Scenario documents (multiple files)").setInputFiles([
    {
      name: "dispatch.pdf",
      mimeType: "application/pdf",
      buffer: pdf(
        "Dispatch confirmations are checked against warehouse receiving.",
      ),
    },
    {
      name: "inventory.pdf",
      mimeType: "application/pdf",
      buffer: pdf(
        "Inventory allocations affect production and customer delivery.",
      ),
    },
    {
      name: "notes.md",
      mimeType: "text/markdown",
      buffer: Buffer.from(
        "Use synthetic records and safe response choices for this scenario.",
      ),
    },
  ]);
  await expect(sources).toContainText("3 documents extracted locally");
  await sources
    .getByText("Preview extracted text: dispatch.pdf", { exact: true })
    .first()
    .click();
  await expect(sources).toContainText("Dispatch confirmations are checked");
  await sources.getByLabel("notes.md", { exact: true }).first().uncheck();
  let payload;
  await page.route("**/api/authoring/codex", (route) => {
    payload = route.request().postDataJSON();
    return route.fulfill({
      status: 503,
      json: { detail: "Generation mocked; no inference requested" },
    });
  });
  await page
    .getByRole("button", { name: "Generate draft with Codex", exact: true })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Generation mocked" }),
  ).toBeVisible();
  expect(payload.document_ids).toHaveLength(2);
  expect(payload.prompt).toContain("supplier disruption");
  await page.getByLabel("Authoring engine").selectOption("manual");
  await page
    .getByRole("button", { name: "Validate & save draft", exact: true })
    .click();
  const queue = page.getByRole("region", {
    name: "Scenario publication queue",
  });
  const draft = queue
    .locator(".draft-review")
    .filter({
      has: page.getByRole("button", {
        name: "Publish & notify learners",
        exact: true,
      }),
    })
    .first();
  await draft
    .getByRole("button", { name: "Publish & notify learners", exact: true })
    .click();
  await expect(queue).toContainText(
    "Scenario published. Learners have been notified.",
  );
  const lc = await browser.newContext();
  const learner = await lc.newPage();
  await learner.goto("/");
  await learner.getByRole("button", { name: "learner", exact: true }).click();
  await learner.getByRole("button", { name: "Open workspace" }).click();
  await expect(learner.locator(".role-guide strong").first()).toContainText(
    "Learner",
  );
  const notifications = await (
    await learner.request.get("/api/notifications")
  ).json();
  expect(notifications.length).toBeGreaterThan(0);
  const key = notifications[0].scenario_key;
  const prepared = await (
    await learner.request.post("/api/preparations", {
      headers: { "X-SimForge-Request": "1" },
      data: { scenario_key: key, population: 30 },
    })
  ).json();
  await page
    .getByText("Fresh demo: archive previous custom scenarios", { exact: true })
    .click();
  const cleanup = page.locator("details").filter({
    has: page.getByText("Fresh demo: archive previous custom scenarios", {
      exact: true,
    }),
  });
  await expect(
    cleanup.getByRole("button", {
      name: "Archive previous scenarios and drafts",
      exact: true,
    }),
  ).toBeDisabled();
  await page.getByLabel("Type ARCHIVE to confirm cleanup").fill("ARCHIVE");
  await cleanup
    .getByRole("button", {
      name: "Archive previous scenarios and drafts",
      exact: true,
    })
    .click();
  await expect(cleanup).toContainText("records archived");
  await expect(queue).toContainText("No drafts yet");
  expect(
    (await (await learner.request.get("/api/notifications")).json()).some(
      (n) => n.scenario_key === key,
    ),
  ).toBeFalsy();
  const saved = await (
    await learner.request.get(`/api/preparations/${prepared.id}`)
  ).json();
  expect(saved.scenario.key).toBe(key);
  expect(saved.population).toBe(30);
  await page.screenshot({
    path: path.resolve("../artifacts/scenario-documents-cleanup.png"),
    fullPage: true,
  });
  await cleanup
    .getByRole("button", { name: /^Restore archive/ })
    .first()
    .click();
  await expect(cleanup).toContainText("records restored");
  await expect(queue.locator(".draft-review").first()).toBeVisible();
  expect(errors).toEqual([]);
  await lc.close();
});

test("voice dictation appends reviewed text once, stops, handles permission denial and aborts on navigation", async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.SpeechRecognition = class {
      start() {
        window.__voice = this;
      }
      stop() {
        this.stopped = true;
        this.onend?.();
      }
      abort() {
        this.aborted = true;
        this.onend?.();
      }
    };
  });
  let requests = 0;
  await page.route("**/api/authoring/codex", (route) => {
    requests++;
    return route.fulfill({ status: 503, json: { detail: "No model calls" } });
  });
  await adminLab(page);
  const voice = page.getByRole("region", {
    name: "Voice dictation controls",
  });
  await page.getByLabel("Scenario description").fill("");
  await expect(
    voice.getByRole("button", { name: "Start voice dictation" }),
  ).toBeDisabled();
  await voice.getByLabel("I agree to browser speech processing").check();
  await voice.getByLabel("Dictation language").selectOption("hi-IN");
  await voice.getByRole("button", { name: "Start voice dictation" }).click();
  expect(await page.evaluate(() => window.__voice.lang)).toBe("hi-IN");
  await page.evaluate(() => {
    const result = [
      { transcript: "Create a safe logistics training scenario" },
    ];
    result.isFinal = false;
    window.__voice.onresult({ resultIndex: 0, results: [result] });
  });
  await expect(voice).toContainText("Listening… Create a safe logistics");
  await expect(page.getByLabel("Scenario description")).toHaveValue("");
  await page.evaluate(() => {
    const result = [
      { transcript: "Create a safe logistics training scenario" },
    ];
    result.isFinal = true;
    const event = { resultIndex: 0, results: [result] };
    window.__voice.onresult(event);
    window.__voice.onresult(event);
  });
  await expect(page.getByLabel("Scenario description")).toHaveValue(
    "Create a safe logistics training scenario",
  );
  await page.locator(".codex-author").screenshot({
    path: path.resolve("../artifacts/scenario-voice-controls.png"),
  });
  await voice.getByRole("button", { name: "Stop dictation" }).click();
  expect(await page.evaluate(() => window.__voice.stopped)).toBeTruthy();
  await voice.getByRole("button", { name: "Start voice dictation" }).click();
  await page.evaluate(() => {
    window.__voice.onerror({ error: "not-allowed" });
    window.__voice.onend();
  });
  await expect(voice.getByRole("alert")).toContainText("not-allowed");
  await voice.getByRole("button", { name: "Start voice dictation" }).click();
  await page
    .getByRole("button", { name: "Scenario library", exact: true })
    .click();
  expect(await page.evaluate(() => window.__voice.aborted)).toBeTruthy();
  expect(requests).toBe(0);
});

test("unsupported voice preserves typing and multi-document upload", async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.SpeechRecognition = undefined;
    window.webkitSpeechRecognition = undefined;
  });
  await adminLab(page);
  const voice = page.getByRole("region", {
    name: "Voice dictation controls",
  });
  await expect(voice).toContainText("not supported in this browser");
  await page
    .getByLabel("Scenario description")
    .fill(
      "Create a synthetic staff training environment with linked mock records.",
    );
  await expect(page.getByLabel("Scenario description")).toHaveValue(
    "Create a synthetic staff training environment with linked mock records.",
  );
  await expect(
    page.getByLabel("Scenario documents (multiple files)"),
  ).toHaveAttribute("multiple", "");
});
