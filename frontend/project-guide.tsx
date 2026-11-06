"use client";
import { useEffect, useState } from "react";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import {tr, useUiLanguage, trMap} from "@/core/i18n/ui-text";

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
const states: Record<string, string> = trMap({ passed:["Superato", "Passed"], completed:["Conclusa", "Completed"], running:["In corso", "In progress"], paused:["Fermata", "Stopped"], needs_revision:["Da correggere", "To fix"], not_run:["Non eseguito", "Not run"], not_verified:["Non verificato", "Not verified"], needs_review:["Da valutare", "To assess"], failed:["Fallito", "Failed"] });
const status = (value: string) => states[value] ?? value;
const steps = (items: string[]) => <ol className="list-decimal space-y-1 pl-5">{items.map((item, i) => <li className="whitespace-pre-wrap break-words" key={i}>{item}</li>)}</ol>;

export function ProjectGuide({ threadId, deliveryId, revision }: { threadId: string; deliveryId: string; revision?: string }) {useUiLanguage();
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
      if (!response.ok) throw new Error(tr("Guida non disponibile. I file originali restano nelle Consegne.", "Guide unavailable. The original files remain in Deliveries."));
      const value: Guide = await response.json();
      if (!controller.signal.aborted) setLoaded({ key, value });
    }).catch(reason => { if (!controller.signal.aborted) setError({ key, message: String(reason.message ?? reason) }); });
    return () => controller.abort();
  }, [base, key, open]);
  return <section className="space-y-2" data-testid="delivery-download">
    <div className="flex flex-wrap gap-2">{!guide?.unavailable_files.length && <a className="rounded border px-3 py-2 font-medium" href={`${base}&format=zip`} download>{tr("Scarica file e guida", "Download files and guide")}</a>}<a className="rounded border px-3 py-2" href={`${base}&format=markdown`} download>{tr("Scarica guida", "Download guide")}</a></div>
    <p className="text-muted-foreground text-xs">{tr("File della stessa lavorazione con LEGGIMI e istruzioni. I sorgenti nativi mantengono le verifiche e i limiti registrati.", "Files from the same work step with README and instructions. Native sources keep their recorded checks and limits.")}</p>
    <details className="rounded-xl border p-3 text-sm" data-testid="project-guide" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer font-semibold">{tr("Guida del progetto · come è stato fatto e come modificarlo", "Project guide · how it was made and how to change it")}</summary>
    {open && <div className="mt-3 space-y-4">
      {guide?.delivery && <p data-testid="source-package-status">{guide.delivery.label} {tr("· Sorgenti:", "· Sources:")} {({verified: tr("pacchetto verificato", "package verified"), incomplete: tr("pacchetto da completare", "package to complete"), not_packaged: tr("file singoli, pacchetto non preparato", "single files, package not prepared"), not_applicable: tr("non previsti", "not planned"), not_verified: tr("verifica del pacchetto non registrata", "package check not recorded")} as Record<string,string>)[guide.delivery.source_package_status] ?? tr("verifica non registrata", "check not recorded")}</p>}
      {!!guide?.unavailable_files.length && <p role="alert">{tr("Alcuni file registrati non sono più disponibili. La guida indica quelli mancanti; puoi scaricare separatamente i file conservati.", "Some recorded files are no longer available. The guide lists the missing ones; you can download the kept files separately.")}</p>}
      {message && <div role="alert">{message} <button type="button" className="underline" onClick={() => setRetry(n => n + 1)}>{tr("Riprova", "Retry")}</button></div>}
      {!guide && !message && <p>{tr("Ricostruisco la guida dalle lavorazioni registrate…", "Rebuilding the guide from the recorded work…")}</p>}
      {guide && <>
        <section className="space-y-2"><h4 className="font-semibold">{tr("Il risultato di questa consegna", "The result of this delivery")}</h4><p>{guide.result}</p><p className="text-muted-foreground text-xs">{guide.is_current ? tr("Consegna corrente", "Current delivery") : tr("Consegna precedente o campione", "Previous delivery or sample")} · {guide.delivery_id} {tr("· Controlli tecnici:", "· Technical checks:")} {status(guide.technical_status)}</p></section>
        <section className="space-y-2"><h4 className="font-semibold">{tr("Come è stato fatto", "How it was made")}</h4><p className="whitespace-pre-wrap">{guide.method.approach || tr("Metodo non registrato per questa lavorazione.", "Method not recorded for this work step.")}</p>{steps(guide.method.steps)}
          {!!guide.components.length && <ul className="space-y-1">{guide.components.map((c, i) => <li key={i}>{c.name}: <strong>{c.tool} {c.version}</strong> · {status(c.status)}</li>)}</ul>}
          <p className="text-muted-foreground text-xs">{tr("Metodo e istruzioni sono dichiarati dalla squadra. Le verifiche registrate sono riportate separatamente.", "Method and instructions are declared by the team. Recorded checks are listed separately.")}</p>
          <details><summary className="cursor-pointer">{tr("Dalla prima costruzione alle revisioni: procedure registrate", "From the first build to the revisions: recorded procedures")}</summary><div className="mt-2 space-y-3">{guide.methods.map((m, i) => <details className="rounded border p-2" key={`${m.id}:${i}`}><summary className="cursor-pointer">{m.kind}: {m.approach}{m.selected ? tr(" · questa consegna", " · this delivery") : ""}</summary><p className="my-2">{m.actor} · {m.title}</p>{steps(m.steps)}{m.path && <a className="underline" href={artifact(m.path)}>{tr("Apri registrazione del metodo", "Open method record")}</a>}</details>)}{!!guide.methods_omitted && <p>{tr("Procedure intermedie omesse:", "Intermediate procedures omitted:")} {guide.methods_omitted}.</p>}</div></details>
          <details><summary className="cursor-pointer">{tr("Ruoli e responsabilità", "Roles and responsibilities")}</summary><ul className="mt-2 space-y-2">{guide.team.map((t, i) => <li key={i}><strong>{t.title}</strong>: {t.goal}</li>)}</ul></details>
        </section>
        <section className="space-y-2"><h4 className="font-semibold">{tr("Come usarlo e dove intervenire", "How to use it and where to change it")}</h4><p className="whitespace-pre-wrap">{guide.instructions.overview}</p>{steps(guide.instructions.use)}
          {guide.instructions.editing.map((item, i) => <div className="space-y-2 rounded border p-2" key={i}><h5 className="font-medium">{item.goal}</h5><ul>{item.files.map(path => <li key={path}><a className="break-all underline" href={artifact(path)}>{guide.files.find(f => f.path === path)?.name ?? path}</a></li>)}</ul>{steps(item.steps)}{item.check && <p>{tr("Controllo dopo la modifica:", "Check after the change:")} {item.check}</p>}</div>)}
          {!guide.instructions.editing.length && <p className="text-muted-foreground">{tr("Procedure dettagliate non registrate: consulta la mappa dei file e le istruzioni originali incluse.", "Detailed procedures not recorded: see the file map and the original instructions included.")}</p>}
          {guide.documents.map(doc => <details key={doc.path}><summary className="cursor-pointer break-all">{tr("Istruzioni originali:", "Original instructions:")} {doc.name}</summary><pre className="my-2 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded border p-2 text-xs">{doc.text}</pre><a className="underline" href={artifact(doc.path)}>{tr("Scarica istruzioni originali", "Download original instructions")}</a></details>)}
          <details><summary className="cursor-pointer">{tr("Mappa dei file e istruzioni di apertura", "File map and opening instructions")}</summary><ul className="mt-2 space-y-3">{guide.files.map(f => <li key={f.path}><a className="break-all underline" href={artifact(f.path)}>{f.name}</a><p>{tr("Apertura:", "Opening:")} {f.open_with || tr("Non registrata", "Not recorded")}</p><p>{tr("Modifiche:", "Changes:")} {f.editability || tr("Non registrate", "Not recorded")}</p>{f.limitations.map((s, i) => <p className="text-muted-foreground" key={i}>{s}</p>)}</li>)}</ul></details>
        </section>
        <details><summary className="cursor-pointer font-semibold">{tr("Storia delle lavorazioni", "Work history")}</summary><p className="my-2 text-xs text-muted-foreground">{tr("Storia della conversazione, anche di altre consegne e release: non tutti i passaggi appartengono alla versione aperta. Un file diverso non dimostra un miglioramento creativo.", "Conversation history, including other deliveries and releases: not every step belongs to the open version. A different file does not prove a creative improvement.")}</p><ol className="space-y-3">{guide.history.map((entry, i) => <li className="border-l pl-3" key={`${entry.id}:${i}`}><time className="text-xs text-muted-foreground" dateTime={entry.started_at}>{new Date(entry.started_at).toLocaleString()}</time><p><strong>{entry.kind}: {entry.title}</strong></p><p>{entry.actor} · {status(entry.status)}{entry.review_status && ` · Revisione: ${status(entry.review_status)}`}</p>{entry.change === "identical_export" && <p>{tr("Export identico al precedente: nessuna modifica al prodotto.", "Export identical to the previous one: no change to the product.")}</p>}{entry.change === "different_export" && <p>{tr("Export con contenuto in byte diverso dal precedente.", "Export with byte content different from the previous one.")}</p>}{(entry.detail || entry.runtime_image) && <details><summary className="cursor-pointer">{tr("Esito e ambiente del passaggio", "Outcome and environment of the step")}</summary>{entry.detail && <p className="whitespace-pre-wrap break-words">{entry.detail}</p>}{entry.runtime_image && <p className="break-all text-xs text-muted-foreground">{tr("Immagine sandbox configurata:", "Configured sandbox image:")} {entry.runtime_image}</p>}</details>}</li>)}</ol>{!!guide.history_omitted && <p>{tr("Passaggi intermedi omessi dalla sintesi:", "Intermediate steps omitted from the summary:")} {guide.history_omitted}.</p>}</details>
        <details><summary className="cursor-pointer font-semibold">{tr("Verifiche e limiti", "Checks and limits")}</summary><div className="mt-2 space-y-3">{!guide.reviews.length && <p>{tr("Nessuna revisione associata agli hash registrati di questa consegna.", "No review linked to the recorded hashes of this delivery.")}</p>}{guide.reviews.map((r, i) => <div key={i}><p>{tr("Revisione registrata sull’export:", "Review recorded on the export:")} {status(r.status)} · {r.matches_current_brief ? tr("contratto corrente", "current contract") : tr("contratto precedente", "previous contract")}</p><p>{r.matches_sources ? tr("Sorgenti associati agli input della revisione.", "Sources linked to the review inputs.") : tr("Associazione ai sorgenti di questa consegna non confermata.", "Link to the sources of this delivery not confirmed.")}</p>{r.path && <a className="underline" href={artifact(r.path)}>{tr("Apri rapporto", "Open report")}</a>}<ul className="space-y-2">{r.criteria.map((c, j) => <li key={j}><strong>{status(c.status)} · {c.criterion}</strong>{c.scope === "supplementary" && <p className="text-muted-foreground text-xs">{tr("Controllo aggiuntivo, fuori dai requisiti concordati.", "Additional check, outside the agreed requirements.")}</p>}<p>{c.evidence}</p></li>)}</ul></div>)}<ul>{[...new Set([...guide.limitations, ...guide.method.limits, ...guide.instructions.limits])].map((s, i) => <li key={i}>{s}</li>)}</ul><p className="text-muted-foreground text-xs">{tr("La guida documenta il lavoro; non esegue nuove verifiche e non attiva lezioni.", "The guide documents the work; it runs no new checks and enables no lessons.")}</p></div></details>
      </>}
    </div>}
  </details></section>;
}
