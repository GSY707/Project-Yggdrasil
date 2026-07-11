"use client";

import { SUPPORTED_LOCALES } from "../i18n";
import { useTranslation } from "./locale-provider";

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useTranslation();

  return (
    <div
      aria-label={t("locale.control")}
      className="language-switcher"
      role="group"
      style={{
        display: "inline-flex",
        alignItems: "center",
        width: "fit-content",
        padding: 2,
        border: "1px solid #404944",
        borderRadius: 4,
        background: "#141b2b",
      }}
    >
      {SUPPORTED_LOCALES.map((candidate) => {
        const active = locale === candidate;
        return (
          <button
            aria-pressed={active}
            key={candidate}
            onClick={() => setLocale(candidate)}
            style={{
              minWidth: candidate === "en" ? 36 : 48,
              border: 0,
              borderRadius: 2,
              padding: "5px 8px",
              background: active ? "#4edea3" : "transparent",
              color: active ? "#003824" : "#bfc9c3",
              cursor: "pointer",
              fontFamily: "JetBrains Mono, monospace",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.04em",
              lineHeight: 1.2,
            }}
            type="button"
          >
            {t(`locale.${candidate}`)}
          </button>
        );
      })}
    </div>
  );
}
