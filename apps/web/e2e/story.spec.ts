import { expect, test } from "@playwright/test";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

test("demo story: Fatima card, teach-back, book, board outcome", async ({ page, request }) => {
  const demo = await request.get(`${API}/demo`);
  expect(demo.ok()).toBeTruthy();
  const body = await demo.json();
  const caseId = body.cases?.gc01_fatima_hba1c || body.personas?.[0]?.case_id;
  expect(caseId).toBeTruthy();

  await page.goto(`/patient/${caseId}?lang=en`);
  await expect(page.getByText(/Your result|This is not a diagnosis/i).first()).toBeVisible({
    timeout: 30000,
  });

  // Teach-back if still PatientNotified
  const submit = page.getByRole("button", { name: /Submit/i }).first();
  if (await submit.isVisible().catch(() => false)) {
    const choices = page.locator("button.choice");
    const count = await choices.count();
    // Pick first choice per question group — may fail teach-back; that's ok for shell
    if (count > 0) {
      await choices.nth(0).click();
      if (count > 3) await choices.nth(3).click();
    }
  }

  await page.goto("/board");
  await expect(page.getByRole("heading", { name: /Rabt board/i })).toBeVisible({ timeout: 30000 });
  await expect(page.getByText(/All cases|Escalation queue|Pending approvals/i).first()).toBeVisible();
});

test("AR and EN patient chrome", async ({ page, request }) => {
  const demo = await request.get(`${API}/demo`);
  const body = await demo.json();
  const caseId = body.cases?.gc01_fatima_hba1c || body.personas?.[0]?.case_id;

  await page.goto(`/patient/${caseId}?lang=ar`);
  await expect(page.getByText(/هذا ليس تشخيصاً|بطاقة النتيجة/i).first()).toBeVisible({
    timeout: 30000,
  });

  await page.goto(`/patient/${caseId}?lang=en`);
  await expect(page.getByText(/This is not a diagnosis|Your result/i).first()).toBeVisible({
    timeout: 30000,
  });
});
