import { cookies } from "next/headers";
import { locales, themes, type Locale, type Theme } from "./messages";

export async function getPreferences(): Promise<{ locale: Locale; theme: Theme }> {
  const jar = await cookies();
  const locale = jar.get("qvelt-locale")?.value;
  const theme = jar.get("qvelt-theme")?.value;
  return {
    locale: locales.find(value => value === locale) ?? "en",
    theme: themes.find(value => value === theme) ?? "system",
  };
}
