"use client";
import Link from "next/link";
import { I18nProvider, LanguageSelector, useI18n } from "@/app/workspace/i18n";

function HostingContent() {
  const { locale } = useI18n();
  const it = locale === "it";
  return <main className="mx-auto max-w-3xl space-y-6 p-6">
    <header className="flex items-center justify-between"><h1 className="text-2xl font-semibold">RigHaven Cloud</h1><LanguageSelector /></header>
    <p>{it ? "La versione ospitata utilizza lo stesso account e lo stesso motore della versione Community." : "The hosted edition uses the same account and execution engine as the Community edition."}</p>
    <p>{it ? "Il servizio Cloud pubblico è in preparazione. Le quote per organizzazione e la gestione dei piani non sono ancora disponibili." : "The public Cloud service is in preparation. Organization quotas and plan management are not yet available."}</p>
    <nav className="flex gap-4"><Link className="underline" href="/workspace/chats">{it ? "Apri lo spazio di lavoro" : "Open workspace"}</Link><Link className="underline" href="/workspace/gallery">{it ? "Esplora la Gallery" : "Explore the Gallery"}</Link></nav>
  </main>;
}
export default function CloudPortalPage() { return <I18nProvider><HostingContent /></I18nProvider>; }
