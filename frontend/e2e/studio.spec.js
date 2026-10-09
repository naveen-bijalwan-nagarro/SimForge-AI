import { test, expect } from "@playwright/test";
import path from "node:path";

test("complete a gaming simulation, inspect agents, replay and export a debrief", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByRole("button", { name: "learner", exact: true }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(
    page.getByRole("heading", {
      name: "My learning workspace",
    }),
  ).toBeVisible();
  await page.screenshot({
    path: path.resolve("../artifacts/studio-overview.png"),
    fullPage: false,
  });
  await page
    .getByRole("button", { name: "Scenario library", exact: true })
    .click();
  await page.getByLabel("Search scenarios").fill("MMORPG Economy Crisis");
  await page
    .locator(".scenario-card")
    .filter({ hasText: "MMORPG Economy Crisis" })
    .click();
  await page
    .getByRole("dialog")
    .getByLabel("Work items to generate")
    .fill("100");
  await page
    .getByRole("button", { name: "Generate scenario datasets" })
    .click();
  await expect(page.getByText("relationship checks passed")).toBeVisible();
  await page
    .getByRole("button", { name: "Enter simulation with these datasets" })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "MMORPG Economy Crisis",
      exact: true,
      level: 1,
    }),
  ).toBeVisible();
  for (let i = 0; i < 5; i++)
    await page
      .getByRole("button", { name: "Step one simulated minute" })
      .click();
  await expect(page.locator(".clock strong")).toContainText("5");
  await page.getByText("Data & visual tools", { exact: true }).click();
  await page
    .getByRole("button", { name: "Agent council", exact: true })
    .click();
  await page.getByRole("button", { name: "Convene council" }).click();
  await expect(page.locator(".agent")).toHaveCount(3);
  await page.getByRole("button", { name: "Operations", exact: true }).click();
  await page
    .locator(".action-card")
    .filter({ hasText: "Patch reward idempotency" })
    .getByRole("button", { name: "Commit action" })
    .click();
  await expect(
    page
      .locator(".action-card")
      .filter({ hasText: "Patch reward idempotency" })
      .getByRole("button"),
  ).toContainText("Committed");
  for (let i = 0; i < 5; i++)
    await page
      .getByRole("button", { name: "Step one simulated minute" })
      .click();
  await expect(page.locator(".clock strong")).toContainText("09:10:00");
  await page.screenshot({
    path: path.resolve("../artifacts/studio-world.png"),
    fullPage: true,
  });
  await page.getByText("Data & visual tools", { exact: true }).click();
  await page
    .getByRole("button", { name: "Event timeline", exact: true })
    .click();
  await page.getByRole("slider", { name: "Replay minute" }).fill("5");
  await expect(
    page.getByText("Historical inspection only.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Complete run", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "A duplicated quest-reward transaction creates unbacked currency.",
    }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export report" }).click();
  expect((await download).suggestedFilename()).toMatch(/simforge.*json/);
  await page.screenshot({
    path: path.resolve("../artifacts/studio-debrief.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: path.resolve("../artifacts/studio-mobile.png"),
    fullPage: false,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});

test("training, synthesis and a local SQLite integration work through the UI", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "admin", exact: true }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page
    .getByRole("button", { name: "Scenario library", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Training library", exact: true })
    .click();
  await page
    .getByRole("button")
    .filter({
      has: page.getByRole("heading", {
        name: "Supplier Delivery Risk",
        exact: true,
      }),
    })
    .click();
  await page
    .getByRole("button", { name: "Open historical case assessment instead" })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Supplier Delivery Risk",
      exact: true,
      level: 1,
    }),
  ).toBeVisible();
  await page.getByLabel("Root cause").selectOption({
    label: "Supplier S-03 deterioration is causing late inbound deliveries",
  });
  await page.getByLabel("Evidence labels").fill("S-03, late, lead_time, stock");
  await page
    .getByLabel("Your recommendation")
    .fill("alternate supplier buffer contract expedite");
  await page.getByRole("button", { name: "Submit assessment" }).click();
  await expect(page.locator(".assessment-result strong")).toHaveText(
    "100 / 100",
  );
  await page.getByText("Advanced tools", { exact: true }).click();
  await page
    .getByRole("button", { name: "Generator lab", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Generate dataset", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Generated records" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Local integrations", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Create integration", exact: true })
    .click();
  await page
    .locator(".connector")
    .last()
    .getByRole("button", { name: "Export", exact: true })
    .click();
  await expect(page.getByText("10 tables exported")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Scenario Lab", exact: true }),
  ).toHaveCount(1);
});
