import fs from "node:fs";
import { expect, test } from "@playwright/test";
import { PATIENT_LOCALES, RTL, untranslated } from "./helpers";

/**
 * i18n audit: every patient screen in every locale (normal and easy mode) and every staff screen in EN/AR
 * must have no hard-coded English UI text. Writes per-locale coverage to test-results/i18n-coverage.json.
 */
const PATIENT_ROUTES = ["/patient/case-gc01-fatima", "/patient/case-gc05-fit", "/patient/case-gc10-closure", "/patient/case-gc11-senior"];
const STAFF_ROUTES = ["/", "/board?focus=case-gc02-bp", "/admin", "/insurer", "/no-such-page"];
const coverage: Record<string, { checked: number; untranslated: number }> = {};

function record(lang: string, total: number, bad: number) {
  coverage[lang] = coverage[lang] || { checked: 0, untranslated: 0 };
  coverage[lang].checked += total;
  coverage[lang].untranslated += bad;
}

test.describe.configure({ mode: "serial" });

for (const lang of PATIENT_LOCALES.filter((l) => l !== "en")) {
  test(`patient screens are fully translated: ${lang}`, async ({ page }) => {
    // Phone width: long words (Malayalam, Bengali) and large easy-mode text must not overflow sideways.
    await page.setViewportSize({ width: 390, height: 844 });
    for (const route of PATIENT_ROUTES) {
      for (const easy of [0, 1]) {
        await page.goto(`${route}?lang=${lang}&easy=${easy}`);
        await expect(page.locator("html")).toHaveAttribute("lang", lang, { timeout: 30000 });
        await expect(page.locator("html")).toHaveAttribute("dir", RTL.includes(lang) ? "rtl" : "ltr");
        await page.locator(".stepper").waitFor({ timeout: 30000 });
        const u = await untranslated(page, lang);
        record(lang, u.total, u.hits.length);
        expect(u.hits, `${route} easy=${easy}`).toEqual([]);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        expect(overflow, `${route} easy=${easy} horizontal overflow`).toBeLessThanOrEqual(1);
      }
    }
  });
}

test("staff screens are fully translated: ar", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("rabt.lang.staff", "ar"));
  for (const route of STAFF_ROUTES) {
    await page.goto(route);
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl", { timeout: 30000 });
    await page.waitForLoadState("networkidle");
    const u = await untranslated(page);
    record("ar-staff", u.total, u.hits.length);
    expect(u.hits, route).toEqual([]);
  }
});

test("language choice persists and can be switched anywhere", async ({ page }) => {
  await page.goto("/patient/case-gc05-fit?lang=en");
  await page.getByRole("combobox", { name: /Language/i }).first().selectOption("ur");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.goto("/patient/case-gc05-fit");
  await expect(page.locator("html")).toHaveAttribute("lang", "ur", { timeout: 30000 });
});

test.afterAll(() => {
  const report = Object.fromEntries(
    Object.entries(coverage).map(([k, v]) => [k, { ...v, coverage_pct: v.checked ? Math.round((1 - v.untranslated / v.checked) * 1000) / 10 : 100 }])
  );
  fs.mkdirSync("test-results", { recursive: true });
  fs.writeFileSync("test-results/i18n-coverage.json", JSON.stringify(report, null, 2));
  console.log("i18n coverage", JSON.stringify(report));
});
