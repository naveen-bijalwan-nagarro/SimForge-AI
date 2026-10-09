import { test, expect } from "@playwright/test";
import path from "node:path";

async function signIn(page, role) {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "trainer", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: role, exact: true }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.locator(".role-guide strong").first()).toBeVisible();
}

test("one Scenario Lab: admin configures a write-only API key; learner cannot access authoring", async ({
  browser,
}) => {
  const ac = await browser.newContext(),
    lc = await browser.newContext();
  const admin = await ac.newPage(),
    learner = await lc.newPage();
  const errors = [];
  for (const page of [admin, learner])
    page.on("pageerror", (e) => errors.push(e.message));
  await signIn(admin, "admin");
  await admin
    .getByRole("button", { name: "Scenario Lab", exact: true })
    .click();
  await expect(
    admin.getByRole("heading", { name: "Scenario Lab", exact: true }),
  ).toBeVisible();
  await expect(
    admin.getByRole("tab", { name: "Advanced builder", exact: true }),
  ).toHaveCount(0);
  await expect(
    admin.getByRole("tab", { name: "From an SOP", exact: true }),
  ).toHaveCount(0);
  await expect(
    admin.getByRole("button", { name: "SOP factory", exact: true }),
  ).toHaveCount(0);
  await expect(admin.getByLabel("Authoring engine")).toHaveValue("codex");
  let generations = 0;
  await admin.route("**/api/authoring/openai", async (route) => {
    if (route.request().method() === "POST") {
      generations++;
      return route.fulfill({
        status: 503,
        json: { detail: "No paid calls in UI tests" },
      });
    }
    return route.continue();
  });
  await admin
    .getByRole("button", { name: "Use OpenAI API backup", exact: true })
    .click();
  await expect(admin.getByLabel("Authoring engine")).toHaveValue("openai_api");
  expect(generations).toBe(0);
  const panel = admin.getByTestId("openai-connection");
  const fake = "sk-browser-placeholder-not-a-real-key-12345";
  await panel.getByLabel("OpenAI API key").fill(fake);
  await panel.getByRole("button", { name: "Save API connection" }).click();
  await expect(panel.getByLabel("OpenAI API key")).toHaveValue("");
  await expect(panel).toContainText("server memory");
  await expect(
    admin.getByRole("button", { name: "Generate draft with OpenAI API" }),
  ).toBeEnabled();
  const status = await admin.request.get("/api/authoring/openai");
  expect(status.ok()).toBeTruthy();
  expect(await status.text()).not.toContain(fake);
  expect(
    await admin.evaluate(() => JSON.stringify([localStorage, sessionStorage])),
  ).not.toContain(fake);
  await admin.screenshot({
    path: path.resolve("../artifacts/scenario-lab-api.png"),
    fullPage: true,
  });
  // No generation is requested: this test must never make a real billed provider call.
  await panel.getByRole("button", { name: "Remove memory-only key" }).click();
  await expect(
    admin.getByRole("button", { name: "Generate draft with OpenAI API" }),
  ).toBeDisabled();
  await admin
    .getByRole("button", { name: "Return to primary Codex", exact: true })
    .click();
  await expect(admin.getByLabel("Authoring engine")).toHaveValue("codex");
  expect(generations).toBe(0);
  await admin.reload();
  await expect(admin.getByLabel("Authoring engine")).toHaveValue("codex");
  await admin.goto("/#/sandbox");
  await expect(admin).toHaveURL(/#\/designer$/);
  await expect(
    admin.getByRole("heading", { name: "Scenario Lab", exact: true }),
  ).toBeVisible();
  await signIn(learner, "learner");
  await expect(
    learner.getByRole("button", { name: "Scenario Lab", exact: true }),
  ).toHaveCount(0);
  expect((await learner.request.get("/api/authoring/openai")).status()).toBe(
    403,
  );
  await learner.goto("/#/designer");
  await expect(learner).toHaveURL(/#\/overview$/);
  expect(errors).toEqual([]);
  await ac.close();
  await lc.close();
});

test("All exercises discovers ML investigations without a separate ML navigation page", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await signIn(page, "learner");
  await page
    .getByRole("button", { name: "Scenario library", exact: true })
    .click();
  await page.getByLabel("Search scenarios").fill("Schema change (units)");
  const card = page
    .locator(".scenario-card")
    .filter({ hasText: "Schema change (units)" })
    .first();
  await expect(card).toContainText("ML INVESTIGATION");
  await card.click();
  await expect(page).toHaveURL(/#\/mllab\/[^/]+$/);
  await page
    .getByRole("button", { name: "All challenges", exact: true })
    .click();
  await expect(page).toHaveURL(/#\/catalog\/ml$/);
  await page.reload();
  await expect(
    page.getByRole("tab", { name: "ML investigations", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  expect(errors).toEqual([]);
});
