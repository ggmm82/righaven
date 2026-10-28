"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { I18nProvider, LanguageSelector, useI18n } from "@/app/workspace/i18n";

function HarnessContent() {
  const { t } = useI18n();
  const router = useRouter();
  const [access, setAccess] = useState("loading");
  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/v1/cloud/edition", { signal: controller.signal, credentials: "same-origin" })
      .then(async response => {
        if (!response.ok) throw new Error("Deployment configuration unreachable");
        const edition = await response.json() as { edition: string };
        if (edition.edition === "cloud") {
          router.replace("/workspace/cloud");
          return null;
        }
        return fetch("/harness/api/catalog", { signal: controller.signal, credentials: "same-origin" });
      })
      .then((response) => {
        if (!response) return;
        if (!controller.signal.aborted) setAccess(response.ok ? "admin" : response.status === 403 ? "user" : "error");
      })
      .catch(() => { if (!controller.signal.aborted) setAccess("error"); });
    return () => controller.abort();
  }, [router]);
  return (
    <div className="flex flex-col">
      <header className="flex items-center justify-between border-b px-6 py-2">
        <div className="flex items-center gap-3 text-sm font-medium">
          <span>{t("harness.title")}</span>
          <Link href="/workspace/gallery" className="rounded border px-2.5 py-1 text-xs hover:bg-muted">
            {t("navbar.gallery")}
          </Link>
          <Link href="/workspace/cloud" className="rounded border px-2.5 py-1 text-xs hover:bg-muted">
            {t("navbar.cloud_portal")}
          </Link>
        </div>
        <LanguageSelector />
      </header>
      {access === "admin" ? (
        <iframe title="RigHaven" src="/harness/" style={{ width: "100%", height: "calc(100vh - 108px)", border: 0 }} />
      ) : (
        <section className="space-y-4 p-6">
          <h1 className="text-xl font-semibold">{t("harness.title")}</h1>
          <p>
            {access === "loading"
              ? "Checking access…"
              : access === "user"
              ? "The administrator configures shared AI providers and budgets. You can launch multi-agent tasks directly from chat."
              : "Configuration unreachable. Reload the page to retry."}
          </p>
          {access !== "loading" && (
            <Link className="underline" href="/workspace/chats/new">
              {t("navbar.new_chat")} →
            </Link>
          )}
        </section>
      )}
    </div>
  );
}

export default function HarnessPage() {
  return (
    <I18nProvider>
      <HarnessContent />
    </I18nProvider>
  );
}
