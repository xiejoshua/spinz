import { expect, test } from "@playwright/test";

/**
 * These E2E tests assume a backend is running at `NEXT_PUBLIC_API_URL`
 * with the auth endpoints wired (T053). Without the backend reachable,
 * the form-validation tests still pass; the happy-path signup/login
 * tests are skipped via the BACKEND_REACHABLE env check.
 */

const BACKEND_REACHABLE = process.env.E2E_BACKEND_REACHABLE === "true";

test.describe("auth — form validation (backend-independent)", () => {
  test("signup shows Zod errors before hitting the server", async ({ page }) => {
    await page.goto("/signup");
    await page.getByLabel("Email").fill("not-an-email");
    await page.getByLabel("Handle").fill("X"); // too short, uppercase
    await page.getByLabel("Password").fill("short");
    await page.getByRole("button", { name: /sign up/i }).click();

    await expect(page.getByText("Enter a valid email address")).toBeVisible();
    await expect(
      page
        .getByText("Handle can only contain lowercase letters, numbers, and underscores")
        .or(page.getByText("Handle must be at least 3 characters"))
    ).toBeVisible();
    await expect(page.getByText("Password must be at least 12 characters")).toBeVisible();
  });

  test("login requires a password", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("user@example.com");
    await page.getByRole("button", { name: /log in/i }).click();
    await expect(page.getByText("Password is required")).toBeVisible();
  });
});

test.describe("auth — guard + redirect", () => {
  test("unauthenticated visit to / redirects to /login", async ({ page, context }) => {
    await context.clearCookies();
    await page.goto("/");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("unauthenticated visit to /onboarding/step-1 redirects to /login", async ({
    page,
    context,
  }) => {
    await context.clearCookies();
    await page.goto("/onboarding/step-1");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("fake session cookie reaches the shell (no validation gate at the edge)", async ({
    page,
    context,
  }) => {
    await context.addCookies([
      {
        name: "auxd_session",
        value: "fake-not-validated",
        domain: "localhost",
        path: "/",
        httpOnly: true,
        sameSite: "Lax",
      },
    ]);
    const response = await page.goto("/");
    expect(response?.ok()).toBe(true);
    await expect(page).toHaveURL(/\/$/);
  });
});

test.describe("auth — happy path (backend-required)", () => {
  test.skip(!BACKEND_REACHABLE, "Set E2E_BACKEND_REACHABLE=true with a live API to enable.");

  const handle = `e2e_${Date.now()}`;
  const email = `${handle}@example.com`;
  const password = "playwright-e2e-test-pw";

  test("signup → redirect to onboarding → session persists across reload", async ({ page }) => {
    await page.goto("/signup");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Handle").fill(handle);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign up/i }).click();

    await expect(page).toHaveURL(/\/onboarding\/step-1$/);
    await expect(page.getByRole("heading", { name: "Welcome to auxd" })).toBeVisible();

    await page.reload();
    await expect(page).toHaveURL(/\/onboarding\/step-1$/);
    await expect(page.getByRole("heading", { name: "Welcome to auxd" })).toBeVisible();
  });

  test("login with the just-created account → redirect home", async ({ page, context }) => {
    await context.clearCookies();
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /log in/i }).click();

    await expect(page).toHaveURL(/\/$/);
  });

  test("wrong password surfaces a friendly error", async ({ page, context }) => {
    await context.clearCookies();
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("definitely-wrong");
    await page.getByRole("button", { name: /log in/i }).click();
    await expect(page.getByText(/wrong email or password/i)).toBeVisible();
  });
});
