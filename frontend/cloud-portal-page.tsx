"use client";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { fetch as authenticatedFetch } from "@/core/api/fetcher";
import { I18nProvider, LanguageSelector, useI18n } from "@/app/workspace/i18n";
import {tr, useUiLanguage} from "@/core/i18n/ui-text";

type Edition = { edition: string; hosting_status: string };
type Limits = { max_parallel: number; jobs_per_month: number; used_jobs: number; active_jobs: number };
type Profile = { engine: string; model: string };
type Profiles = { coordinator: Profile | null; squad: Profile | null };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authenticatedFetch("/api/v1/cloud/" + path, init);
  if (!response.ok) {
    const value = await response.json().catch(() => ({})) as { detail?: string };
    throw new Error(value.detail ?? tr("Richiesta non riuscita (", "Request failed (") + response.status + ")");
  }
  return response.json() as Promise<T>;
}

function HostingContent() {useUiLanguage();
  const { locale } = useI18n();
  const it = locale === "it";
  const [edition, setEdition] = useState<Edition>();
  const [limits, setLimits] = useState<Limits>();
  const [profiles, setProfiles] = useState<Profiles>();
  const [engine, setEngine] = useState("deepseek");
  const [model, setModel] = useState("deepseek-chat");
  const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
  const [scope, setScope] = useState("both");
  const [key, setKey] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    void api<Edition>("edition").then(async value => {
      if (!alive) return;
      setEdition(value);
      if (value.edition === "cloud") {
        const [usage, selected] = await Promise.all([api<Limits>("limits"), api<Profiles>("providers")]);
        if (alive) { setLimits(usage); setProfiles(selected); }
      }
    }).catch(reason => { if (alive) setError(String(reason.message)); });
    return () => { alive = false; };
  }, []);

  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setStatus("");
    try {
      await api("providers", { method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({engine, model, api_key: key, scope, ...(engine === "openai" ? {base_url: baseUrl} : {})}) });
      setKey("");
      setProfiles(await api<Profiles>("providers"));
      setStatus(it ? "Connessione privata salvata. La disponibilità del modello sarà verificata alla prima richiesta." : "Private connection saved. Model availability will be checked on the first request.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }

  return <main className="flex-1 overflow-y-auto"><div className="mx-auto max-w-3xl space-y-8 p-6 md:p-10">
    <header className="flex items-start justify-between gap-4 border-b pb-6"><div><p className="text-xs uppercase tracking-widest text-muted-foreground">RigHaven</p><h1 className="mt-2 text-2xl font-semibold">{it ? "Installazione e connessioni" : "Deployment & connections"}</h1></div><LanguageSelector /></header>
    {error && <p role="alert" className="rounded-xl border border-destructive p-4 text-sm">{error}</p>}
    {!edition && !error && <p role="status">{it ? "Caricamento…" : "Loading…"}</p>}
    {edition && <section className="space-y-3 rounded-2xl border p-6"><h2 className="text-lg font-semibold">RigHaven {edition.edition === "cloud" ? tr("Cloud · Anteprima", "Cloud · Preview") : "Community"}</h2><p className="text-sm text-muted-foreground">{it ? "Progetti, ambienti e Gallery utilizzano lo stesso account e motore di esecuzione. Non occorre un secondo accesso." : "Projects, environments and Gallery use the same account and execution engine. No second sign-in is required."}</p>
      {edition.edition !== "cloud" && <Link className="inline-block underline" href="/workspace/harness">{it ? "Configura modelli e risorse" : "Configure models & resources"}</Link>}
      {edition.edition === "cloud" && <p className="text-sm text-muted-foreground">{it ? "Anteprima ospitata con connessioni private per account. Piani commerciali e organizzazioni condivise non sono ancora disponibili." : "Hosted preview with private account connections. Commercial plans and shared organizations are not yet available."}</p>}
    </section>}
    {edition?.edition === "cloud" && <>
      {limits && <section className="space-y-4"><h2 className="text-lg font-semibold">{it ? "Utilizzo del tuo account" : "Your account usage"}</h2><dl className="grid grid-cols-2 gap-4"><div className="rounded-xl border p-4"><dt className="text-sm text-muted-foreground">{it ? "Incarichi attivi" : "Active jobs"}</dt><dd className="mt-2 text-2xl">{limits.active_jobs} / {limits.max_parallel}</dd></div><div className="rounded-xl border p-4"><dt className="text-sm text-muted-foreground">{it ? "Incarichi avviati questo mese" : "Jobs started this month"}</dt><dd className="mt-2 text-2xl">{limits.used_jobs} / {limits.jobs_per_month}</dd></div></dl><p className="text-sm text-muted-foreground">{it ? "I limiti sono definiti dall’amministratore. Anche gli incarichi falliti consumano un avvio; i token del provider sono conteggiati separatamente." : "Allowances are set by the administrator. Failed jobs also count as starts; provider token usage is separate."}</p></section>}
      <section className="space-y-4"><h2 className="text-lg font-semibold">{it ? "Modelli privati" : "Private models"}</h2><dl className="grid gap-3 sm:grid-cols-2">{(["coordinator","squad"] as const).map(target => <div key={target} className="rounded-xl border p-4"><dt className="text-sm text-muted-foreground">{target === "coordinator" ? it ? "Coordinatore" : "Coordinator" : it ? "Squadra" : "Team"}</dt><dd className="mt-2 font-medium">{profiles?.[target]?.model ?? (it ? "Da configurare" : "Not configured")}</dd></div>)}</dl>
      <form onSubmit={event => void save(event)} className="grid gap-4 rounded-2xl border p-6">
        <label className="grid gap-2 text-sm">{"Provider"}<select aria-label={"Provider"} className="rounded-md border bg-background p-2" value={engine} onChange={event => {setEngine(event.target.value); setModel(event.target.value === "deepseek" ? "deepseek-chat" : "");}}><option value="deepseek">DeepSeek</option><option value="openai">OpenAI / OpenAI-compatible</option></select></label>
        {engine === "openai" && <label className="grid gap-2 text-sm">Endpoint<input className="rounded-md border bg-background p-2" type="url" required value={baseUrl} onChange={event => setBaseUrl(event.target.value)} /><span className="text-xs text-muted-foreground">{it ? "L’host deve essere approvato dall’operatore del servizio." : "The host must be approved by the service operator."}</span></label>}
        <label className="grid gap-2 text-sm">{it ? "Modello" : "Model"}<input className="rounded-md border bg-background p-2" required maxLength={200} value={model} onChange={event => setModel(event.target.value)} /></label>
        <label className="grid gap-2 text-sm">{tr("Chiave API", "API key")}<input className="rounded-md border bg-background p-2" type="password" autoComplete="new-password" required maxLength={4096} value={key} onChange={event => setKey(event.target.value)} /></label>
        <label className="grid gap-2 text-sm">{it ? "Usa per" : "Use for"}<select aria-label={it?"Usa per":"Use for"} className="rounded-md border bg-background p-2" value={scope} onChange={event => setScope(event.target.value)}><option value="both">{it ? "Coordinatore e squadra" : "Coordinator & team"}</option><option value="coordinator">{it ? "Solo coordinatore" : "Coordinator only"}</option><option value="squad">{it ? "Solo squadra" : "Team only"}</option></select></label>
        <button disabled={busy} className="rounded-lg bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50">{busy ? it ? "Salvataggio…" : "Saving…" : it ? "Salva connessione privata" : "Save private connection"}</button>
        {status && <p role="status" className="text-sm">{status}</p>}
      </form></section>
    </>}
  </div></main>;
}
export default function CloudPortalPage() {useUiLanguage(); return <I18nProvider><HostingContent /></I18nProvider>; }
