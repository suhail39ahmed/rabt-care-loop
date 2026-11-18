import { expect, test } from "@playwright/test";
import { resetDemo } from "./helpers";

test("senior patient gets easy mode, one step per screen, and a call-me button the board sees", async ({ page, request }) => {
  await resetDemo(request);
  await page.goto("/patient/case-gc11-senior?lang=en");
  await expect(page.locator("html")).toHaveClass(/easy-mode/, { timeout: 30000 });
  await expect(page.getByText("We turned on easy mode to help")).toBeVisible();
  await expect(page.getByText(/Step 1 of \d/)).toBeVisible();
  const size = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
  expect(size).toBeGreaterThanOrEqual(20);
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText(/Step 2 of \d/)).toBeVisible();
  await page.getByRole("button", { name: /Call me instead/ }).first().click();
  await expect(page.getByText("A coordinator will call you soon.").first()).toBeVisible({ timeout: 15000 });

  await page.goto("/board");
  await page.getByRole("button", { name: /Senior \/ assisted/ }).click();
  const row = page.locator(".case-row", { hasText: "Saeed" });
  await expect(row).toBeVisible({ timeout: 15000 });
  await expect(row).toContainText("Assisted");
  await expect(row).toContainText("Call requested");
});

test("easy mode can be switched off and on anywhere", async ({ page }) => {
  await page.goto("/patient/case-gc05-fit?lang=en");
  const toggle = page.getByRole("button", { name: /Easy mode/ });
  await expect(toggle).toHaveAttribute("aria-pressed", "false", { timeout: 30000 });
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText(/Step 1 of/)).toBeVisible();
});
