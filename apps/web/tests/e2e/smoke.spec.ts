import { expect, test } from "@playwright/test";

test.describe("smoke", () => {
  test("unauthenticated root redirects to /login", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.ok()).toBe(true);
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
  });

  test("signup page renders and validates locally", async ({ page }) => {
    await page.goto("/signup");
    await expect(page.getByRole("heading", { name: "Sign up" })).toBeVisible();
    await page.getByRole("button", { name: /sign up/i }).click();
    await expect(page.getByText("Enter a valid email address")).toBeVisible();
  });

  test("login page renders and validates locally", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
    await page.getByLabel("Email").fill("not-an-email");
    await page.getByRole("button", { name: /log in/i }).click();
    await expect(page.getByText("Enter a valid email address")).toBeVisible();
  });
});
