import { expect, test } from "@playwright/test";

test("patient app is installable (manifest, icons, service worker)", async ({ page, request, browserName }) => {
  const m = await request.get("/manifest.webmanifest");
  expect(m.ok()).toBeTruthy();
  const manifest = await m.json();
  expect(manifest.short_name).toBe("Rabt");
  expect(manifest.display).toBe("standalone");
  expect(manifest.theme_color).toBe("#0e8f9e");
  expect(manifest.icons.some((i: { sizes: string; purpose?: string }) => i.sizes === "512x512" && i.purpose === "maskable")).toBeTruthy();
  for (const i of manifest.icons) expect((await request.get(i.src)).ok()).toBeTruthy();

  await page.goto("/patient/case-gc05-fit?lang=en");
  await expect(page.locator('link[rel="manifest"]')).toHaveCount(1);
  await page.waitForFunction(async () => !!(await navigator.serviceWorker.getRegistration()), null, { timeout: 30000 });
  await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 30000 }).catch(() => undefined);

  if (browserName === "chromium") {
    const cdp = await page.context().newCDPSession(page);
    const { installabilityErrors } = await cdp.send("Page.getInstallabilityErrors");
    expect(installabilityErrors).toEqual([]);
  }
  const offline = await request.get("/offline.html");
  expect(offline.ok()).toBeTruthy();
});
