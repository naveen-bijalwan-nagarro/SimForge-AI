import { test, expect } from "@playwright/test";

async function signIn(page, role) {
  await page.goto("/");
  await page.getByRole("button", { name: role, exact: true }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.locator(".role-guide strong").first()).toBeVisible();
}
const crumbs = (page) => page.getByRole("navigation", { name: "Breadcrumb" });

test("breadcrumbs, browser Back/Forward and reload navigate between workspace, runs and a live run", async ({
  page,
}) => {
  test.setTimeout(120000);
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await signIn(page, "learner");
  await expect(crumbs(page)).toContainText("Overview");
  await expect(page).toHaveURL(/#\/overview$/);

  // Launch a live world; its breadcrumb leads back to Simulation runs.
  await page.getByRole("button", { name: /^Scenario library/ }).click();
  await expect(page).toHaveURL(/#\/catalog$/);
  await page.getByLabel("Search scenarios").fill("Airline Operations");
  await page
    .locator(".scenario-card")
    .filter({ hasText: "Airline Operations Command" })
    .first()
    .click();
  const title = (
    await page.getByRole("dialog").getByRole("heading").first().textContent()
  ).trim();
  await page.getByLabel("Work items to generate").fill("40");
  await page
    .getByRole("button", { name: "Generate scenario datasets" })
    .click();
  await page
    .getByRole("button", { name: "Enter simulation with these datasets" })
    .click();
  await expect(crumbs(page).locator("[aria-current=page]")).toHaveText(title);
  await expect(page).toHaveURL(/#\/runs\/[^/]+$/);
  const runUrl = page.url();
  await expect(
    page.locator(".sidebar button[aria-current=page]"),
  ).toContainText("Simulation runs");

  await crumbs(page)
    .getByRole("button", { name: "Back to Simulation runs" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Your simulation runs" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/#\/runs$/);
  await expect(
    page.locator(".list-row").filter({ hasText: title }).first(),
  ).toBeVisible();

  // Browser Back returns to the run, Forward to the list; a reload keeps the page.
  await page.goBack();
  await expect(crumbs(page).locator("[aria-current=page]")).toHaveText(title);
  await page.goForward();
  await expect(
    page.getByRole("heading", { name: "Your simulation runs" }),
  ).toBeVisible();
  await page.goto(runUrl);
  await page.reload();
  await expect(crumbs(page).locator("[aria-current=page]")).toHaveText(title);

  await crumbs(page).getByRole("button", { name: "Back to Workspace" }).click();
  await expect(page).toHaveURL(/#\/overview$/);
  await expect(
    page.getByRole("heading", {
      name: "My learning workspace",
    }),
  ).toBeVisible();

  // A missing run falls back to its list instead of a blank page.
  await page.goto(runUrl.replace(/#\/runs\/.*/, "#/runs/does-not-exist"));
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Your simulation runs" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("training datasets explain their purpose and a case file links back to the list", async ({
  page,
}) => {
  test.setTimeout(90000);
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await signIn(page, "learner");
  await page
    .getByRole("button", { name: "Training datasets", exact: true })
    .click();
  const purpose = page.getByRole("region", {
    name: "What training datasets are for",
  });
  await expect(purpose).toContainText("Generate a case file");
  await expect(purpose).toContainText(
    "root cause 55, evidence 25, recommendation 20",
  );

  await page
    .getByRole("button", { name: /^Browse the \d+ training cases$/ })
    .click();
  await expect(page).toHaveURL(/#\/catalog\/data$/);
  await expect(page.locator(".filters button.active")).toHaveText(
    "Training library",
  );
  await page
    .locator(".scenario-card")
    .filter({ hasText: "Payment Fraud Spike" })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Open historical case assessment instead" })
    .click();
  await expect(crumbs(page).locator("[aria-current=page]")).toHaveText(
    "Payment Fraud Spike",
  );
  await expect(page).toHaveURL(/#\/training\/[^/]+$/);
  await expect(
    page.getByText("Scored out of 100: root cause 55"),
  ).toBeVisible();

  await crumbs(page)
    .getByRole("button", { name: "Back to Training datasets" })
    .click();
  await expect(page).toHaveURL(/#\/training$/);
  await expect(
    page
      .locator(".list-row")
      .filter({ hasText: "Payment Fraud Spike" })
      .first(),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
