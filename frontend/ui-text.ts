"use client";

// Inline Italian/English text for the RigHaven workspace panels.
// tr(it, en) reads the language of the component being rendered: every
// component that shows such text calls useUiLanguage() first, so a change of
// language re-renders it with the other text. Event handlers that run later
// use the language of the last render, which is the current one.
import { useI18n } from "@/core/i18n/hooks";

let active: "it" | "en" = "en";

export function useUiLanguage(): "it" | "en" {
  const { locale } = useI18n();
  active = String(locale).toLowerCase().startsWith("it") ? "it" : "en";
  // Shared with modules that cannot import this one (delegate-progress-state.ts).
  (globalThis as { __righavenUiLanguage?: string }).__righavenUiLanguage = active;
  return active;
}

export function tr(it: string, en: string): string {
  return active === "it" ? it : en;
}

/** A label table whose values follow the current language when read. */
export function trMap(entries: Record<string, readonly [string, string]>): Record<string, string> {
  const table: Record<string, string> = {};
  for (const [key, [it, en]] of Object.entries(entries)) {
    Object.defineProperty(table, key, { enumerable: true, get: () => tr(it, en) });
  }
  return table;
}
