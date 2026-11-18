import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const ROUTES = ["/", "/board?focus=case-gc02-bp", "/admin", "/insurer", "/patient/case-gc05-fit", "/patient/case-gc11-senior"];

for (const width of [390, 1440]) {
  for (const lang of ["en", "ar"]) {
    test(`no axe violations at ${width}px in ${lang}`, async ({ page }) => {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
      await page.addInitScript((l) => localStorage.setItem("rabt.lang.staff", l), lang);
      for (const route of ROUTES) {
        const url = route.startsWith("/patient") ? `${route}?lang=${lang}` : route;
        await page.goto(url);
        await page.waitForLoadState("networkidle");
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        expect(overflow, `${url} horizontal overflow`).toBeLessThanOrEqual(1);
        const res = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
        expect(res.violations.map((v) => `${url}: ${v.id}`)).toEqual([]);
      }
    });
  }
}
