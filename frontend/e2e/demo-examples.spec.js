import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const sample = path.resolve("../samples/sample1");
const manualFixture = path.resolve("../tests/fixtures/factorypulse_scenario.json");
async function signIn(page, role) {
  await page.goto("/");
  await page.getByRole("button", { name: role, exact: true }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.locator(".role-guide strong").first()).toBeVisible();
}
async function lab(page) {
  await signIn(page, "admin");
  await page.getByRole("button", { name: "Scenario Lab", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Scenario Lab", exact: true }),
  ).toBeVisible();
}

test("admin uploads FactoryPulse references and manually publishes to an already signed-in learner", async ({
  browser,
}) => {
  test.setTimeout(120000);
  const ac = await browser.newContext(),
    lc = await browser.newContext();
  const admin = await ac.newPage(),
    learner = await lc.newPage();
  const errors = [];
  for (const p of [admin, learner])
    p.on("pageerror", (e) => errors.push(e.message));
  await lab(admin);
  await signIn(learner, "learner");
  await learner
    .getByRole("button", { name: "Scenario library", exact: true })
    .click();
  await learner.getByRole("button", { name: "Overview", exact: true }).click();
  await expect(
    admin.getByRole("button", { name: "Load brief and references" }),
  ).toHaveCount(0);
  await admin
    .getByLabel("Scenario description")
    .fill(
      fs.readFileSync(
        path.join(sample, "admin_prompt.txt"),
        "utf8",
      ),
    );
  await admin
    .getByLabel("Scenario documents (multiple files)")
    .setInputFiles([
      path.join(sample, "FactoryPulse_Operations_Brief.docx"),
      path.join(sample, "FactoryPulse_Sensor_Charts.pdf"),
      path.join(sample, "FactoryPulse_Privacy_Examples.docx"),
    ]);
  await admin
    .getByRole("button", { name: "Upload reviewed references" })
    .click();
  await expect(admin.getByText(/3 documents extracted locally/)).toBeVisible({
    timeout: 20000,
  });
  await admin
    .getByText("Review reference documents (3 selected)", { exact: true })
    .click();
  const privacy = admin
    .getByRole("region", { name: "Scenario reference documents" })
    .locator(".document-reference")
    .filter({ hasText: "FactoryPulse_Privacy_Examples.docx" });
  await privacy
    .getByText("Preview extracted text: FactoryPulse_Privacy_Examples.docx", { exact: true })
    .click();
  await expect(
    privacy.locator(".document-text"),
  ).toContainText("<EMAIL_ADDRESS>");
  await expect(
    privacy.locator(".document-text"),
  ).not.toContainText("ava.fixture@example.invalid");
  await admin
    .getByText("Review reference documents (3 selected)", { exact: true })
    .click();
  await admin.evaluate(() => window.scrollTo(0, 0));
  await admin.screenshot({
    path: path.resolve("../artifacts/demo-example-admin.png"),
    fullPage: true,
  });
  await admin.getByLabel("Authoring engine").selectOption("manual");
  const spec = JSON.parse(fs.readFileSync(manualFixture, "utf8"));
  spec.title = `FactoryPulse run-${Date.now().toString(36)}`;
  await admin.getByLabel("Scenario definition JSON").fill(JSON.stringify(spec));
  await admin
    .getByRole("button", { name: "Validate & save draft", exact: true })
    .click();
  const review = admin.locator(".draft-review").filter({ hasText: spec.title });
  await expect(
    review.getByRole("button", { name: "Publish & notify learners" }),
  ).toBeEnabled();
  await review
    .getByRole("button", { name: "Publish & notify learners" })
    .click();
  await expect(
    review.getByRole("button", { name: "Published", exact: true }),
  ).toBeDisabled();
  await learner.getByRole("button", { name: /Notifications/ }).click();
  const notice = learner
    .locator(".notification-item")
    .filter({ hasText: spec.title });
  await expect(notice).toBeVisible({ timeout: 10000 });
  await notice.click();
  await expect(learner.getByRole("dialog")).toContainText(spec.title);
  await learner.getByLabel("Close launch dialog").click();
  await learner
    .getByRole("button", { name: "Scenario library", exact: true })
    .click();
  await learner.getByLabel("Search scenarios").fill(spec.title);
  const publishedCard = learner
    .locator(".scenario-card")
    .filter({ hasText: spec.title });
  await expect(publishedCard).toBeVisible();
  await publishedCard.click();
  await learner.getByLabel("Work items to generate").fill("60");
  await learner.getByLabel("Exercise duration (simulated minutes)").fill("35");
  await learner
    .getByRole("button", { name: "Generate scenario datasets" })
    .click();
  await expect(learner.getByText("relationship checks passed")).toBeVisible();
  await learner
    .getByRole("button", { name: "Enter simulation with these datasets" })
    .click();
  await expect(
    learner.getByLabel("Mock application console", { exact: true }),
  ).toBeVisible();
  const baseline = learner.getByRole("region", { name: "Learning assessment" });
  await expect(baseline.locator(".learning-summary > div")).toHaveCount(4);
  for (const [i, answer] of [1, 0, 0].entries()) {
    await baseline.getByRole("radio").nth(answer).check();
    if (i < 2)
      await baseline.getByRole("button", { name: "Next question" }).click();
  }
  await baseline
    .getByRole("button", { name: "Save starting knowledge" })
    .click();
  await expect(baseline).toContainText("66.7%");
  await learner
    .getByRole("button", { name: "Start playback", exact: true })
    .click();
  await expect(
    learner.locator(".service-work-list button").first(),
  ).toBeVisible({ timeout: 15000 });
  await learner
    .getByRole("button", { name: "Pause simulation", exact: true })
    .click();
  for (let i = 0; i < 6; i++)
    await learner
      .getByRole("button", { name: "Step one simulated minute" })
      .click();
  await learner
    .locator(".action-card")
    .filter({ hasText: "Investigate source signals" })
    .getByRole("button", { name: "Commit action" })
    .click();
  await learner
    .getByRole("button", { name: "Diagnose & act", exact: true })
    .click();
  await learner
    .getByLabel("First failing system")
    .selectOption(spec.incident_node);
  await learner
    .locator(".diagnosis-form label")
    .filter({ hasText: spec.cause })
    .locator("input")
    .check();
  await learner.getByRole("button", { name: "Submit diagnosis" }).click();
  await learner
    .locator(".action-card")
    .filter({ hasText: "Repair the source" })
    .getByRole("button", { name: "Commit action" })
    .click();
  await learner
    .getByRole("button", { name: "Complete run", exact: true })
    .click();
  await expect(learner.getByText(/Dynamic scorecard/)).toBeVisible();
  const runId = learner.url().split("/").pop();
  const report = await (
    await learner.request.get(`/api/runs/${runId}/report`)
  ).json();
  expect(report.comparison.loss_avoided).toBeGreaterThan(0);
  const assessment = learner.getByRole("region", {
    name: "Learning assessment",
  });
  for (const [i, answer] of [2, 1, 0].entries()) {
    await assessment.getByRole("radio").nth(answer).check();
    if (i < 2)
      await assessment.getByRole("button", { name: "Next question" }).click();
  }
  await expect(assessment.locator("textarea")).toHaveCount(0);
  await assessment
    .getByRole("button", { name: "Show my learning score" })
    .click();
  await expect(assessment).toContainText("+33.3 pp");
  await expect(assessment).toContainText("100/100");
  await expect(
    assessment.getByRole("heading", { name: "What you demonstrated" }),
  ).toBeVisible();
  await admin.goto(`/#/runs/${runId}`);
  await admin
    .getByRole("button", { name: "Learning review", exact: true })
    .click();
  const trainer = admin.getByRole("region", { name: "Learning assessment" });
  await expect(trainer).toContainText("100/100");
  await expect(trainer.locator("textarea")).toHaveCount(0);
  await expect(
    trainer.getByRole("button", { name: "Save trainer review" }),
  ).toHaveCount(0);
  await expect(trainer.getByRole("radio")).toHaveCount(0);
  await learner.reload();
  await learner
    .getByRole("button", { name: "Learning review", exact: true })
    .click();
  await expect(
    learner.getByRole("region", { name: "Learning assessment" }),
  ).toContainText("100/100");
  await admin.screenshot({
    path: path.resolve("../artifacts/demo-example-trainer.png"),
    fullPage: true,
  });
  await learner.screenshot({
    path: path.resolve("../artifacts/demo-example-debrief.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
  await ac.close();
  await lc.close();
});

test("failed checks can be revised in Scenario Lab and privacy preview screens the brief", async ({
  page,
}) => {
  await lab(page);
  await page
    .getByLabel("Scenario description")
    .fill(
      "Create a synthetic logistics exercise. Contact fixture@example.test. api_key=demo_placeholder_not_a_live_key",
    );
  await page.getByRole("button", { name: "Preview privacy checks" }).click();
  await expect(page.getByLabel("Scenario description")).toHaveValue(
    /fixture@example.test/,
  );
  await page
    .getByText("Sanitized brief sent to the authoring model", { exact: true })
    .click();
  await expect(
    page
      .locator(".document-text")
      .filter({ hasText: "Create a synthetic logistics exercise" }),
  ).not.toContainText("fixture@example.test");
  await expect(
    page
      .getByRole("region", { name: "Security screening log" })
      .getByText(/2 matches redacted/),
  ).toBeVisible();
  await page.getByLabel("Authoring engine").selectOption("manual");
  const spec = JSON.parse(fs.readFileSync(manualFixture, "utf8"));
  spec.title = `Revise FactoryPulse run-${Date.now().toString(36)}`;
  spec.incident_node = "delivery";
  await page.getByLabel("Scenario definition JSON").fill(JSON.stringify(spec));
  await page
    .getByRole("button", { name: "Validate & save draft", exact: true })
    .click();
  const review = page
    .locator(".draft-review")
    .filter({ hasText: spec.title })
    .first();
  await expect(
    review.getByRole("button", { name: "Publish & notify learners" }),
  ).toBeDisabled();
  await review.getByRole("button", { name: "Edit and revalidate" }).click();
  spec.incident_node = "sensors";
  await page.getByLabel("Scenario definition JSON").fill(JSON.stringify(spec));
  await page
    .getByRole("button", { name: "Validate & save revision", exact: true })
    .click();
  await expect(
    review.getByRole("button", { name: "Publish & notify learners" }),
  ).toBeEnabled();
  await expect(review).toContainText("Administrator revised");
});

test("image upload uses a reviewed description and no image bytes reach generation", async ({
  page,
}) => {
  await lab(page);
  await page
    .getByLabel("Scenario documents (multiple files)")
    .setInputFiles({
      name: "workflow.png",
      mimeType: "image/png",
      buffer: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WlFE8gAAAAASUVORK5CYII=",
        "base64",
      ),
    });
  const images = page.getByRole("region", { name: "Review image references" });
  await expect(
    images.getByRole("button", { name: "Upload reviewed references" }),
  ).toBeDisabled();
  await images
    .getByLabel("Reviewed description for workflow.png")
    .fill(
      "Sensors feed M-204 machine condition before production. Contact fixture@example.test.",
    );
  await images
    .getByRole("button", { name: "Upload reviewed references" })
    .click();
  const latest = page
    .locator(".document-reference")
    .filter({ hasText: "workflow.png" })
    .first();
  await page
    .getByText("Review reference documents (1 selected)", { exact: true })
    .click();
  await expect(latest).toContainText("1 detected PII matches redacted");
  await latest
    .getByText("Preview extracted text: workflow.png", { exact: true })
    .click();
  await expect(latest.locator("pre")).toContainText("<EMAIL_ADDRESS>");
  await expect(latest).toContainText(
    "No OCR or automatic visual PII detection",
  );
});
