import { test, expect } from "@playwright/test";
import path from "node:path";

const shot = (page, name) =>
  page.screenshot({
    path: path.resolve(`../artifacts/${name}.png`),
    fullPage: true,
  });

async function signIn(page, role) {
  await page.goto("/");
  await page.getByRole("button", { name: role, exact: true }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.locator(".role-guide")).toBeVisible();
}

function watch(page, errors) {
  page.on("pageerror", (e) => errors.push(e.message));
}

test("learner investigates a crisis world: 3D, evidence, commander, diagnosis, scorecard", async ({
  page,
}) => {
  test.setTimeout(180000);
  const errors = [];
  watch(page, errors);
  await signIn(page, "learner");
  await page.getByRole("button", { name: /^Scenario library/ }).click();
  await page.getByLabel("Search scenarios").fill("Pandemic");
  await page
    .locator(".scenario-card")
    .filter({ hasText: "Pandemic Command Centre" })
    .click();
  await page.getByLabel("Work items to generate").fill("80");
  await page
    .getByRole("button", { name: "Generate scenario datasets" })
    .click();
  await page
    .getByRole("button", { name: "Enter simulation with these datasets" })
    .click();
  for (let i = 0; i < 15; i++)
    await page
      .getByRole("button", { name: "Step one simulated minute" })
      .click();
  await page.getByText("Data & visual tools", { exact: true }).click();
  await page.getByRole("button", { name: "Live 3D", exact: true }).click();
  await expect(page.locator(".world3d canvas")).toBeVisible({ timeout: 30000 });
  await page.waitForTimeout(1500);
  await shot(page, "world-live-3d");
  await page.getByRole("button", { name: "Evidence", exact: true }).click();
  await expect(page.locator(".evidence-card").first()).toBeVisible({
    timeout: 20000,
  });
  await page.getByLabel("Evidence perspective").selectOption("medical");
  await expect(page.locator(".evidence-card").first()).toBeVisible();
  await shot(page, "world-evidence-locker");
  await expect(
    page.getByRole("button", { name: "Agent population", exact: true }),
  ).toHaveCount(0);
  await page.getByText("Data & visual tools", { exact: true }).click();
  await page
    .getByRole("button", { name: "Agent council", exact: true })
    .click();
  await page.getByRole("button", { name: "Ask the commander" }).click();
  await expect(page.locator(".plan-row").first()).toBeVisible();
  await page
    .getByRole("button", { name: "Diagnose & act", exact: true })
    .click();
  await page
    .getByLabel("First failing system")
    .selectOption({ label: "Community infections" });
  await page.locator(".diagnosis-form input[type=radio]").first().check();
  await page.getByRole("button", { name: "Submit diagnosis" }).click();
  await expect(page.getByText(/Submitted at minute/)).toBeVisible();
  await page.getByRole("button", { name: "Complete run", exact: true }).click();
  await expect(page.getByText(/Dynamic scorecard ·/)).toBeVisible({
    timeout: 30000,
  });
  await expect(page.getByText("Connected scenarios")).toBeVisible();
  await shot(page, "world-debrief-scorecard");
  expect(errors).toEqual([]);
});

test("ML failure lab, dataset studio and scenario graph", async ({ page }) => {
  test.setTimeout(180000);
  const errors = [];
  watch(page, errors);
  await signIn(page, "learner");
  await page
    .getByRole("button", { name: "Scenario library", exact: true })
    .click();
  await page
    .getByRole("tab", { name: "ML investigations", exact: true })
    .click();
  await page.getByRole("button", { name: /^Bad-prediction drills/ }).click();
  await page
    .locator(".scenario-card")
    .filter({ hasText: "Schema change (units)" })
    .first()
    .click();
  await expect(page.getByText(/Offline the model looked fine/)).toBeVisible({
    timeout: 60000,
  });
  await shot(page, "mllab-production");
  await page.getByRole("tab", { name: /Investigate/ }).click();
  await page.getByRole("button", { name: /Serving pipeline trace/ }).click();
  await page.getByRole("button", { name: /Producer schema registry/ }).click();
  await expect(page.locator(".probe-result")).toHaveCount(2, {
    timeout: 30000,
  });
  await shot(page, "mllab-investigate");
  await page.getByRole("tab", { name: /Fix/ }).click();
  await page
    .locator(".option")
    .filter({ hasText: "Schema change (units)" })
    .locator("input")
    .check();
  await page.getByRole("button", { name: "Add fix" }).click();
  await page.getByLabel("Fix", { exact: true }).selectOption("fix_units");
  await page
    .getByLabel("Feature", { exact: true })
    .selectOption("invoice_amount");
  await page
    .getByRole("button", { name: /Retrain, redeploy & rescore/ })
    .click();
  await expect(page.getByText("Your score")).toBeVisible({ timeout: 60000 });
  await page.getByRole("button", { name: "Run AI investigator" }).click();
  await expect(page.getByText(/AI investigator scored/)).toBeVisible({
    timeout: 60000,
  });
  await shot(page, "mllab-rescore");
  await page.getByText("Advanced tools", { exact: true }).click();
  await page
    .getByRole("button", { name: "Dataset studio", exact: true })
    .click();
  await page
    .getByLabel("Simulation world (recommended datasets)")
    .selectOption("wind_turbine");
  await expect(page.getByText("What to generate and why")).toBeVisible();
  await expect(page.getByText("Schema is valid")).toBeVisible({
    timeout: 15000,
  });
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await expect(page.locator(".echart").first()).toBeVisible({ timeout: 30000 });
  await shot(page, "dataset-studio");
  await page
    .getByRole("button", { name: "Scenario graph", exact: true })
    .click();
  await expect(page.locator(".cy-graph canvas").first()).toBeVisible({
    timeout: 30000,
  });
  await shot(page, "scenario-graph");
  expect(errors).toEqual([]);
});
