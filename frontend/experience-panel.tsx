"use client";
import { useEffect, useRef, useState } from "react";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

type Observation = { id: string; at: string; excluded: boolean; observation: {
  criterion: string; status: string; method: string; evidence: string; corrections: string[];
  tools: Record<string, string>; product_sha256: string; report_sha256: string; source_thread?: string; producer_method?: { status: string; notice: string; declared_method?: { approach: string; steps: string[]; limits: string[] } }; limitations?: string[];
} };
type Impact = { level: "major" | "minor" | "unknown"; basis: "measured" | "observed" | "hypothesis"; reason: string };
type Lesson = { category?: "tool_operation" | "production_method"; approval?: "automatic" | "manual" | "pending"; id: string; accepted: boolean; excluded: boolean; basis: { tool_versions?: Record<string,string>; impact?: Impact; source_ids: string[]; source_statuses?: string[]; lesson: { title: string; applies_when: string; procedure: string[]; verification: string[]; limits: string; tools: string[] } } };
type Library = { total: number; excluded: number; pending?: number; current_project?: { observations: number; pending: number; meaningful: number; lessons: number; lesson_ids: string[] }; curation?: { status: string; message: string }; lessons?: Lesson[]; observations: Observation[] };
export function ExperiencePanel({ threadId, deliveries = [], productionBusy = false, onReadingChange }: { onReadingChange?: (reading: boolean) => void; productionBusy?: boolean; threadId: string; deliveries?: { id: string; title: string; purpose: string }[] }) {
  const [reading, setReading] = useState<string | null>(null);
  const panelRoot = useRef<HTMLDivElement>(null);
  const readerHeading = useRef<HTMLHeadingElement>(null);
  const listPosition = useRef(0);
  const [library, setLibrary] = useState<Library | null>(null);
  const [error, setError] = useState("");
  const [delivery, setDelivery] = useState(deliveries.find(d => d.purpose !== "review")?.id ?? "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [scope, setScope] = useState("current");
  const [showSources, setShowSources] = useState(false);
  const alive = useRef(false);
  const base = `${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-experience`;
  useEffect(() => {
    alive.current = true;
    const controller = new AbortController();
    void fetch(base, { signal: controller.signal, cache: "no-store" }).then(async response => {
      if (!response.ok) { const detail = await response.json().catch(() => ({})); throw new Error(detail.detail || "Modifica non confermata."); }
      const data = await response.json() as Library;
      if (!controller.signal.aborted) setLibrary(data);
    }).catch(() => { if (!controller.signal.aborted) setError("Archivio non disponibile: nessuna esperienza è stata cancellata."); });
    return () => { alive.current = false; controller.abort(); };
  }, [base]);
  useEffect(() => {
    onReadingChange?.(reading !== null);
    const content = panelRoot.current?.closest<HTMLElement>('[data-testid="rh-drawer-content"]');
    if (content) content.scrollTop = reading ? 0 : listPosition.current;
    if (reading) readerHeading.current?.focus({ preventScroll: true });
    return () => onReadingChange?.(false);
  }, [reading, onReadingChange]);
  function readLesson(id: string) {
    listPosition.current = panelRoot.current?.closest<HTMLElement>('[data-testid="rh-drawer-content"]')?.scrollTop ?? 0;
    setReading(id);
  }
  async function change(path: string, body?: object) {
    setBusy(true); setError("");
    try {
      const response = await fetch(base + path, { method: path === "/prefer" || !body ? "POST" : "PUT", headers: { "Content-Type": "application/json" }, ...(body ? { body: JSON.stringify(body) } : {}) });
      if (!response.ok) { const detail = await response.json().catch(() => ({})); throw new Error(detail.detail || "Modifica non confermata."); }
      const data = await response.json() as Library;
      if (alive.current) setLibrary(data);
    } catch (reason) { if (alive.current) setError(reason instanceof Error ? reason.message : "Modifica non confermata. Riapri la scheda per verificare."); }
    finally { if (alive.current) setBusy(false); }
  }
  async function download() {
    setError("");
    try {
      const response = await fetch(base + "?export=true", { cache: "no-store" });
      if (!response.ok) throw new Error();
      const url = URL.createObjectURL(new Blob([JSON.stringify(await response.json(), null, 2)], { type: "application/json" }));
      const link = document.createElement("a"); link.href = url; link.download = "skill-esperienza.json"; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { if (alive.current) setError("Esportazione non riuscita. Le esperienze restano nell’archivio."); }
  }
  const impactRank = (record: Lesson) => {
    const impact = record.basis.impact;
    const key = `${impact?.level ?? "unknown"}:${impact?.basis ?? "hypothesis"}`;
    return ({"major:measured":0,"major:observed":1,"minor:measured":2,"minor:observed":3,"major:hypothesis":4,"minor:hypothesis":5} as Record<string,number>)[key] ?? 6;
  };
  const ordered = [...(library?.lessons ?? [])].filter(record => scope === "library" || library?.current_project?.lesson_ids.includes(record.id)).sort((a,b) => impactRank(a) - impactRank(b));
  const sources = (library?.observations ?? []).filter(record => scope === "library" || record.observation.source_thread === threadId);
  const pending = library?.current_project?.meaningful ?? 0;
  const technical = ordered.filter(record => record.category === "tool_operation");
  const proposals = ordered.filter(record => record.category !== "tool_operation" && !record.accepted && !record.excluded);
  const approved = ordered.filter(record => record.category !== "tool_operation" && record.accepted);
  const lessonCard = (record: Lesson) => <article key={record.id} className="min-w-0 space-y-3 rounded-xl border p-4 [overflow-wrap:anywhere]" data-testid="general-lesson">
      <h4 className="font-semibold">{record.basis.lesson.title}</h4>
      <p className="text-xs font-medium">{record.basis.impact?.level === "major" ? "Miglioramento rilevante" : record.basis.impact?.level === "minor" ? "Perfezionamento minore" : "Impatto da valutare"} · {record.basis.impact?.basis === "measured" ? "con misure registrate" : record.basis.impact?.basis === "observed" ? "osservato" : "da confermare"}</p>
      <p className="text-xs">{record.approval === "automatic" ? "Tecnica attivata automaticamente dopo il test" : record.category === "tool_operation" && !record.accepted ? "In attesa di verifica tecnica automatica" : record.accepted ? "Accettata per il riutilizzo" : "Proposta: non ancora usata nelle skills"}</p>
      {record.basis.impact && <p className="line-clamp-2 text-sm">{record.basis.impact.reason}</p>}
      <button type="button" className="rounded border px-3 py-2 text-left" data-testid="read-lesson" onClick={() => readLesson(record.id)}>Leggi la lezione completa</button>
      {(record.category !== "tool_operation" || record.accepted) && <button className="rounded border px-3 py-2 disabled:opacity-50" disabled={busy} onClick={() => void change("/lesson", { id: record.id, accepted: !record.accepted })}>{record.accepted ? "Rimuovi dalle skills" : "Accetta questa lezione"}</button>}
    </article>;

  const selected = library?.lessons?.find(record => record.id === reading);
  if (selected) {
    const lesson = selected.basis.lesson;
    return <div ref={panelRoot} className="min-w-0 space-y-5 text-sm [overflow-wrap:anywhere]" data-testid="lesson-reader">
      <button type="button" className="bg-background sticky top-0 z-10 rounded border px-3 py-2" onClick={() => setReading(null)}>← Torna alle lezioni</button>
      <h4 ref={readerHeading} tabIndex={-1} className="text-lg font-semibold outline-none">{lesson.title}</h4>
      <p>{selected.excluded ? "Archiviata: non viene riutilizzata." : selected.accepted ? "Accettata per il riutilizzo quando pertinente al progetto." : selected.category === "tool_operation" ? "Nota tecnica: inattiva finché non supera la verifica automatica." : "Proposta di metodo: non ancora usata nelle skills."}</p>
      {selected.basis.impact && <section className="space-y-2"><h5 className="font-semibold">{selected.basis.impact.basis === "hypothesis" ? "Beneficio da verificare" : "Beneficio osservato"}</h5><p className="whitespace-pre-wrap" data-testid="lesson-full-impact">{selected.basis.impact.reason}</p></section>}
      <section className="space-y-2"><h5 className="font-semibold">Quando usarla</h5><p className="whitespace-pre-wrap">{lesson.applies_when}</p></section>
      <section className="space-y-2"><h5 className="font-semibold">Procedimento</h5><ol className="list-inside list-decimal space-y-3">{lesson.procedure.map((step,i) => <li className="whitespace-pre-wrap" key={i}>{step}</li>)}</ol></section>
      <section className="space-y-2"><h5 className="font-semibold">Come verificarla</h5><ul className="list-inside list-disc space-y-3">{lesson.verification.map((step,i) => <li className="whitespace-pre-wrap" key={i}>{step}</li>)}</ul></section>
      <section className="space-y-2"><h5 className="font-semibold">Limiti</h5><p className="whitespace-pre-wrap" data-testid="lesson-full-limits">{lesson.limits}</p></section>
      <details className="space-y-2 rounded border p-3"><summary className="cursor-pointer font-medium">Fonti e strumenti ({selected.basis.source_ids.length})</summary>
        <p className="my-2">Strumenti: {Object.entries(selected.basis.tool_versions ?? {}).map(([tool,version]) => `${tool} ${version}`).join(", ") || "Principio generale"}</p>
        <p className="my-2 text-xs">Le prove del progetto di origine non garantiscono lo stesso beneficio in un altro progetto.</p>
        {library?.observations.filter(source => selected.basis.source_ids.includes(source.id)).map(source => <div className="my-3 space-y-2" key={source.id}><p className="whitespace-pre-wrap">{source.observation.evidence}</p>{source.observation.source_thread && <a className="underline" href={`/workspace/chats/${encodeURIComponent(source.observation.source_thread)}`}>Apri progetto di origine</a>}</div>)}
      </details>
      {error && <p role="alert">{error}</p>}
      {!selected.excluded && (selected.category !== "tool_operation" || selected.accepted) && <button className="rounded border px-3 py-2 disabled:opacity-50" disabled={busy} onClick={() => void change("/lesson",{id:selected.id,accepted:!selected.accepted})}>{selected.accepted ? "Rimuovi dalle skills" : "Accetta questa lezione"}</button>}
    </div>;
  }

  return <div ref={panelRoot} className="min-w-0 space-y-3 text-sm" data-testid="experience-panel">
    <p>Una fonte è un’osservazione, una lezione è una regola generale salvata. I metodi entrano nelle skills dopo la tua accettazione; le tecniche dopo un test verificabile, se pertinenti agli strumenti e alle versioni.</p>
    <div className="flex gap-2"><button className="rounded border px-3 py-2" aria-pressed={scope === "current"} onClick={() => { setScope("current"); setShowSources(false); }}>Questo progetto</button><button className="rounded border px-3 py-2" aria-pressed={scope === "library"} onClick={() => { setScope("library"); setShowSources(false); }}>Archivio personale</button></div>
    {scope === "library" && <p className="text-xs text-muted-foreground">Include altri progetti dello stesso account. Le lezioni attive compatibili si possono riutilizzare anche nelle nuove chat.</p>}
    {error && <p role="alert">{error}</p>}
    {!library && !error && <p role="status">Carico proposte e lezioni accettate…</p>}
    {library && <p>{proposals.length} metodi da valutare · {approved.length} metodi accettati · {technical.filter(record => record.accepted && !record.excluded).length} conoscenze tecniche attive{technical.some(record => !record.accepted && !record.excluded) && ` · ${technical.filter(record => !record.accepted && !record.excluded).length} note tecniche da verificare`}</p>}
    {library && <div className="space-y-2" data-testid="curation-controls"><p className="text-xs">{library.current_project?.observations ?? 0} fonti di questo progetto · {pending} osservazioni significative da valutare.</p><button className="rounded border px-3 py-2 disabled:opacity-50" disabled={busy || productionBusy || !pending} onClick={() => void change("/curate")}>{busy ? "Valutazione in corso…" : "Valuta le osservazioni"}</button>{productionBusy && <p className="text-xs text-muted-foreground">Disponibile al termine della lavorazione. Aprire questa scheda non ferma il progetto.</p>}{!pending && <p className="text-xs text-muted-foreground">Nessuna nuova scoperta significativa da valutare. È normale: un comando riuscito non richiede una nuova lezione.</p>}{library.curation && <p role="status">{library.curation.message}</p>}</div>}
    {proposals.slice(0, 3).map(lessonCard)}
    {proposals.length > 3 && <details className="rounded-xl border p-3"><summary className="cursor-pointer font-medium">Altre proposte ({proposals.length - 3})</summary><div className="mt-3 space-y-3">{proposals.slice(3).map(lessonCard)}</div></details>}
    {approved.length > 0 && <details className="rounded-xl border p-3" data-testid="accepted-lessons"><summary className="cursor-pointer font-medium">Lezioni accettate ({approved.length})</summary><div className="mt-3 space-y-3">{approved.map(lessonCard)}</div></details>}
    {technical.length > 0 && <details className="rounded-xl border p-3" data-testid="technical-lessons"><summary className="cursor-pointer font-medium">Conoscenze tecniche ({technical.length})</summary><p className="my-2 text-xs">Non richiedono la tua approvazione. Senza un test verificabile restano inattive; puoi rimuovere quelle attive.</p><div className="space-y-3">{technical.map(lessonCard)}</div></details>}
    {library && !library.lessons?.length && <p>Nessuna lezione generale ancora compilata. Le fonti già conservate non vengono copiate nelle nuove skills.</p>}
    <details className="space-y-3 rounded-xl border p-3"><summary className="cursor-pointer font-medium">Fonti e preferenze · {scope === "current" ? "questo progetto" : "archivio personale"} ({sources.length})</summary>
    <div className="flex flex-wrap gap-2">
      <button className="rounded border px-3 py-2 disabled:opacity-50" disabled={busy} onClick={() => void change("/collect")}>Recupera esperienza di questa chat</button>
      <button className="rounded border px-3 py-2" disabled={!library} onClick={() => void download()}>Esporta esperienza</button>
    </div>
    <div className="space-y-2 rounded border p-3">
      <p className="font-medium">Conserva un metodo che ti ha soddisfatto</p>
      <label className="block">Lavorazione<select className="w-full rounded border p-2" value={delivery} onChange={event => setDelivery(event.target.value)}>{deliveries.filter(d => d.purpose !== "review").map(d => <option key={d.id} value={d.id}>{d.title || d.id}</option>)}</select></label>
      <label className="block">Cosa vuoi riutilizzare?<textarea className="w-full rounded border p-2" maxLength={2000} value={note} onChange={event => setNote(event.target.value)} placeholder="Ad esempio: cambiare metodo dopo il campione, conservare la struttura valida, verificare due casi diversi." /></label>
      <button className="rounded border px-3 py-2 disabled:opacity-50" disabled={busy || !delivery || note.trim().length < 5} onClick={() => void change("/prefer", { delivery_id: delivery, note })}>Conserva questo metodo</button>
      <p className="text-xs text-muted-foreground">Conserva una fonte per la successiva generalizzazione del coordinatore. Non entra direttamente nelle skills.</p>
    </div>
    {library?.total === 0 && <p>Nessuna revisione utilizzabile ancora registrata. I soli comandi riusciti non diventano buone pratiche.</p>}
    {sources.slice(0,showSources ? undefined : 6).map(record => <article className="space-y-2 rounded border p-3" key={record.id}>
      <p className="font-medium">{record.observation.criterion}</p>
      <p>{record.observation.status === "preferred_by_user" ? "Metodo preferito dall’utente" : record.observation.status === "sandbox_observation" ? "Scoperta operativa della sandbox" : record.observation.status === "needs_generalization" ? "Appunto conservato da generalizzare, non verificato" : record.observation.status === "passed" ? "Esito positivo osservato" : "Difetto osservato"} · {record.observation.method} · {record.excluded ? "Esclusa" : "Fonte conservata, separata dalle skills"}</p>
      <p>{record.observation.evidence}</p>
      {record.observation.producer_method && <details><summary>Procedimento conservato</summary><p>{record.observation.producer_method.notice}</p><p>{record.observation.producer_method.declared_method?.approach}</p><ol className="list-inside list-decimal">{record.observation.producer_method.declared_method?.steps.map((step, i) => <li key={i}>{step}</li>)}</ol></details>}
      {record.observation.limitations?.map((limit, i) => <p key={i}>Limite conservato: {limit}</p>)}
      {record.observation.corrections.map((action, i) => <p key={i}>Correzione proposta: {action}</p>)}
      <p>Strumenti: {Object.entries(record.observation.tools).map(([tool, version]) => `${tool} ${version}`).join(", ") || "Workspace generale"}</p>
      {record.observation.source_thread && <a className="underline" href={`/workspace/chats/${encodeURIComponent(record.observation.source_thread)}`}>Apri il progetto di origine</a>}
      <details><summary>Provenienza e versioni</summary><p className="break-all">Prodotto SHA256: {record.observation.product_sha256}</p><p className="break-all">Rapporto SHA256: {record.observation.report_sha256}</p></details>

    </article>)}
    {sources.length > 6 && <button className="rounded border px-3 py-2" onClick={() => setShowSources(value => !value)}>{showSources ? "Mostra meno fonti" : `Mostra altre ${sources.length-6} fonti`}</button>}
    </details>
  </div>;
}
