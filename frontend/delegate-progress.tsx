"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import {tr, useUiLanguage, trMap} from "@/core/i18n/ui-text";
import { duration, jobHealth, secondsSince, terminalJob, type JobProgress } from "./delegate-progress-state";

import { ConversationAudit, OperationDetails } from "./conversation-audit";
import { ExperiencePanel } from "./experience-panel";
import { ProjectConnections } from "./project-connections";
import { ProjectDesign, type Design } from "./project-design";
import { ProjectGuide } from "./project-guide";
import { GovernanceStrip, ProfileUseLine, ToolChoices, type LiveGovernance, type ToolDecision } from "./project-governance";
import { JourneyPhases, JourneyStrip, ProjectJourney, useJourney } from "./project-journey";

const providers: Record<string, string> = trMap({ codex:["Codex", "Codex"], gemini:["Antigravity", "Antigravity"], deepseek:["DeepSeek", "DeepSeek"], openai:["OpenAI compatibile", "OpenAI compatible"] });
type Delivery = { version_state?: string; recovery?: { status: string; message: string; session_error: string }; unchanged_content?: boolean; change_kind?: string; content_version?: number | null; reused_archive_checks?: number; finalization_pending?: string[]; source_coverage?: { status: string; components: { name: string; tool: string; status: string; sources: {path: string; member?: string}[] }[] }; timing?: {status:string; cues:{name:string;status:string;delta_seconds:number}[]}; category?: string; version?: number | null; execution_status?: string; file_count?: number; role_title?: string; review?: { target_delivery_id: string | null; target_version?: number | null; target_label: string; status: string; validated: boolean; matches_current_brief: boolean; report_path: string; correction_count: number }; id: string; title: string; agent: string; at: string; current: boolean; contribution?: boolean; technical_status: string; issues: string[]; purpose: string };
type MethodStrategy = { state: string; method: string; reason: string; user_action: string; stop_reason: string; alternatives: { method: string; reason: string; status: string; tools: string[]; evidence: { path: string; sha256: string }[] }[] };
type RevisionAction = { requirement_id: string; action: string; reason?: string; priority: number; strategy: string };
type Comparison = { baseline_path: string; criteria: { requirement_id: string; status: string; evidence: string }[] };
type Criterion = { requirement_id?: string; criterion: string; status: string; evidence: string; method: string };
type Outcome = { title: string; result: string; format: string; use: string; quality: string; constraints: string[]; assumptions: string[]; questions: string[]; tool_options?: ToolDecision[] };
type ProjectRole = { capability_rationale?: string; tool_versions?: Record<string,string>; skills?: string[]; skill_bindings?: {name:string;revision:string}[]; experience?: { count: number; ids: string[] }; id: string; title: string; mission: string; version: string; expertise: string[]; procedure?: string[]; checks: string[]; tools: string[] };
type Orientation = { active_step_ids?: string[]; history_step_ids?: string[]; history_count?: number; total: number; counts: Record<string, number>; current: { id: string; goal: string; role_id: string; task: string }[]; remaining: { id: string; goal: string; status: string }[]; roles?: Record<string, { attempts: number; completed: number; running: number }>; needs_briefing: boolean };
type UserDirection = { visual_approach: string; instructions: string; revision: number };
type Project = { review_findings?: { severity: string; location: string; evidence: string; impact: string }[]; version_selection?: { approved: string | null; candidate: string | null; partial: string | null }; designs?: Design[]; updated_at?: string; latest_sample?: Result | null; correction_focus?: { requirement_id: string; criterion: string; reassess_role: boolean; action: string }[]; user_control?: { paused: boolean; deliver_now?: boolean }; user_direction?: UserDirection | null; strategy?: MethodStrategy | null; method_recovery?: { message: string } | null; outcome?: Outcome | null; orientation?: Orientation; roles?: ProjectRole[]; acceptance?: { user_requests: string[]; request_manifest?: { path: string }; request_documents?: { path: string }[]; request_count?: number; criteria: { id: string; requirement: string; critical: boolean; origin?: string; source_quote?: string }[] } | null; review_criteria?: Criterion[]; revision_actions?: RevisionAction[]; comparison?: Comparison | null; deliveries?: Delivery[]; quality_status?: string; summary?: string; next_action?: string; status?: string; product_path?: string; results?: Result[]; attention?: { code: string; message: string; action: string } | null; id: string; brief: string; steps: { id: string; agent: string; goal: string;
  status: string; role_id?: string; role_title?: string; note?: string; error?: string; attempt_count?: number }[] };
type Result = { path: string; agent: string; label: string; validated: boolean; at: string; delivery_id?: string; role?: string; open_with?: string; editability?: string; limitations?: string[] };
const roles: Record<string, string> = trMap({ export:["Prodotto", "Product"], editable_source:["Sorgente modificabile", "Editable source"], source_archive:["Pacchetto sorgenti", "Source package"], preview:["Anteprima", "Preview"], report:["Rapporto", "Report"], dependency:["Risorsa collegata", "Linked resource"], file:["File", "File"] });
const stepLabels: Record<string, string> = trMap({ pending:["Da fare", "To do"], running:["In corso", "In progress"],
  completed:["Incarico concluso", "Assignment completed"], needs_revision:["Da rivedere", "To review"], review:["Da valutare", "To assess"], paused:["In pausa", "Paused"], skipped:["Non necessaria", "Not needed"] });

type Tone = "active" | "done" | "attention" | "neutral";
function StatusBadge({ children, tone = "neutral" }: { children: ReactNode; tone?: Tone }) {useUiLanguage();
  const colors = { active: "border-blue-500/25 bg-blue-500/10 text-blue-700 dark:text-blue-300",
    done: "border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    attention: "border-amber-500/25 bg-amber-500/10 text-amber-800 dark:text-amber-300",
    neutral: "border-border bg-muted/50 text-muted-foreground" };
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${colors[tone]}`}>{children}</span>;
}
const stepTone = (state: string): Tone => state === "running" ? "active" : state === "completed" ? "done"
  : ["paused", "needs_revision", "review"].includes(state) ? "attention" : "neutral";
const tabStyle = "rounded-lg border border-transparent px-3 py-2 transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring aria-expanded:border-border aria-expanded:bg-muted aria-expanded:font-semibold disabled:opacity-50";

function ProjectDirection({ saved, onApply, busy }: { busy: boolean; saved?: UserDirection | null; onApply: (choice: string, instructions: string) => Promise<void> }) {useUiLanguage();
  const [choice, setChoice] = useState(saved?.visual_approach || "unspecified");
  const [instructions, setInstructions] = useState(saved?.instructions || "");
  async function apply() { await onApply(choice, instructions); }
  return <form id="harness-direction-form" onSubmit={event => { event.preventDefault(); void apply(); }} className="space-y-3 rounded-xl border p-4" data-testid="project-direction">
    <h4 className="font-semibold">{tr("Cambia le indicazioni", "Change the directions")}</h4>
    <p className="text-muted-foreground text-xs">{tr("La squadra si ferma, conserva i file salvati e riparte dalle nuove indicazioni.", "The team stops, keeps the saved files and restarts from the new directions.")}</p>
    <label className="block space-y-1"><span>{tr("Tecnica visiva, se pertinente", "Visual technique, if relevant")}</span>
      <select disabled={busy} className="bg-background w-full rounded border p-2" value={choice} onChange={e => setChoice(e.target.value)}>
        <option value="unspecified">{tr("Come indicato nel brief o in chat", "As stated in the brief or in chat")}</option>
        <option value="generated">{tr("Immagini generate", "Generated images")}</option>
        <option value="vector">{tr("Grafica vettoriale modificabile", "Editable vector graphics")}</option>
        <option value="mixed">{tr("Combinazione di immagini e vettori", "Mix of images and vectors")}</option>
        <option value="automatic">{tr("Lascio scegliere alla squadra", "Let the team choose")}</option>
      </select>
    </label>
    <label className="block space-y-1"><span>{tr("Indicazioni per questo progetto", "Directions for this project")}</span>
      <textarea className="w-full rounded border p-2" disabled={busy} maxLength={2000} rows={3} value={instructions} onChange={e => setInstructions(e.target.value)} placeholder={tr("Stile, strumenti, sorgenti richiesti o cambi di direzione…", "Style, tools, required sources or changes of direction…")} />
    </label>
    {choice === "vector" && <p className="text-muted-foreground text-xs">{tr("La generazione nativa di immagini sarà disattivata nei prossimi worker Codex. Un PNG inserito in un SVG non soddisfa la richiesta di vettori modificabili.", "Native image generation will be disabled in the next Codex workers. A PNG embedded in an SVG does not meet a request for editable vectors.")}</p>}
  </form>;
}

function JobCard({ job, now, threadId, role }: { job: JobProgress; now: number; threadId: string; role?: ProjectRole }) {useUiLanguage();
  const [stopping, setStopping] = useState(false);
  const [stopError, setStopError] = useState("");
  async function stop() {
    setStopping(true); setStopError("");
    try {
      const response = await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-jobs/${encodeURIComponent(job.job_id)}/stop`, { method: "POST" });
      if (!response.ok) throw new Error();
    } catch { setStopError(tr("Arresto non confermato: controlla lo stato aggiornato prima di riprovare.", "Stop not confirmed: check the updated status before retrying.")); setStopping(false); }
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
      <span className="text-muted-foreground text-xs">{duration(elapsed)} {tr("trascorsi", "elapsed")}</span>
    </div>
    {job.environment && <section className="space-y-1 text-xs" data-testid="job-environment">
      <p className="font-semibold">{job.resources_reclaimed ? tr("Sandbox chiusa · file salvati conservati", "Sandbox closed · saved files kept") : terminal ? tr("Incarico terminato · controlla il rilascio delle risorse sotto", "Assignment ended · check the resource release below") : tr("Ambiente dell’incarico", "Assignment environment")}</p>
      {assigned && <p>{tr("Strumenti assegnati:", "Assigned tools:")} {assigned.length ? assigned.map(person).join(", ") : tr("strumenti di base", "basic tools")}.</p>}
      {job.environment.profile&&<ProfileUseLine use={job.environment.profile}/>}
      {job.egress&&<p data-testid="job-egress">{tr("Rete limitata a", "Network limited to")} {job.egress.domains.join(", ") || tr("nessun dominio", "no domain")}.{job.egress.refused.length>0&&<strong className="text-amber-700 dark:text-amber-300"> {tr("Connessioni bloccate", "Blocked connections")}: {job.egress.refused.map((r)=>`${r.destination} ×${r.attempts}`).join(", ")}.</strong>}</p>}
      {job.environment.versions&&Object.keys(job.environment.versions).length>0&&<p>{tr("Versioni scelte:", "Chosen versions:")} {Object.entries(job.environment.versions).map(([tool,version])=>`${person(tool)} ${version}`).join(", ")}.</p>}
      <details><summary className="cursor-pointer">{tr("Programmi presenti nell’ambiente (", "Programs in the environment (")}{job.environment.tools.length})</summary>
        <p>{job.environment.tools.map(person).join(", ") || tr("Solo la base software", "Software base only")}.</p>
        <p>{tr("Possono essere condivisi con altri preset. La presenza di un programma non significa che sia stato usato: le operazioni osservate sono riportate sotto.", "They can be shared with other presets. A program being present does not mean it was used: the observed operations are listed below.")}</p>
        <p className="break-all">{tr("Identificativo tecnico del software:", "Technical software identifier:")} {job.environment.id}</p>
      </details>
    </section>}
    {operation && <div className="rounded-md border p-2 text-sm" data-testid="operation-progress">
      <p>{operation.label} · {operation.state === "running" && !terminal ? tr("in esecuzione", "running") : operation.state === "completed" ? "conclusa" : operation.state === "out_of_memory" ? tr("memoria esaurita", "out of memory") : "interrotta"}</p>
      {operation.progress?.total && <p>{operation.progress.done ?? 0}/{operation.progress.total} {tr("campioni osservati", "samples observed")}</p>}
      {operation.estimate_seconds !== undefined && <p>{tr("Stima iniziale dal campione: circa", "Initial estimate from the sample: about")} {duration(Math.round(operation.estimate_seconds))}{tr(". Può variare.", ". It may vary.")}</p>}
      {operation.elapsed_seconds !== undefined && <p>{duration(Math.floor(operation.elapsed_seconds))} {tr("di elaborazione", "of processing")}</p>}
    </div>}
    <details className="text-xs"><summary className="cursor-pointer">{tr("Modello e risorse", "Model and resources")}</summary>
    {job.resources?.memory_bytes !== undefined && <p className="text-muted-foreground text-xs">{terminal ? tr("Ultima RAM osservata", "Last RAM observed") : tr("RAM osservata", "RAM observed")}: {Math.round(job.resources.memory_bytes / 1048576)} MiB{job.resources.memory_limit_bytes ? tr(` · limite ${Math.round(job.resources.memory_limit_bytes / 1048576)} MiB`, ` · limit ${Math.round(job.resources.memory_limit_bytes / 1048576)} MiB`) : ""}</p>}
    {!!job.limits?.cpus && <p className="text-muted-foreground">{tr("CPU: massimo", "CPU: maximum")} {job.limits.cpus} {tr("core assegnati; non è il consumo istantaneo.", "cores assigned; this is not instantaneous usage.")}</p>}
    {!!job.resources?.oom_kills && <p role="status" className="text-sm">{tr("Il sistema ha terminato un processo per memoria esaurita. Conserva i file e verifica il budget della squadra prima di riprovare.", "The system ended a process because it ran out of memory. Keep the files and check the team budget before retrying.")}</p>}
    {job.model && <p className="text-muted-foreground text-xs">{tr("Modello:", "Model:")} {job.model}</p>}
    </details>
    {job.work_summary && job.work_summary !== job.summary && <p className="text-sm">{job.work_summary}</p>}
    <p className="text-sm" data-testid="delegate-summary">{job.summary}</p>
    {job.phase === "queued" && <p className="text-sm" data-testid="queue-position">{job.queue_position ? tr(`Posizione in coda: ${job.queue_position}. `, `Queue position: ${job.queue_position}. `) : tr("In coda. ", "Queued. ")}{job.queue_detail || tr("L’incarico parte automaticamente quando la sandbox si libera.", "The assignment starts automatically when the sandbox is free.")} {job.queue_activity_since && `Risorse occupate da ${duration(secondsSince(job.queue_activity_since, now))}. `}{tr("Puoi chiudere la pagina.", "You can close the page.")}</p>}
    {job.cancel_error && !job.resources_reclaimed && <p role="alert" className="text-sm">{tr("Arresto del worker non confermato. Verifica il collegamento Docker; non è sufficiente fermare il coordinatore.", "Worker stop not confirmed. Check the Docker connection; stopping the coordinator is not enough.")}</p>}
    {job.resources_reclaimed && <p className="text-muted-foreground text-xs" data-testid="worker-reclaimed">{tr("Risorse della fase liberate; file salvati conservati.", "Phase resources released; saved files kept.")}</p>}
    {job.cleanup_started_at && !job.resources_reclaimed && <p className="text-xs" role="status">{job.cleanup_error ? tr("Rimozione del container non confermata: la squadra richiede un controllo.", "Container removal not confirmed: the team needs a check.") : tr("Chiusura del container e rilascio delle risorse in corso.", "Closing the container and releasing resources.")}</p>}
    {!terminal && <details className="text-muted-foreground space-y-1 text-xs"><summary className="cursor-pointer">{tr("Tempi e segnali osservati", "Timing and signals observed")}</summary>
      <p>{tr("Ultimo avanzamento osservato:", "Last observed progress:")} {duration(secondsSince(job.last_activity_at, now))} {tr("fa", "ago")}</p>
      {job.execution_started_at && <p>{job.execution_state === "model" ? tr("Attesa del modello", "Waiting for the model") : tr("Comando in esecuzione", "Command running")}: {duration(secondsSince(job.execution_started_at, now))}</p>}
      {job.last_model_event_at && <p>{tr("Ultimo evento ricevuto dal modello:", "Last event received from the model:")} {duration(secondsSince(job.last_model_event_at, now))} {tr("fa", "ago")}</p>}
      {job.last_file_change_at && <p>{tr("Ultima modifica dei file:", "Last file change:")} {duration(secondsSince(job.last_file_change_at, now))} {tr("fa", "ago")}</p>}
      {remaining !== null && remaining > 0 && <p>{tr("Limite di esecuzione tra", "Execution limit in")} {duration(remaining)}{tr(". Non è una stima di consegna.", ". It is not a delivery estimate.")}</p>}
      {(job.limits?.model_wait_seconds ?? 0) > 0 && ["codex", "gemini"].includes(job.engine) && <p>{tr("Budget senza eventi del modello:", "Budget without model events:")} {duration(job.limits?.model_wait_seconds ?? 0)}{tr("; poi il coordinatore può ripianificare.", "; then the coordinator can replan.")}</p>}
      {heartbeat !== null && heartbeat <= 15 && <p>{tr("Monitor della sandbox presente · non conferma l’avanzamento del modello", "Sandbox monitor present · does not confirm the model's progress")}</p>}
    </details>}
    {!terminal && job.can_stop && <div className="space-y-1 text-xs">
      <button type="button" className="rounded border px-3 py-2 disabled:opacity-50" disabled={stopping || job.cancel_requested} onClick={() => void stop()}>{stopping || job.cancel_requested ? tr("Arresto richiesto…", "Stop requested…") : (job.phase === "queued" ? tr("Annulla attesa", "Cancel wait") : tr("Interrompi questa fase", "Stop this phase"))}</button>
      <p>{job.phase === "queued" ? tr("Rimuove solo questo incarico dalla coda. Il lavoro già in esecuzione continua.", "Removes only this assignment from the queue. Work already running continues.") : tr("Termina la fase corrente e restituisce il controllo al coordinatore. Le consegne precedenti restano disponibili; i file incompleti vengono conservati nello staging separato.", "Ends the current phase and returns control to the coordinator. Previous deliveries remain available; incomplete files are kept in the separate staging area.")}</p>
      {stopError && <p role="alert">{stopError}</p>}
    </div>}
    {health && <p className="rounded-md border border-amber-500/50 p-2 text-sm" role="status">{health}</p>}
    {job.files.length > 0 && <div className="text-xs">
      <p>{job.files_count} {tr("file", "files")} {job.phase === "completed" ? tr("presenti alla consegna", "present at delivery") : terminal ? tr("provvisori, non consegnati", "provisional, not delivered") : tr("in lavorazione, ancora da verificare", "in progress, still to verify")}</p>
      <ul className="text-muted-foreground list-inside list-disc">
        {job.files.slice(0, 5).map((file) => <li key={file.name} className="break-all">{file.name} ({file.size} byte)</li>)}
      </ul>
    </div>}
    {job.events.length > 0 && <details className="text-xs">
      <summary className="cursor-pointer">{tr("Cronologia operativa (", "Operational timeline (")}{job.events.length} {tr("eventi recenti)", "recent events)")}</summary>
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

export function DelegateProgress({ threadId, active, pending, coordinatorError = false, onContinue, onPause }: Props) {useUiLanguage();
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
  // The team and its activities are one section; old links to activities keep working.
  const tab = panel?.threadId === threadId ? (panel.tab === "activity" ? "team" : panel.tab) : null;
  const guided = useJourney(threadId);
  const guidedStage = guided.journey?.stages.find(stage => stage.id === guided.journey?.current);
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
  const versionStates: Record<string, string> = { working: tr("In lavorazione", "In progress"), approved: tr("Approvata", "Approved"), candidate: tr("Candidata · da valutare", "Candidate · to assess"), partial: tr("Parziale · non verificata", "Partial · not verified"), needs_revision: tr("Da correggere", "To fix") };
  const editing = versions.find(d => d.execution_status === "running");
  const versionName = (delivery: Delivery) => delivery.unchanged_content ? tr(`${delivery.change_kind === "sources" ? tr("Sorgenti", "Sources") : tr("Metadati", "Metadata")} aggiornati · versione ${delivery.content_version ?? tr("precedente", "previous")} invariata`, `${delivery.change_kind === "sources" ? tr("Sorgenti", "Sources") : tr("Metadati", "Metadata")} updated · version ${delivery.content_version ?? tr("precedente", "previous")} unchanged`) : delivery.category === "sample" || delivery.purpose === "preview" ? tr("Campione", "Sample") : delivery.version ? tr(`Versione ${delivery.version}`, `Version ${delivery.version}`) : delivery.current ? tr("Versione selezionata", "Selected version") : tr("Tentativo di consegna", "Delivery attempt");
  const currentResults = selectedDelivery ? results.filter((r) => r.delivery_id === selectedDelivery.id) : results;
  const media = [...currentResults].filter(r => r.role !== "dependency" && r.role !== "report").sort((a, b) => b.at.localeCompare(a.at)).filter((r) => kind(r.path) !== "source");
  const selected: Result | undefined = project?.product_path
    ? results.find((r) => r.path === project.product_path) ?? { path: project.product_path, label: project.product_path.split("/").pop() ?? tr("Risultato", "Result"), agent: "", validated: false, at: "" }
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
  const title = deliveryRequested ? (working ? tr("Consegna richiesta · verifico i file disponibili", "Delivery requested · checking the available files") : results.length ? tr("Consegna disponibile · attendo le tue indicazioni", "Delivery available · waiting for your directions") : tr("Chiusura richiesta · nessun nuovo prodotto verificato", "Shutdown requested · no new verified product")) : activeJobs.length>1 ? tr(`${activeJobs.length} incarichi attivi`, `${activeJobs.length} active assignments`) : paused ? (working || active ? tr("Pausa richiesta", "Pause requested") : tr("Progetto in pausa", "Project paused")) : working && current.phase === "queued" ? (current.queue_reason === "preload" ? tr("Il precaricamento lascia spazio alla chat", "Preloading is making room for the chat") : tr("In attesa del proprio turno", "Waiting for its turn")) : working && jobHealth(current, now) ? tr("Avanzamento da verificare", "Progress to verify") : working ? `${current.role_title || person(current.agent)} ${tr("sta lavorando", "is working")}` : clarifying ? tr("Definiamo il risultato insieme", "Let's define the result together") : active ? tr("La squadra sta preparando il prossimo risultato", "The team is preparing the next result")
    : coordinatorError || attention || project?.status === "blocked" ? tr("Il lavoro è in pausa", "Work is paused") : ready ? tr("Il risultato è pronto", "The result is ready") : results.length ? tr("Una versione è disponibile", "A version is available") : tr("La squadra è pronta", "The team is ready");
  const specificAction = current && ["running_tool", "exporting", "checking", "finalizing"].includes(current.phase)
    && current.summary !== "Esecuzione di uno strumento";
  const nativeOperation = current?.operations?.find(o => o.state === "running");
  const nativeSummary = nativeOperation ? nativeOperation.label + (nativeOperation.progress?.total ? tr(` · ${nativeOperation.progress.done ?? 0}/${nativeOperation.progress.total} campioni`, ` · ${nativeOperation.progress.done ?? 0}/${nativeOperation.progress.total} samples`) : "") : null;
  const summary = clarifying && !working ? (questions[0] || tr("Mancano risultato atteso e forma della consegna.", "Expected result and delivery form are missing.")) : working ? (nativeSummary ?? (specificAction ? current.summary : current.work_summary || current.summary)) : attention?.message
    ?? (coordinatorError ? tr("Il coordinatore si è fermato. I file già salvati restano disponibili.", "The coordinator has stopped. Files already saved remain available.") : project?.summary || project?.brief);
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
      if(!response.ok) throw Error(tr("Consegna non confermata: controlla lo stato e riprova.", "Delivery not confirmed: check the status and retry."));
      const result=await response.json();
      setSnapshot(previous=>previous?.threadId===threadId&&previous.project?{...previous,project:{...previous.project,user_control:result.user_control}}:previous);
      setControlNotice(tr("Consegna richiesta. Chiudo le attività e verifico i file già salvati.", "Delivery requested. Closing activities and checking the files already saved."));
    } catch(error) {setControlNotice(error instanceof Error?error.message:tr("Consegna non confermata", "Delivery not confirmed"));}
    finally {setControlBusy(false);}
  }
  async function control(paused: boolean) {
    const response = await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-control`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ paused }),
    });
    if (!response.ok) throw new Error(tr("Controllo non confermato", "Check not confirmed"));
    if (resumeOwner.current !== threadId) throw new Error(tr("Conversazione cambiata", "Conversation changed"));
    setSnapshot(previous => previous?.threadId === threadId && previous.project
      ? { ...previous, project: { ...previous.project, user_control: { paused } } } : previous);
  }
  async function pause() {
    if (!onPause) throw new Error(tr("Arresto non disponibile", "Stop unavailable"));
    await control(true); // Close the server-side start gate before canceling the run.
    setControlNotice(tr("Arresto in corso. Attendo la chiusura delle sandbox…", "Stopping. Waiting for the sandboxes to close…"));
    await onPause();
    const deadline = Date.now() + 30000;
    do {
      const response = await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-jobs`, { cache: "no-store" });
      if (!response.ok) throw new Error(tr("Stato non disponibile", "Status unavailable"));
      const data = await response.json() as { jobs: JobProgress[]; project: Project | null; governance?: LiveGovernance | null };
      if (resumeOwner.current !== threadId) throw new Error(tr("Conversazione cambiata", "Conversation changed"));
      setSnapshot({ threadId, jobs: data.jobs, project: data.project, governance: data.governance ?? null });
      if (data.jobs.every(job => terminalJob(job) && (!job.can_stop || job.resources_reclaimed))) {
        setControlNotice(tr("In pausa. I file salvati sono conservati.", "Paused. Saved files are kept.")); return;
      }
      await new Promise(resolve => setTimeout(resolve, 1000));
    } while (Date.now() < deadline);
    throw new Error(tr("Chiusura delle sandbox ancora da confermare. Il progetto resta in pausa: verifica Attività prima di riprendere.", "Sandbox shutdown not yet confirmed. The project stays paused: check Activities before resuming."));
  }
  async function pauseWork() {
    setControlBusy(true); setControlNotice("");
    try { await pause(); } catch (error) { setControlNotice(error instanceof Error ? error.message : tr("Pausa non confermata.", "Pause not confirmed.")); }
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
      if (!response.ok) throw new Error(tr("Indicazioni non salvate. Il progetto resta in pausa.", "Directions not saved. The project stays paused."));
      await control(false);
      await onContinue(tr(`Ho aggiornato le indicazioni dal pannello: tecnica visiva ${choice}; ${instructions || tr("restano valide le altre indicazioni", "the other directions still apply")}. Rileggi le scelte salvate, conserva i file validi e ripianifica il lavoro. Se manca una risposta decisiva chiedimela prima di produrre.`, `I updated the directions from the panel: visual technique ${choice}; ${instructions || tr("restano valide le altre indicazioni", "the other directions still apply")}. Reread the saved choices, keep the valid files and replan the work. If a decisive answer is missing, ask me before producing.`));
      if (resumeOwner.current === threadId) { setPanel(null); setControlNotice(tr("Nuove indicazioni inviate alla squadra.", "New directions sent to the team.")); }
    } catch (error) {
      if (resumeOwner.current === threadId) {
        try { await control(true); } catch { /* Keep the original actionable error. */ }
        setControlNotice(error instanceof Error ? error.message : tr("Aggiornamento non confermato.", "Update not confirmed."));
      }
    }
    finally { if (resumeOwner.current === threadId) setControlBusy(false); }
  }
  useEffect(() => { if (active) { setResumeRequested(null); setResumeError(null); } }, [active]);
  useEffect(() => {
    if (resumeRequested !== threadId || active || working) return;
    const timer = setTimeout(() => { setResumeRequested(null); setResumeError(tr("Avvio non confermato: verifica lo stato e riprova se il lavoro resta fermo.", "Start not confirmed: check the status and retry if the work stays stuck.")); }, 15000);
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
        setResumeRequested(null); setResumeError(tr("Non riesco a inviare la richiesta di ripresa. I risultati restano disponibili: riprova.", "I cannot send the resume request. Results remain available: retry."));
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
      if (!response.ok) throw new Error(tr("Versione non disponibile", "Version unavailable"));
      const data = await response.json() as { project: Project };
      if (resumeOwner.current === owner) setSnapshot((current) => current?.threadId === owner ? { ...current, project: data.project } : current);
    } catch {
      if (resumeOwner.current === owner) setAcceptError(tr("Non posso accettare questa versione: potrebbe essere cambiata o avere sorgenti incompleti. Aggiorna e controlla la consegna.", "I cannot accept this version: it may have changed or have incomplete sources. Refresh and check the delivery."));
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
        if (!response.ok) throw new Error(tr("Avanzamento non disponibile", "Progress unavailable"));
        const data = await response.json() as { jobs: JobProgress[]; project?: Project | null; governance?: LiveGovernance | null };
        if (!Array.isArray(data.jobs)) throw new Error(tr("Avanzamento non valido", "Invalid progress"));
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
  if (!jobs.length && !project && !pending && !coordinatorError) return <><ProjectJourney threadId={threadId} state={guided} onContinue={onContinue}/><details className="mb-2 rounded-xl border text-sm" data-testid="chat-audit-only" onToggle={event => setPanel(event.currentTarget.open ? { threadId, tab: "audit" } : null)}>
    <summary className="cursor-pointer p-3">{tr("Registro della conversazione", "Conversation log")}</summary>
    {tab === "audit" && <div className="p-3"><ConversationAudit key={threadId} threadId={threadId} /></div>}
  </details></>;
  const health = current ? jobHealth(current, now) : null;
  const recent = [...jobs.filter((job) => !terminalJob(job)), ...jobs.filter(terminalJob).slice(0, 4)];
  return <section ref={dock} className="bg-background relative mb-2 rounded-2xl border shadow-sm" aria-label={tr("Il tuo progetto", "Your project")} data-testid="delegate-progress">
    {tab && <dialog ref={dialog} onCancel={() => setPanel(null)} onClose={() => setPanel(null)} aria-labelledby="harness-panel-title" className={`bg-background text-foreground fixed inset-0 m-auto ${readingLesson && tab === "experience" ? "h-[calc(100dvh-2rem)]" : "h-[85dvh]"} max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-3xl overflow-hidden rounded-2xl border p-0 shadow-xl backdrop:bg-black/40`} data-testid="harness-drawer">
      <div className="flex h-full min-h-0 flex-col">
      <header className="flex shrink-0 items-center justify-between gap-2 border-b px-4 py-3">
        <h3 id="harness-panel-title" className="font-semibold">{readingLesson && tab === "experience" ? tr("Lezione completa", "Full lesson") : tab === "intervene" ? tr("Intervieni sul progetto", "Step into the project") : tr("Il tuo progetto", "Your project")}</h3>
        <button type="button" className="rounded-lg border px-3 py-2 text-sm" onClick={() => setPanel(null)} aria-label={tr("Chiudi dettagli del progetto", "Close project details")}>{tr("Chiudi", "Close")}</button>
      </header>
      {!(readingLesson && tab === "experience") && <nav className="grid shrink-0 grid-cols-3 gap-1 border-b p-2 text-sm sm:flex sm:flex-wrap" aria-label={tr("Sezioni del progetto", "Project sections")}>
        {([["project", tr("Stato", "Status")], ...(guided.journey ? [["journey", tr("Percorso", "Path")]] : []), ["preview", tr("Risultato", "Result")], ["files", tr("Versioni", "Versions")], ["team", tr("Squadra", "Team")], ...(project?.designs?.length ? [["design", tr("Tavole", "Boards")]] : []), ["experience", tr("Lezioni", "Lessons")], ["audit", tr("Registro", "Log")]] as [string, string][]).map(([id, label]) => <button key={id} type="button" className={`${tabStyle} shrink-0`} aria-current={tab === id ? "page" : undefined} aria-expanded={tab === id} onClick={() => setPanel({ threadId, tab: id })}>{label}</button>)}
      </nav>}
      <div key={tab} className="min-h-0 flex-1 overflow-y-auto p-4" data-testid="rh-drawer-content">
      {tab === "journey" && <JourneyPhases threadId={threadId} state={guided}/>}
      {tab === "intervene" && <ProjectDirection key={threadId} saved={project?.user_direction} onApply={applyDirection} busy={controlBusy} />}
      {tab === "project" && project && <div className="space-y-4 text-sm" data-testid="project-overview">
        <section className="space-y-2 rounded-xl border border-blue-500/25 bg-blue-500/5 p-4" data-testid="project-position">
          <h4 className="font-semibold">{tr("Dove siamo", "Where we are")}</h4>
          <p>{planned.length ? tr(`${completed} di ${planned.length} incarichi conclusi nella squadra attuale`, `${completed} of ${planned.length} assignments completed in the current team`) : tr("La squadra e le attività sono ancora da definire.", "The team and activities are still to be defined.")}</p>
          {currentActivity && <p><strong>{tr("Responsabilità attuale:", "Current responsibility:")}</strong> {currentActivity.role_title || person(currentActivity.agent)}</p>}
          {guidedStage && <p><strong>{tr("Fase del percorso:", "Path phase:")}</strong> {tr(guidedStage.title.it, guidedStage.title.en)}</p>}
          {summary && <p><strong>{tr("Adesso:", "Now:")}</strong> {summary}</p>}
          {!working && !clarifying && project.next_action && <p><strong>{tr("Prossima azione:", "Next action:")}</strong> {project.next_action}</p>}
          <p className="text-muted-foreground text-xs">{tr("Gli incarichi possono cambiare. Il conteggio non è una percentuale di completamento o una stima dei tempi.", "Assignments may change. The count is not a completion percentage or a time estimate.")}</p>
        </section>
        {project.correction_focus?.some(f => f.reassess_role) && <details className="rounded-xl border p-3" data-testid="recurring-defects"><summary className="cursor-pointer font-medium">{tr("Correzione da ripensare", "Fix to rethink")}</summary><p className="my-2 text-xs">{tr("La squadra deve rivalutare metodo o competenza prima di estendere il lavoro.", "The team must reassess method or skill before extending the work.")}</p>{project.correction_focus.filter(f => f.reassess_role).map(f => <p className="my-2" key={f.requirement_id}>{f.criterion}: {f.action}</p>)}</details>}
        <section className="bg-muted/30 space-y-3 rounded-xl border p-4">
          <h4 className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">{tr("Risultato da ottenere", "Result to achieve")}</h4>
          <p className="text-base font-medium leading-relaxed">{project.outcome?.result || project.brief}</p>
          <p><strong>{tr("Consegna:", "Delivery:")}</strong> {project.outcome?.format || tr("Da definire con te prima di proseguire la produzione.", "To define with you before production continues.")}</p>
          {project.outcome?.use && <p><strong>{tr("Uso e destinatari:", "Use and audience:")}</strong> {project.outcome.use}</p>}
          {project.outcome?.quality && <p><strong>{tr("Qualità attesa:", "Expected quality:")}</strong> {project.outcome.quality}</p>}
        </section>
        <ToolChoices decisions={project.outcome?.tool_options}/>
        <GovernanceStrip governance={governance} expanded threadId={threadId} onChanged={next => setSnapshot(previous => previous?.threadId === threadId ? { ...previous, governance: next } : previous)}/>
        <ProjectConnections threadId={threadId}/>
        {questions.length > 0 && <section className="space-y-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4" data-testid="brief-questions">
          <h4 className="font-semibold">{tr("Le scelte che mancano", "Choices still missing")}</h4>
          <ul className="list-inside list-disc">{questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
          <p>{tr("Rispondi alle domande nella chat. La produzione attende queste scelte.", "Answer the questions in the chat. Production waits for these choices.")}</p>
        </section>}
        {planned.some(step => step.status !== "completed") && <section className="space-y-2">
          <h4 className="font-semibold">{tr("Attività ancora previste", "Activities still planned")}</h4>
          <ul className="space-y-2">{planned.filter(step => step.status !== "completed").map(step => <li key={step.id} className="flex items-start gap-3 rounded-lg border p-3">
            <span className="shrink-0"><StatusBadge tone={stepTone(step.status)}>{stepLabels[step.status] ?? step.status}</StatusBadge></span><span>{step.goal}</span>
          </li>)}</ul>
        </section>}
        {otherSteps.length > 0 && <details className="space-y-2 rounded-xl border p-3" data-testid="project-history">
          <summary className="cursor-pointer font-medium">{tr("Altre attività del progetto (", "Other project activities (")}{otherSteps.length})</summary>
          <p className="text-muted-foreground">{tr("Queste attività appartengono a ruoli fuori dalla squadra attuale. Tentativi e file restano conservati; possono essere ripresi senza ricominciare.", "These activities belong to roles outside the current team. Attempts and files are kept; they can be resumed without starting over.")}</p>
          <ul className="space-y-2">{otherSteps.map(step => <li key={step.id}><StatusBadge tone={stepTone(step.status)}>{stepLabels[step.status] ?? step.status}</StatusBadge> {step.goal}</li>)}</ul>
        </details>}
        {(project.strategy || project.method_recovery) && <details className="space-y-2 rounded-xl border p-3" data-testid="project-method">
          <summary className="cursor-pointer font-semibold">{tr("Metodo e alternative", "Method and alternatives")}</summary>
          {project.method_recovery && <p className="text-amber-700 dark:text-amber-300">{project.method_recovery.message}</p>}
          {project.strategy && <>
            <p><strong>{project.strategy.state === "selected" ? tr("Metodo scelto", "Chosen method") : project.strategy.state === "needs_user" ? tr("Decisione necessaria", "Decision needed") : tr("Metodo in valutazione", "Method under evaluation")}:</strong> {project.strategy.method}</p>
            <p>{project.strategy.reason}</p>
            <ul className="space-y-2">{project.strategy.alternatives.map((item, index) => <li key={index} className="rounded-lg border p-2">
              <p><strong>{item.method}</strong> · {item.status === "candidate" ? tr("Da provare", "To try") : item.status === "tested" ? tr("Prova disponibile", "Trial available") : tr("Valutato non disponibile", "Assessed as unavailable")}</p>
              <p>{item.reason}</p>
              {!!item.tools.length && <p className="text-muted-foreground text-xs">{tr("Strumenti:", "Tools:")} {item.tools.join(", ")}</p>}
              {item.evidence.map((proof, i) => { const href = artifactURL(threadId, proof.path); return href ? <a key={i} href={href} target="_blank" rel="noreferrer" className="mr-3 underline">{tr("Prova", "Trial")} {i + 1}</a> : null; })}
            </li>)}</ul>
            {project.strategy.state === "needs_user" && <p><strong>{tr("Per proseguire:", "To continue:")}</strong> {project.strategy.user_action}</p>}
          </>}
          {!!project.outcome?.assumptions.length && <div><h5 className="font-medium">{tr("Scelte provvisorie della squadra", "Team's provisional choices")}</h5><ul className="list-inside list-disc">{project.outcome.assumptions.map((item, i) => <li key={i}>{item}</li>)}</ul><p className="text-muted-foreground text-xs">{tr("Si possono rivedere mantenendo il risultato e i vincoli richiesti.", "They can be revised while keeping the requested result and constraints.")}</p></div>}
        </details>}
        {!!project.review_findings?.length && <details className="rounded-xl border p-3"><summary className="cursor-pointer">{tr("Rilievi della revisione (", "Review findings (")}{project.review_findings.length})</summary><ul className="mt-2 space-y-3">{project.review_findings.map((f, i) => <li key={i}><strong>{f.severity === "blocking" ? tr("Difetto bloccante", "Blocking defect") : f.severity === "advisory" ? tr("Suggerimento facoltativo", "Optional suggestion") : tr("Da verificare", "To verify")}</strong> · {f.location}<p>{f.evidence}</p><p className="text-muted-foreground">{tr("Impatto:", "Impact:")} {f.impact}</p></li>)}</ul></details>}
        {!!project.revision_actions?.length && <section className="space-y-2 rounded-xl border border-amber-500/30 p-3" data-testid="revision-actions">
          <h4 className="font-semibold">{tr("Correzioni dal controllo qualità", "Fixes from quality control")}</h4>
          <ol className="list-inside list-decimal space-y-2">{project.revision_actions.map((action, i) => <li key={i}>{action.action}{action.strategy === "change_method" && <p className="text-muted-foreground text-xs">{tr("Serve provare un metodo diverso.", "A different method needs to be tried.")}</p>}</li>)}</ol>
        </section>}
        {project.comparison && <section className="space-y-2 rounded-xl border p-3" data-testid="quality-comparison">
          <h4 className="font-semibold">{tr("Confronto con la versione precedente", "Comparison with the previous version")}</h4>
          <ul className="space-y-2">{project.comparison.criteria.map((item, i) => <li key={i}><strong>{item.status === "improved" ? tr("Migliorato", "Improved") : item.status === "unchanged" ? tr("Invariato", "Unchanged") : item.status === "regressed" ? tr("Peggiorato", "Worse") : tr("Non verificato", "Not verified")}</strong> · {item.evidence}</li>)}</ul>
        </section>}
        {!!project.outcome?.constraints.length && <section><h4 className="font-semibold">{tr("Vincoli", "Constraints")}</h4><ul className="list-inside list-disc">{project.outcome.constraints.map((c, i) => <li key={i}>{c}</li>)}</ul></section>}

      </div>}
      {tab === "preview" && <div className="space-y-3">
        <p><StatusBadge tone={ready ? "done" : "attention"}>{ready ? tr("Prodotto finale", "Final product") : tr("Bozza di lavoro: può essere incompleta e non sostituisce il prodotto finale.", "Working draft: it may be incomplete and does not replace the final product.")}</StatusBadge></p>
        {previewDelivery && <section className="space-y-1 text-sm" data-testid="selected-version">
          <p className="font-semibold">{versionName(previewDelivery)} · {ready ? tr("Consegna finale", "Final delivery") : tr("Da valutare", "To assess")}</p>
          <p>{previewDelivery.title}</p>
          {!!previewDelivery.issues.length && <p role="status" className="rounded border border-amber-500/30 p-2 text-sm">{tr("Da correggere:", "To fix:")} {previewDelivery.issues.join("; ")}</p>}
          {!!previewDelivery.reused_archive_checks && <p className="text-muted-foreground text-xs">{tr("Verifiche sorgenti riutilizzate per", "Source checks reused for")} {previewDelivery.reused_archive_checks} {tr("archivio/i identico/i nella stessa versione degli strumenti.", "identical archive(s) with the same tool versions.")}</p>}
          {!!previewDelivery.finalization_pending?.length && <p className="text-muted-foreground">{tr("Prima della consegna finale:", "Before final delivery:")} {previewDelivery.finalization_pending.join("; ")}</p>}
          {editing && editing.id !== previewDelivery.id && <p className="text-muted-foreground">{versionName(editing)} {tr("in lavorazione. Qui vedi ancora", "in progress. Here you still see")} {versionName(previewDelivery).toLowerCase()}.</p>}
          <p className="text-muted-foreground text-xs">{tr("Anteprima, download e sorgenti sotto appartengono a questa lavorazione.", "Preview, download and sources below belong to this work step.")}</p>
          {previewDelivery.source_coverage && <details className="rounded border p-3" data-testid="component-sources"><summary className="cursor-pointer">{tr("Sorgenti delle componenti ·", "Component sources ·")} {previewDelivery.source_coverage.status === "documented" ? "documentati" : tr("da completare", "to complete")}</summary>{previewDelivery.source_coverage.components.map((c,i) => <div className="my-2" key={i}><p><strong>{c.name}</strong> · {c.tool} · {c.status === "documented" ? tr("sorgenti associati", "linked sources") : tr("sorgenti incompleti", "incomplete sources")}</p>{c.sources.map((r,n) => <p className="break-all text-xs" key={n}>{r.member || r.path.split("/").pop()}</p>)}</div>)}<p className="text-xs">{tr("Il progetto principale non dimostra la modificabilità di tutte le risorse. Apertura e ricostruzione hanno verifiche distinte.", "The main project does not prove that every resource is editable. Opening and rebuilding are checked separately.")}</p></details>}
          {previewDelivery.timing && <details className="rounded border p-3" data-testid="delivery-timing"><summary className="cursor-pointer">{tr("Sincronismo ·", "Sync ·")} {previewDelivery.timing.status === "passed" ? tr("cue misurati", "cues measured") : tr("da verificare", "to verify")}</summary>{previewDelivery.timing.cues.map((c,i) => <p className="my-1 text-xs" key={i}>{c.name}: {c.status === "not_run" ? tr("non verificato", "not verified") : tr(`${c.delta_seconds} s di scarto`, `${c.delta_seconds} s of offset`)}</p>)}<p className="text-xs">{tr("Il controllo dei picchi audio non sostituisce l’ascolto e la verifica visiva.", "The audio peak check does not replace listening and visual review.")}</p></details>}
        </section>}
        {showLatestResult && latestResult && <p className="text-sm" data-testid={previewDelivery?.purpose === "preview" ? "latest-sample" : "latest-result"}>{previewDelivery?.purpose === "preview" ? tr("Ultimo campione disponibile", "Latest sample available") : tr("Ultimo risultato disponibile", "Latest result available")} · {new Date(latestResult.at).toLocaleString()} {tr("· Da valutare prima di considerarlo definitivo.", "· To assess before treating it as final.")}</p>}
        {preview && <div className="bg-muted/20 space-y-3 rounded-xl border p-3" data-testid="primary-result">
          {kind(preview.path) === "video" && <video key={preview.path} className="max-h-[35dvh] w-full rounded" controls playsInline preload="metadata" aria-label={tr("Anteprima video", "Video preview")} src={artifactURL(threadId, preview.path)} />}
          {kind(preview.path) === "image" && <img className="max-h-[35dvh] w-full object-contain" alt={tr("Anteprima del lavoro", "Work preview")} src={artifactURL(threadId, preview.path)} />}
          {kind(preview.path) === "audio" && <audio controls aria-label={tr("Anteprima audio", "Audio preview")} src={artifactURL(threadId, preview.path)} />}
          {kind(preview.path) === "pdf" && <iframe title={tr("Anteprima PDF", "PDF preview")} className="h-[50dvh] min-h-72 w-full rounded border" src={artifactURL(threadId, preview.path)} /> }
          {kind(preview.path) === "source" && <p className="text-sm">{tr("Risultato disponibile come documento o progetto: scaricalo e aprilo con l’app indicata nella consegna.", "Result available as a document or project: download it and open it with the app named in the delivery.")}</p>}
          <p className="text-muted-foreground text-xs">{tr("Scarica il risultato", "Download the result")}</p>
          <a className="bg-foreground text-background inline-flex max-w-full items-center rounded-lg px-4 py-2 text-sm font-medium break-all focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring" href={artifactURL(threadId, preview.path, true)}>{preview.label}</a>
          {preview.open_with && <p className="text-sm">{tr("Come aprire:", "How to open:")} {preview.open_with}</p>}
          {preview.limitations?.map((limit, i) => <p className="text-muted-foreground text-xs" key={i}>{limit}</p>)}
        </div>}
        {audio && preview && kind(preview.path) === "video" && audio.path !== preview.path && <div>
          {!ready && <p className="text-sm">{tr("Audio disponibile separatamente. Questa bozza video potrebbe non contenerlo ancora.", "Audio available separately. This video draft may not contain it yet.")}</p>}
          <audio controls preload="metadata" aria-label={tr("Traccia audio disponibile", "Audio track available")} src={artifactURL(threadId, audio.path)} />
        </div>}
        {!preview && <p className="text-sm">{tr("Nessuna anteprima disponibile. Puoi controllare attività e file salvati.", "No preview available. You can check activities and saved files.")}</p>}
        {previewDelivery && <ProjectGuide threadId={threadId} deliveryId={previewDelivery.id} revision={project?.updated_at}/>}
        {pairedSources.length > 0 && <section className="space-y-3 rounded-xl border p-3 text-sm" data-testid="paired-sources">
          <h4 className="font-semibold">{tr("Sorgenti della stessa consegna", "Sources of the same delivery")}</h4>
          <ul className="space-y-3">{pairedSources.map(file => <DeliveryFile key={file.path} file={file} threadId={threadId} />)}</ul>
        </section>}
        {showLatestResult && selectedDelivery && selectedDelivery.id !== preview?.delivery_id && <details className="rounded-xl border p-3 text-sm" data-testid="previous-delivery">
          <summary className="cursor-pointer font-medium">{tr("Consegna precedente conservata", "Previous delivery kept")}</summary>
          <p className="my-2">{selectedDelivery.title}{tr(". Il risultato mostrato sopra non la sostituisce e deve ancora essere valutato.", ". The result shown above does not replace it and must still be assessed.")}</p>
          <ul className="space-y-3">{currentResults.filter(file => ["export", "editable_source", "source_archive"].includes(file.role ?? "")).map(file => <DeliveryFile key={file.path} file={file} threadId={threadId}/>)}</ul>
        </details>}
        {project?.quality_status && !showLatestResult && <p className="text-sm">{project.quality_status === "accepted_by_user" ? tr("Questa versione è stata accettata da te.", "You accepted this version.") : project.quality_status === "passed" ? tr("Revisione dello specialista registrata per questa versione.", "Specialist review recorded for this version.") : tr("Qualità ancora da valutare: i controlli tecnici non verificano tutti i requisiti del progetto.", "Quality still to assess: technical checks do not verify every project requirement.")}</p>}
        {project?.acceptance && <details className="rounded border p-3 text-sm" data-testid="acceptance-criteria">
          <summary className="cursor-pointer font-medium">{tr("Rispondenza alla tua richiesta", "Match with your request")}</summary>
          <p className="my-2 whitespace-pre-wrap">{project.acceptance.user_requests[0]}</p>
          <ul className="space-y-2">{project.acceptance.criteria.map((rule) => {
            const observations = project.review_criteria?.filter(c => c.requirement_id === rule.id) ?? [];
            const verdict = observations.some(c => c.status === 'failed') ? 'failed' : observations.length && observations.every(c => c.status === 'passed') ? 'passed' : 'not_run';
            return <li key={rule.id}><strong>{verdict === "passed" ? tr("Verificato", "Verified") : verdict === "failed" ? tr("Da correggere", "To fix") : tr("Da verificare", "To verify")}</strong> · {rule.requirement}
              {rule.origin === "proposal" && <p className="text-muted-foreground text-xs">{tr("Criterio proposto dalla squadra, rivedibile nel rispetto della richiesta.", "Criterion proposed by the team, revisable within the request.")}</p>}
              {rule.origin === "user" && rule.source_quote && <p className="text-muted-foreground text-xs">{tr("Dalla tua richiesta: «", "From your request: “")}{rule.source_quote}»</p>}
              {observations.length > 0 && <details className="mt-1 text-muted-foreground"><summary className="cursor-pointer">{tr("Evidenze (", "Evidence (")}{observations.length})</summary><ul className="list-inside list-disc">{observations.map((observed, i) => <li key={i}>{observed.status === "failed" ? tr("Difetto", "Defect") : observed.status === "passed" ? tr("Verificato", "Verified") : tr("Non verificato", "Not verified")}: {observed.evidence}</li>)}</ul></details>}</li>;
          })}</ul>
          {project.acceptance.request_documents?.[0] && <p><a className="underline" href={artifactURL(threadId, project.acceptance.request_documents[0].path, true)}>{tr("Leggi la richiesta originale completa", "Read the full original request")}</a></p>}
          {project.acceptance.request_manifest && <p><a className="underline" href={artifactURL(threadId, project.acceptance.request_manifest.path, true)}>{tr("Indice dei messaggi conservati (", "Index of kept messages (")}{project.acceptance.request_count ?? 1})</a></p>}
        </details>}
        {!ready && !showLatestResult && !working && !active && selectedDelivery?.technical_status === "passed" && !selectedDelivery.finalization_pending?.length && <div className="space-y-2 border-t pt-3">
          <p className="text-sm">{tr("Se hai verificato il risultato e ti soddisfa, puoi accettare questa versione. I controlli dei sorgenti restano obbligatori.", "If you checked the result and are satisfied, you can accept this version. Source checks remain mandatory.")}</p>
          <button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-50" disabled={accepting} onClick={() => void acceptVersion()}>{accepting ? tr("Registro la scelta…", "Recording the choice…") : tr("Ho verificato: accetta questa versione", "I checked it: accept this version")}</button>
        </div>}
        {acceptError && <p className="text-sm" role="alert">{acceptError}</p>}
      </div>}
      {tab === "design" && <ProjectDesign threadId={threadId} designs={project?.designs ?? []} steps={project?.steps ?? []} roles={project?.roles ?? []} onReview={() => setPanel({threadId,tab:"intervene"})}/>}
      {tab === "team" && <div data-testid="team-plan" className="space-y-3">
        <p className="text-sm">{tr("La squadra si adatta al risultato: può riprendere, cambiare ordine e integrare i file già disponibili.", "The team adapts to the result: it can resume, reorder and build on the files already available.")}</p>
        {(project?.roles ?? []).map(role => {
          const activities = currentSteps.filter(step => step.role_id === role.id);
          const live = jobs.find(job => job.role_id === role.id && !terminalJob(job));
          const usage = project?.orientation?.roles?.[role.id];
          const used = (usage?.attempts ?? jobs.filter(job => job.role_id === role.id).length) > 0;
          const state = live || !!usage?.running ? tr("Al lavoro", "Working") : used && activities.some(step => step.status === "paused") ? tr("In pausa", "Paused") : used ? tr("Ha lavorato al progetto", "Worked on the project") : tr("Previsto", "Planned");
          return <article key={role.id} className="bg-muted/20 space-y-3 rounded-xl border p-4 text-sm" data-testid="compiled-role">
            <div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-base">{role.title}</strong><StatusBadge tone={live || usage?.running ? "active" : state === "In pausa" ? "attention" : "neutral"}>{state}</StatusBadge></div>
            <p>{role.mission}</p>
            {role.experience && <p>{role.experience.count} {tr("lezioni generali pertinenti incluse nella skill compilata.", "relevant general lessons included in the compiled skill.")}</p>}
            <h4 className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">{tr("Competenze assegnate", "Assigned skills")}</h4>
            <ul className="list-inside list-disc">{role.expertise.map((skill, i) => <li key={i}>{skill}</li>)}</ul>
            {!!role.skill_bindings?.length && <div className="space-y-2" data-testid="role-method-skills"><p className="text-muted-foreground text-xs font-semibold">{tr("Skill riutilizzate", "Reused skills")}</p><ul>{role.skill_bindings.map(binding=><li key={binding.name}>{binding.name.replace(/^skill-/, "")}</li>)}</ul></div>}
            <div className="space-y-2"><p className="text-muted-foreground text-xs font-semibold">{tr("Strumenti assegnati", "Assigned tools")}</p><div className="flex flex-wrap gap-1.5">{role.tools.length ? role.tools.map(tool => <StatusBadge key={tool}>{person(tool)}</StatusBadge>) : <span>{tr("Strumenti di base del progetto", "Project's basic tools")}</span>}</div></div>
            {role.capability_rationale&&<details data-testid="role-capability-choice"><summary className="cursor-pointer">{tr("Perché questi strumenti", "Why these tools")}</summary><p className="mt-2">{role.capability_rationale}</p></details>}
            {live && <p><strong>{tr("Adesso:", "Now:")}</strong> {live.work_summary || live.summary}</p>}
            <ul className="space-y-1">{activities.map(step => <li key={step.id}><StatusBadge tone={stepTone(step.status)}>{stepLabels[step.status] ?? step.status}</StatusBadge> {step.goal}</li>)}</ul>
            {!activities.length && <p className="text-muted-foreground">{used ? tr("Contributi registrati nelle attività precedenti.", "Contributions recorded in earlier activities.") : tr("Nessun incarico ancora assegnato.", "No assignment yet.")}</p>}
            <details><summary className="cursor-pointer">{tr("Metodo e verifiche previste", "Method and planned checks")}</summary>
              {!!role.procedure?.length && <ol className="mt-2 list-inside list-decimal">{role.procedure.map((item, i) => <li key={i}>{item}</li>)}</ol>}
              <ul className="mt-2 list-inside list-disc">{role.checks.map((check, i) => <li key={i}>{check}</li>)}</ul>
              <p className="text-muted-foreground mt-2 text-xs">{tr("Questi sono controlli da eseguire, non verifiche già superate. Gli strumenti effettivamente invocati sono nell’attività dell’incarico.", "These are checks to run, not checks already passed. The tools actually invoked are in the assignment's activity.")}</p>
            </details>
            <details className="text-xs"><summary className="cursor-pointer">{tr("Dettagli tecnici delle istruzioni", "Technical details of the instructions")}</summary>
              <p>{tr("I codici identificano il contenuto delle istruzioni. Non indicano il livello di competenza né una versione progressiva.", "The codes identify the content of the instructions. They do not indicate skill level or a sequential version.")}</p>
              <p className="break-all">{tr("Impronta del ruolo:", "Role fingerprint:")} {role.version}</p>
              {role.skill_bindings?.map(binding=><p className="break-all" key={binding.name}>{binding.name}: {binding.revision}</p>)}
              {!!role.tool_versions && <p>{tr("Versioni dei programmi:", "Program versions:")} {Object.entries(role.tool_versions).map(([name,version])=>`${person(name)} ${version}`).join(", ")}</p>}
            </details>
          </article>;
        })}
        {currentSteps.filter(step => !(project?.roles ?? []).some(role => role.id === step.role_id)).map(step => <article className="rounded border p-3 text-sm" key={step.id}>
          <strong>{step.role_title || person(step.agent)}</strong> · {stepLabels[step.status] ?? step.status}
          <p>{step.goal}</p>{step.note && <p className="text-muted-foreground">{step.note}</p>}
        </article>)}
      </div>}
      {tab === "files" && <div className="space-y-3 text-sm" data-testid="delivery-list">
        <p>{tr("Ogni pacchetto appartiene alla consegna indicata. Estrai tutto lo ZIP e segui le istruzioni di apertura; conserva le risorse accanto al progetto.", "Each package belongs to the delivery shown. Extract the whole ZIP and follow the opening instructions; keep the resources next to the project.")}</p>
        {project?.version_selection && <div className="rounded-lg border p-3" data-testid="version-selection"><strong>{tr("Versioni del progetto", "Project versions")}</strong>{([['approved', tr("Ultima approvata", "Latest approved")], ['candidate', tr("Ultima candidata", "Latest candidate")], ['partial', tr("Ultimo lavoro parziale", "Latest partial work")]] as const).map(([state, label]) => { const delivery = versions.find(d => d.id === project.version_selection?.[state]); return <p key={state}>{label}: {delivery ? versionName(delivery) : tr("Nessuna", "None")}</p>; })}<p className="mt-2 text-xs text-muted-foreground">{tr("I controlli tecnici non equivalgono all’approvazione. Le versioni precedenti restano disponibili.", "Technical checks are not approval. Previous versions remain available.")}</p></div>}
        {!versions.length && supporting.some(d => d.purpose === "preview") && <p>{tr("È disponibile un campione. La consegna del prodotto completo non è ancora registrata.", "A sample is available. Delivery of the complete product is not yet recorded.")}</p>}
        {versions.map(d => <details key={d.id} open={d.current || d.id === project?.version_selection?.candidate || d.execution_status === "running"} className={`rounded-xl border p-4 ${d.current ? "border-blue-500/30 bg-blue-500/5" : "bg-muted/20"}`} data-testid="delivery-group">
          <summary className="cursor-pointer"><strong>{versionName(d)}</strong> · {d.version_state ? versionStates[d.version_state] : d.execution_status === "running" ? tr("In lavorazione", "In progress") : tr("Stato non verificato", "Status not verified")}{d.current && " · visualizzata"}<p className="mt-1 text-sm">{d.title}</p></summary>
          <p className="mt-2 text-xs">{d.role_title || person(d.agent)}{d.at ? ` · ${new Date(d.at).toLocaleString("it-IT")}` : ""}</p>
          {d.execution_status !== "running" && <p className="mt-2"><StatusBadge tone={d.technical_status === "passed" ? "done" : "attention"}>{d.technical_status === "passed" ? tr("Controlli tecnici superati", "Technical checks passed") : d.technical_status === "needs_revision" ? tr("Consegna incompleta: da correggere", "Incomplete delivery: to fix") : tr("Controlli tecnici non confermati", "Technical checks not confirmed")}</StatusBadge></p>}
          {d.recovery?.status === "verified" && <p className="mt-2">{tr("Recuperata dopo", "Recovered after")} {d.recovery.session_error === "provider_quota" ? tr("esaurimento quota", "quota exhaustion") : tr("scadenza del tempo", "timeout")}{tr(", senza nuova generazione. Restano validi solo i controlli registrati.", ", without new generation. Only the recorded checks remain valid.")}</p>}
          {d.issues.map((issue, i) => <p className="mt-1 text-sm" key={i}>{issue}</p>)}
          {!!d.finalization_pending?.length && <p className="mt-2 text-muted-foreground">{tr("Prova disponibile. Prima della consegna finale:", "Trial available. Before final delivery:")} {d.finalization_pending.join("; ")}</p>}
          {d.execution_status === "running" && <p className="mt-2">{tr("I file in preparazione non sostituiscono ancora la versione selezionata.", "Files being prepared do not replace the selected version yet.")}</p>}
          <DeliveryContents delivery={d} results={results} threadId={threadId} revision={project?.updated_at} />
          {deliveries.filter(review => review.review?.target_delivery_id === d.id).map(review => <ReviewCard key={review.id} delivery={review} threadId={threadId} />)}

        </details>)}
        {supporting.length > 0 && <details open={!versions.length} className="rounded-xl border p-3" data-testid="supporting-deliveries">
          <summary className="cursor-pointer font-medium">{tr("Campioni, contributi e verifiche (", "Samples, contributions and checks (")}{supporting.length})</summary>
          <p className="my-2 text-xs text-muted-foreground">{tr("Sono lavorazioni della squadra, non nuove versioni del prodotto completo.", "These are team work steps, not new versions of the complete product.")}</p>
          {supporting.map(d => <details key={d.id} className="my-2 rounded-lg border p-3" data-testid="delivery-group"><summary className="cursor-pointer">{d.purpose === "review" ? tr("Verifica", "Check") : d.purpose === "preview" ? tr("Campione", "Sample") : tr("Contributo", "Contribution")} · {d.title}</summary>
            {!!d.finalization_pending?.length && <p className="mt-2 text-muted-foreground">{tr("Prima della consegna finale:", "Before final delivery:")} {d.finalization_pending.join("; ")}</p>}
            {d.review && <ReviewCard delivery={d} threadId={threadId} />}
            <DeliveryContents delivery={d} results={results} threadId={threadId} revision={project?.updated_at} />
          </details>)}
        </details>}
        {!deliveries.length && <ul className="space-y-3">{results.map((r) => <DeliveryFile key={r.path} file={r} threadId={threadId} />)}</ul>}
        {!results.length && <p>{tr("I file appariranno qui quando saranno disponibili.", "Files will appear here when they are available.")}</p>}
      </div>}
      {tab === "experience" && <ExperiencePanel key={threadId} threadId={threadId} deliveries={deliveries} productionBusy={active || working || pending} onReadingChange={setReadingLesson} />}
      {tab === "audit" && <ConversationAudit key={threadId} threadId={threadId} />}
      {tab === "team" && recent.length > 0 && <div className="mt-6 space-y-3 border-t pt-4" data-testid="team-activity"><h4 className="font-semibold">{tr("Attività in corso e recenti", "Current and recent activities")}</h4>{recent.map((job) => <JobCard key={job.job_id} job={job} now={now} threadId={threadId} role={job.role_version ? project?.roles?.find(role=>role.id===job.role_id && role.version===job.role_version) : undefined} />)}</div>}
      </div>
      {tab !== "experience" && <footer className="shrink-0 space-y-2 border-t bg-background p-3">
        {controlNotice && <p className="text-sm" role="status">{controlNotice}</p>}
        <div className="flex flex-wrap gap-2 text-sm">
          {tab === "intervene" ? <button type="submit" form="harness-direction-form" className="bg-foreground text-background rounded-lg px-3 py-2 disabled:opacity-50" disabled={controlBusy || !onContinue || !onPause}>{controlBusy ? tr("Attendi…", "Please wait…") : tr("Applica e riprendi", "Apply and resume")}</button>
            : <button type="button" className={tabStyle} onClick={() => setPanel({ threadId, tab: "intervene" })}>{tr("Intervieni", "Step in")}</button>}
          {(active || working) && onPause && <button type="button" className={tabStyle} disabled={controlBusy} onClick={() => void pauseWork()}>{tr("Metti in pausa", "Pause")}</button>}
        </div>
      </footer>}
      </div>
    </dialog>}
    {guided.journey && <JourneyStrip threadId={threadId} state={guided} busyTeam={active || working} onContinue={onContinue} onOpen={() => toggle("journey")}/>}
    <div className="space-y-1 p-3" role="status" aria-live="polite" aria-atomic="true">
      {project && <div className="mb-2 space-y-1 border-b pb-2" data-testid="project-identity">
        <p className="line-clamp-1 text-sm font-semibold tracking-tight">{project.outcome?.title || project.outcome?.result || tr("Il tuo progetto", "Your project")}</p>
        {selectedDelivery?.version && <p className="text-xs">{versionName(selectedDelivery)}{editing && editing.id !== selectedDelivery.id ? tr(` · ${versionName(editing)} in lavorazione`, ` · ${versionName(editing)} in progress`) : ""}</p>}
        <p className="text-muted-foreground line-clamp-1 text-xs">{tr("Consegna:", "Delivery:")} {project.outcome?.format || tr("da definire", "to be defined")}</p>
        {planned.length > 0 && <p className="text-muted-foreground line-clamp-2 text-xs">{completed} {tr("di", "of")} {planned.length} {tr("incarichi conclusi", "assignments completed")}</p>}
        <GovernanceStrip governance={governance}/>
      </div>}
      <div className="flex items-center justify-between gap-2"><strong className="text-sm" data-testid="harness-status"><span aria-hidden="true" className={`mr-2 inline-block h-2 w-2 rounded-full ${working ? "bg-blue-500" : ready ? "bg-emerald-500" : attention || clarifying || coordinatorError ? "bg-amber-500" : "bg-muted-foreground"}`} />{title}</strong>
        {current && <span className="text-muted-foreground shrink-0 text-xs">{duration(secondsSince(current.started_at || current.created_at, now))}</span>}
      </div>
      {summary && !paused && <p className="line-clamp-2 text-sm" data-testid="harness-summary">{summary}</p>}
      {health && <p className="text-muted-foreground line-clamp-1 text-xs" data-testid="harness-health">{health}</p>}
      {!paused && !working && !clarifying && project?.next_action && !attention && <p className="text-muted-foreground line-clamp-2 text-xs">{tr("Prossimo passo:", "Next step:")} {project.next_action}</p>}
      {waitingForReview && !active && <p className="text-xs">{tr("Guarda il risultato e indica nella chat cosa vuoi correggere. Una verifica non disponibile non richiede di rigenerare tutto.", "Look at the result and say in the chat what you want to fix. An unavailable check does not require regenerating everything.")}</p>}
      {(attention || coordinatorError) && !active && !working && <p className="text-xs">{attention?.action ?? tr("Verifica il servizio AI e riprendi il lavoro dai risultati disponibili.", "Check the AI service and resume work from the available results.")}
        {(!attention || attention.code.startsWith("provider_")) && <> <a className="underline" href="/workspace/harness">{tr("Apri La tua squadra", "Open Your team")}</a></>}</p>}
      {clarifying && !working && <p className="text-xs">{tr("Rispondi nella chat: la produzione attende le scelte sul risultato.", "Reply in the chat: production waits for the choices about the result.")}</p>}
      {unavailable && <p className="text-xs" role="alert">{tr("Aggiornamenti non disponibili: questo stato potrebbe non essere attuale. Riprovo automaticamente.", "Updates unavailable: this status may be out of date. Retrying automatically.")}</p>}
      {controlNotice && <p className="text-xs" role="status">{controlNotice}</p>}
      {resumeError && <p className="text-xs" role="alert">{resumeError}</p>}
    </div>
    <nav className="flex flex-wrap items-center gap-2 border-t p-3 text-sm" aria-label={tr("Controlli del progetto", "Project checks")}>
      <button type="button" className="bg-foreground text-background rounded-lg px-3 py-2 disabled:opacity-50" disabled={!preview} onClick={() => toggle("preview")}>{ready ? tr("Apri consegna", "Open delivery") : showLatestResult ? (previewDelivery?.purpose === "preview" ? tr("Apri ultimo campione", "Open latest sample") : tr("Apri ultimo risultato", "Open latest result")) : tr("Apri risultato", "Open result")}</button>
      {preview&&<a className="rounded-lg border px-3 py-2 text-sm underline break-all" href={artifactURL(threadId,preview.path,true)} download>{tr("Scarica", "Download")} {preview.label}</a>}
      <button type="button" className={tabStyle} onClick={() => toggle("intervene")}>{tr("Intervieni", "Step in")}</button>
      {(active || working) && <button type="button" className={tabStyle} disabled={controlBusy||deliveryRequested} onClick={()=>void deliverNow()}>{deliveryRequested?tr("Consegna richiesta…", "Delivery requested…"):tr("Consegna ora", "Deliver now")}</button>}
      {(active || working) && onPause && <button type="button" className={tabStyle} disabled={controlBusy} onClick={() => void pauseWork()}>{controlBusy ? tr("Attendi…", "Please wait…") : tr("Metti in pausa", "Pause")}</button>}
      {!active && !working && (deliveryRequested || (!ready && !waitingForReview && !questions.length)) && onContinue && <button type="button" className={tabStyle} disabled={controlBusy || resumeRequested === threadId} onClick={() => void resume()}>{resumeRequested === threadId ? tr("Ripresa richiesta…", "Resume requested…") : tr("Riprendi lavoro", "Resume work")}</button>}
      <button type="button" className={`${tabStyle} ml-auto`} onClick={() => toggle("project")}>{tr("Dettagli progetto", "Project details")}</button>
    </nav>

  </section>;
}

function DeliveryContents({delivery,results,threadId,revision}:{delivery:Delivery;results:Result[];threadId:string;revision?:string}) {useUiLanguage();
  const files=results.filter(f=>f.delivery_id===delivery.id);
  const groups=[{label:tr("Risultati da aprire", "Results to open"),roles:["export"]},{label:tr("Sorgenti da modificare", "Sources to edit"),roles:["source_archive","editable_source"]},{label:tr("Rapporti e istruzioni", "Reports and instructions"),roles:["report"]}];
  const known=groups.flatMap(g=>g.roles);
  return <div className="mt-3 space-y-4" data-testid="delivery-contents">
    {files.length>0 && delivery.purpose!=="review" && <ProjectGuide threadId={threadId} deliveryId={delivery.id} revision={revision}/>}
    {groups.map(group=>{const selected=files.filter(f=>group.roles.includes(f.role??""));return selected.length>0 && <section key={group.label}><h4 className="mb-2 font-semibold">{group.label}</h4><ul className="space-y-3">{selected.sort((a,b)=>Number(b.role==="source_archive")-Number(a.role==="source_archive")).map(f=><DeliveryFile key={f.path} file={f} threadId={threadId}/>)}</ul></section>})}
    {files.some(f=>!known.includes(f.role??"")) && <details><summary className="cursor-pointer">{tr("Risorse collegate e altri file", "Linked resources and other files")}</summary><ul className="mt-2 space-y-3">{files.filter(f=>!known.includes(f.role??"")).map(f=><DeliveryFile key={f.path} file={f} threadId={threadId}/>)}</ul></details>}
  </div>;
}

function DeliveryFile({ file, threadId }: { file: Result; threadId: string }) {useUiLanguage();
  return <li className="border-l-2 border-border pl-3"><span className="text-muted-foreground text-xs font-medium">{roles[file.role ?? "file"] ?? "File"}: </span><a className="break-all underline" href={artifactURL(threadId, file.path, true)}>{file.label}</a>
    {file.open_with && <p className="mt-1">{tr("Come aprire:", "How to open:")} {file.open_with}</p>}
    {file.editability && <p className="text-muted-foreground">{tr("Modificabile:", "Editable:")} {file.editability}</p>}
    {file.limitations?.map((limit, i) => <p className="text-muted-foreground" key={i}>{limit}</p>)}
  </li>;
}

function ReviewCard({ delivery, threadId }: { delivery: Delivery; threadId: string }) {useUiLanguage();
  const review = delivery.review;
  if (!review) return null;
  const target = review.target_version ? tr(`versione ${review.target_version}`, `version ${review.target_version}`) : review.target_label;
  const status = !review.validated ? tr("Verifica non convalidata", "Check not validated") : !review.matches_current_brief ? tr("Da aggiornare al brief attuale", "To update to the current brief") : review.status === "passed" ? tr("Revisione superata", "Review passed") : review.status === "needs_revision" ? tr("Correzioni richieste", "Fixes requested") : tr("Verifiche ancora incomplete", "Checks still incomplete");
  return <section className="mt-3 space-y-2 rounded-lg border p-3 text-sm" data-testid="version-review">
    <p className="font-medium">{status} · {target}</p>
    {review.correction_count > 0 && <p>{review.correction_count} {tr("correzioni indicate nel rapporto.", "fixes listed in the report.")}</p>}
    <p className="text-xs text-muted-foreground">{tr("Questo controllo riguarda il file indicato, non le versioni successive.", "This check covers the file shown, not later versions.")}</p>
    {artifactURL(threadId, review.report_path) && <a className="underline" href={artifactURL(threadId, review.report_path)} target="_blank" rel="noreferrer">{tr("Apri rapporto della verifica", "Open check report")}</a>}
  </section>;
}
