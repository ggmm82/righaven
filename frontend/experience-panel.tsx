"use client";
import { useEffect, useRef, useState } from "react";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import {tr, useUiLanguage} from "@/core/i18n/ui-text";

type Observation = { id: string; at: string; excluded: boolean; observation: {
  criterion: string; status: string; method: string; evidence: string; corrections: string[];
  tools: Record<string, string>; product_sha256: string; report_sha256: string; source_thread?: string; producer_method?: { status: string; notice: string; declared_method?: { approach: string; steps: string[]; limits: string[] } }; limitations?: string[];
} };
type Impact = { level: "major" | "minor" | "unknown"; basis: "measured" | "observed" | "hypothesis"; reason: string };
type Lesson = { category?: "tool_operation" | "production_method"; approval?: "automatic" | "manual" | "pending"; id: string; accepted: boolean; excluded: boolean; basis: { tool_versions?: Record<string,string>; impact?: Impact; source_ids: string[]; source_statuses?: string[]; lesson: { title: string; applies_when: string; procedure: string[]; verification: string[]; limits: string; tools: string[] } } };
type Library = { total: number; excluded: number; pending?: number; current_project?: { observations: number; pending: number; meaningful: number; lessons: number; lesson_ids: string[] }; curation?: { status: string; message: string }; lessons?: Lesson[]; observations: Observation[] };
export function ExperiencePanel({ threadId, deliveries = [], productionBusy = false, onReadingChange }: { onReadingChange?: (reading: boolean) => void; productionBusy?: boolean; threadId: string; deliveries?: { id: string; title: string; purpose: string }[] }) {useUiLanguage();
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
      if (!response.ok) { const detail = await response.json().catch(() => ({})); throw new Error(detail.detail || tr("Modifica non confermata.", "Change not confirmed.")); }
      const data = await response.json() as Library;
      if (!controller.signal.aborted) setLibrary(data);
    }).catch(() => { if (!controller.signal.aborted) setError(tr("Archivio non disponibile: nessuna esperienza è stata cancellata.", "Archive unavailable: no experience was deleted.")); });
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
      if (!response.ok) { const detail = await response.json().catch(() => ({})); throw new Error(detail.detail || tr("Modifica non confermata.", "Change not confirmed.")); }
      const data = await response.json() as Library;
      if (alive.current) setLibrary(data);
    } catch (reason) { if (alive.current) setError(reason instanceof Error ? reason.message : tr("Modifica non confermata. Riapri la scheda per verificare.", "Change not confirmed. Reopen the tab to check.")); }
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
    } catch { if (alive.current) setError(tr("Esportazione non riuscita. Le esperienze restano nell’archivio.", "Export failed. Experiences remain in the archive.")); }
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
      <p className="text-xs font-medium">{record.basis.impact?.level === "major" ? tr("Miglioramento rilevante", "Significant improvement") : record.basis.impact?.level === "minor" ? tr("Perfezionamento minore", "Minor refinement") : tr("Impatto da valutare", "Impact to assess")} · {record.basis.impact?.basis === "measured" ? tr("con misure registrate", "with recorded measurements") : record.basis.impact?.basis === "observed" ? "osservato" : tr("da confermare", "to confirm")}</p>
      <p className="text-xs">{record.approval === "automatic" ? tr("Tecnica attivata automaticamente dopo il test", "Technique enabled automatically after the test") : record.category === "tool_operation" && !record.accepted ? tr("In attesa di verifica tecnica automatica", "Waiting for automatic technical check") : record.accepted ? tr("Accettata per il riutilizzo", "Accepted for reuse") : tr("Proposta: non ancora usata nelle skills", "Proposal: not yet used in the skills")}</p>
      {record.basis.impact && <p className="line-clamp-2 text-sm">{record.basis.impact.reason}</p>}
      <button type="button" className="rounded border px-3 py-2 text-left" data-testid="read-lesson" onClick={() => readLesson(record.id)}>{tr("Leggi la lezione completa", "Read the full lesson")}</button>
      {(record.category !== "tool_operation" || record.accepted) && <button className="rounded border px-3 py-2 disabled:opacity-50" disabled={busy} onClick={() => void change("/lesson", { id: record.id, accepted: !record.accepted })}>{record.accepted ? tr("Rimuovi dalle skills", "Remove from skills") : tr("Accetta questa lezione", "Accept this lesson")}</button>}
    </article>;

  const selected = library?.lessons?.find(record => record.id === reading);
  if (selected) {
    const lesson = selected.basis.lesson;
    return <div ref={panelRoot} className="min-w-0 space-y-5 text-sm [overflow-wrap:anywhere]" data-testid="lesson-reader">
      <button type="button" className="bg-background sticky top-0 z-10 rounded border px-3 py-2" onClick={() => setReading(null)}>{tr("← Torna alle lezioni", "← Back to lessons")}</button>
      <h4 ref={readerHeading} tabIndex={-1} className="text-lg font-semibold outline-none">{lesson.title}</h4>
      <p>{selected.excluded ? tr("Archiviata: non viene riutilizzata.", "Archived: not reused.") : selected.accepted ? tr("Accettata per il riutilizzo quando pertinente al progetto.", "Accepted for reuse when relevant to the project.") : selected.category === "tool_operation" ? tr("Nota tecnica: inattiva finché non supera la verifica automatica.", "Technical note: inactive until it passes the automatic check.") : tr("Proposta di metodo: non ancora usata nelle skills.", "Method proposal: not yet used in the skills.")}</p>
      {selected.basis.impact && <section className="space-y-2"><h5 className="font-semibold">{selected.basis.impact.basis === "hypothesis" ? tr("Beneficio da verificare", "Benefit to verify") : tr("Beneficio osservato", "Observed benefit")}</h5><p className="whitespace-pre-wrap" data-testid="lesson-full-impact">{selected.basis.impact.reason}</p></section>}
      <section className="space-y-2"><h5 className="font-semibold">{tr("Quando usarla", "When to use it")}</h5><p className="whitespace-pre-wrap">{lesson.applies_when}</p></section>
      <section className="space-y-2"><h5 className="font-semibold">{tr("Procedimento", "Procedure")}</h5><ol className="list-inside list-decimal space-y-3">{lesson.procedure.map((step,i) => <li className="whitespace-pre-wrap" key={i}>{step}</li>)}</ol></section>
      <section className="space-y-2"><h5 className="font-semibold">{tr("Come verificarla", "How to verify it")}</h5><ul className="list-inside list-disc space-y-3">{lesson.verification.map((step,i) => <li className="whitespace-pre-wrap" key={i}>{step}</li>)}</ul></section>
      <section className="space-y-2"><h5 className="font-semibold">{tr("Limiti", "Limits")}</h5><p className="whitespace-pre-wrap" data-testid="lesson-full-limits">{lesson.limits}</p></section>
      <details className="space-y-2 rounded border p-3"><summary className="cursor-pointer font-medium">{tr("Fonti e strumenti (", "Sources and tools (")}{selected.basis.source_ids.length})</summary>
        <p className="my-2">{tr("Strumenti:", "Tools:")} {Object.entries(selected.basis.tool_versions ?? {}).map(([tool,version]) => `${tool} ${version}`).join(", ") || tr("Principio generale", "General principle")}</p>
        <p className="my-2 text-xs">{tr("Le prove del progetto di origine non garantiscono lo stesso beneficio in un altro progetto.", "Evidence from the source project does not guarantee the same benefit in another project.")}</p>
        {library?.observations.filter(source => selected.basis.source_ids.includes(source.id)).map(source => <div className="my-3 space-y-2" key={source.id}><p className="whitespace-pre-wrap">{source.observation.evidence}</p>{source.observation.source_thread && <a className="underline" href={`/workspace/chats/${encodeURIComponent(source.observation.source_thread)}`}>{tr("Apri progetto di origine", "Open source project")}</a>}</div>)}
      </details>
      {error && <p role="alert">{error}</p>}
      {!selected.excluded && (selected.category !== "tool_operation" || selected.accepted) && <button className="rounded border px-3 py-2 disabled:opacity-50" disabled={busy} onClick={() => void change("/lesson",{id:selected.id,accepted:!selected.accepted})}>{selected.accepted ? tr("Rimuovi dalle skills", "Remove from skills") : tr("Accetta questa lezione", "Accept this lesson")}</button>}
    </div>;
  }

  return <div ref={panelRoot} className="min-w-0 space-y-3 text-sm" data-testid="experience-panel">
    <p>{tr("Una fonte è un’osservazione, una lezione è una regola generale salvata. I metodi entrano nelle skills dopo la tua accettazione; le tecniche dopo un test verificabile, se pertinenti agli strumenti e alle versioni.", "A source is an observation; a lesson is a saved general rule. Methods enter the skills after you accept them; techniques after a verifiable test, if relevant to the tools and versions.")}</p>
    <div className="flex gap-2"><button className="rounded border px-3 py-2" aria-pressed={scope === "current"} onClick={() => { setScope("current"); setShowSources(false); }}>{tr("Questo progetto", "This project")}</button><button className="rounded border px-3 py-2" aria-pressed={scope === "library"} onClick={() => { setScope("library"); setShowSources(false); }}>{tr("Archivio personale", "Personal archive")}</button></div>
    {scope === "library" && <p className="text-xs text-muted-foreground">{tr("Include altri progetti dello stesso account. Le lezioni attive compatibili si possono riutilizzare anche nelle nuove chat.", "Includes other projects of the same account. Compatible active lessons can be reused in new chats too.")}</p>}
    {error && <p role="alert">{error}</p>}
    {!library && !error && <p role="status">{tr("Carico proposte e lezioni accettate…", "Loading proposals and accepted lessons…")}</p>}
    {library && <p>{proposals.length} {tr("metodi da valutare ·", "methods to assess ·")} {approved.length} {tr("metodi accettati ·", "methods accepted ·")} {technical.filter(record => record.accepted && !record.excluded).length} {tr("conoscenze tecniche attive", "active technical knowledge")}{technical.some(record => !record.accepted && !record.excluded) && ` · ${technical.filter(record => !record.accepted && !record.excluded).length} note tecniche da verificare`}</p>}
    {library && <div className="space-y-2" data-testid="curation-controls"><p className="text-xs">{library.current_project?.observations ?? 0} {tr("fonti di questo progetto ·", "sources from this project ·")} {pending} {tr("osservazioni significative da valutare.", "significant observations to assess.")}</p><button className="rounded border px-3 py-2 disabled:opacity-50" disabled={busy || productionBusy || !pending} onClick={() => void change("/curate")}>{busy ? tr("Valutazione in corso…", "Assessment in progress…") : tr("Valuta le osservazioni", "Assess the observations")}</button>{productionBusy && <p className="text-xs text-muted-foreground">{tr("Disponibile al termine della lavorazione. Aprire questa scheda non ferma il progetto.", "Available when the work step ends. Opening this tab does not stop the project.")}</p>}{!pending && <p className="text-xs text-muted-foreground">{tr("Nessuna nuova scoperta significativa da valutare. È normale: un comando riuscito non richiede una nuova lezione.", "No significant new finding to assess. That is normal: a successful command does not need a new lesson.")}</p>}{library.curation && <p role="status">{library.curation.message}</p>}</div>}
    {proposals.slice(0, 3).map(lessonCard)}
    {proposals.length > 3 && <details className="rounded-xl border p-3"><summary className="cursor-pointer font-medium">{tr("Altre proposte (", "Other proposals (")}{proposals.length - 3})</summary><div className="mt-3 space-y-3">{proposals.slice(3).map(lessonCard)}</div></details>}
    {approved.length > 0 && <details className="rounded-xl border p-3" data-testid="accepted-lessons"><summary className="cursor-pointer font-medium">{tr("Lezioni accettate (", "Accepted lessons (")}{approved.length})</summary><div className="mt-3 space-y-3">{approved.map(lessonCard)}</div></details>}
    {technical.length > 0 && <details className="rounded-xl border p-3" data-testid="technical-lessons"><summary className="cursor-pointer font-medium">{tr("Conoscenze tecniche (", "Technical knowledge (")}{technical.length})</summary><p className="my-2 text-xs">{tr("Non richiedono la tua approvazione. Senza un test verificabile restano inattive; puoi rimuovere quelle attive.", "They do not need your approval. Without a verifiable test they stay inactive; you can remove the active ones.")}</p><div className="space-y-3">{technical.map(lessonCard)}</div></details>}
    {library && !library.lessons?.length && <p>{tr("Nessuna lezione generale ancora compilata. Le fonti già conservate non vengono copiate nelle nuove skills.", "No general lesson compiled yet. Sources already kept are not copied into new skills.")}</p>}
    <details className="space-y-3 rounded-xl border p-3"><summary className="cursor-pointer font-medium">{tr("Fonti e preferenze ·", "Sources and preferences ·")} {scope === "current" ? tr("questo progetto", "this project") : tr("archivio personale", "personal archive")} ({sources.length})</summary>
    <div className="flex flex-wrap gap-2">
      <button className="rounded border px-3 py-2 disabled:opacity-50" disabled={busy} onClick={() => void change("/collect")}>{tr("Recupera esperienza di questa chat", "Recover experience from this chat")}</button>
      <button className="rounded border px-3 py-2" disabled={!library} onClick={() => void download()}>{tr("Esporta esperienza", "Export experience")}</button>
    </div>
    <div className="space-y-2 rounded border p-3">
      <p className="font-medium">{tr("Conserva un metodo che ti ha soddisfatto", "Keep a method that satisfied you")}</p>
      <label className="block">{tr("Lavorazione", "Work step")}<select className="w-full rounded border p-2" value={delivery} onChange={event => setDelivery(event.target.value)}>{deliveries.filter(d => d.purpose !== "review").map(d => <option key={d.id} value={d.id}>{d.title || d.id}</option>)}</select></label>
      <label className="block">{tr("Cosa vuoi riutilizzare?", "What do you want to reuse?")}<textarea className="w-full rounded border p-2" maxLength={2000} value={note} onChange={event => setNote(event.target.value)} placeholder={tr("Ad esempio: cambiare metodo dopo il campione, conservare la struttura valida, verificare due casi diversi.", "For example: change method after the sample, keep the valid structure, check two different cases.")} /></label>
      <button className="rounded border px-3 py-2 disabled:opacity-50" disabled={busy || !delivery || note.trim().length < 5} onClick={() => void change("/prefer", { delivery_id: delivery, note })}>{tr("Conserva questo metodo", "Keep this method")}</button>
      <p className="text-xs text-muted-foreground">{tr("Conserva una fonte per la successiva generalizzazione del coordinatore. Non entra direttamente nelle skills.", "Keeps a source for the coordinator's later generalization. It does not go directly into the skills.")}</p>
    </div>
    {library?.total === 0 && <p>{tr("Nessuna revisione utilizzabile ancora registrata. I soli comandi riusciti non diventano buone pratiche.", "No usable review recorded yet. Successful commands alone do not become best practices.")}</p>}
    {sources.slice(0,showSources ? undefined : 6).map(record => <article className="space-y-2 rounded border p-3" key={record.id}>
      <p className="font-medium">{record.observation.criterion}</p>
      <p>{record.observation.status === "preferred_by_user" ? tr("Metodo preferito dall’utente", "Method preferred by the user") : record.observation.status === "sandbox_observation" ? tr("Scoperta operativa della sandbox", "Operational sandbox finding") : record.observation.status === "needs_generalization" ? tr("Appunto conservato da generalizzare, non verificato", "Note kept for generalization, not verified") : record.observation.status === "passed" ? tr("Esito positivo osservato", "Positive outcome observed") : tr("Difetto osservato", "Defect observed")} · {record.observation.method} · {record.excluded ? tr("Esclusa", "Excluded") : tr("Fonte conservata, separata dalle skills", "Source kept, separate from the skills")}</p>
      <p>{record.observation.evidence}</p>
      {record.observation.producer_method && <details><summary>{tr("Procedimento conservato", "Procedure kept")}</summary><p>{record.observation.producer_method.notice}</p><p>{record.observation.producer_method.declared_method?.approach}</p><ol className="list-inside list-decimal">{record.observation.producer_method.declared_method?.steps.map((step, i) => <li key={i}>{step}</li>)}</ol></details>}
      {record.observation.limitations?.map((limit, i) => <p key={i}>{tr("Limite conservato:", "Limit kept:")} {limit}</p>)}
      {record.observation.corrections.map((action, i) => <p key={i}>{tr("Correzione proposta:", "Proposed fix:")} {action}</p>)}
      <p>{tr("Strumenti:", "Tools:")} {Object.entries(record.observation.tools).map(([tool, version]) => `${tool} ${version}`).join(", ") || tr("Workspace generale", "General workspace")}</p>
      {record.observation.source_thread && <a className="underline" href={`/workspace/chats/${encodeURIComponent(record.observation.source_thread)}`}>{tr("Apri il progetto di origine", "Open the source project")}</a>}
      <details><summary>{tr("Provenienza e versioni", "Origin and versions")}</summary><p className="break-all">{tr("Prodotto SHA256:", "Product SHA256:")} {record.observation.product_sha256}</p><p className="break-all">{tr("Rapporto SHA256:", "Report SHA256:")} {record.observation.report_sha256}</p></details>

    </article>)}
    {sources.length > 6 && <button className="rounded border px-3 py-2" onClick={() => setShowSources(value => !value)}>{showSources ? tr("Mostra meno fonti", "Show fewer sources") : tr(`Mostra altre ${sources.length-6} fonti`, `Show ${sources.length-6} more sources`)}</button>}
    </details>
  </div>;
}
