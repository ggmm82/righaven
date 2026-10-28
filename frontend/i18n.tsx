"use client";

import React, { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import enCommon from "./locales/en/common.json";
import itCommon from "./locales/it/common.json";

export type Locale = "en" | "it";
type Dictionary = typeof enCommon;

const DICTIONARIES: Record<Locale, Dictionary> = {
  en: enCommon,
  it: itCommon,
};

type I18nContextValue = {
  locale: Locale;
  setLocale: (next: Locale) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  dictionary: Dictionary;
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function detectBrowserLocale(): Locale {
  if (typeof window === "undefined") return "en";
  try {
    const saved = window.localStorage.getItem("righaven_locale");
    if (saved === "en" || saved === "it") return saved;
  } catch {
    // Ignore storage restrictions.
  }
  const nav = (typeof navigator !== "undefined" ? navigator.language : "en").toLowerCase();
  return nav.startsWith("it") ? "it" : "en";
}

export function translateKey(locale: Locale, key: string, params?: Record<string, string | number>): string {
  const dict = DICTIONARIES[locale] ?? DICTIONARIES.en;
  let node: unknown = dict;
  for (const part of key.split(".")) {
    if (node && typeof node === "object" && part in (node as Record<string, unknown>)) {
      node = (node as Record<string, unknown>)[part];
    } else {
      node = undefined;
      break;
    }
  }
  if (typeof node !== "string" && locale !== "en") {
    node = DICTIONARIES.en;
    for (const part of key.split(".")) {
      node = node && typeof node === "object" ? (node as Record<string, unknown>)[part] : undefined;
    }
  }
  let text = typeof node === "string" ? node : key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      text = text.replaceAll(`{${k}}`, String(v));
    }
  }
  return text;
}

export function I18nProvider({ children, initialLocale }: { children: ReactNode; initialLocale?: Locale }) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale ?? "en");

  useEffect(() => {
    if (!initialLocale) {
      setLocaleState(detectBrowserLocale());
    }
  }, [initialLocale]);

  function setLocale(next: Locale) {
    setLocaleState(next);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem("righaven_locale", next);
      } catch {
        // Ignore storage restrictions.
      }
    }
  }

  const value: I18nContextValue = {
    locale,
    setLocale,
    t: (key, params) => translateKey(locale, key, params),
    dictionary: DICTIONARIES[locale] ?? DICTIONARIES.en,
  };

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    return {
      locale: "en",
      setLocale: () => {},
      t: (key, params) => translateKey("en", key, params),
      dictionary: DICTIONARIES.en,
    };
  }
  return ctx;
}

export function LanguageSelector({ className = "" }: { className?: string }) {
  const { locale, setLocale, t } = useI18n();
  return (
    <div
      className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs font-medium ${className}`}
      role="group"
      aria-label={t("navbar.language_selector")}
      data-testid="language-selector"
    >
      <button
        type="button"
        onClick={() => setLocale("en")}
        aria-pressed={locale === "en"}
        className={`rounded px-2 py-0.5 transition-colors ${locale === "en" ? "bg-primary text-primary-foreground font-semibold" : "hover:bg-muted"}`}
      >
        EN
      </button>
      <span className="text-muted-foreground">|</span>
      <button
        type="button"
        onClick={() => setLocale("it")}
        aria-pressed={locale === "it"}
        className={`rounded px-2 py-0.5 transition-colors ${locale === "it" ? "bg-primary text-primary-foreground font-semibold" : "hover:bg-muted"}`}
      >
        IT
      </button>
    </div>
  );
}
