import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("shell exposes a labelled composer without pretending to send", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Where shall we begin?" })).toBeVisible();
  const draft = page.getByRole("textbox", { name: "Your message" });
  await draft.fill("My idea");
  await expect(draft).toHaveValue("My idea");
  await expect(page.getByRole("button", { name: "Send message" })).toBeDisabled();
  await expect(page.getByText("Messaging is coming soon. Your draft stays in this tab.")).toBeVisible();
});

test("preferences survive reload and language changes preserve the draft", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Your message" }).fill("Private draft");
  await page.locator("#locale").selectOption("uk");
  await expect(page.locator("html")).toHaveAttribute("lang", "uk");
  await expect(page.getByRole("heading", { name: "З чого почнемо?" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Ваше повідомлення" })).toHaveValue("Private draft");
  await page.locator("#theme").selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "uk");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("textbox")).toBeEmpty();
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
  await page.locator("#locale").selectOption("ru");
  await expect(page.getByRole("heading", { name: "С чего начнём?" })).toBeVisible();
});

test("new draft asks before discarding text and supports the keyboard", async ({ page }) => {
  await page.goto("/");
  const draft = page.getByRole("textbox", { name: "Your message" });
  await draft.fill("Keep this");
  page.once("dialog", dialog => dialog.dismiss());
  await page.getByRole("button", { name: "New chat", exact: true }).click();
  await expect(draft).toHaveValue("Keep this");
  page.once("dialog", dialog => dialog.accept());
  await page.keyboard.press("Control+Shift+O");
  await expect(draft).toBeEmpty();
  await expect(draft).toBeFocused();
  await page.getByRole("button", { name: "Explain a concept" }).click();
  await expect(draft).toHaveValue("Help me understand a concept step by step.");
  await page.getByRole("button", { name: "Shape an idea" }).click();
  await expect(draft).toHaveValue("Help me understand a concept step by step.\n\nHelp me turn an idea into a clear plan.");
});

test("mobile navigation traps focus, closes with Escape and returns focus", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const trigger = page.getByRole("button", { name: "Open navigation" });
  await trigger.click();
  const drawer = page.getByRole("dialog", { name: "Navigation" });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByRole("button", { name: "New chat" })).toBeFocused();
  for (let i = 0; i < 10; i++) {
    await page.keyboard.press("Tab");
    expect(await drawer.evaluate(el => el.contains(document.activeElement))).toBe(true);
  }
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(drawer).not.toBeVisible();
  await expect(trigger).toBeFocused();
});

test("sidebar collapse preserves access to navigation", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(page.getByRole("button", { name: "Expand sidebar" })).toBeVisible();
  await page.getByRole("button", { name: "Expand sidebar" }).click();
  await expect(page.getByRole("navigation", { name: "Workspace" })).toBeVisible();
});

test("untrusted preference cookies fall back to known values", async ({ page, context }) => {
  await context.addCookies([
    { name: "qvelt-locale", value: "unknown", url: "http://127.0.0.1:3100" },
    { name: "qvelt-theme", value: "untrusted", url: "http://127.0.0.1:3100" },
  ]);
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "system");
});

test("system theme follows the OS and preferences are present before hydration", async ({ page, context }) => {
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "system");
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(27, 26, 25)");
  await context.addCookies([
    { name: "qvelt-locale", value: "uk", url: "http://127.0.0.1:3100" },
    { name: "qvelt-theme", value: "light", url: "http://127.0.0.1:3100" },
  ]);
  const html = await (await page.request.get("/")).text();
  expect(html).toContain('lang="uk"');
  expect(html).toContain('data-theme="light"');
});

for (const width of [390, 768, 1440]) {
  for (const theme of ["light", "dark"]) {
    for (const direction of ["ltr", "rtl"]) {
      test(`accessible shell ${width} ${theme} ${direction}`, async ({ page, context }, info) => {
        await context.addCookies([
          { name: "qvelt-theme", value: theme, url: "http://127.0.0.1:3100" },
        ]);
        await page.setViewportSize({ width, height: 960 });
        const errors: string[] = [];
        page.on("pageerror", error => errors.push(error.message));
        await page.goto("/");
        await page.evaluate(dir => document.documentElement.setAttribute("dir", dir), direction);
        await expect(page.getByRole("heading", { name: "Where shall we begin?" })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
        expect(errors).toEqual([]);
        await page.screenshot({ path: info.outputPath("shell.png"), fullPage: true });
      });
    }
  }
}
