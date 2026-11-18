import { expect, test } from "@playwright/test";
import { resetDemo } from "./helpers";

test("follow-up tracker flags a delayed result, a missed visit and an unowned case; taking ownership clears it", async ({ page, request }) => {
  await resetDemo(request);
  await page.goto("/board?view=tracker");
  const tracker = page.locator("section.tracker");
  await expect(tracker.getByRole("heading", { name: "Follow-up tracker" })).toBeVisible({ timeout: 30000 });

  const missed = tracker.locator("tr", { hasText: "case-gc13-missed" });
  await expect(missed).toContainText("Missed visit", { timeout: 15000 });
  await expect(missed).toContainText("Appointment time passed with no attendance recorded");
  await expect(missed).toContainText("Dr Aisha");

  const delayed = tracker.locator("tr", { hasText: "case-gc12-result" });
  await expect(delayed).toContainText("Result delayed");
  await expect(delayed).toContainText("Overdue");
  await expect(delayed).toContainText("Dr Khan");

  await tracker.locator("button.chip", { hasText: "Unowned" }).click();
  const unowned = tracker.locator("tr", { hasText: "case-gc07-data" });
  await expect(unowned.locator(".tag", { hasText: "Unowned" }).first()).toBeVisible();
  await unowned.getByRole("button", { name: "Take ownership" }).click();
  await expect(page.getByText("Ownership updated").first()).toBeVisible({ timeout: 15000 });
  await tracker.locator("button.chip", { hasText: "Open cases" }).click();
  const owned = tracker.locator("tr", { hasText: "case-gc07-data" });
  await expect(owned).toContainText("Coordinator Sara");
  await expect(owned.locator(".tag", { hasText: "Unowned" })).toHaveCount(0);

  // The critical escalated case is never without an owner.
  await expect(tracker.locator("tr", { hasText: "case-gc02-bp" })).toContainText("On-call supervisor");
});

test("board rows show the owner and follow-up flags; split screen opens the tracker", async ({ page, request }) => {
  await resetDemo(request);
  await page.goto("/board");
  const row = page.locator(".case-row", { hasText: "Joel" });
  await expect(row).toContainText("Missed visit", { timeout: 30000 });
  await expect(row).toContainText("Owner");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/demo/split?tracker=1");
  await expect(page.locator('iframe[title="Rabt board"]')).toHaveAttribute("src", /view=tracker/);
  await page.getByRole("button", { name: "Hide tracker" }).click();
  await expect(page.locator('iframe[title="Rabt board"]')).not.toHaveAttribute("src", /view=tracker/);
});
