import { expect, test } from "@playwright/test";

test("home board and patient shell load", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/Rabt|ر/i).first()).toBeVisible();

  await page.goto("/board");
  await expect(page.getByText(/Rabt board|HITL/i).first()).toBeVisible();

  await page.goto("/admin");
  await expect(page.getByText(/Loop-leak|False closures|Critical/i).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "AI layer" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Knowledge base review" })).toBeVisible();

  await page.goto("/insurer");
  await expect(page.getByRole("heading", { name: /Insurer agent/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Agent card" })).toBeVisible();
});

test("board live translation uses the approved glossary", async ({ page }) => {
  await page.goto("/board?focus=case-gc01-fatima");
  await expect(page.getByRole("heading", { name: "Live translation" })).toBeVisible({ timeout: 30000 });
  await page.getByRole("button", { name: "Translate" }).click();
  await expect(page.getByText("Approved translation")).toBeVisible();
});

test("patient asks the approved knowledge base and sees sources", async ({ page }) => {
  await page.goto("/patient/case-gc05-fit?lang=en");
  await page.getByPlaceholder(/what does my result mean/i).fill("What does a positive FIT mean?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText(/Approved sources/i)).toBeVisible({ timeout: 15000 });
});
