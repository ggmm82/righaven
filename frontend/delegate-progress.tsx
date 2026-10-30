"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import { duration, jobHealth, secondsSince, terminalJob, type JobProgress } from "./delegate-progress-state";

import { ConversationAudit, OperationDetails } from "./conversation-audit";
import { ExperiencePanel } from "./experience-panel";
import { ProjectDesign, type Design } from "./project-design";
import { ProjectGuide } from "./project-guide";
import { GovernanceStrip, ProfileUseLine, type LiveGovernance } from "./project-governance";

const providers: Record<string, string> = { codex: "Codex", gemini: "Antigravity", deepseek: "DeepSeek", openai: "OpenAI compatibile" };
type Delivery = { version_state?: string; recovery?: { status: string; message: string; session_error: string }; unchanged_content?: boolean; change_kind?: string; content_version?: number | null; reused_archive_checks?: number; finalization_pending?: string[]; source_coverage?: { status: string; components: { name: string; tool: string; status: string; sources: {path: string; member?: string}[] }[] }; timing?: {status:string; cues:{name:string;status:string;delta_seconds:number}[]}; category?: string; version?: number | null; execution_status?: string; file_count?: number; role_title?: string; review?: { target_delivery_id: string | null; target_version?: number | null; target_label: string; status: string; validated: boolean; matches_current_brief: boolean; report_path: string; correction_count: number }; id: string; title: string; agent: string; at: string; current: boolean; contribution?: boolean; technical_status: string; issues: string[]; purpose: string };
type MethodStrategy = { state: string; method: string; reason: string; user_action: string; stop_reason: string; alternatives: { method: string; reason: string; status: string; tools: string[]; evidence: { path: string; sha256: string }[] }[] };
type RevisionAction = { requirement_id: string; action: string; reason?: string; priority: number; strategy: string };
type Comparison = { baseline_path: string; criteria: { requirement_id: string; status: string; evidence: string }[] };
type Criterion = { requirement_id?: string; criterion: string; status: string; evidence: string; method: string };
type Outcome = { title: string; result: string; format: string; use: string; quality: string; constraints: string[]; assumptions: string[]; questions: string[] };
type ProjectRole = { capability_rationale?: string; tool_versions?: Record<string,string>; skills?: string[]; skill_bindings?: {name:string;revision:string}[]; experience?: { count: number; ids: string[] }; id: string; title: string; mission: string; version: string; expertise: string[]; procedure?: string[]; checks: string[]; tools: string[] };
type Orientation = { active_step_ids?: string[]; history_step_ids?: string[]; history_count?: number; total: number; counts: Record<string, number>; current: { id: string; goal: string; role_id: string; task: string }[]; remaining: { id: string; goal: string; status: string }[]; roles?: Record<string, { attempts: number; completed: number; running: number }>; needs_briefing: boolean };
type UserDirection = { visual_approach: string; instructions: string; revision: number };
type Project = { review_findings?: { severity: string; location: string; evidence: string; impact: string }[]; version_selection?: { approved: string | null; candidate: string | null; partial: string | null }; designs?: Design[]; updated_at?: string; latest_sample?: Result | null; correction_focus?: { requirement_id: string; criterion: string; reassess_role: boolean; action: string }[]; user_control?: { paused: boolean; deliver_now?: boolean }; user_direction?: UserDirection | null; strategy?: MethodStrategy | null; method_recovery?: { message: string } | null; outcome?: Outcome | null; orientation?: Orientation; roles?: ProjectRole[]; acceptance?: { user_requests: string[]; request_manifest?: { path: string }; request_documents?: { path: string }[]; request_count?: number; criteria: { id: string; requirement: string; critical: boolean; origin?: string; source_quote?: string }[] } | null; review_criteria?: Criterion[]; revision_actions?: RevisionAction[]; comparison?: Comparison | null; deliveries?: Delivery[]; quality_status?: string; summary?: string; next_action?: string; status?: string; product_path?: string; results?: Result[]; attention?: { code: string; message: string; action: string } | null; id: string; brief: string; steps: { id: string; agent: string; goal: string;
  status: string; role_id?: string; role_title?: string; note?: string; error?: string; attempt_count?: number }[] };
type Result = { path: string; agent: string; label: string; validated: boolean; at: string; delivery_id?: string; role?: string; open_with?: string; editability?: string; limitations?: string[] };
const roles: Record<string, string> = { export: "Prodotto", editable_source: "Sorgente modificabile", source_archive: "Pacchetto sorgenti", preview: "Anteprima", report: "Rapporto", dependency: "Risorsa collegata", file: "File" };
const stepLabels: Record<string, string> = { pending: "Da fare", running: "In corso",
  completed: "Incarico concluso", needs_revision: "Da rivedere", review: "Da valutare", paused: "In pausa", skipped: "Non necessaria" };

type Tone = "active" | "done" | "attention" | "neutral";
function StatusBadge({ children, tone = "neutral" }: { children: ReactNode; tone?: Tone }) {
  const colors = { active: "border-blue-500/25 bg-blue-500/10 text-blue-700 dark:text-blue-300",
    done: "border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    attention: "border-amber-500/25 bg-amber-500/10 text-amber-800 dark:text-amber-300",
    neutral: "border-border bg-muted/50 text-muted-foreground" };
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${colors[tone]}`}>{children}</span>;
}
const stepTone = (state: string): Tone => state === "running" ? "active" : state === "completed" ? "done"
  : ["paused", "needs_revision", "review"].includes(state) ? "attention" : "neutral";
const tabStyle = "rounded-lg border border-transparent px-3 py-2 transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring aria-expanded:border-border aria-expanded:bg-muted aria-expanded:font-semibold disabled:opacity-50";

function ProjectDirection({ saved, onApply, busy }: { busy: boolean; saved?: UserDirection | null; onApply: (choice: string, instructions: string) => Promise<void> }) {
  const [choice, setChoice] = useState(saved?.visual_approach || "unspecified");
  const [instructions, setInstructions] = useState(saved?.instructions || "");
  async function apply() { await onApply(choice, instructions); }
  return <form id="harness-direction-form" onSubmit={event => { event.preventDefault(); void apply(); }} className="space-y-3 rounded-xl border p-4" data-testid="project-direction">
    <h4 className="font-semibold">Cambia le indicazioni</h4>
    <p className="text-muted-foreground text-xs">La squadra si ferma, conserva i file salvati e riparte dalle nuove indicazioni.</p>
    <label className="block space-y-1"><span>Tecnica visiva, se pertinente</span>
      <select disabled={busy} className="bg-background w-full rounded border p-2" value={choice} onChange={e => setChoice(e.target.value)}>
        <option value="unspecified">Come indicato nel brief o in chat</option>
        <option value="generated">Immagini generate</option>
        <option value="vector">Grafica vettoriale modificabile</option>
        <option value="mixed">Combinazione di immagini e vettori</option>
        <option value="automatic">Lascio scegliere alla squadra</option>
      </select>
    </label>
    <label className="block space-y-1"><span>Indicazioni per questo progetto</span>
      <textarea className="w-full rounded border p-2" disabled={busy} maxLength={2000} rows={3} value={instructions} onChange={e => setInstructions(e.target.value)} placeholder="Stile, strumenti, sorgenti richiesti o cambi di direzione…" />
    </label>
    {choice === "vector" && <p className="text-muted-foreground text-xs">La generazione nativa di immagini sarà disattivata nei prossimi worker Codex. Un PNG inserito in un SVG non soddisfa la richiesta di vettori modificabili.</p>}
  </form>;
}

function JobCard({ job, now, threadId, role }: { job: JobProgress; now: number; threadId: string; role?: ProjectRole }) {
  const [stopping, setStopping] = useState(false);
  const [stopError, setStopError] = useState("");
  async function stop() {
    setStopping(true); setStopError("");
    try {
      const response = await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-jobs/${encodeURIComponent(job.job_id)}/stop`, { method: "POST" });
      if (!response.ok) throw new Error();
    } catch { setStopError("Arresto non confermato: controlla lo stato aggiornato prima di riprovare."); setStopping(false); }
  }
  const assigned = job.environment?.assigned_tools ?? role?.tools;
  const operation = job.operations?.find(o => o.state === "running") ?? job.operations?.[0];
  const terminal = terminalJob(job);
  const end = terminal ? (Date.parse(job.finished_at) || now) : now;
  const elapsed = secondsSince(job.started_at || job.created_at, end);
  const deadline = Date.parse(job.deadline_at);
  const remaining = Number.isFinite(deadline) ? Math.max(0, Math.floor((deadline - now) / 1000)) : null;
  const heartbeat = secondsSince(job.heartbeat_at, now);
  const health = jobHealth(job, now);
  const stamp = (value: string) => Number.isFinite(Date.parse(value))
    ? new Date(value).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
  return <article className="bg-background space-y-3 rounded-2xl border p-4 shadow-sm" data-testid="delegate-job">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <strong>{job.role_title || job.agent.charAt(0).toUpperCase() + job.agent.slice(1)} · {providers[job.engine] ?? job.engine}</strong>
      <span className="text-muted-foreground text-xs">{duration(elapsed)} trascorsi</span>
    </div>
    {job.environment && <section className="space-y-1 text-xs" data-testid="job-environment">
      <p className="font-semibold">{job.resources_reclaimed ? "Sandbox chiusa · file salvati conservati" : terminal ? "Incarico terminato · controlla il rilascio delle risorse sotto" : "Ambiente dell’incarico"}</p>
      {assigned && <p>Strumenti assegnati: {assigned.length ? assigned.map(person).join(", ") : "strumenti di base"}.</p>}
      {job.environment.profile&&<ProfileUseLine use={job.environment.profile}/>}
      {job.environment.versions&&Object.keys(job.environment.versions).length>0&&<p>Versioni scelte: {Object.entries(job.environment.versions).map(([tool,version])=>`${person(tool)} ${version}`).join(", ")}.</p>}
      <details><summary className="cursor-pointer">Programmi presenti nell’ambiente ({job.environment.tools.length})</summary>
        <p>{job.environment.tools.map(person).join(", ") || "Solo la base software"}.</p>
        <p>Possono essere condivisi con altri preset. La presenza di un programma non significa che sia stato usato: le operazioni osservate sono riportate sotto.</p>
        <p className="break-all">Identificativo tecnico del software: {job.environment.id}</p>
      </details>
    </section>}
    {operation && <div className="rounded-md border p-2 text-sm" data-testid="operation-progress">
      <p>{operation.label} · {operation.state === "running" && !terminal ? "in esecuzione" : operation.state === "completed" ? "conclusa" : operation.state === "out_of_memory" ? "memoria esaurita" : "interrotta"}</p>
      {operation.progress?.total && <p>{operation.progress.done ?? 0}/{operation.progress.total} campioni osservati</p>}
      {operation.estimate_seconds !== undefined && <p>Stima iniziale dal campione: circa {duration(Math.round(operation.estimate_seconds))}. Può variare.</p>}
      {operation.elapsed_seconds !== undefined && <p>{duration(Math.floor(operation.elapsed_seconds))} di elaborazione</p>}
    </div>}
    <details className="text-xs"><summary className="cursor-pointer">Modello e risorse</summary>
    {job.resources?.memory_bytes !== undefined && <p className="text-muted-foreground text-xs">{terminal ? "Ultima RAM osservata" : "RAM osservata"}: {Math.round(job.resources.memory_bytes / 1048576)} MiB{job.resources.memory_limit_bytes ? ` · limite ${Math.round(job.resources.memory_limit_bytes / 1048576)} MiB` : ""}</p>}
    {!!job.limits?.cpus && <p className="text-muted-foreground">CPU: massimo {job.limits.cpus} core assegnati; non è il consumo istantaneo.</p>}
    {!!job.resources?.oom_kills && <p role="status" className="text-sm">Il sistema ha terminato un processo per memoria esaurita. Conserva i file e verifica il budget della squadra prima di riprovare.</p>}
    {job.model && <p className="text-muted-foreground text-xs">Modello: {job.model}</p>}
    </details>
    {job.work_summary && job.work_summary !== job.summary && <p className="text-sm">{job.work_summary}</p>}
    <p className="text-sm" data-testid="delegate-summary">{job.summary}</p>
    {job.phase === "queued" && <p className="text-sm" data-testid="queue-position">{job.queue_position ? `Posizione in coda: ${job.queue_position}. ` : "In coda. "}{job.queue_detail || "L’incarico parte automaticamente quando la sandbox si libera."} {job.queue_activity_since && `Risorse occupate da ${duration(secondsSince(job.queue_activity_since, now))}. `}Puoi chiudere la pagina.</p>}
    {job.cancel_error && !job.resources_reclaimed && <p role="alert" className="text-sm">Arresto del worker non confermato. Verifica il collegamento Docker; non è sufficiente fermare il coordinatore.</p>}
    {job.resources_reclaimed && <p className="text-muted-foreground text-xs" data-testid="worker-reclaimed">Risorse della fase liberate; file salvati conservati.</p>}
    {job.cleanup_started_at && !job.resources_reclaimed && <p className="text-xs" role="status">{job.cleanup_error ? "Rimozione del container non confermata: la squadra richiede un controllo." : "Chiusura del container e rilascio delle risorse in corso."}</p>}
    {!terminal && <details className="text-muted-foreground space-y-1 text-xs"><summary className="cursor-pointer">Tempi e segnali osservati</summary>
      <p>Ultimo avanzamento osservato: {duration(secondsSince(job.last_activity_at, now))} fa</p>
      {job.execution_started_at && <p>{job.execution_state === "model" ? "Attesa del modello" : "Comando in esecuzione"}: {duration(secondsSince(job.execution_started_at, now))}</p>}
      {job.last_model_event_at && <p>Ultimo evento ricevuto dal modello: {duration(secondsSince(job.last_model_event_at, now))} fa</p>}
      {job.last_file_change_at && <p>Ultima modifica dei file: {duration(secondsSince(job.last_file_change_at, now))} fa</p>}
      {remaining !== null && remaining > 0 && <p>Limite di esecuzione tra {duration(remaining)}. Non è una stima di consegna.</p>}
      {(job.limits?.model_wait_seconds ?? 0) > 0 && ["codex", "gemini"].includes(job.engine) && <p>Budget senza eventi del modello: {duration(job.limits?.model_wait_seconds ?? 0)}; poi il coordinatore può ripianificare.</p>}
      {heartbeat !== null && heartbeat <= 15 && <p>Monitor della sandbox presente · non conferma l’avanzamento del modello</p>}
    </details>}
    {!terminal && job.can_stop && <div className="space-y-1 text-xs">
      <button type="button" className="rounded border px-3 py-2 disabled:opacity-50" disabled={stopping || job.cancel_requested} onClick={() => void stop()}>{stopping || job.cancel_requested ? "Arresto richiesto…" : (job.phase === "queued" ? "Annulla attesa" : "Interrompi questa fase")}</button>
      <p>{job.phase === "queued" ? "Rimuove solo questo incarico dalla coda. Il lavoro già in esecuzione continua." : "Termina la fase corrente e restituisce il controllo al coordinatore. Le consegne precedenti restano disponibili; i file incompleti vengono conservati nello staging separato."}</p>
      {stopError && <p role="alert">{stopError}</p>}
    </div>}
    {health && <p className="rounded-md border border-amber-500/50 p-2 text-sm" role="status">{health}</p>}
    {job.files.length > 0 && <div className="text-xs">
      <p>{job.files_count} file {job.phase === "completed" ? "presenti alla consegna" : terminal ? "provvisori, non consegnati" : "in lavorazione, ancora da verificare"}</p>
      <ul className="text-muted-foreground list-inside list-disc">
        {job.files.slice(0, 5).map((file) => <li key={file.name} className="break-all">{file.name} ({file.size} byte)</li>)}
      </ul>
    </div>}
    {job.events.length > 0 && <details className="text-xs">
      <summary className="cursor-pointer">Cronologia operativa ({job.events.length} eventi recenti)</summary>
      <ol className="mt-2 space-y-1">{job.events.map((event, i) => <li key={i}><time>{stamp(event.at)}</time> · {event.summary}<OperationDetails value={event.context} threadId={threadId}/></li>)}</ol>
    </details>}
  </article>;
}

type Props = { threadId: string; active: boolean; pending: boolean; coordinatorError?: boolean; onPause?: () => void | Promise<void>; onContinue?: (message?: string) => void | Promise<void> };
const person = (agent: string) => agent.charAt(0).toUpperCase() + agent.slice(1);
const kind = (path: string) => /\.pdf$/i.test(path) ? "pdf" : /\.(mp4|webm|mov)$/i.test(path) ? "video" : /\.(wav|mp3|m4a|ogg)$/i.test(path) ? "audio" : /\.(png|jpe?g|gif|webp)$/i.test(path) ? "image" : "source";
function artifactURL(threadId: string, path: string, download = false) {
  if (!path.startsWith("/mnt/user-data/")) return "";
  const encoded = path.split("/").map(encodeURIComponent).join("/");
  return `${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/artifacts${encoded}${download ? "?download=true" : ""}`;
}

export function DelegateProgress({ threadId, active, pending, coordinatorError = false, onContinue, onPause }: Props) {
  const [snapshot, setSnapshot] = useState<{ threadId: string; jobs: JobProgress[]; project: Project | null; governance?: LiveGovernance | null } | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [readingLesson, setReadingLesson] = useState(false);
  const [panel, setPanel] = useState<{ threadId: string; tab: string } | null>(null);
  const [resumeRequested, setResumeRequested] = useState<string | null>(null);
  const [resumeError, setResumeError] = useState<string | null>(null);
  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState<string | null>(null);
  const resumeOwner = useRef(threadId);
  const dock = useRef<HTMLElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [controlBusy, setControlBusy] = useState(false);
  const [controlNotice, setControlNotice] = useState("");
  const resumeSequence = useRef(0);
  resumeOwner.current = threadId;
  const [now, setNow] = useState(Date.now);
  const jobs = snapshot?.threadId === threadId ? snapshot.jobs : [];
  const project = snapshot?.threadId === threadId ? snapshot.project : null;
  const governance = snapshot?.threadId === threadId ? snapshot.governance : null;
  const tab = panel?.threadId === threadId ? panel.tab : null;
  const activeJobs=jobs.filter(job=>!terminalJob(job));
  const current = activeJobs[0];
  const deliveryRequested=project?.user_control?.deliver_now===true;
  const questions = project?.outcome?.questions ?? [];
  const clarifying = questions.length > 0 || project?.status === "clarifying";
  const allSteps = project?.steps ?? [];
  const activeStepIds = new Set(project?.orientation?.active_step_ids ?? allSteps.map(step => step.id));
  const currentSteps = allSteps.filter(step => activeStepIds.has(step.id));
  const otherSteps = allSteps.filter(step => !activeStepIds.has(step.id));
  const currentActivity = currentSteps.find(step => step.status === "running");
  const planned = currentSteps.filter(step => step.status !== "skipped");
  const completed = planned.filter(step => step.status === "completed").length;
  const working = !!current;
  const results = (project?.results ?? []).filter((r) => artifactURL(threadId, r.path));
  const deliveries = project?.deliveries ?? [];
  const selectedDelivery = deliveries.find((d) => d.current);
  const versions = deliveries.filter(d => d.category === "version" || (!d.category && (d.purpose === "delivery" || d.current)))
    .sort((a, b) => Number(b.execution_status === "running") - Number(a.execution_status === "running") || (b.version ?? 0) - (a.version ?? 0));
  const supporting = deliveries.filter(d => !versions.includes(d)).sort((a,b) => b.at.localeCompare(a.at));
  const versionStates: Record<string, string> = { working: "In lavorazione", approved: "Approvata", candidate: "Candidata · da valutare", partial: "Parziale · non verificata", needs_revision: "Da correggere" };
  const editing = versions.find(d => d.execution_status === "running");
  const versionName = (delivery: Delivery) => delivery.unchanged_content ? `${delivery.change_kind === "sources" ? "Sorgenti" : "Metadati"} aggiornati · versione ${delivery.content_version ?? "precedente"} invariata` : delivery.category === "sample" || delivery.purpose === "preview" ? "Campione" : delivery.version ? `Versione ${delivery.version}` : delivery.current ? "Versione selezionata" : "Tentativo di consegna";
  const currentResults = selectedDelivery ? results.filter((r) => r.delivery_id === selectedDelivery.id) : results;
  const media = [...currentResults].filter(r => r.role !== "dependency" && r.role !== "report").sort((a, b) => b.at.localeCompare(a.at)).filter((r) => kind(r.path) !== "source");
  const selected: Result | undefined = project?.product_path
    ? results.find((r) => r.path === project.product_path) ?? { path: project.product_path, label: project.product_path.split("/").pop() ?? "Risultato", agent: "", validated: false, at: "" }
    : undefined;
  const latestSample = project?.latest_sample;
  // Availability is separate from approval: a new render can be a delivery,
  // not just a sample, while the previous native product stays selected.
  const latestAvailable = [...results].filter(r => r.validated && ["export", "preview"].includes(r.role ?? "")
    && deliveries.some(d => d.id === r.delivery_id && ["delivery", "preview"].includes(d.purpose)))
    .sort((a, b) => b.at.localeCompare(a.at) || Number(b.role === "export") - Number(a.role === "export"))[0];
  const latestResult = latestSample && (!latestAvailable || latestSample.at >= latestAvailable.at) ? latestSample : latestAvailable;
  const showLatestResult = latestResult && (!selectedDelivery || latestResult.at > selectedDelivery.at
    || (selectedDelivery.purpose === "preview" && latestResult.at === selectedDelivery.at));
  const chosenResult = (showLatestResult ? latestResult : selected) ?? currentResults.find(r => r.role === "export");
  const sameDeliveryMedia = results.filter(r => r.delivery_id === chosenResult?.delivery_id && r.validated
    && ["export", "preview"].includes(r.role ?? "") && kind(r.path) !== "source");
  const preview = chosenResult && kind(chosenResult.path) === "source" ? sameDeliveryMedia[0] ?? chosenResult
    : chosenResult ?? media.find(r => kind(r.path) === "video") ?? media[0];
  const previewDelivery = deliveries.find(d => d.id === preview?.delivery_id) ?? selectedDelivery;
  const pairedSources = preview?.delivery_id ? results.filter(r => r.delivery_id === preview.delivery_id && ["editable_source", "source_archive"].includes(r.role ?? "")) : [];
  const audio = (preview?.delivery_id ? results.filter(r => r.delivery_id === preview.delivery_id) : currentResults).find((r) => kind(r.path) === "audio");
  const attention = !working && !active ? project?.attention : null;
  const ready = !showLatestResult && project?.status === "ready" && !!project.product_path && selectedDelivery?.technical_status === "passed"
    && ["passed", "accepted_by_user"].includes(project.quality_status ?? "") && !coordinatorError && !working;
  const waitingForReview = !showLatestResult && project?.status === "review" && !!project.product_path && selectedDelivery?.technical_status === "passed"
    && project.quality_status !== "passed" && !attention && !coordinatorError;
  const paused = project?.user_control?.paused === true;
  const title = deliveryRequested ? (working ? "Consegna richiesta · verifico i file disponibili" : results.length ? "Consegna disponibile · attendo le tue indicazioni" : "Chiusura richiesta · nessun nuovo prodotto verificato") : activeJobs.length>1 ? `${activeJobs.length} incarichi attivi` : paused ? (working || active ? "Pausa richiesta" : "Progetto in pausa") : working && current.phase === "queued" ? (current.queue_reason === "preload" ? "Il precaricamento lascia spazio alla chat" : "In attesa del proprio turno") : working && jobHealth(current, now) ? "Avanzamento da verificare" : working ? `${current.role_title || person(current.agent)} sta lavorando` : clarifying ? "Definiamo il risultato insieme" : active ? "La squadra sta preparando il prossimo risultato"
    : coordinatorError || attention || project?.status === "blocked" ? "Il lavoro è in pausa" : ready ? "Il risultato è pronto" : results.length ? "Una versione è disponibile" : "La squadra è pronta";
  const specificAction = current && ["running_tool", "exporting", "checking", "finalizing"].includes(current.phase)
    && current.summary !== "Esecuzione di uno strumento";
  const nativeOperation = current?.operations?.find(o => o.state === "running");
  const nativeSummary = nativeOperation ? nativeOperation.label + (nativeOperation.progress?.total ? ` · ${nativeOperation.progress.done ?? 0}/${nativeOperation.progress.total} campioni` : "") : null;
  const summary = clarifying && !working ? (questions[0] || "Mancano risultato atteso e forma della consegna.") : working ? (nativeSummary ?? (specificAction ? current.summary : current.work_summary || current.summary)) : attention?.message
    ?? (coordinatorError ? "Il coordinatore si è fermato. I file già salvati restano disponibili." : project?.summary || project?.brief);
  const toggle = (value: string) => setPanel(tab === value ? null : { threadId, tab: value });
  useEffect(() => { setPanel(null); setResumeRequested(null); setResumeError(null); setAcceptError(null); setAccepting(false); setControlBusy(false); setControlNotice(""); }, [threadId]);
  useEffect(() => {
    const element = dialog.current;
    if (tab && element && !element.open) element.showModal();
    if (!tab && element?.open) element.close();
  }, [tab]);
  async function deliverNow() {
    setControlBusy(true);setControlNotice("");
    try {
      const response=await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-deliver-now`,{method:"POST"});
      if(!response.ok) throw Error("Consegna non confermata: controlla lo stato e riprova.");
      const result=await response.json();
      setSnapshot(previous=>previous?.threadId===threadId&&previous.project?{...previous,project:{...previous.project,user_control:result.user_control}}:previous);
      setControlNotice("Consegna richiesta. Chiudo le attività e verifico i file già salvati.");
    } catch(error) {setControlNotice(error instanceof Error?error.message:"Consegna non confermata");}
    finally {setControlBusy(false);}
  }
  async function control(paused: boolean) {
    const response = await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-control`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ paused }),
    });
    if (!response.ok) throw new Error("Controllo non confermato");
    if (resumeOwner.current !== threadId) throw new Error("Conversazione cambiata");
    setSnapshot(previous => previous?.threadId === threadId && previous.project
      ? { ...previous, project: { ...previous.project, user_control: { paused } } } : previous);
  }
  async function pause() {
    if (!onPause) throw new Error("Arresto non disponibile");
    await control(true); // Close the server-side start gate before canceling the run.
    setControlNotice("Arresto in corso. Attendo la chiusura delle sandbox…");
    await onPause();
    const deadline = Date.now() + 30000;
    do {
      const response = await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-jobs`, { cache: "no-store" });
      if (!response.ok) throw new Error("Stato non disponibile");
      const data = await response.json() as { jobs: JobProgress[]; project: Project | null; governance?: LiveGovernance | null };
      if (resumeOwner.current !== threadId) throw new Error("Conversazione cambiata");
      setSnapshot({ threadId, jobs: data.jobs, project: data.project, governance: data.governance ?? null });
      if (data.jobs.every(job => terminalJob(job) && (!job.can_stop || job.resources_reclaimed))) {
        setControlNotice("In pausa. I file salvati sono conservati."); return;
      }
      await new Promise(resolve => setTimeout(resolve, 1000));
    } while (Date.now() < deadline);
    throw new Error("Chiusura delle sandbox ancora da confermare. Il progetto resta in pausa: verifica Attività prima di riprendere.");
  }
  async function pauseWork() {
    setControlBusy(true); setControlNotice("");
    try { await pause(); } catch (error) { setControlNotice(error instanceof Error ? error.message : "Pausa non confermata."); }
    finally { if (resumeOwner.current === threadId) setControlBusy(false); }
  }
  async function applyDirection(choice: string, instructions: string) {
    if (!onContinue || controlBusy) return;
    setControlBusy(true); setControlNotice("");
    try {
      await pause();
      const response = await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-direction`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ visual_approach: choice, instructions }),
      });
      if (!response.ok) throw new Error("Indicazioni non salvate. Il progetto resta in pausa.");
      await control(false);
      await onContinue(`Ho aggiornato le indicazioni dal pannello: tecnica visiva ${choice}; ${instructions || "restano valide le altre indicazioni"}. Rileggi le scelte salvate, conserva i file validi e ripianifica il lavoro. Se manca una risposta decisiva chiedimela prima di produrre.`);
      if (resumeOwner.current === threadId) { setPanel(null); setControlNotice("Nuove indicazioni inviate alla squadra."); }
    } catch (error) {
      if (resumeOwner.current === threadId) {
        try { await control(true); } catch { /* Keep the original actionable error. */ }
        setControlNotice(error instanceof Error ? error.message : "Aggiornamento non confermato.");
      }
    }
    finally { if (resumeOwner.current === threadId) setControlBusy(false); }
  }
  useEffect(() => { if (active) { setResumeRequested(null); setResumeError(null); } }, [active]);
  useEffect(() => {
    if (resumeRequested !== threadId || active || working) return;
    const timer = setTimeout(() => { setResumeRequested(null); setResumeError("Avvio non confermato: verifica lo stato e riprova se il lavoro resta fermo."); }, 15000);
    return () => clearTimeout(timer);
  }, [resumeRequested, threadId, active, working]);
  async function resume() {
    const owner = threadId;
    const sequence = ++resumeSequence.current;
    setResumeRequested(threadId); setResumeError(null);
    try {
      if (paused) { await pause(); await control(false); }
      else if(deliveryRequested) await control(false);
      await onContinue?.();
      if (resumeOwner.current === owner && resumeSequence.current === sequence) setControlNotice("");
    }
    catch {
      if (paused && resumeOwner.current === owner) { try { await control(true); } catch { /* Report submission failure below. */ } }
      if (resumeOwner.current === owner && resumeSequence.current === sequence) {
        setResumeRequested(null); setResumeError("Non riesco a inviare la richiesta di ripresa. I risultati restano disponibili: riprova.");
      }
    }
  }
  async function acceptVersion() {
    if (!selectedDelivery || accepting) return;
    const owner = threadId;
    setAccepting(true); setAcceptError(null);
    try {
      const response = await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-delivery/accept`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ delivery_id: selectedDelivery.id }),
      });
      if (!response.ok) throw new Error("Version unavailable");
      const data = await response.json() as { project: Project };
      if (resumeOwner.current === owner) setSnapshot((current) => current?.threadId === owner ? { ...current, project: data.project } : current);
    } catch {
      if (resumeOwner.current === owner) setAcceptError("Non posso accettare questa versione: potrebbe essere cambiata o avere sorgenti incompleti. Aggiorna e controlla la consegna.");
    } finally { if (resumeOwner.current === owner) setAccepting(false); }
  }
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function refresh() {
      let running = false;
      try {
        const response = await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-jobs`,
          { signal: controller.signal, cache: "no-store" });
        if (!response.ok) throw new Error("Progress unavailable");
        const data = await response.json() as { jobs: JobProgress[]; project?: Project | null; governance?: LiveGovernance | null };
        if (!Array.isArray(data.jobs)) throw new Error("Invalid progress");
        if (controller.signal.aborted) return;
        setSnapshot({ threadId, jobs: data.jobs, project: data.project ?? null, governance: data.governance ?? null });
        setUnavailable(false);
        running = data.jobs.some((job) => !terminalJob(job));
      } catch {
        if (controller.signal.aborted) return;
        setUnavailable(true);
      }
      // Keep watching an open conversation even between delegate calls or after a
      // background reconnect. A missing SSE event must not leave a frozen board.
      if (!controller.signal.aborted) timer = setTimeout(() => void refresh(), active || running ? 2000 : 5000);
    }
    if (threadId) void refresh();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [threadId, active]);
  useEffect(() => {
    if (!working && !pending) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [working, pending]);
  if (!jobs.length && !project && !pending && !coordinatorError) return <details className="mb-2 rounded-xl border text-sm" data-testid="chat-audit-only" onToggle={event => setPanel(event.currentTarget.open ? { threadId, tab: "audit" } : null)}>
    <summary className="cursor-pointer p-3">Registro della conversazione</summary>
    {tab === "audit" && <div className="p-3"><ConversationAudit key={threadId} threadId={threadId} /></div>}
  </details>;
  const health = current ? jobHealth(current, now) : null;
  const recent = [...jobs.filter((job) => !terminalJob(job)), ...jobs.filter(terminalJob).slice(0, 4)];
  return <section ref={dock} className="bg-background relative mb-2 rounded-2xl border shadow-sm" aria-label="Il tuo progetto" data-testid="delegate-progress">
    {tab && <dialog ref={dialog} onCancel={() => setPanel(null)} onClose={() => setPanel(null)} aria-labelledby="harness-panel-title" className={`bg-background text-foreground fixed inset-0 m-auto ${readingLesson && tab === "experience" ? "h-[calc(100dvh-2rem)]" : "h-[85dvh]"} max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-3xl overflow-hidden rounded-2xl border p-0 shadow-xl backdrop:bg-black/40`} data-testid="harness-drawer">
      <div className="flex h-full min-h-0 flex-col">
      <header className="flex shrink-0 items-center justify-between gap-2 border-b px-4 py-3">
        <h3 id="harness-panel-title" className="font-semibold">{readingLesson && tab === "experience" ? "Lezione completa" : tab === "intervene" ? "Intervieni sul progetto" : "Il tuo progetto"}</h3>
        <button type="button" className="rounded-lg border px-3 py-2 text-sm" onClick={() => setPanel(null)} aria-label="Chiudi dettagli del progetto">Chiudi</button>
      </header>
      {!(readingLesson && tab === "experience") && <nav className="grid shrink-0 grid-cols-3 gap-1 border-b p-2 text-sm sm:flex sm:flex-wrap" aria-label="Sezioni del progetto">
        {([["project", "Stato"], ["preview", "Risultato"], ["team", "Squadra"], ["design", "Tavole"], ["files", "Consegne"], ["activity", "Attività"], ["experience", "Lezioni"], ["audit", "Registro"]] as const).map(([id, label]) => <button key={id} type="button" className={`${tabStyle} shrink-0`} aria-current={tab === id ? "page" : undefined} aria-expanded={tab === id} onClick={() => setPanel({ threadId, tab: id })}>{label}</button>)}
      </nav>}
      <div key={tab} className="min-h-0 flex-1 overflow-y-auto p-4" data-testid="rh-drawer-content">
      {tab === "intervene" && <ProjectDirection key={threadId} saved={project?.user_direction} onApply={applyDirection} busy={controlBusy} />}
      {tab === "project" && project && <div className="space-y-4 text-sm" data-testid="project-overview">
        <section className="space-y-2 rounded-xl border border-blue-500/25 bg-blue-500/5 p-4" data-testid="project-position">
          <h4 className="font-semibold">Dove siamo</h4>
          <p>{planned.length ? `${completed} di ${planned.length} incarichi conclusi nella squadra attuale` : "La squadra e le attività sono ancora da definire."}</p>
          {currentActivity && <p><strong>Responsabilità attuale:</strong> {currentActivity.role_title || person(currentActivity.agent)}</p>}
          {summary && <p><strong>Adesso:</strong> {summary}</p>}
          {!working && !clarifying && project.next_action && <p><strong>Prossima azione:</strong> {project.next_action}</p>}
          <p className="text-muted-foreground text-xs">Gli incarichi possono cambiare. Il conteggio non è una percentuale di completamento o una stima dei tempi.</p>
        </section>
        {project.correction_focus?.some(f => f.reassess_role) && <details className="rounded-xl border p-3" data-testid="recurring-defects"><summary className="cursor-pointer font-medium">Correzione da ripensare</summary><p className="my-2 text-xs">La squadra deve rivalutare metodo o competenza prima di estendere il lavoro.</p>{project.correction_focus.filter(f => f.reassess_role).map(f => <p className="my-2" key={f.requirement_id}>{f.criterion}: {f.action}</p>)}</details>}
        <section className="bg-muted/30 space-y-3 rounded-xl border p-4">
          <h4 className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">Risultato da ottenere</h4>
          <p className="text-base font-medium leading-relaxed">{project.outcome?.result || project.brief}</p>
          <p><strong>Consegna:</strong> {project.outcome?.format || "Da definire con te prima di proseguire la produzione."}</p>
          {project.outcome?.use && <p><strong>Uso e destinatari:</strong> {project.outcome.use}</p>}
          {project.outcome?.quality && <p><strong>Qualità attesa:</strong> {project.outcome.quality}</p>}
        </section>
        <GovernanceStrip governance={governance} expanded/>
        {questions.length > 0 && <section className="space-y-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4" data-testid="brief-questions">
          <h4 className="font-semibold">Le scelte che mancano</h4>
          <ul className="list-inside list-disc">{questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
          <p>Rispondi alle domande nella chat. La produzione attende queste scelte.</p>
        </section>}
        {planned.some(step => step.status !== "completed") && <section className="space-y-2">
          <h4 className="font-semibold">Attività ancora previste</h4>
          <ul className="space-y-2">{planned.filter(step => step.status !== "completed").map(step => <li key={step.id} className="flex items-start gap-3 rounded-lg border p-3">
            <span className="shrink-0"><StatusBadge tone={stepTone(step.status)}>{stepLabels[step.status] ?? step.status}</StatusBadge></span><span>{step.goal}</span>
          </li>)}</ul>
        </section>}
        {otherSteps.length > 0 && <details className="space-y-2 rounded-xl border p-3" data-testid="project-history">
          <summary className="cursor-pointer font-medium">Altre attività del progetto ({otherSteps.length})</summary>
          <p className="text-muted-foreground">Queste attività appartengono a ruoli fuori dalla squadra attuale. Tentativi e file restano conservati; possono essere ripresi senza ricominciare.</p>
          <ul className="space-y-2">{otherSteps.map(step => <li key={step.id}><StatusBadge tone={stepTone(step.status)}>{stepLabels[step.status] ?? step.status}</StatusBadge> {step.goal}</li>)}</ul>
        </details>}
        {(project.strategy || project.method_recovery) && <details className="space-y-2 rounded-xl border p-3" data-testid="project-method">
          <summary className="cursor-pointer font-semibold">Metodo e alternative</summary>
          {project.method_recovery && <p className="text-amber-700 dark:text-amber-300">{project.method_recovery.message}</p>}
          {project.strategy && <>
            <p><strong>{project.strategy.state === "selected" ? "Metodo scelto" : project.strategy.state === "needs_user" ? "Decisione necessaria" : "Metodo in valutazione"}:</strong> {project.strategy.method}</p>
            <p>{project.strategy.reason}</p>
            <ul className="space-y-2">{project.strategy.alternatives.map((item, index) => <li key={index} className="rounded-lg border p-2">
              <p><strong>{item.method}</strong> · {item.status === "candidate" ? "Da provare" : item.status === "tested" ? "Prova disponibile" : "Valutato non disponibile"}</p>
              <p>{item.reason}</p>
              {!!item.tools.length && <p className="text-muted-foreground text-xs">Strumenti: {item.tools.join(", ")}</p>}
              {item.evidence.map((proof, i) => { const href = artifactURL(threadId, proof.path); return href ? <a key={i} href={href} target="_blank" rel="noreferrer" className="mr-3 underline">Prova {i + 1}</a> : null; })}
            </li>)}</ul>
            {project.strategy.state === "needs_user" && <p><strong>Per proseguire:</strong> {project.strategy.user_action}</p>}
          </>}
          {!!project.outcome?.assumptions.length && <div><h5 className="font-medium">Scelte provvisorie della squadra</h5><ul className="list-inside list-disc">{project.outcome.assumptions.map((item, i) => <li key={i}>{item}</li>)}</ul><p className="text-muted-foreground text-xs">Si possono rivedere mantenendo il risultato e i vincoli richiesti.</p></div>}
        </details>}
        {!!project.review_findings?.length && <details className="rounded-xl border p-3"><summary className="cursor-pointer">Rilievi della revisione ({project.review_findings.length})</summary><ul className="mt-2 space-y-3">{project.review_findings.map((f, i) => <li key={i}><strong>{f.severity === "blocking" ? "Difetto bloccante" : f.severity === "advisory" ? "Suggerimento facoltativo" : "Da verificare"}</strong> · {f.location}<p>{f.evidence}</p><p className="text-muted-foreground">Impatto: {f.impact}</p></li>)}</ul></details>}
        {!!project.revision_actions?.length && <section className="space-y-2 rounded-xl border border-amber-500/30 p-3" data-testid="revision-actions">
          <h4 className="font-semibold">Correzioni dal controllo qualità</h4>
          <ol className="list-inside list-decimal space-y-2">{project.revision_actions.map((action, i) => <li key={i}>{action.action}{action.strategy === "change_method" && <p className="text-muted-foreground text-xs">Serve provare un metodo diverso.</p>}</li>)}</ol>
        </section>}
        {project.comparison && <section className="space-y-2 rounded-xl border p-3" data-testid="quality-comparison">
          <h4 className="font-semibold">Confronto con la versione precedente</h4>
          <ul className="space-y-2">{project.comparison.criteria.map((item, i) => <li key={i}><strong>{item.status === "improved" ? "Migliorato" : item.status === "unchanged" ? "Invariato" : item.status === "regressed" ? "Peggiorato" : "Non verificato"}</strong> · {item.evidence}</li>)}</ul>
        </section>}
        {!!project.outcome?.constraints.length && <section><h4 className="font-semibold">Vincoli</h4><ul className="list-inside list-disc">{project.outcome.constraints.map((c, i) => <li key={i}>{c}</li>)}</ul></section>}

      </div>}
      {tab === "preview" && <div className="space-y-3">
        <p><StatusBadge tone={ready ? "done" : "attention"}>{ready ? "Prodotto finale" : "Bozza di lavoro: può essere incompleta e non sostituisce il prodotto finale."}</StatusBadge></p>
        {previewDelivery && <section className="space-y-1 text-sm" data-testid="selected-version">
          <p className="font-semibold">{versionName(previewDelivery)} · {ready ? "Consegna finale" : "Da valutare"}</p>
          <p>{previewDelivery.title}</p>
          {!!previewDelivery.issues.length && <p role="status" className="rounded border border-amber-500/30 p-2 text-sm">Da correggere: {previewDelivery.issues.join("; ")}</p>}
          {!!previewDelivery.reused_archive_checks && <p className="text-muted-foreground text-xs">Verifiche sorgenti riutilizzate per {previewDelivery.reused_archive_checks} archivio/i identico/i nella stessa versione degli strumenti.</p>}
          {!!previewDelivery.finalization_pending?.length && <p className="text-muted-foreground">Prima della consegna finale: {previewDelivery.finalization_pending.join("; ")}</p>}
          {editing && editing.id !== previewDelivery.id && <p className="text-muted-foreground">{versionName(editing)} in lavorazione. Qui vedi ancora {versionName(previewDelivery).toLowerCase()}.</p>}
          <p className="text-muted-foreground text-xs">Anteprima, download e sorgenti sotto appartengono a questa lavorazione.</p>
          {previewDelivery.source_coverage && <details className="rounded border p-3" data-testid="component-sources"><summary className="cursor-pointer">Sorgenti delle componenti · {previewDelivery.source_coverage.status === "documented" ? "documentati" : "da completare"}</summary>{previewDelivery.source_coverage.components.map((c,i) => <div className="my-2" key={i}><p><strong>{c.name}</strong> · {c.tool} · {c.status === "documented" ? "sorgenti associati" : "sorgenti incompleti"}</p>{c.sources.map((r,n) => <p className="break-all text-xs" key={n}>{r.member || r.path.split("/").pop()}</p>)}</div>)}<p className="text-xs">Il progetto principale non dimostra la modificabilità di tutte le risorse. Apertura e ricostruzione hanno verifiche distinte.</p></details>}
          {previewDelivery.timing && <details className="rounded border p-3" data-testid="delivery-timing"><summary className="cursor-pointer">Sincronismo · {previewDelivery.timing.status === "passed" ? "cue misurati" : "da verificare"}</summary>{previewDelivery.timing.cues.map((c,i) => <p className="my-1 text-xs" key={i}>{c.name}: {c.status === "not_run" ? "non verificato" : `${c.delta_seconds} s di scarto`}</p>)}<p className="text-xs">Il controllo dei picchi audio non sostituisce l’ascolto e la verifica visiva.</p></details>}
        </section>}
        {showLatestResult && latestResult && <p className="text-sm" data-testid={previewDelivery?.purpose === "preview" ? "latest-sample" : "latest-result"}>{previewDelivery?.purpose === "preview" ? "Ultimo campione disponibile" : "Ultimo risultato disponibile"} · {new Date(latestResult.at).toLocaleString()} · Da valutare prima di considerarlo definitivo.</p>}
        {preview && <div className="bg-muted/20 space-y-3 rounded-xl border p-3" data-testid="primary-result">
          {kind(preview.path) === "video" && <video key={preview.path} className="max-h-[35dvh] w-full rounded" controls playsInline preload="metadata" aria-label="Anteprima video" src={artifactURL(threadId, preview.path)} />}
          {kind(preview.path) === "image" && <img className="max-h-[35dvh] w-full object-contain" alt="Anteprima del lavoro" src={artifactURL(threadId, preview.path)} />}
          {kind(preview.path) === "audio" && <audio controls aria-label="Anteprima audio" src={artifactURL(threadId, preview.path)} />}
          {kind(preview.path) === "pdf" && <iframe title="Anteprima PDF" className="h-[50dvh] min-h-72 w-full rounded border" src={artifactURL(threadId, preview.path)} /> }
          {kind(preview.path) === "source" && <p className="text-sm">Risultato disponibile come documento o progetto: scaricalo e aprilo con l’app indicata nella consegna.</p>}
          <p className="text-muted-foreground text-xs">Scarica il risultato</p>
          <a className="bg-foreground text-background inline-flex max-w-full items-center rounded-lg px-4 py-2 text-sm font-medium break-all focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring" href={artifactURL(threadId, preview.path, true)}>{preview.label}</a>
          {preview.open_with && <p className="text-sm">Come aprire: {preview.open_with}</p>}
          {preview.limitations?.map((limit, i) => <p className="text-muted-foreground text-xs" key={i}>{limit}</p>)}
        </div>}
        {audio && preview && kind(preview.path) === "video" && audio.path !== preview.path && <div>
          {!ready && <p className="text-sm">Audio disponibile separatamente. Questa bozza video potrebbe non contenerlo ancora.</p>}
          <audio controls preload="metadata" aria-label="Traccia audio disponibile" src={artifactURL(threadId, audio.path)} />
        </div>}
        {!preview && <p className="text-sm">Nessuna anteprima disponibile. Puoi controllare attività e file salvati.</p>}
        {previewDelivery && <ProjectGuide threadId={threadId} deliveryId={previewDelivery.id} revision={project?.updated_at}/>}
        {pairedSources.length > 0 && <section className="space-y-3 rounded-xl border p-3 text-sm" data-testid="paired-sources">
          <h4 className="font-semibold">Sorgenti della stessa consegna</h4>
          <ul className="space-y-3">{pairedSources.map(file => <DeliveryFile key={file.path} file={file} threadId={threadId} />)}</ul>
        </section>}
        {showLatestResult && selectedDelivery && selectedDelivery.id !== preview?.delivery_id && <details className="rounded-xl border p-3 text-sm" data-testid="previous-delivery">
          <summary className="cursor-pointer font-medium">Consegna precedente conservata</summary>
          <p className="my-2">{selectedDelivery.title}. Il risultato mostrato sopra non la sostituisce e deve ancora essere valutato.</p>
          <ul className="space-y-3">{currentResults.filter(file => ["export", "editable_source", "source_archive"].includes(file.role ?? "")).map(file => <DeliveryFile key={file.path} file={file} threadId={threadId}/>)}</ul>
        </details>}
        {project?.quality_status && !showLatestResult && <p className="text-sm">{project.quality_status === "accepted_by_user" ? "Questa versione è stata accettata da te." : project.quality_status === "passed" ? "Revisione dello specialista registrata per questa versione." : "Qualità ancora da valutare: i controlli tecnici non verificano tutti i requisiti del progetto."}</p>}
        {project?.acceptance && <details className="rounded border p-3 text-sm" data-testid="acceptance-criteria">
          <summary className="cursor-pointer font-medium">Rispondenza alla tua richiesta</summary>
          <p className="my-2 whitespace-pre-wrap">{project.acceptance.user_requests[0]}</p>
          <ul className="space-y-2">{project.acceptance.criteria.map((rule) => {
            const observations = project.review_criteria?.filter(c => c.requirement_id === rule.id) ?? [];
            const verdict = observations.some(c => c.status === 'failed') ? 'failed' : observations.length && observations.every(c => c.status === 'passed') ? 'passed' : 'not_run';
            return <li key={rule.id}><strong>{verdict === "passed" ? "Verificato" : verdict === "failed" ? "Da correggere" : "Da verificare"}</strong> · {rule.requirement}
              {rule.origin === "proposal" && <p className="text-muted-foreground text-xs">Criterio proposto dalla squadra, rivedibile nel rispetto della richiesta.</p>}
              {rule.origin === "user" && rule.source_quote && <p className="text-muted-foreground text-xs">Dalla tua richiesta: «{rule.source_quote}»</p>}
              {observations.length > 0 && <details className="mt-1 text-muted-foreground"><summary className="cursor-pointer">Evidenze ({observations.length})</summary><ul className="list-inside list-disc">{observations.map((observed, i) => <li key={i}>{observed.status === "failed" ? "Difetto" : observed.status === "passed" ? "Verificato" : "Non verificato"}: {observed.evidence}</li>)}</ul></details>}</li>;
          })}</ul>
          {project.acceptance.request_documents?.[0] && <p><a className="underline" href={artifactURL(threadId, project.acceptance.request_documents[0].path, true)}>Leggi la richiesta originale completa</a></p>}
          {project.acceptance.request_manifest && <p><a className="underline" href={artifactURL(threadId, project.acceptance.request_manifest.path, true)}>Indice dei messaggi conservati ({project.acceptance.request_count ?? 1})</a></p>}
        </details>}
        {!ready && !showLatestResult && !working && !active && selectedDelivery?.technical_status === "passed" && !selectedDelivery.finalization_pending?.length && <div className="space-y-2 border-t pt-3">
          <p className="text-sm">Se hai verificato il risultato e ti soddisfa, puoi accettare questa versione. I controlli dei sorgenti restano obbligatori.</p>
          <button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-50" disabled={accepting} onClick={() => void acceptVersion()}>{accepting ? "Registro la scelta…" : "Ho verificato: accetta questa versione"}</button>
        </div>}
        {acceptError && <p className="text-sm" role="alert">{acceptError}</p>}
      </div>}
      {tab === "design" && <ProjectDesign threadId={threadId} designs={project?.designs ?? []} steps={project?.steps ?? []} roles={project?.roles ?? []} onReview={() => setPanel({threadId,tab:"intervene"})}/>}
      {tab === "team" && <div data-testid="team-plan" className="space-y-3">
        <p className="text-sm">La squadra si adatta al risultato: può riprendere, cambiare ordine e integrare i file già disponibili.</p>
        {(project?.roles ?? []).map(role => {
          const activities = currentSteps.filter(step => step.role_id === role.id);
          const live = jobs.find(job => job.role_id === role.id && !terminalJob(job));
          const usage = project?.orientation?.roles?.[role.id];
          const used = (usage?.attempts ?? jobs.filter(job => job.role_id === role.id).length) > 0;
          const state = live || !!usage?.running ? "Al lavoro" : used && activities.some(step => step.status === "paused") ? "In pausa" : used ? "Ha lavorato al progetto" : "Previsto";
          return <article key={role.id} className="bg-muted/20 space-y-3 rounded-xl border p-4 text-sm" data-testid="compiled-role">
            <div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-base">{role.title}</strong><StatusBadge tone={live || usage?.running ? "active" : state === "In pausa" ? "attention" : "neutral"}>{state}</StatusBadge></div>
            <p>{role.mission}</p>
            {role.experience && <p>{role.experience.count} lezioni generali pertinenti incluse nella skill compilata.</p>}
            <h4 className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">Competenze assegnate</h4>
            <ul className="list-inside list-disc">{role.expertise.map((skill, i) => <li key={i}>{skill}</li>)}</ul>
            {!!role.skill_bindings?.length && <div className="space-y-2" data-testid="role-method-skills"><p className="text-muted-foreground text-xs font-semibold">Skill riutilizzate</p><ul>{role.skill_bindings.map(binding=><li key={binding.name}>{binding.name.replace(/^skill-/, "")}</li>)}</ul></div>}
            <div className="space-y-2"><p className="text-muted-foreground text-xs font-semibold">Strumenti assegnati</p><div className="flex flex-wrap gap-1.5">{role.tools.length ? role.tools.map(tool => <StatusBadge key={tool}>{person(tool)}</StatusBadge>) : <span>Strumenti di base del progetto</span>}</div></div>
            {role.capability_rationale&&<details data-testid="role-capability-choice"><summary className="cursor-pointer">Perché questi strumenti</summary><p className="mt-2">{role.capability_rationale}</p></details>}
            {live && <p><strong>Adesso:</strong> {live.work_summary || live.summary}</p>}
            <ul className="space-y-1">{activities.map(step => <li key={step.id}><StatusBadge tone={stepTone(step.status)}>{stepLabels[step.status] ?? step.status}</StatusBadge> {step.goal}</li>)}</ul>
            {!activities.length && <p className="text-muted-foreground">{used ? "Contributi registrati nelle attività precedenti." : "Nessun incarico ancora assegnato."}</p>}
            <details><summary className="cursor-pointer">Metodo e verifiche previste</summary>
              {!!role.procedure?.length && <ol className="mt-2 list-inside list-decimal">{role.procedure.map((item, i) => <li key={i}>{item}</li>)}</ol>}
              <ul className="mt-2 list-inside list-disc">{role.checks.map((check, i) => <li key={i}>{check}</li>)}</ul>
              <p className="text-muted-foreground mt-2 text-xs">Questi sono controlli da eseguire, non verifiche già superate. Gli strumenti effettivamente invocati sono nell’attività dell’incarico.</p>
            </details>
            <details className="text-xs"><summary className="cursor-pointer">Dettagli tecnici delle istruzioni</summary>
              <p>I codici identificano il contenuto delle istruzioni. Non indicano il livello di competenza né una versione progressiva.</p>
              <p className="break-all">Impronta del ruolo: {role.version}</p>
              {role.skill_bindings?.map(binding=><p className="break-all" key={binding.name}>{binding.name}: {binding.revision}</p>)}
              {!!role.tool_versions && <p>Versioni dei programmi: {Object.entries(role.tool_versions).map(([name,version])=>`${person(name)} ${version}`).join(", ")}</p>}
            </details>
          </article>;
        })}
        {currentSteps.filter(step => !(project?.roles ?? []).some(role => role.id === step.role_id)).map(step => <article className="rounded border p-3 text-sm" key={step.id}>
          <strong>{step.role_title || person(step.agent)}</strong> · {stepLabels[step.status] ?? step.status}
          <p>{step.goal}</p>{step.note && <p className="text-muted-foreground">{step.note}</p>}
        </article>)}
      </div>}
      {tab === "files" && <div className="space-y-3 text-sm" data-testid="delivery-list">
        <p>Ogni pacchetto appartiene alla consegna indicata. Estrai tutto lo ZIP e segui le istruzioni di apertura; conserva le risorse accanto al progetto.</p>
        {project?.version_selection && <div className="rounded-lg border p-3" data-testid="version-selection"><strong>Versioni del progetto</strong>{([['approved', 'Ultima approvata'], ['candidate', 'Ultima candidata'], ['partial', 'Ultimo lavoro parziale']] as const).map(([state, label]) => { const delivery = versions.find(d => d.id === project.version_selection?.[state]); return <p key={state}>{label}: {delivery ? versionName(delivery) : "Nessuna"}</p>; })}<p className="mt-2 text-xs text-muted-foreground">I controlli tecnici non equivalgono all’approvazione. Le versioni precedenti restano disponibili.</p></div>}
        {!versions.length && supporting.some(d => d.purpose === "preview") && <p>È disponibile un campione. La consegna del prodotto completo non è ancora registrata.</p>}
        {versions.map(d => <details key={d.id} open={d.current || d.id === project?.version_selection?.candidate || d.execution_status === "running"} className={`rounded-xl border p-4 ${d.current ? "border-blue-500/30 bg-blue-500/5" : "bg-muted/20"}`} data-testid="delivery-group">
          <summary className="cursor-pointer"><strong>{versionName(d)}</strong> · {d.version_state ? versionStates[d.version_state] : d.execution_status === "running" ? "In lavorazione" : "Stato non verificato"}{d.current && " · visualizzata"}<p className="mt-1 text-sm">{d.title}</p></summary>
          <p className="mt-2 text-xs">{d.role_title || person(d.agent)}{d.at ? ` · ${new Date(d.at).toLocaleString("it-IT")}` : ""}</p>
          {d.execution_status !== "running" && <p className="mt-2"><StatusBadge tone={d.technical_status === "passed" ? "done" : "attention"}>{d.technical_status === "passed" ? "Controlli tecnici superati" : d.technical_status === "needs_revision" ? "Consegna incompleta: da correggere" : "Controlli tecnici non confermati"}</StatusBadge></p>}
          {d.recovery?.status === "verified" && <p className="mt-2">Recuperata dopo {d.recovery.session_error === "provider_quota" ? "esaurimento quota" : "scadenza del tempo"}, senza nuova generazione. Restano validi solo i controlli registrati.</p>}
          {d.issues.map((issue, i) => <p className="mt-1 text-sm" key={i}>{issue}</p>)}
          {!!d.finalization_pending?.length && <p className="mt-2 text-muted-foreground">Prova disponibile. Prima della consegna finale: {d.finalization_pending.join("; ")}</p>}
          {d.execution_status === "running" && <p className="mt-2">I file in preparazione non sostituiscono ancora la versione selezionata.</p>}
          <DeliveryContents delivery={d} results={results} threadId={threadId} revision={project?.updated_at} />
          {deliveries.filter(review => review.review?.target_delivery_id === d.id).map(review => <ReviewCard key={review.id} delivery={review} threadId={threadId} />)}

        </details>)}
        {supporting.length > 0 && <details open={!versions.length} className="rounded-xl border p-3" data-testid="supporting-deliveries">
          <summary className="cursor-pointer font-medium">Campioni, contributi e verifiche ({supporting.length})</summary>
          <p className="my-2 text-xs text-muted-foreground">Sono lavorazioni della squadra, non nuove versioni del prodotto completo.</p>
          {supporting.map(d => <details key={d.id} className="my-2 rounded-lg border p-3" data-testid="delivery-group"><summary className="cursor-pointer">{d.purpose === "review" ? "Verifica" : d.purpose === "preview" ? "Campione" : "Contributo"} · {d.title}</summary>
            {!!d.finalization_pending?.length && <p className="mt-2 text-muted-foreground">Prima della consegna finale: {d.finalization_pending.join("; ")}</p>}
            {d.review && <ReviewCard delivery={d} threadId={threadId} />}
            <DeliveryContents delivery={d} results={results} threadId={threadId} revision={project?.updated_at} />
          </details>)}
        </details>}
        {!deliveries.length && <ul className="space-y-3">{results.map((r) => <DeliveryFile key={r.path} file={r} threadId={threadId} />)}</ul>}
        {!results.length && <p>I file appariranno qui quando saranno disponibili.</p>}
      </div>}
      {tab === "experience" && <ExperiencePanel key={threadId} threadId={threadId} deliveries={deliveries} productionBusy={active || working || pending} onReadingChange={setReadingLesson} />}
      {tab === "audit" && <ConversationAudit key={threadId} threadId={threadId} />}
      {tab === "activity" && <div className="space-y-3">{recent.map((job) => <JobCard key={job.job_id} job={job} now={now} threadId={threadId} role={job.role_version ? project?.roles?.find(role=>role.id===job.role_id && role.version===job.role_version) : undefined} />)}</div>}
      </div>
      {tab !== "experience" && <footer className="shrink-0 space-y-2 border-t bg-background p-3">
        {controlNotice && <p className="text-sm" role="status">{controlNotice}</p>}
        <div className="flex flex-wrap gap-2 text-sm">
          {tab === "intervene" ? <button type="submit" form="harness-direction-form" className="bg-foreground text-background rounded-lg px-3 py-2 disabled:opacity-50" disabled={controlBusy || !onContinue || !onPause}>{controlBusy ? "Attendi…" : "Applica e riprendi"}</button>
            : <button type="button" className={tabStyle} onClick={() => setPanel({ threadId, tab: "intervene" })}>Intervieni</button>}
          {(active || working) && onPause && <button type="button" className={tabStyle} disabled={controlBusy} onClick={() => void pauseWork()}>Metti in pausa</button>}
        </div>
      </footer>}
      </div>
    </dialog>}
    <div className="space-y-1 p-3" role="status" aria-live="polite" aria-atomic="true">
      {project && <div className="mb-2 space-y-1 border-b pb-2" data-testid="project-identity">
        <p className="line-clamp-1 text-sm font-semibold tracking-tight">{project.outcome?.title || project.outcome?.result || "Il tuo progetto"}</p>
        {selectedDelivery?.version && <p className="text-xs">{versionName(selectedDelivery)}{editing && editing.id !== selectedDelivery.id ? ` · ${versionName(editing)} in lavorazione` : ""}</p>}
        <p className="text-muted-foreground line-clamp-1 text-xs">Consegna: {project.outcome?.format || "da definire"}</p>
        {planned.length > 0 && <p className="text-muted-foreground line-clamp-2 text-xs">{completed} di {planned.length} incarichi conclusi</p>}
        <GovernanceStrip governance={governance}/>
      </div>}
      <div className="flex items-center justify-between gap-2"><strong className="text-sm" data-testid="harness-status"><span aria-hidden="true" className={`mr-2 inline-block h-2 w-2 rounded-full ${working ? "bg-blue-500" : ready ? "bg-emerald-500" : attention || clarifying || coordinatorError ? "bg-amber-500" : "bg-muted-foreground"}`} />{title}</strong>
        {current && <span className="text-muted-foreground shrink-0 text-xs">{duration(secondsSince(current.started_at || current.created_at, now))}</span>}
      </div>
      {summary && !paused && <p className="line-clamp-2 text-sm" data-testid="harness-summary">{summary}</p>}
      {health && <p className="text-muted-foreground line-clamp-1 text-xs" data-testid="harness-health">{health}</p>}
      {!paused && !working && !clarifying && project?.next_action && !attention && <p className="text-muted-foreground line-clamp-2 text-xs">Prossimo passo: {project.next_action}</p>}
      {waitingForReview && !active && <p className="text-xs">Guarda il risultato e indica nella chat cosa vuoi correggere. Una verifica non disponibile non richiede di rigenerare tutto.</p>}
      {(attention || coordinatorError) && !active && !working && <p className="text-xs">{attention?.action ?? "Verifica il servizio AI e riprendi il lavoro dai risultati disponibili."}
        {(!attention || attention.code.startsWith("provider_")) && <> <a className="underline" href="/workspace/harness">Apri La tua squadra</a></>}</p>}
      {clarifying && !working && <p className="text-xs">Rispondi nella chat: la produzione attende le scelte sul risultato.</p>}
      {unavailable && <p className="text-xs" role="alert">Aggiornamenti non disponibili: questo stato potrebbe non essere attuale. Riprovo automaticamente.</p>}
      {controlNotice && <p className="text-xs" role="status">{controlNotice}</p>}
      {resumeError && <p className="text-xs" role="alert">{resumeError}</p>}
    </div>
    <nav className="flex flex-wrap items-center gap-2 border-t p-3 text-sm" aria-label="Controlli del progetto">
      <button type="button" className="bg-foreground text-background rounded-lg px-3 py-2 disabled:opacity-50" disabled={!preview} onClick={() => toggle("preview")}>{ready ? "Apri consegna" : showLatestResult ? (previewDelivery?.purpose === "preview" ? "Apri ultimo campione" : "Apri ultimo risultato") : "Apri risultato"}</button>
      {preview&&<a className="rounded-lg border px-3 py-2 text-sm underline break-all" href={artifactURL(threadId,preview.path,true)} download>Scarica {preview.label}</a>}
      <button type="button" className={tabStyle} onClick={() => toggle("intervene")}>Intervieni</button>
      {(active || working) && <button type="button" className={tabStyle} disabled={controlBusy||deliveryRequested} onClick={()=>void deliverNow()}>{deliveryRequested?"Consegna richiesta…":"Consegna ora"}</button>}
      {(active || working) && onPause && <button type="button" className={tabStyle} disabled={controlBusy} onClick={() => void pauseWork()}>{controlBusy ? "Attendi…" : "Metti in pausa"}</button>}
      {!active && !working && (deliveryRequested || (!ready && !waitingForReview && !questions.length)) && onContinue && <button type="button" className={tabStyle} disabled={controlBusy || resumeRequested === threadId} onClick={() => void resume()}>{resumeRequested === threadId ? "Ripresa richiesta…" : "Riprendi lavoro"}</button>}
      <button type="button" className={`${tabStyle} ml-auto`} onClick={() => toggle("project")}>Dettagli progetto</button>
    </nav>

  </section>;
}

function DeliveryContents({delivery,results,threadId,revision}:{delivery:Delivery;results:Result[];threadId:string;revision?:string}) {
  const files=results.filter(f=>f.delivery_id===delivery.id);
  const groups=[{label:"Risultati da aprire",roles:["export"]},{label:"Sorgenti da modificare",roles:["source_archive","editable_source"]},{label:"Rapporti e istruzioni",roles:["report"]}];
  const known=groups.flatMap(g=>g.roles);
  return <div className="mt-3 space-y-4" data-testid="delivery-contents">
    {files.length>0 && delivery.purpose!=="review" && <ProjectGuide threadId={threadId} deliveryId={delivery.id} revision={revision}/>}
    {groups.map(group=>{const selected=files.filter(f=>group.roles.includes(f.role??""));return selected.length>0 && <section key={group.label}><h4 className="mb-2 font-semibold">{group.label}</h4><ul className="space-y-3">{selected.sort((a,b)=>Number(b.role==="source_archive")-Number(a.role==="source_archive")).map(f=><DeliveryFile key={f.path} file={f} threadId={threadId}/>)}</ul></section>})}
    {files.some(f=>!known.includes(f.role??"")) && <details><summary className="cursor-pointer">Risorse collegate e altri file</summary><ul className="mt-2 space-y-3">{files.filter(f=>!known.includes(f.role??"")).map(f=><DeliveryFile key={f.path} file={f} threadId={threadId}/>)}</ul></details>}
  </div>;
}

function DeliveryFile({ file, threadId }: { file: Result; threadId: string }) {
  return <li className="border-l-2 border-border pl-3"><span className="text-muted-foreground text-xs font-medium">{roles[file.role ?? "file"] ?? "File"}: </span><a className="break-all underline" href={artifactURL(threadId, file.path, true)}>{file.label}</a>
    {file.open_with && <p className="mt-1">Come aprire: {file.open_with}</p>}
    {file.editability && <p className="text-muted-foreground">Modificabile: {file.editability}</p>}
    {file.limitations?.map((limit, i) => <p className="text-muted-foreground" key={i}>{limit}</p>)}
  </li>;
}

function ReviewCard({ delivery, threadId }: { delivery: Delivery; threadId: string }) {
  const review = delivery.review;
  if (!review) return null;
  const target = review.target_version ? `versione ${review.target_version}` : review.target_label;
  const status = !review.validated ? "Verifica non convalidata" : !review.matches_current_brief ? "Da aggiornare al brief attuale" : review.status === "passed" ? "Revisione superata" : review.status === "needs_revision" ? "Correzioni richieste" : "Verifiche ancora incomplete";
  return <section className="mt-3 space-y-2 rounded-lg border p-3 text-sm" data-testid="version-review">
    <p className="font-medium">{status} · {target}</p>
    {review.correction_count > 0 && <p>{review.correction_count} correzioni indicate nel rapporto.</p>}
    <p className="text-xs text-muted-foreground">Questo controllo riguarda il file indicato, non le versioni successive.</p>
    {artifactURL(threadId, review.report_path) && <a className="underline" href={artifactURL(threadId, review.report_path)} target="_blank" rel="noreferrer">Apri rapporto della verifica</a>}
  </section>;
}
