import { test, expect } from "@playwright/test";
import path from "node:path";

async function signIn(page, role) {
  await page.goto("/");
  await page.getByRole("button", { name: role, exact: true }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.locator(".role-guide")).toBeVisible();
}

test("admin signs in, cancels, uses device code and signs out from the shared UI", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let enabled = false,
    authenticated = false,
    session = null,
    logouts = 0,
    model = null,
    effort = null;
  const status = () => ({
    enabled,
    authenticated,
    model,
    effort,
    installed: true,
    version: "codex-cli UI test",
    ready: enabled && authenticated,
    can_launch_login: true,
    can_configure: true,
    reason: !enabled
      ? "Enable Codex authoring in this panel"
      : authenticated
        ? "Ready for Codex authoring"
        : "Sign in to Codex from this panel",
    mode: "Test connection",
    safety: "Constrained JSON drafts",
  });
  await page.route("**/api/authoring/**", async (route) => {
    const request = route.request(),
      url = new URL(request.url());
    const json = (value) => route.fulfill({ json: value });
    if (url.pathname.endsWith("/status")) return json(status());
    if (url.pathname.endsWith("/settings")) {
      enabled = request.postDataJSON().enabled;
      return json(status());
    }
    if (url.pathname.endsWith("/models"))
      return json({
        models: [
          {
            id: "available-model",
            label: "Available test model",
            default: true,
            efforts: ["low", "medium"],
            default_effort: "low",
          },
        ],
        configured_model: "unavailable-model",
      });
    if (url.pathname.endsWith("/model")) {
      ({ model, effort } = request.postDataJSON());
      return json(status());
    }
    if (url.pathname.endsWith("/login/cancel")) {
      session = { status: "cancelled", message: "Sign-in cancelled." };
      return json(session);
    }
    if (url.pathname.endsWith("/logout")) {
      logouts++;
      authenticated = false;
      session = null;
      return json(status());
    }
    if (url.pathname.endsWith("/login")) {
      if (request.method() === "POST") {
        const device = request.postDataJSON().method === "device";
        session = {
          id: "test-login",
          status: "pending",
          message: "Complete sign-in on the official OpenAI page.",
          auth_url: device
            ? "https://auth.openai.com/codex/device"
            : "https://auth.openai.com/oauth/authorize?state=test",
          device_code: device ? "ABCD-EFGH" : null,
        };
      }
      return json(session);
    }
    return route.continue();
  });
  await signIn(page, "admin");
  await page.getByRole("button", { name: "Scenario Lab", exact: true }).click();
  const panel = page.getByTestId("codex-connection");
  await page.locator(".connection-details > summary").click();
  await panel
    .getByRole("button", { name: "Enable Codex authoring", exact: true })
    .click();
  await panel
    .getByRole("button", { name: "Sign in to Codex", exact: true })
    .click();
  await expect(
    panel.getByRole("link", { name: /Open official OpenAI sign-in/ }),
  ).toHaveAttribute("href", /auth\.openai\.com\/oauth\/authorize/);
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.getByRole("button", { name: "Scenario Lab", exact: true }).click();
  await page.locator(".connection-details > summary").click();
  await expect(
    panel.getByRole("button", { name: "Cancel sign-in" }),
  ).toBeVisible();
  await panel.getByRole("button", { name: "Cancel sign-in" }).click();
  await panel.getByRole("button", { name: "Use device-code sign-in" }).click();
  await expect(panel.locator("code")).toHaveText("ABCD-EFGH");
  await page.screenshot({
    path: path.resolve("../artifacts/codex-ui-device-login.png"),
    fullPage: true,
  });
  authenticated = true;
  session = { status: "authenticated", message: "Codex is signed in." };
  await expect(
    panel.getByText("Ready for Codex authoring", { exact: true }),
  ).toBeVisible({ timeout: 15000 });
  await expect(panel.getByLabel("Codex model")).toHaveValue("available-model");
  await panel.getByLabel("Reasoning effort").selectOption("medium");
  await panel.getByRole("button", { name: "Save SimForge model" }).click();
  expect(model).toBe("available-model");
  expect(effort).toBe("medium");
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.getByRole("button", { name: "Scenario Lab", exact: true }).click();
  await page.locator(".connection-details > summary").click();
  await expect(panel).toContainText("Ready for Codex authoring");
  page.once("dialog", (dialog) => dialog.accept());
  await panel.getByRole("button", { name: "Sign out of Codex" }).click();
  await expect(
    panel.getByRole("button", { name: "Sign in to Codex", exact: true }),
  ).toBeVisible();
  expect(logouts).toBe(1);
  await page
    .locator("header")
    .getByRole("button", { name: "Log out", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Open workspace" }),
  ).toBeVisible();
  expect(logouts).toBe(1); // App logout must never remove the local CLI credentials.
  expect(errors).toEqual([]);
});

for (const role of ["admin", "learner"]) {
  test(`${role} has visible desktop/mobile logout and returns to a clean session`, async ({
    page,
  }) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await signIn(page, role);
    if (role === "admin")
      await page
        .getByRole("button", { name: "Scenario Lab", exact: true })
        .click();
    await expect(
      page
        .locator(".sidebar-footer")
        .getByRole("button", { name: "Log out", exact: true }),
    ).toBeVisible();
    await expect(
      page
        .locator(".sidebar-footer")
        .getByRole("button", { name: "Log out", exact: true }),
    ).toBeInViewport();
    await page.setViewportSize({ width: 390, height: 844 });
    const logout = page
      .locator("header")
      .getByRole("button", { name: "Log out", exact: true });
    await expect(logout).toBeVisible();
    await logout.click();
    await expect(
      page.getByRole("button", { name: "Open workspace" }),
    ).toBeVisible();
    expect((await page.request.get("/api/auth/me")).status()).toBe(401);
    await page.getByRole("button", { name: "learner", exact: true }).click();
    await page.getByRole("button", { name: "Open workspace" }).click();
    await expect(page.locator(".role-guide strong").first()).toContainText(
      "Learner",
    );
    await expect(
      page.getByRole("button", { name: "Scenario Lab", exact: true }),
    ).toHaveCount(0);
    await expect(page).toHaveURL(/#\/overview$/);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    expect(errors).toEqual([]);
  });
}

test("live local Codex creates a validated admin draft that can be published", async ({
  page,
}) => {
  test.skip(
    process.env.SIMFORGE_LIVE_CODEX !== "1",
    "Opt-in: uses one real Codex generation, never logs out the local CLI.",
  );
  test.setTimeout(180000);
  await signIn(page, "admin");
  await page.getByRole("button", { name: "Scenario Lab", exact: true }).click();
  const panel = page.getByTestId("codex-connection");
  await page.locator(".connection-details > summary").click();
  await expect(panel.getByText("Signed in", { exact: true })).toBeVisible({
    timeout: 30000,
  });
  const enable = panel.getByRole("button", {
    name: "Enable Codex authoring",
    exact: true,
  });
  if (await enable.count()) await enable.click();
  await expect(panel.getByLabel("Codex model")).not.toHaveValue("", {
    timeout: 30000,
  });
  await panel.getByRole("button", { name: "Save SimForge model" }).click();
  await expect(
    panel.getByText("Ready for Codex authoring", { exact: true }),
  ).toBeVisible();
  const title = "Codex UI Warehouse run-" + Date.now().toString(36);
  await page
    .getByLabel("Scenario description")
    .fill(
      `Create a mock training scenario titled '${title}'. Use six warehouse systems: intake, triage, stock, picking, packing and dispatch. Connect them in an acyclic graph with a branch from triage to stock and picking, both joining at packing. A triage allocation fault causes delays. Learner is a warehouse controller, investigating and restoring deliveries within a budget. Use synthetic data only, environment_style service_app.`,
    );
  await page.getByRole("button", { name: "Generate draft with Codex" }).click();
  const review = page.locator(".draft-review").filter({ hasText: title });
  await expect(review).toBeVisible({ timeout: 145000 });
  await expect(review).toContainText("codex");
  await expect(review.locator(".fail")).toHaveCount(0);
  await page.screenshot({
    path: path.resolve("../artifacts/codex-ui-live-draft.png"),
    fullPage: true,
  });
  await review
    .getByRole("button", { name: "Publish & notify learners" })
    .click();
  await expect(
    review.getByRole("button", { name: "Published", exact: true }),
  ).toBeDisabled();
  await page
    .locator("header")
    .getByRole("button", { name: "Log out", exact: true })
    .click();
  await page.getByRole("button", { name: "learner", exact: true }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByRole("button", { name: /Notifications/ }).click();
  await expect(
    page.locator(".notification-item").filter({ hasText: title }),
  ).toBeVisible({ timeout: 12000 });
});
