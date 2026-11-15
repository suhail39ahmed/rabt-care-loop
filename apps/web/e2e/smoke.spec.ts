import { expect, test } from "@playwright/test";

test("home board and patient shell load", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/Rabt|ر/i).first()).toBeVisible();

  await page.goto("/board");
  await expect(page.getByText(/Rabt board|HITL/i).first()).toBeVisible();

  await page.goto("/admin");
  await expect(page.getByText(/Loop-leak|False closures|Critical/i).first()).toBeVisible();
});
