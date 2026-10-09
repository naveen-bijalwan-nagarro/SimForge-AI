import { test, expect } from "@playwright/test";
import path from "node:path";

async function signIn(page, role) {
  await page.goto("/");
  await page.getByRole("button", { name: role, exact: true }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.locator(".role-guide strong").first()).toContainText(
    role === "admin" ? "Admin / Trainer" : "Learner",
  );
}

test("two roles: admin publishes, assigns and observes; learner receives and runs the exercise", async ({
  browser,
}) => {
  test.setTimeout(120000);
  const errors = [];
  const adminContext = await browser.newContext(),
    learnerContext = await browser.newContext();
  const admin = await adminContext.newPage(),
    learner = await learnerContext.newPage();
  for (const page of [admin, learner])
    page.on("pageerror", (e) => errors.push(e.message));
  await signIn(admin, "admin");
  await signIn(learner, "learner");
  await expect(
    learner.getByRole("button", { name: "Scenario Lab", exact: true }),
  ).toHaveCount(0);
  await admin
    .getByRole("button", { name: "Scenario Lab", exact: true })
    .click();
  await admin
    .getByText("Review and edit scenario · New training scenario", {
      exact: true,
    })
    .click();
  const editor = admin.getByLabel("Scenario definition JSON");
  const spec = JSON.parse(await editor.inputValue());
  spec.environment_style = "voxel";
  spec.title = "Settlement review run-" + Date.now().toString(36);
  await editor.fill(JSON.stringify(spec));
  await admin.getByRole("button", { name: "Validate & save draft" }).click();
  const review = admin.locator(".draft-review").filter({ hasText: spec.title });
  await expect(review.locator(".fail")).toHaveCount(0);
  await expect(
    review.getByRole("button", { name: "Publish & notify learners" }),
  ).toBeEnabled();
  await admin.screenshot({
    path: path.resolve("../artifacts/admin-publication.png"),
    fullPage: true,
  });
  await review
    .getByRole("button", { name: "Publish & notify learners" })
    .click();
  await expect(
    review.getByRole("button", { name: "Published", exact: true }),
  ).toBeDisabled();
  await learner.getByRole("button", { name: /Notifications/ }).click();
  await expect(
    learner.locator(".notification-item").filter({ hasText: spec.title }),
  ).toBeVisible({ timeout: 10000 });
  await learner
    .locator(".notification-item")
    .filter({ hasText: spec.title })
    .click();
  await expect(
    learner
      .getByRole("dialog")
      .getByRole("heading", { name: spec.title, exact: true }),
  ).toBeVisible();
  await learner.getByLabel("Work items to generate").fill("60");
  await learner
    .getByRole("button", { name: "Generate scenario datasets" })
    .click();
  await expect(learner.getByText("relationship checks passed")).toBeVisible();
  await learner
    .getByLabel("Dataset", { exact: true })
    .selectOption("workflow_steps");
  await expect(learner.locator(".relational-grid")).toContainText("work_id");
  await learner.screenshot({
    path: path.resolve("../artifacts/learner-data-preparation.png"),
    fullPage: true,
  });
  await learner
    .getByRole("button", { name: "Enter simulation with these datasets" })
    .click();
  await expect(learner.locator(".live-operations.voxel")).toBeVisible();
  await learner
    .getByRole("button", { name: "Start playback", exact: true })
    .click();
  await expect(learner.locator(".live-activity")).toContainText("processing", {
    timeout: 10000,
  });
  await learner
    .getByRole("button", { name: "Pause simulation", exact: true })
    .click();
  await expect(
    learner.getByRole("button", { name: "Start playback", exact: true }),
  ).toBeEnabled();
  const paused = await learner.locator(".clock strong").innerText();
  await learner.getByText("Data & visual tools", { exact: true }).click();
  await learner
    .getByRole("button", { name: "Live datasets", exact: true })
    .click();
  await learner
    .getByLabel("Dataset", { exact: true })
    .selectOption("live_telemetry");
  await expect(learner.locator(".relational-grid")).toContainText("health");
  await expect(learner.locator(".clock strong")).toHaveText(paused);
  await learner
    .getByRole("button", { name: "Operations", exact: true })
    .click();
  await learner.screenshot({
    path: path.resolve("../artifacts/learner-live-world.png"),
    fullPage: true,
  });
  await admin
    .getByRole("button", { name: "Assignments & results", exact: true })
    .click();
  await admin
    .getByLabel("Published scenario")
    .selectOption({ label: spec.title });
  await admin.getByLabel("Learner", { exact: true }).check();
  await admin.getByRole("button", { name: "Assign & notify learners" }).click();
  await expect(
    admin.getByText("Exercise assigned. Learners have been notified."),
  ).toBeVisible();
  await admin.locator(".list-row").filter({ hasText: spec.title }).click();
  await expect(
    admin.getByText("Observation mode", { exact: true }),
  ).toBeVisible();
  await expect(
    admin.getByRole("button", { name: "Start playback", exact: true }),
  ).toBeDisabled();
  await expect(
    admin.getByRole("button", { name: "Commit action" }).first(),
  ).toBeDisabled();
  await admin
    .getByRole("button", { name: "Training datasets", exact: true })
    .click();
  const saved = admin.getByRole("region", {
    name: "Scenario-generated datasets",
  });
  const environment = saved
    .locator(".list-row")
    .filter({ hasText: spec.title });
  await expect(environment).toContainText("Inspect only");
  await environment.click();
  await expect(
    admin
      .getByRole("dialog")
      .getByRole("button", { name: "Enter simulation with these datasets" }),
  ).toBeDisabled();
  await expect(
    admin.getByText(/Inspection only: this workload belongs/),
  ).toBeVisible();
  await learner
    .getByRole("button", { name: "My training", exact: true })
    .click();
  await expect(
    learner.locator(".assignment").filter({ hasText: spec.title }),
  ).toBeVisible();
  await learner.setViewportSize({ width: 390, height: 844 });
  await learner.screenshot({
    path: path.resolve("../artifacts/learner-assignments-mobile.png"),
    fullPage: true,
  });
  expect(
    await learner.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
  await adminContext.close();
  await learnerContext.close();
});

test("admin publishes a mock app whose generated records move through live queues", async ({
  browser,
}) => {
  test.setTimeout(120000);
  const errors = [];
  const ac = await browser.newContext(),
    lc = await browser.newContext();
  const admin = await ac.newPage(),
    learner = await lc.newPage();
  for (const page of [admin, learner])
    page.on("pageerror", (e) => errors.push(e.message));
  await signIn(admin, "admin");
  await signIn(learner, "learner");
  await admin
    .getByRole("button", { name: "Scenario Lab", exact: true })
    .click();
  await admin
    .getByText("Review and edit scenario · New training scenario", {
      exact: true,
    })
    .click();
  const editor = admin.getByLabel("Scenario definition JSON");
  const spec = JSON.parse(await editor.inputValue());
  spec.title = "Mock operations app run-" + Date.now().toString(36);
  spec.environment_style = "service_app";
  await editor.fill(JSON.stringify(spec));
  await admin.getByRole("button", { name: "Validate & save draft" }).click();
  const review = admin.locator(".draft-review").filter({ hasText: spec.title });
  await review
    .getByRole("button", { name: "Publish & notify learners" })
    .click();
  await learner.getByRole("button", { name: /Notifications/ }).click();
  const notice = learner
    .locator(".notification-item")
    .filter({ hasText: spec.title });
  await expect(notice).toBeVisible({ timeout: 10000 });
  await notice.click();
  await learner.getByLabel("Work items to generate").fill("60");
  await learner
    .getByRole("button", { name: "Generate scenario datasets" })
    .click();
  await learner
    .getByLabel("Dataset", { exact: true })
    .selectOption("work_items");
  await expect(learner.locator(".relational-grid")).toContainText("work_id");
  await learner
    .getByRole("button", { name: "Enter simulation with these datasets" })
    .click();
  await expect(
    learner.getByLabel("Mock application console", { exact: true }),
  ).toBeVisible();
  await learner
    .getByRole("button", { name: "Start playback", exact: true })
    .click();
  const records = learner.locator(".service-work-list button");
  await expect(records.first()).toBeVisible({ timeout: 15000 });
  await learner
    .getByRole("button", { name: "Pause simulation", exact: true })
    .click();
  await expect(
    learner.getByRole("button", { name: "Start playback", exact: true }),
  ).toBeEnabled();
  const workId = await records.first().locator("strong").innerText();
  await records.first().click();
  await expect(learner.locator(".service-record")).toContainText(workId);
  await expect(learner.locator(".service-record")).toContainText("Route:");
  await expect(learner.locator(".service-record")).toContainText("Deadline:");
  await learner.screenshot({
    path: path.resolve("../artifacts/learner-mock-application.png"),
    fullPage: true,
  });
  await learner.getByText("Data & visual tools", { exact: true }).click();
  await learner
    .getByRole("button", { name: "Live datasets", exact: true })
    .click();
  await learner
    .getByLabel("Dataset", { exact: true })
    .selectOption("work_items");
  await learner.getByLabel("Trace work ID").fill(workId);
  await expect(learner.locator(".relational-grid")).toContainText(workId);
  for (let i = 0; i < 10; i++)
    await learner
      .getByRole("button", { name: "Step one simulated minute" })
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
  await expect(learner.getByText(/Submitted at minute/)).toBeVisible();
  await learner
    .getByRole("button", { name: "Operations", exact: true })
    .click();
  await learner
    .locator(".action-card")
    .filter({ hasText: "Repair the source" })
    .getByRole("button", { name: "Commit action" })
    .click();
  await expect(
    learner
      .locator(".action-card")
      .filter({ hasText: "Repair the source" })
      .getByRole("button"),
  ).toContainText("Committed");
  for (let i = 0; i < 5; i++)
    await learner
      .getByRole("button", { name: "Step one simulated minute" })
      .click();
  await learner
    .getByRole("button", { name: "Complete run", exact: true })
    .click();
  await expect(learner.getByText(/Dynamic scorecard ·/)).toBeVisible();
  await expect(
    learner.getByRole("heading", { name: spec.cause, exact: true }),
  ).toBeVisible();
  const report = await learner.request.get(
    `/api/runs/${learner.url().split("/").pop()}/report`,
  );
  expect(report.ok()).toBeTruthy();
  expect((await report.json()).comparison.loss_avoided).toBeGreaterThan(0);
  await learner.screenshot({
    path: path.resolve("../artifacts/hackathon-supplier-debrief.png"),
    fullPage: true,
  });
  await learner
    .getByRole("button", { name: "Training datasets", exact: true })
    .click();
  const saved = learner.getByRole("region", {
    name: "Scenario-generated datasets",
  });
  const environment = saved
    .locator(".list-row")
    .filter({ hasText: spec.title });
  await expect(environment).toContainText("60 work items");
  await environment.click();
  const dialog = learner.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: spec.title, exact: true }),
  ).toBeVisible();
  await dialog
    .getByLabel("Dataset", { exact: true })
    .selectOption("work_items");
  await expect(dialog.getByText("60 records", { exact: true })).toBeVisible();
  if (!(await dialog.locator(".relational-grid").innerText()).includes(workId))
    await dialog
      .getByRole("button", { name: "Next rows", exact: true })
      .click();
  await expect(dialog.locator(".relational-grid")).toContainText(workId);
  await expect(
    dialog.getByRole("button", {
      name: "Enter simulation with these datasets",
    }),
  ).toBeEnabled();
  await learner.screenshot({
    path: path.resolve("../artifacts/scenario-saved-datasets.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
  await ac.close();
  await lc.close();
});
