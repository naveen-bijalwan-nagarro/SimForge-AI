import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
const genericScenario = JSON.parse(
  fs.readFileSync(
    path.resolve("../tests/fixtures/factorypulse_scenario.json"),
    "utf8",
  ),
);

test("fresh authoring screens input before generation and loads the generated definition", async ({
  page,
}) => {
  const requests = [],
    sequence = [];
  page.on("request", (r) => requests.push(r.url()));
  await page.route("**/api/authoring/status*", (route) =>
    route.fulfill({
      json: {
        enabled: true,
        installed: true,
        authenticated: true,
        ready: true,
        reason: "Test connection",
        model: "test",
        mode: "Read-only draft",
      },
    }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: "admin", exact: true }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByRole("button", { name: "Scenario Lab", exact: true }).click();
  await expect(page.getByLabel("Admin prompt")).toHaveValue("");
  await expect(
    page.getByRole("button", { name: "Load brief and references" }),
  ).toHaveCount(0);
  await page
    .getByText("System prompt and safety rules", { exact: true })
    .click();
  await expect(
    page.locator("pre").filter({ hasText: "incident_node" }),
  ).toBeVisible();
  const definition = { ...genericScenario, title: "Generated incident review" };
  const response = await page.request.post("/api/scenario-drafts", {
    data: definition,
    headers: { "X-SimForge-Request": "1" },
  });
  expect(response.ok()).toBeTruthy();
  const draft = await response.json();
  await page.route("**/api/authoring/preview", async (route) => {
    sequence.push("screen");
    await route.continue();
  });
  await page.route("**/api/authoring/codex", (route) => {
    sequence.push("generate");
    return route.fulfill({
      json: { id: "ui-test-job", status: "running", engine: "codex" },
    });
  });
  await page.route("**/api/authoring/jobs/ui-test-job", (route) =>
    route.fulfill({
      json: {
        id: "ui-test-job",
        status: "ready",
        draft_id: draft.id,
        engine: "codex",
        message: "Test fixture generated",
      },
    }),
  );
  await page
    .getByLabel("Admin prompt")
    .fill(
      "Create an interruption exercise with synthetic records. Contact fixture@example.test.",
    );
  await page
    .getByRole("button", { name: "Generate draft with Codex", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Security screening log" }).first(),
  ).toContainText("EMAIL_ADDRESS");
  await expect(page.getByLabel("Scenario definition JSON")).toHaveValue(
    JSON.stringify(draft.definition, null, 2),
    { timeout: 15000 },
  );
  await expect(
    page.getByRole("button", { name: "Validate & save revision" }),
  ).toBeVisible();
  expect(sequence).toEqual(["screen", "generate"]);
  expect(
    requests.some((url) => url.includes("/api/scenario-examples")),
  ).toBeFalsy();
  await page.getByRole("button", { name: "New scenario", exact: true }).click();
  await expect(page.getByLabel("Admin prompt")).toHaveValue("");
  await expect(page.getByLabel("Scenario definition JSON")).toHaveValue(
    /New training scenario/,
  );
  await expect(
    page.getByRole("button", { name: "Validate & save draft", exact: true }),
  ).toBeVisible();
});
