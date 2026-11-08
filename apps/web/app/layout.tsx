import type { Metadata } from "next";
import { getPreferences } from "../lib/preferences";
import "../styles/tokens.css";
import "./globals.css";

export const metadata: Metadata = { title: "QVELT", description: "QVELT" };

export default async function Layout({ children }: { children: React.ReactNode }) {
  const { locale, theme } = await getPreferences();
  return <html lang={locale} dir="ltr" data-theme={theme}><body>{children}</body></html>;
}
