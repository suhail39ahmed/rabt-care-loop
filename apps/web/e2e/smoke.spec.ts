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
  await expect(page.getByText("Approved phrase", { exact: true }).first()).toBeVisible();
});

test("patient asks the approved knowledge base and sees sources", async ({ page }) => {
  await page.goto("/patient/case-gc05-fit?lang=en");
  await page.getByRole("button", { name: /Open the assistant/ }).click();
  await page.getByRole("dialog").getByRole("textbox").fill("What does a positive FIT mean?");
  await page.getByRole("dialog").getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("dialog").locator(".cite-chip").first()).toBeVisible({ timeout: 15000 });
});
