import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "./components/app-shell";
import { LocaleProvider } from "./components/locale-provider";
import { DEFAULT_LOCALE, translate } from "./i18n";

import "./globals.css";

export const metadata: Metadata = {
  title: translate(DEFAULT_LOCALE, "meta.title"),
  description: translate(DEFAULT_LOCALE, "meta.description"),
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang={DEFAULT_LOCALE} suppressHydrationWarning>
      <body>
        <LocaleProvider>
          <AppShell>{children}</AppShell>
        </LocaleProvider>
      </body>
    </html>
  );
}
