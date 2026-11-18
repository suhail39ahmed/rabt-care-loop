import { expect, test } from "@playwright/test";
import { API, resetDemo } from "./helpers";

/** Minimal PDF that runs JavaScript on open: must be quarantined, never shown to staff or indexed. */
function maliciousPdf(): Buffer {
  const objs = [
    "<< /Type /Catalog /Pages 2 0 R /OpenAction 4 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>",
    "<< /S /JavaScript /JS (app.alert('x')) >>",
  ];
  let body = "%PDF-1.4\n";
  const offs: number[] = [];
  objs.forEach((o, i) => {
    offs.push(body.length);
    body += `${i + 1} 0 obj\n${o}\nendobj\n`;
  });
  const xref = body.length;
  body += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n` + offs.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("");
  body += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body, "latin1");
}

test("a malicious claim PDF is quarantined and flagged on the board", async ({ page, request }) => {
  await resetDemo(request);
  const c = await (await request.get(`${API}/cases/case-gc05-fit`)).json();
  if (c.state !== "Referred") test.skip(true, `case is ${c.state}`);
  const reimb = c.options.find((o: { payment?: { mode: string } }) => o.payment?.mode === "reimbursement");
  test.skip(!reimb, "no pay-and-claim option in seed");
  const booked = await request.post(`${API}/cases/case-gc05-fit/book`, {
    headers: { "X-Rabt-Persona": "patient:fatima" },
    data: { option_id: reimb.id },
  });
  expect(booked.ok()).toBeTruthy();

  await page.goto("/patient/case-gc05-fit?lang=en");
  await page.locator('input[type="file"]').setInputFiles({ name: "receipt.pdf", mimeType: "application/pdf", buffer: maliciousPdf() });
  await expect(page.getByText("Held for review. A coordinator will contact you.")).toBeVisible({ timeout: 20000 });

  await page.goto("/board");
  await page.getByRole("button", { name: /Document flagged/ }).click();
  await expect(page.locator(".case-row").first()).toContainText("Document quarantined", { timeout: 15000 });
});
