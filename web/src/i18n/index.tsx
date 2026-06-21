// Seryvon — i18n context + hook. AGPL-3.0-or-later.
//
// English is the default; the choice persists in localStorage. A heavier i18n
// library can replace this later without touching the call sites (they use t.*).

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import type { Dict, Locale } from "./dict";
import { en } from "./en";
import { fr } from "./fr";

const DICTS: Record<Locale, Dict> = { en, fr };
const STORAGE_KEY = "seryvon.locale";

interface I18nContextValue {
  locale: Locale;
  t: Dict;
  setLocale: (locale: Locale) => void;
  formatDate: (iso: string | null) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function initialLocale(): Locale {
  const stored = typeof localStorage !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
  return stored === "fr" ? "fr" : "en";
}

const DATE_LOCALE: Record<Locale, string> = { en: "en-US", fr: "fr-FR" };

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage unavailable (private mode) — ignore
    }
  }, []);

  const formatDate = useCallback(
    (iso: string | null) => {
      if (!iso) return "—";
      return new Date(iso).toLocaleString(DATE_LOCALE[locale], {
        dateStyle: "medium",
        timeStyle: "short",
      });
    },
    [locale],
  );

  const value = useMemo<I18nContextValue>(
    () => ({ locale, t: DICTS[locale], setLocale, formatDate }),
    [locale, setLocale, formatDate],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within an I18nProvider");
  return ctx;
}

export const LOCALES: Locale[] = ["en", "fr"];
export const LOCALE_NAMES: Record<Locale, string> = { en: en.localeName, fr: fr.localeName };
