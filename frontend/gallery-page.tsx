"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import { I18nProvider, LanguageSelector, useI18n } from "@/app/workspace/i18n";

export type GalleryPack = {
  id: string;
  name: string;
  version: string;
  author: string;
  category: "environment" | "cli-tool" | "skill";
  display_title: string;
  display_description: string;
  tags: string[];
  stars: number;
  forks: number;
  verified: boolean;
  activated?: boolean;
  tools: string[];
  verification_command: string;
  skill_prompt_template: string;
  cli_binaries: { name: string; executable: string; safe_flags: string[]; health_check: string }[];
  security_policy: { rootless: boolean; network_access: boolean; writable_paths: string[]; read_only_mounts: string[] };
};

function GalleryContent() {
  const { locale, t } = useI18n();
  const [packs, setPacks] = useState<GalleryPack[]>([]);
  const [category, setCategory] = useState<string>("");
  const [query, setQuery] = useState<string>("");
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [selectedPack, setSelectedPack] = useState<GalleryPack | null>(null);
  const [showPublish, setShowPublish] = useState<boolean>(false);
  const [publishJson, setPublishJson] = useState<string>("");
  const base = `${getBackendBaseURL()}/api/v1/gallery`;

  async function loadPacks() {
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (query.trim()) params.set("q", query.trim());
    params.set("locale", locale);
    try {
      const response = await fetch(`${base}/packs?${params.toString()}`, {
        headers: { "Accept-Language": locale },
      });
      if (!response.ok) return;
      const data = await response.json();
      setPacks(data.packs ?? []);
    } catch {
      // Offline fallback ignored.
    }
  }

  useEffect(() => {
    void loadPacks();
  }, [locale, category, query]);

  async function handleActivate(packId: string) {
    try {
    const response = await fetch(`${base}/packs/${encodeURIComponent(packId)}/activate`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept-Language": locale },
      body: JSON.stringify({}),
    });
    const data = await response.json();
    if (response.ok) {
      setStatusMessage(data.message || t("notifications.pack_activated", { id: packId }));
      await loadPacks();
    } else {
      setStatusMessage(typeof data.detail === "string" ? data.detail : (locale === "it" ? "Attivazione non riuscita" : "Activation failed"));
    }
    } catch {
      setStatusMessage(locale === "it" ? "Impossibile contattare la Gallery" : "Cannot reach the Gallery");
    }
  }

  async function handleStar(packId: string) {
    const response = await fetch(`${base}/packs/${encodeURIComponent(packId)}/star`, {
      method: "POST",
      headers: { "Accept-Language": locale },
    });
    if (response.ok) {
      await loadPacks();
    }
  }

  async function handlePublish(e: React.FormEvent) {
    e.preventDefault();
    try {
      const parsed = JSON.parse(publishJson);
      const response = await fetch(`${base}/packs/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept-Language": locale },
        body: JSON.stringify(parsed),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Validation error");
      setStatusMessage(data.message);
      setShowPublish(false);
      setPublishJson("");
      await loadPacks();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Invalid manifest");
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6" data-testid="righaven-gallery">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b pb-4">
        <div>
          <h1 className="text-2xl font-bold">{t("gallery.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("gallery.subtitle")}</p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/workspace/harness" className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted">
            {t("navbar.dashboard")}
          </Link>
          <Link href="/workspace/environments" className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted">
            {t("navbar.environments")}
          </Link>
          <Link href="/workspace/cloud" className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted">
            {t("navbar.cloud_portal")}
          </Link>
          <button
            type="button"
            onClick={() => setShowPublish(!showPublish)}
            className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground"
          >
            {t("gallery.publish_button")}
          </button>
          <LanguageSelector />
        </div>
      </header>

      {statusMessage && (
        <div role="status" className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm">
          {statusMessage}
        </div>
      )}

      {showPublish && (
        <form onSubmit={handlePublish} className="space-y-3 rounded-xl border p-4">
          <h2 className="text-base font-semibold">{t("gallery.publish_button")} (righaven-pack.json)</h2>
          <textarea
            className="min-h-48 w-full rounded border bg-background p-2 font-mono text-xs"
            placeholder='{"id":"skill-custom","name":"Custom Skill","version":"1.0.0","author":"you","category":"skill",...}'
            value={publishJson}
            onChange={(e) => setPublishJson(e.target.value)}
            required
          />
          <button type="submit" className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground">
            {t("gallery.publish_button")}
          </button>
        </form>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("gallery.search_placeholder")}
          className="min-w-64 flex-1 rounded-lg border bg-background px-3 py-2 text-sm"
        />
        <div className="flex flex-wrap gap-2">
          {([
            ["", t("gallery.filter_all")],
            ["environment", t("gallery.filter_environment")],
            ["cli-tool", t("gallery.filter_cli_tool")],
            ["skill", t("gallery.filter_skill")],
          ] as const).map(([cat, label]) => (
            <button
              key={cat}
              type="button"
              onClick={() => setCategory(cat)}
              className={`rounded-lg border px-3 py-1.5 text-sm ${category === cat ? "bg-primary text-primary-foreground font-medium" : "hover:bg-muted"}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {packs.map((pack) => (
          <article key={pack.id} className="flex flex-col justify-between rounded-xl border p-4 shadow-sm">
            <div className="space-y-2">
              <div className="flex items-start justify-between gap-2">
                <span className="rounded-full border px-2 py-0.5 text-xs font-medium uppercase">
                  {pack.category}
                </span>
                <span className="text-xs text-muted-foreground">{pack.version}</span>
              </div>
              <h3 className="text-base font-semibold">{pack.display_title}</h3>
              <p className="text-xs text-muted-foreground">{pack.display_description}</p>
              <div className="flex flex-wrap gap-1 pt-1">
                {pack.tags?.slice(0, 4).map((tag) => (
                  <span key={tag} className="rounded bg-muted px-1.5 py-0.5 text-[11px]">
                    #{tag}
                  </span>
                ))}
              </div>
            </div>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t pt-3">
              <div className="flex items-center gap-2 text-xs">
                <button
                  type="button"
                  onClick={() => void handleStar(pack.id)}
                  className="rounded border px-2 py-1 hover:bg-muted"
                >
                  ★ {pack.stars}
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedPack(pack)}
                  className="rounded border px-2 py-1 hover:bg-muted"
                >
                  Manifest
                </button>
              </div>
              <button
                type="button"
                onClick={() => void handleActivate(pack.id)}
                className={`rounded-lg px-3 py-1 text-xs font-medium ${pack.activated ? "border border-emerald-500/40 bg-emerald-500/10 text-emerald-700" : "bg-primary text-primary-foreground"}`}
              >
                {pack.activated ? t("gallery.activated_badge") : t("gallery.activate_button")}
              </button>
            </div>
          </article>
        ))}
      </div>

      {selectedPack && (
        <section className="rounded-xl border p-4 text-xs" data-testid="pack-manifest-inspector">
          <div className="flex items-center justify-between border-b pb-2">
            <h4 className="text-sm font-semibold">{selectedPack.display_title} ({selectedPack.id})</h4>
            <button type="button" onClick={() => setSelectedPack(null)} className="rounded border px-2 py-1">
              Close
            </button>
          </div>
          <p className="mt-2 font-medium">{t("gallery.reopen_verification")}: <code>{selectedPack.verification_command}</code></p>
          <pre className="mt-2 max-h-64 overflow-auto rounded bg-muted/40 p-3">
            {JSON.stringify(selectedPack, null, 2)}
          </pre>
        </section>
      )}
    </div>
  );
}

export default function GalleryPage() {
  return (
    <I18nProvider>
      <GalleryContent />
    </I18nProvider>
  );
}
