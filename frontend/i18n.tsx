"use client";

import React, { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useI18n as useCoreI18n } from "@/core/i18n/hooks";
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

export function I18nProvider({ children }: { children: ReactNode; initialLocale?: Locale }) {
  return <>{children}</>;
}

export function useI18n(): I18nContextValue {
  const core = useCoreI18n();
  const locale: Locale = core.locale === "it-IT" ? "it" : "en";
  return { locale, setLocale: (next) => core.changeLocale(next === "it" ? "it-IT" : "en-US"),
    t: (key, params) => translateKey(locale, key, params), dictionary: DICTIONARIES[locale] };
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
