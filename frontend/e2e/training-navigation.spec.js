import { test, expect } from "@playwright/test";

async function signIn(page, role) {
  await page.goto("/");
  await page.getByRole("button", { name: role, exact: true }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.locator(".role-guide strong").first()).toBeVisible();
}

async function seedExercise(page) {
  const options = { headers: { "X-SimForge-Request": "1" } };
  const run = await page.request.post("/api/runs", {
    ...options,
    data: { scenario_key: "mmorpg_economy", population: 20, horizon: 30 },
  });
  expect(run.ok()).toBeTruthy();
  const dataset = await page.request.post("/api/datasets", {
    ...options,
    data: { scenario_key: "supplier_risk", seed: 2026 },
  });
  expect(dataset.ok()).toBeTruthy();
  return { run: await run.json(), dataset: await dataset.json() };
}

for (const [role, previousPage] of [
  ["learner", "Simulation runs"],
  ["admin", "Activity & audit"],
]) {
  test(`${role} opens training datasets after ${previousPage}, even with a slow response`, async ({
    page,
  }) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await signIn(page, role);
    const { run, dataset } = await seedExercise(page);
    if (previousPage === "Activity & audit")
      await page.getByText("Advanced tools", { exact: true }).click();
    await page.getByRole("button", { name: previousPage, exact: true }).click();
    if (previousPage === "Simulation runs") {
      await expect(
        page.locator(".list-row").filter({ hasText: run.title }).first(),
      ).toBeVisible();
    } else {
      await expect(page.locator("main .panel table").last()).toContainText(
        "dataset.generate",
      );
    }

    let release;
    const gate = new Promise((resolve) => {
      release = resolve;
    });
    await page.route("**/api/datasets", async (route) => {
      const response = await route.fetch();
      await gate;
      await route.fulfill({ response });
    });
    try {
      await page
        .getByRole("button", { name: "Training datasets", exact: true })
        .click();
      await expect(
        page.getByRole("heading", { name: "Training datasets", exact: true }),
      ).toBeVisible();
      const loadingCases = page
        .getByRole("status")
        .filter({ hasText: "Loading training datasets…" });
      await expect(loadingCases).toBeVisible();
      expect(errors).toEqual([]);
      release();
      await expect(loadingCases).toHaveCount(0);
      const entry = page
        .locator(".list-row")
        .filter({ hasText: dataset.title })
        .first();
      await expect(entry).toContainText(
        `${Object.keys(dataset.tables).length} tables`,
      );
      await entry.click();
      await expect(page).toHaveURL(new RegExp(`#/training/${dataset.id}$`));
      await page.getByRole("button", { name: /^suppliers\d+$/ }).click();
      await expect(page.locator("main .panel table").last()).toContainText(
        "S-03",
      );
      await page
        .getByRole("button", { name: "Back to Training datasets" })
        .click();
      await expect(page).toHaveURL(/#\/training$/);
      await page.goBack();
      await expect(page).toHaveURL(new RegExp(`#/training/${dataset.id}$`));
      await page.reload();
      await expect(
        page.getByRole("heading", { name: dataset.title, exact: true }),
      ).toBeVisible();
      expect(errors).toEqual([]);
    } finally {
      release();
      expect(errors, "Navigation must not crash the application").toEqual([]);
    }
  });
}

test("older dataset responses cannot replace a newer visit's case files", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await signIn(page, "learner");
  const { run, dataset } = await seedExercise(page);
  let release, started, finished;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const firstStarted = new Promise((resolve) => {
    started = resolve;
  });
  const firstFinished = new Promise((resolve) => {
    finished = resolve;
  });
  let requests = 0;
  await page.route("**/api/datasets", async (route) => {
    if (++requests !== 1) return route.continue();
    started();
    await gate;
    await route.fulfill({ json: [] });
    finished();
  });
  try {
    await page
      .getByRole("button", { name: "Training datasets", exact: true })
      .click();
    await firstStarted;
    await page
      .getByRole("button", { name: "Simulation runs", exact: true })
      .click();
    await expect(
      page.locator(".list-row").filter({ hasText: run.title }).first(),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Training datasets", exact: true })
      .click();
    await expect(
      page.locator(".list-row").filter({ hasText: dataset.title }).first(),
    ).toBeVisible();
    const staleResponse = page.waitForResponse((response) =>
      response.url().endsWith("/api/datasets"),
    );
    release();
    await firstFinished;
    await (await staleResponse).finished();
    // Let React commit the late response without refreshing the list again.
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    await expect(page.getByRole("status")).toHaveCount(0);
    await expect(
      page.locator(".list-row").filter({ hasText: dataset.title }).first(),
    ).toBeVisible();
    expect(errors).toEqual([]);
  } finally {
    release();
  }
});

test("a failed dataset request keeps the workspace usable and can be retried", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await signIn(page, "learner");
  const { dataset } = await seedExercise(page);
  let requests = 0;
  await page.route("**/api/datasets", (route) =>
    ++requests === 1
      ? route.fulfill({
          status: 503,
          json: { detail: "Dataset service temporarily unavailable" },
        })
      : route.continue(),
  );
  await page
    .getByRole("button", { name: "Training datasets", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Dataset service temporarily unavailable",
  );
  await expect(
    page.getByText("No case files yet", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(
    page.locator(".list-row").filter({ hasText: dataset.title }).first(),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("opening another case URL resets its table selection and assessment", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await signIn(page, "learner");
  const { dataset } = await seedExercise(page);
  const response = await page.request.post("/api/datasets", {
    headers: { "X-SimForge-Request": "1" },
    data: { scenario_key: "sales_decline", seed: 2027 },
  });
  expect(response.ok()).toBeTruthy();
  const second = await response.json();
  await page.goto(`/#/training/${dataset.id}`);
  await expect(
    page.getByRole("heading", { name: dataset.title, exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /^suppliers\d+$/ }).click();
  await expect(page.locator("main .panel table").last()).toContainText("S-03");
  await page
    .getByLabel("Your recommendation")
    .fill("Only belongs to the supplier case");
  await page.goto(`/#/training/${second.id}`);
  await expect(
    page.getByRole("heading", { name: second.title, exact: true }),
  ).toBeVisible();
  await expect(page.locator(".table-tabs button.active")).toContainText(
    Object.keys(second.tables)[0],
  );
  await expect(page.getByLabel("Your recommendation")).toHaveValue("");
  await expect(
    page.locator("main .panel table").last().locator("tbody tr").first(),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
