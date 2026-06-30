import { expect, test } from "@playwright/test";

test("空书架页面可加载并通过 Vite 代理访问 API", async ({ page, request }) => {
  const health = await request.get("/api/health");

  expect(health.ok()).toBe(true);
  expect(await health.json()).toEqual({ status: "ok", service: "read-along" });

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Read Along" })).toBeVisible();
  await expect(page.getByText("材料库还是空的")).toBeVisible();
  await expect(page.getByRole("heading", { name: "导入第一篇阅读材料" })).toBeVisible();
});

test("未知路由显示 404 并可回到书架", async ({ page }) => {
  await page.goto("/missing-route");

  await expect(page.getByRole("heading", { name: "页面不存在" })).toBeVisible();
  await page.getByRole("link", { name: /返回书架/ }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: "Read Along" })).toBeVisible();
});
