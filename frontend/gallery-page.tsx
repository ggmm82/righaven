"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import GalleryFeedback, {FeedbackModeration} from "./gallery-feedback";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import { I18nProvider, LanguageSelector, useI18n } from "@/app/workspace/i18n";
import {tr, useUiLanguage} from "@/core/i18n/ui-text";

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
  rating_count?:number;
  rating_average?:number|null;
  tools: string[];
  verification_command: string;
  skill_prompt_template: string;
  cli_binaries: { name: string; executable: string; safe_flags: string[]; health_check: string }[];
  security_policy: { rootless: boolean; network_access: boolean; writable_paths: string[]; read_only_mounts: string[] };
};

type CatalogRecipe={id:string;title:string;summary:string;custom:boolean;shared:boolean;skills:string[];environment:string|null;phases:unknown[]};

function GalleryContent() {useUiLanguage();
  const { locale, t } = useI18n();
  const [packs, setPacks] = useState<GalleryPack[]>([]);
  const [category, setCategory] = useState<string>("");
  useEffect(()=>{const value=new URLSearchParams(location.search).get("category");if(value&&["environment","cli-tool","skill","recipe"].includes(value))setCategory(value);},[]);
  // Recipes join the same catalog: built-in ones and those their authors published, next to environments and skills.
  const [recipes,setRecipes]=useState<CatalogRecipe[]>([]);
  useEffect(()=>{const controller=new AbortController();void fetch(`${getBackendBaseURL()}/api/harness/recipes?locale=${locale}`,{signal:controller.signal}).then(async r=>{if(!r.ok)throw Error(String(r.status));return (await r.json() as {recipes:CatalogRecipe[]}).recipes;})
   .then(v=>{if(!controller.signal.aborted)setRecipes(v.filter(r=>!r.custom||r.shared));}).catch(()=>undefined);return()=>controller.abort();},[locale]);
  const [query, setQuery] = useState<string>("");
  const shownRecipes=(category===""||category==="recipe")?recipes.filter(r=>!query.trim()||(r.title+" "+r.summary).toLowerCase().includes(query.trim().toLowerCase())):[];
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [selectedPack, setSelectedPack] = useState<GalleryPack | null>(null);
  const [feedbackVersion,setFeedbackVersion]=useState("");
  const [sourceLink,setSourceLink]=useState<{id:string;version:string}|null>(null);
  useEffect(()=>{const params=new URLSearchParams(location.search);const id=params.get("pack");if(id)setSourceLink({id,version:params.get("version")??""});},[]);
  useEffect(()=>{if(!sourceLink)return;const pack=packs.find(p=>p.id===sourceLink.id);if(pack){setSelectedPack(pack);setFeedbackVersion(sourceLink.version||pack.version);setSourceLink(null);}},[packs,sourceLink]);
  function selectPack(pack:GalleryPack){setSelectedPack(pack);setFeedbackVersion(pack.version);}
  const [showPublish, setShowPublish] = useState<boolean>(false);
  const [publishJson, setPublishJson] = useState<string>("");
  const base = `${getBackendBaseURL()}/api/v1/gallery`;

  async function loadPacks(signal?:AbortSignal) {
    const params = new URLSearchParams();
    if (category==="recipe") { setPacks([]); return; }
    if (category) params.set("category", category);
    if (query.trim()) params.set("q", query.trim());
    params.set("locale", locale);
    try {
      const response = await fetch(`${base}/packs?${params.toString()}`, {
        headers: { "Accept-Language": locale }, signal,
      });
      if (!response.ok) throw Error(locale === "it" ? "Catalogo non disponibile" : "Catalog unavailable");
      const data = await response.json();
      if(!signal?.aborted)setPacks(data.packs ?? []);
    } catch (error) {
      if(!signal?.aborted)setStatusMessage(error instanceof Error?error.message:tr("Catalogo non disponibile", "Catalog unavailable"));
    }
  }

  useEffect(() => {
    const controller=new AbortController();
    const timer=setTimeout(()=>void loadPacks(controller.signal),250);
    return ()=>{clearTimeout(timer);controller.abort();};
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
      if (!response.ok) throw new Error(data.detail || tr("Errore di validazione", "Validation error"));
      setStatusMessage(data.message);
      setShowPublish(false);
      setPublishJson("");
      await loadPacks();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : tr("Manifest non valido", "Invalid manifest"));
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

      <RegistryManager base={base} locale={locale} onChanged={loadPacks} />
      <FeedbackModeration base={base} locale={locale}/>
      <p className="text-sm"><Link className="underline" href="/workspace/environments">{locale==="it"?"Condividi uno dei tuoi ambienti: Gestisci → Condividi nel catalogo":"Share one of your environments: Manage → Share to catalog"}</Link></p>

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
            ["recipe", locale==="it"?"Ricette":"Recipes"],
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

      {shownRecipes.length>0&&<section className="space-y-2" data-testid="gallery-recipes">
        <h2 className="text-sm font-semibold">{locale==="it"?"Ricette · percorsi a fasi che combinano skill e ambienti":"Recipes · phased paths combining skills and environments"}</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{shownRecipes.map(r=><article key={r.id} className="flex flex-col justify-between rounded-xl border p-4 shadow-sm" data-testid={"gallery-recipe-"+r.id}>
          <div className="space-y-2"><span className="rounded-full border px-2 py-0.5 text-xs font-medium uppercase">{locale==="it"?"ricetta":"recipe"}{r.custom?(locale==="it"?" · community":" · community"):(locale==="it"?" · integrata":" · built-in")}</span>
            <h3 className="text-base font-semibold">{r.title}</h3><p className="text-xs text-muted-foreground">{r.summary}</p>
            <p className="text-xs">{r.phases.length} {locale==="it"?"fasi":"phases"} · {locale==="it"?"skill: ":"skills: "}{r.skills.map(s=>s.replace(/^skill-/,"")).join(", ")}{r.environment?` · ${locale==="it"?"ambiente":"environment"}: ${r.environment}`:""}</p></div>
          <div className="mt-4 flex flex-wrap gap-2 border-t pt-3 text-xs">
            <a className="rounded-lg bg-primary px-3 py-1 font-medium text-primary-foreground" href={`/workspace/recipes?use=${encodeURIComponent(r.id)}`}>{locale==="it"?"Usa questa ricetta":"Use this recipe"}</a>
            <a className="rounded border px-2 py-1" href={`/workspace/recipes?duplicate=${encodeURIComponent(r.id)}`}>{locale==="it"?"Copia nelle mie ricette":"Copy to my recipes"}</a>
          </div></article>)}</div>
        <p className="text-xs text-muted-foreground">{locale==="it"?"Per pubblicare una tua ricetta: Ricette → Pubblica nel catalogo.":"To publish one of your recipes: Recipes → Publish to the catalog."}</p>
      </section>}
      {packs.length===0&&shownRecipes.length===0&&<p role="status">{locale==="it"?"Nessun risultato: cambia ricerca o categoria.":"No matches: try another search or category."}</p>}
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
              <button className="text-xs underline" onClick={()=>selectPack(pack)}>{pack.rating_count?`★ ${pack.rating_average?.toFixed(1)} / 5 (${pack.rating_count})`:(locale==="it"?"Nessuna recensione":"No reviews yet")}</button>
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
                  aria-label={locale==="it"?"Aggiungi ai preferiti":"Add to favorites"}
                >
                  ♡ {pack.stars}
                </button>
                <button
                  type="button"
                  onClick={() => selectPack(pack)}
                  className="rounded border px-2 py-1 hover:bg-muted"
                >
                  {locale==="it"?"Dettagli e recensioni":"Details and reviews"}
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
        <PackDialog title={selectedPack.display_title} onClose={()=>setSelectedPack(null)}>
        <section className="space-y-4 p-4 text-xs" data-testid="pack-manifest-inspector">
          <div className="flex items-center justify-between border-b pb-2">
            <h4 className="text-sm font-semibold">{selectedPack.display_title} ({selectedPack.id})</h4>
            <button type="button" onClick={() => setSelectedPack(null)} className="rounded border px-2 py-1">
              {tr("Chiudi", "Close")}
            </button>
          </div>
          <p className="mt-2 font-medium">{t("gallery.reopen_verification")}: <code>{selectedPack.verification_command}</code></p>
          <GalleryFeedback key={selectedPack.id+selectedPack.version} base={base} pack={selectedPack.id} version={feedbackVersion||selectedPack.version} locale={locale}/>
          <details><summary>{locale==="it"?"Manifest tecnico":"Technical manifest"}</summary><pre className="mt-2 max-h-64 overflow-auto rounded bg-muted/40 p-3">
            {JSON.stringify(selectedPack, null, 2)}
          </pre></details>
        </section></PackDialog>
      )}
    </div>
  );
}

function PackDialog({title,onClose,children}:{title:string;onClose:()=>void;children:React.ReactNode}){useUiLanguage();
 const ref=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const node=ref.current;node?.showModal();return()=>{if(node?.open)node.close();};},[]);
 return <dialog ref={ref} aria-label={title} onCancel={event=>{event.preventDefault();onClose();}} className="m-auto max-h-[92dvh] w-[calc(100%-2rem)] max-w-3xl overflow-y-auto rounded-xl border bg-background text-foreground shadow-xl backdrop:bg-black/50">{children}</dialog>;
}

function RegistryManager({base, locale, onChanged}: {base:string; locale:string; onChanged:()=>Promise<void>}) {useUiLanguage();
  const it = locale === 'it';
  const [admin,setAdmin] = useState(false);
  const [entries,setEntries] = useState<Record<string,{url:string;sha256:string}>>({});
  const [name,setName] = useState(''); const [url,setUrl] = useState('');
  const [pin,setPin] = useState(''); const [busy,setBusy] = useState(false);
  const [message,setMessage] = useState('');
  useEffect(()=>{void fetch(base+'/registries').then(async response=>{
    if(response.ok){setAdmin(true);setEntries(await response.json());}
  }).catch(()=>{});},[base]);
  async function sync(registry:string, save=false) {
    setBusy(true);setMessage('');
    try {
      if(save){const response=await fetch(base+'/registries/'+encodeURIComponent(registry),{
        method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,sha256:pin})});
        if(!response.ok)throw new Error((await response.json()).detail);}
      const response=await fetch(base+'/registries/'+encodeURIComponent(registry)+'/sync',{method:'POST'});
      const result=await response.json();if(!response.ok)throw new Error(result.detail);
      setEntries(await (await fetch(base+'/registries')).json());await onChanged();
      setMessage(it?'Catalogo sincronizzato':'Catalog synchronized');
    }catch(error){setMessage(error instanceof Error?error.message:tr("Registro non disponibile", "Registry unavailable"));}
    finally{setBusy(false);}
  }
  return <details className="rounded-lg border p-4"><summary>{it?'Cataloghi community e trasferimenti':'Community catalogs and transfers'}</summary>
    <a className="my-3 inline-block underline" href={base+'/catalog'}>{it?'Esporta catalogo':'Export catalog'}</a>
    {admin&&<div className="space-y-3"><p>{it?'Autorizza il catalogo HTTPS e il suo hash SHA-256 prima di importarlo.':'Approve the HTTPS catalog and its SHA-256 hash before importing.'}</p>
      {Object.entries(entries).map(([key,value])=><div key={key} className="flex flex-wrap gap-3"><span>{key}: {value.url}</span><button disabled={busy} className="underline" onClick={()=>void sync(key)}>{it?'Sincronizza':'Sync'}</button></div>)}
      <form className="grid gap-3" onSubmit={event=>{event.preventDefault();void sync(name,true);}}>
        <input className="rounded border p-2" required aria-label={tr("Nome del registro", "Registry name")} placeholder={it?'Nome catalogo':'Catalog name'} pattern="[a-z0-9][a-z0-9-]{0,31}" value={name} onChange={e=>setName(e.target.value)}/>
        <input className="rounded border p-2" required type="url" aria-label={tr("URL del registro", "Registry URL")} placeholder="https://example.org/catalog.json" value={url} onChange={e=>setUrl(e.target.value)}/>
        <input className="rounded border p-2" required aria-label="SHA-256" placeholder="SHA-256" pattern="[a-f0-9]{64}" value={pin} onChange={e=>setPin(e.target.value)}/>
        <button className="rounded border p-2" disabled={busy}>{busy?(it?'Importazione…':'Importing…'):(it?'Autorizza e importa':'Approve and import')}</button>
      </form></div>}
    {message&&<p role="status">{message}</p>}
  </details>;
}

export default function GalleryPage() {useUiLanguage();
  return (
    <I18nProvider>
      <GalleryContent />
    </I18nProvider>
  );
}
