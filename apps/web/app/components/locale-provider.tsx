"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { PropsWithChildren } from "react";

import { DEFAULT_LOCALE, isLocale, translate, type Locale, type TranslationKey, type TranslationValues } from "../i18n";

const LOCALE_STORAGE_KEY = "yggdrasil.ui.locale";

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: TranslationKey, values?: TranslationValues) => string;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

function readStoredLocale(): Locale | null {
  try {
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    return isLocale(stored) ? stored : null;
  } catch {
    return null;
  }
}

export function LocaleProvider({ children }: PropsWithChildren) {
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const stored = readStoredLocale();
    if (stored) {
      setLocale(stored);
    }
    setHydrated(true);

    const syncLocaleAcrossTabs = (event: StorageEvent) => {
      if (event.key !== LOCALE_STORAGE_KEY || !isLocale(event.newValue)) {
        return;
      }
      setLocale(event.newValue);
    };
    window.addEventListener("storage", syncLocaleAcrossTabs);
    return () => window.removeEventListener("storage", syncLocaleAcrossTabs);
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = "ltr";
    document.title = translate(locale, "meta.title");
    document.querySelector<HTMLMetaElement>('meta[name="description"]')?.setAttribute(
      "content",
      translate(locale, "meta.description"),
    );

    if (!hydrated) {
      return;
    }
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    } catch {
      // A blocked storage area should not prevent the language selector from working in this tab.
    }
  }, [hydrated, locale]);

  const updateLocale = useCallback((nextLocale: Locale) => {
    setLocale(nextLocale);
  }, []);

  const value = useMemo<LocaleContextValue>(() => ({
    locale,
    setLocale: updateLocale,
    t: (key, values) => translate(locale, key, values),
  }), [locale, updateLocale]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const context = useContext(LocaleContext);
  if (!context) {
    throw new Error("useLocale must be used inside LocaleProvider.");
  }
  return context;
}

export function useTranslation() {
  return useLocale();
}
