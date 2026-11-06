import { QueryClientProvider } from "@/components/query-client-provider";
import { I18nProvider } from "@/core/i18n/context";
import { detectLocaleServer } from "@/core/i18n/server";

export const dynamic = "force-dynamic";

/** Standalone editor uses workspace language without the chat/sidebar shell. */
export default async function EditorLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const locale = await detectLocaleServer();
  return (
    <I18nProvider initialLocale={locale}>
      <QueryClientProvider>{children}</QueryClientProvider>
    </I18nProvider>
  );
}
