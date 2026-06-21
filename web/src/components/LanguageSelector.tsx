// Seryvon — language selector (EN base + FR). AGPL-3.0-or-later.

import { LOCALE_NAMES, LOCALES, useI18n } from "../i18n";
import type { Locale } from "../i18n/dict";

export function LanguageSelector() {
  const { locale, setLocale } = useI18n();
  return (
    <label className="lang-select" aria-label="Language">
      <select value={locale} onChange={(e) => setLocale(e.target.value as Locale)}>
        {LOCALES.map((l) => (
          <option key={l} value={l}>
            {LOCALE_NAMES[l]}
          </option>
        ))}
      </select>
    </label>
  );
}
