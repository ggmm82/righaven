"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import { I18nProvider, LanguageSelector, useI18n } from "@/app/workspace/i18n";

type EditionInfo = {
  edition: "community" | "cloud";
  is_cloud: boolean;
  is_community: boolean;
};

type Quotas = {
  plan: string;
  sandbox_minutes_used: number;
  sandbox_minutes_limit: number;
  storage_bytes_used: number;
  storage_bytes_limit: number;
  tokens_used: number;
  tokens_limit: number;
};

function CloudPortalContent() {
  const { locale, t } = useI18n();
  const [edition, setEdition] = useState<EditionInfo | null>(null);
  const [mode, setMode] = useState<"login" | "signup" | "recover">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState<string>("");
  const [user, setUser] = useState<{ user_id: string; email: string; workspace_path: string } | null>(null);
  const [quotas, setQuotas] = useState<Quotas | null>(null);
  const [vault, setVault] = useState<Record<string, { configured: boolean; masked_preview: string }>>({});
  const [vaultProvider, setVaultProvider] = useState("deepseek");
  const [vaultKey, setVaultKey] = useState("");
  const [notice, setNotice] = useState("");
  const base = `${getBackendBaseURL()}/api/v1/cloud`;

  useEffect(() => {
    void fetch(`${base}/edition`).then(async (r) => {
      if (r.ok) setEdition(await r.json());
    }).catch(() => {});
  }, [base]);

  async function handleAuth(e: React.FormEvent) {
    e.preventDefault();
    setNotice("");
    const endpoint = mode === "signup" ? "signup" : mode === "recover" ? "recover" : "login";
    const body =
      mode === "signup"
        ? { username, email, password, locale }
        : mode === "recover"
        ? { email }
        : { identifier: username || email, password };
    const response = await fetch(`${base}/auth/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept-Language": locale },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) {
      setNotice(data.detail || "Authentication error");
      return;
    }
    if (data.token) {
      setToken(data.token);
      setUser(data.user);
      setQuotas(data.quotas);
    } else if (data.recovery_token) {
      setNotice(`Recovery token issued: ${data.recovery_token}`);
    }
  }

  async function handleOAuth(provider: "github" | "google") {
    const response = await fetch(`${base}/auth/oauth/${provider}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept-Language": locale },
      body: JSON.stringify({ username: `${provider}-dev`, email: `dev@${provider}.example`, locale }),
    });
    if (response.ok) {
      const data = await response.json();
      setToken(data.token);
      setUser(data.user);
      setQuotas(data.quotas);
    }
  }

  async function handleSaveVaultKey(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    const response = await fetch(`${base}/vault/${vaultProvider}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ api_key: vaultKey }),
    });
    if (response.ok) {
      const data = await response.json();
      setVault(data.providers ?? {});
      setVaultKey("");
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6" data-testid="righaven-cloud-portal">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{t("cloud.title")}</h1>
            <span className="rounded-full border px-2.5 py-0.5 text-xs font-medium">
              {edition?.is_cloud ? t("navbar.edition_cloud") : t("navbar.edition_community")}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">{t("cloud.subtitle")}</p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/workspace/harness" className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted">
            {t("navbar.dashboard")}
          </Link>
          <Link href="/workspace/gallery" className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted">
            {t("navbar.gallery")}
          </Link>
          <LanguageSelector />
        </div>
      </header>

      {notice && (
        <div role="alert" className="rounded-lg border p-3 text-sm">
          {notice}
        </div>
      )}

      {!user ? (
        <section className="mx-auto max-w-md space-y-4 rounded-xl border p-6 shadow-sm">
          <div className="flex gap-2 border-b pb-3">
            <button type="button" onClick={() => setMode("login")} className={`text-sm font-semibold ${mode === "login" ? "underline" : "text-muted-foreground"}`}>
              {t("cloud.login_title")}
            </button>
            <button type="button" onClick={() => setMode("signup")} className={`text-sm font-semibold ${mode === "signup" ? "underline" : "text-muted-foreground"}`}>
              {t("cloud.signup_title")}
            </button>
            <button type="button" onClick={() => setMode("recover")} className={`text-sm font-semibold ${mode === "recover" ? "underline" : "text-muted-foreground"}`}>
              {t("cloud.recover_password")}
            </button>
          </div>
          <form onSubmit={handleAuth} className="space-y-3">
            {mode !== "recover" && (
              <input
                type="text"
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded border bg-background px-3 py-2 text-sm"
                required={mode === "signup"}
              />
            )}
            {mode !== "login" && (
              <input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded border bg-background px-3 py-2 text-sm"
                required
              />
            )}
            {mode !== "recover" && (
              <input
                type="password"
                placeholder="Password (min 8 chars)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded border bg-background px-3 py-2 text-sm"
                required
              />
            )}
            <button type="submit" className="w-full rounded-lg bg-primary py-2 text-sm font-medium text-primary-foreground">
              {mode === "signup" ? t("cloud.signup_title") : mode === "recover" ? t("cloud.recover_password") : t("cloud.login_title")}
            </button>
          </form>
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={() => void handleOAuth("github")} className="flex-1 rounded border py-2 text-xs font-medium hover:bg-muted">
              {t("cloud.oauth_github")}
            </button>
            <button type="button" onClick={() => void handleOAuth("google")} className="flex-1 rounded border py-2 text-xs font-medium hover:bg-muted">
              {t("cloud.oauth_google")}
            </button>
          </div>
        </section>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          <section className="space-y-3 rounded-xl border p-4">
            <h2 className="text-base font-semibold">{t("cloud.tenant_workspace")}</h2>
            <p className="text-xs text-muted-foreground">
              User: <strong>{user.user_id}</strong> ({user.email})
            </p>
            <p className="rounded bg-muted p-2 font-mono text-xs">{user.workspace_path}</p>
            {quotas && (
              <div className="space-y-2 pt-2 text-xs">
                <h3 className="font-semibold">{t("cloud.quotas_title")}</h3>
                <p>{t("cloud.sandbox_minutes")}: {quotas.sandbox_minutes_used} / {quotas.sandbox_minutes_limit} min</p>
                <p>{t("cloud.storage_quota")}: {(quotas.storage_bytes_used / (1024 * 1024)).toFixed(1)} MiB / {(quotas.storage_bytes_limit / (1024 * 1024 * 1024)).toFixed(0)} GiB</p>
                <p>{t("cloud.token_budget")}: {quotas.tokens_used.toLocaleString()} / {quotas.tokens_limit.toLocaleString()}</p>
              </div>
            )}
          </section>

          <section className="space-y-3 rounded-xl border p-4">
            <h2 className="text-base font-semibold">{t("cloud.vault_title")}</h2>
            <form onSubmit={handleSaveVaultKey} className="space-y-2">
              <select
                value={vaultProvider}
                onChange={(e) => setVaultProvider(e.target.value)}
                className="w-full rounded border bg-background p-2 text-xs"
              >
                <option value="deepseek">DeepSeek API</option>
                <option value="codex">OpenAI Codex</option>
                <option value="gemini">Google Antigravity</option>
                <option value="openai">OpenAI Compatible</option>
              </select>
              <input
                type="password"
                value={vaultKey}
                onChange={(e) => setVaultKey(e.target.value)}
                placeholder="sk-..."
                className="w-full rounded border bg-background p-2 text-xs"
                required
              />
              <button type="submit" className="rounded bg-primary px-3 py-1.5 text-xs text-primary-foreground">
                Save to Encrypted Vault
              </button>
            </form>
            <ul className="space-y-1 text-xs">
              {Object.entries(vault).map(([prov, info]) => (
                <li key={prov} className="flex justify-between rounded border p-2">
                  <span className="font-medium uppercase">{prov}</span>
                  <span className="font-mono text-muted-foreground">{info.masked_preview}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}

export default function CloudPortalPage() {
  return (
    <I18nProvider>
      <CloudPortalContent />
    </I18nProvider>
  );
}
