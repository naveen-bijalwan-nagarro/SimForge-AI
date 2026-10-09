import { test, expect } from "@playwright/test";
import path from "node:path";

async function runFor(page) {
  await page.goto("/");
  await page.getByRole("button", { name: "learner", exact: true }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.locator(".role-guide")).toBeVisible();
  const response = await page.request.post("/api/runs", {
    headers: { "X-SimForge-Request": "1" },
    data: {
      scenario_key: "supply_chain",
      seed: 2026,
      population: 60,
      horizon: 25,
    },
  });
  expect(response.ok()).toBeTruthy();
  const run = await response.json();
  await page.goto(`/#/runs/${run.id}`);
  return run;
}

async function answer(page, answers, submit) {
  const check = page.getByRole("region", { name: "Learning assessment" });
  await expect(check.locator("fieldset")).toHaveCount(1);
  for (const [i, choice] of answers.entries()) {
    await check.getByRole("radio").nth(choice).check();
    if (i < 2)
      await check.getByRole("button", { name: "Next question" }).click();
  }
  await check.getByRole("button", { name: submit }).click();
  return check;
}

async function complete(page, run) {
  const latest = await (await page.request.get(`/api/runs/${run.id}`)).json();
  const response = await page.request.post(`/api/runs/${run.id}/advance`, {
    headers: { "X-SimForge-Request": "1" },
    data: { ticks: 25, version: latest.version },
  });
  expect(response.ok()).toBeTruthy();
  await page.reload();
  await page
    .getByRole("button", { name: "Learning review", exact: true })
    .click();
}

test("objective learning cards persist, zero gain is honest, and review fits mobile", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const run = await runFor(page);
  const check = page.getByRole("region", { name: "Learning assessment" });
  await expect(
    page.getByRole("region", { name: "Learning journey" }),
  ).toBeVisible();
  await expect(check.locator(".learning-summary > div")).toHaveCount(4);
  await expect(check).toContainText("Unavailable");
  await expect(check.locator("textarea")).toHaveCount(0);
  await answer(page, [1, 0, 2], "Save starting knowledge");
  await expect(check).toContainText("100%");
  await complete(page, run);
  await answer(page, [2, 1, 0], "Show my learning score");
  await expect(check).toContainText("0 pp");
  await expect(check).toContainText("50/100");
  await expect(
    check.getByRole("region", { name: "Objective score breakdown" }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: path.resolve("../artifacts/objective-learning-mobile.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("skipped starting check stays unavailable instead of inventing a gain", async ({
  page,
}) => {
  const run = await runFor(page);
  await complete(page, run);
  const check = await answer(page, [2, 1, 0], "Show my learning score");
  await expect(check).toContainText("Not recorded");
  await expect(check).toContainText("Unavailable");
  await expect(check).toContainText("50/100");
  await expect(check).not.toContainText("+100 pp");
});
