"use client";
import { useEffect, useState } from "react";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

type GuideFile = { path: string; name: string; role: string; open_with: string; editability: string; limitations: string[] };
type Guide = {
  delivery?: { label: string; source_package_status: string; bundle_note: string; pending: string[] };
  title: string; result: string; delivery_id: string; is_current: boolean; technical_status: string;
  team: { title: string; goal: string }[];
  method: { approach: string; steps: string[]; scripts: string[]; limits: string[]; path?: string };
  instructions: { overview: string; use: string[]; editing: { goal: string; files: string[]; steps: string[]; check: string }[]; limits: string[] };
  components: { name: string; tool: string; version: string; status: string }[];
  methods: { id: string; title: string; actor: string; kind: string; selected: boolean; approach: string; steps: string[]; path?: string }[]; methods_omitted: number;
  files: GuideFile[]; unavailable_files: string[]; limitations: string[]; history_omitted: number;
  documents: { name: string; path: string; text: string }[];
  history: { id: string; title: string; kind: string; actor: string; status: string; started_at: string; runtime_image?: string; change: string; detail: string; review_status: string }[];
  reviews: { status: string; matches_current_brief: boolean; matches_sources: boolean; path?: string; criteria: { criterion: string; status: string; evidence: string; scope?: string }[] }[];
};
const states: Record<string, string> = { passed: "Superato", completed: "Conclusa", running: "In corso", paused: "Fermata", needs_revision: "Da correggere", not_run: "Non eseguito", not_verified: "Non verificato", needs_review: "Da valutare", failed: "Fallito" };
const status = (value: string) => states[value] ?? value;
const steps = (items: string[]) => <ol className="list-decimal space-y-1 pl-5">{items.map((item, i) => <li className="whitespace-pre-wrap break-words" key={i}>{item}</li>)}</ol>;

export function ProjectGuide({ threadId, deliveryId, revision }: { threadId: string; deliveryId: string; revision?: string }) {
  const [open, setOpen] = useState(false), [retry, setRetry] = useState(0);
  const [loaded, setLoaded] = useState<{ key: string; value: Guide }>();
  const [error, setError] = useState<{ key: string; message: string }>();
  const base = `${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-guide?delivery_id=${encodeURIComponent(deliveryId)}`;
  const key = `${base}:${revision}:${retry}`;
  const guide = loaded?.key === key ? loaded.value : undefined;
  const message = error?.key === key ? error.message : undefined;
  const artifact = (path: string) => `${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/artifacts/${path.replace(/^\//, "").split("/").map(encodeURIComponent).join("/")}`;
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    void fetch(base, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("Guida non disponibile. I file originali restano nelle Consegne.");
      const value: Guide = await response.json();
      if (!controller.signal.aborted) setLoaded({ key, value });
    }).catch(reason => { if (!controller.signal.aborted) setError({ key, message: String(reason.message ?? reason) }); });
    return () => controller.abort();
  }, [base, key, open]);
  return <section className="space-y-2" data-testid="delivery-download">
    <div className="flex flex-wrap gap-2">{!guide?.unavailable_files.length && <a className="rounded border px-3 py-2 font-medium" href={`${base}&format=zip`} download>Scarica file e guida</a>}<a className="rounded border px-3 py-2" href={`${base}&format=markdown`} download>Scarica guida</a></div>
    <p className="text-muted-foreground text-xs">File della stessa lavorazione con LEGGIMI e istruzioni. I sorgenti nativi mantengono le verifiche e i limiti registrati.</p>
    <details className="rounded-xl border p-3 text-sm" data-testid="project-guide" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer font-semibold">Guida del progetto · come è stato fatto e come modificarlo</summary>
    {open && <div className="mt-3 space-y-4">
      {guide?.delivery && <p data-testid="source-package-status">{guide.delivery.label} · Sorgenti: {({verified: "pacchetto verificato", incomplete: "pacchetto da completare", not_packaged: "file singoli, pacchetto non preparato", not_applicable: "non previsti", not_verified: "verifica del pacchetto non registrata"} as Record<string,string>)[guide.delivery.source_package_status] ?? "verifica non registrata"}</p>}
      {!!guide?.unavailable_files.length && <p role="alert">Alcuni file registrati non sono più disponibili. La guida indica quelli mancanti; puoi scaricare separatamente i file conservati.</p>}
      {message && <div role="alert">{message} <button type="button" className="underline" onClick={() => setRetry(n => n + 1)}>Riprova</button></div>}
      {!guide && !message && <p>Ricostruisco la guida dalle lavorazioni registrate…</p>}
      {guide && <>
        <section className="space-y-2"><h4 className="font-semibold">Il risultato di questa consegna</h4><p>{guide.result}</p><p className="text-muted-foreground text-xs">{guide.is_current ? "Consegna corrente" : "Consegna precedente o campione"} · {guide.delivery_id} · Controlli tecnici: {status(guide.technical_status)}</p></section>
        <section className="space-y-2"><h4 className="font-semibold">Come è stato fatto</h4><p className="whitespace-pre-wrap">{guide.method.approach || "Metodo non registrato per questa lavorazione."}</p>{steps(guide.method.steps)}
          {!!guide.components.length && <ul className="space-y-1">{guide.components.map((c, i) => <li key={i}>{c.name}: <strong>{c.tool} {c.version}</strong> · {status(c.status)}</li>)}</ul>}
          <p className="text-muted-foreground text-xs">Metodo e istruzioni sono dichiarati dalla squadra. Le verifiche registrate sono riportate separatamente.</p>
          <details><summary className="cursor-pointer">Dalla prima costruzione alle revisioni: procedure registrate</summary><div className="mt-2 space-y-3">{guide.methods.map((m, i) => <details className="rounded border p-2" key={`${m.id}:${i}`}><summary className="cursor-pointer">{m.kind}: {m.approach}{m.selected ? " · questa consegna" : ""}</summary><p className="my-2">{m.actor} · {m.title}</p>{steps(m.steps)}{m.path && <a className="underline" href={artifact(m.path)}>Apri registrazione del metodo</a>}</details>)}{!!guide.methods_omitted && <p>Procedure intermedie omesse: {guide.methods_omitted}.</p>}</div></details>
          <details><summary className="cursor-pointer">Ruoli e responsabilità</summary><ul className="mt-2 space-y-2">{guide.team.map((t, i) => <li key={i}><strong>{t.title}</strong>: {t.goal}</li>)}</ul></details>
        </section>
        <section className="space-y-2"><h4 className="font-semibold">Come usarlo e dove intervenire</h4><p className="whitespace-pre-wrap">{guide.instructions.overview}</p>{steps(guide.instructions.use)}
          {guide.instructions.editing.map((item, i) => <div className="space-y-2 rounded border p-2" key={i}><h5 className="font-medium">{item.goal}</h5><ul>{item.files.map(path => <li key={path}><a className="break-all underline" href={artifact(path)}>{guide.files.find(f => f.path === path)?.name ?? path}</a></li>)}</ul>{steps(item.steps)}{item.check && <p>Controllo dopo la modifica: {item.check}</p>}</div>)}
          {!guide.instructions.editing.length && <p className="text-muted-foreground">Procedure dettagliate non registrate: consulta la mappa dei file e le istruzioni originali incluse.</p>}
          {guide.documents.map(doc => <details key={doc.path}><summary className="cursor-pointer break-all">Istruzioni originali: {doc.name}</summary><pre className="my-2 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded border p-2 text-xs">{doc.text}</pre><a className="underline" href={artifact(doc.path)}>Scarica istruzioni originali</a></details>)}
          <details><summary className="cursor-pointer">Mappa dei file e istruzioni di apertura</summary><ul className="mt-2 space-y-3">{guide.files.map(f => <li key={f.path}><a className="break-all underline" href={artifact(f.path)}>{f.name}</a><p>Apertura: {f.open_with || "Non registrata"}</p><p>Modifiche: {f.editability || "Non registrate"}</p>{f.limitations.map((s, i) => <p className="text-muted-foreground" key={i}>{s}</p>)}</li>)}</ul></details>
        </section>
        <details><summary className="cursor-pointer font-semibold">Storia delle lavorazioni</summary><p className="my-2 text-xs text-muted-foreground">Storia della conversazione, anche di altre consegne e release: non tutti i passaggi appartengono alla versione aperta. Un file diverso non dimostra un miglioramento creativo.</p><ol className="space-y-3">{guide.history.map((entry, i) => <li className="border-l pl-3" key={`${entry.id}:${i}`}><time className="text-xs text-muted-foreground" dateTime={entry.started_at}>{new Date(entry.started_at).toLocaleString()}</time><p><strong>{entry.kind}: {entry.title}</strong></p><p>{entry.actor} · {status(entry.status)}{entry.review_status && ` · Revisione: ${status(entry.review_status)}`}</p>{entry.change === "identical_export" && <p>Export identico al precedente: nessuna modifica al prodotto.</p>}{entry.change === "different_export" && <p>Export con contenuto in byte diverso dal precedente.</p>}{(entry.detail || entry.runtime_image) && <details><summary className="cursor-pointer">Esito e ambiente del passaggio</summary>{entry.detail && <p className="whitespace-pre-wrap break-words">{entry.detail}</p>}{entry.runtime_image && <p className="break-all text-xs text-muted-foreground">Immagine sandbox configurata: {entry.runtime_image}</p>}</details>}</li>)}</ol>{!!guide.history_omitted && <p>Passaggi intermedi omessi dalla sintesi: {guide.history_omitted}.</p>}</details>
        <details><summary className="cursor-pointer font-semibold">Verifiche e limiti</summary><div className="mt-2 space-y-3">{!guide.reviews.length && <p>Nessuna revisione associata agli hash registrati di questa consegna.</p>}{guide.reviews.map((r, i) => <div key={i}><p>Revisione registrata sull’export: {status(r.status)} · {r.matches_current_brief ? "contratto corrente" : "contratto precedente"}</p><p>{r.matches_sources ? "Sorgenti associati agli input della revisione." : "Associazione ai sorgenti di questa consegna non confermata."}</p>{r.path && <a className="underline" href={artifact(r.path)}>Apri rapporto</a>}<ul className="space-y-2">{r.criteria.map((c, j) => <li key={j}><strong>{status(c.status)} · {c.criterion}</strong>{c.scope === "supplementary" && <p className="text-muted-foreground text-xs">Controllo aggiuntivo, fuori dai requisiti concordati.</p>}<p>{c.evidence}</p></li>)}</ul></div>)}<ul>{[...new Set([...guide.limitations, ...guide.method.limits, ...guide.instructions.limits])].map((s, i) => <li key={i}>{s}</li>)}</ul><p className="text-muted-foreground text-xs">La guida documenta il lavoro; non esegue nuove verifiche e non attiva lezioni.</p></div></details>
      </>}
    </div>}
  </details></section>;
}
