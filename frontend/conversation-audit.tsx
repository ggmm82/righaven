"use client";
import { useEffect, useRef, useState } from "react";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import {tr, useUiLanguage, trMap} from "@/core/i18n/ui-text";
export type OperationContext = { command_preview?: string; command_path?: string; command_sha256?: string; changed_files?: string[]; record_path?: string; tool?: string; action?: string; duration_seconds?: number; exit_code?: number; diagnostic?: string; files?: string[]; started_at?: string; finished_at?: string; id?: string };
type Event = { context?: OperationContext; seq: number; at: string; actor: string; operation: string; status: string; detail: string; correlation: string };
const labels: Record<string,string> = trMap({ progress: ["Aggiornamento", "Update"], received: ["Ricevuto", "Received"], started: ["Avviata", "Started"], completed: ["Conclusa", "Completed"], failed: ["Errore", "Error"], interrupted: ["Interrotta", "Interrupted"] });
function CommandDetails({ value, threadId }: { value: OperationContext; threadId: string }) {useUiLanguage();
  const [open, setOpen] = useState(false), [content, setContent] = useState<string>(), [error, setError] = useState(false);
  const url = value.command_path ? `${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-job-file?path=${encodeURIComponent(value.command_path)}` : undefined;
  useEffect(() => {
    if (!open || !url) return;
    setError(false); setContent(undefined);
    const controller = new AbortController();
    void fetch(url, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error(tr("Comando non disponibile", "Command unavailable"));
      const data = await response.text();
      if (!value.command_sha256 || data.length > 50000) throw new Error(tr("Comando senza impronta verificabile", "Command without a verifiable fingerprint"));
      const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(data));
      const actual = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
      if (actual !== value.command_sha256) throw new Error(tr("Il testo del comando è stato modificato", "The command text was changed"));
      if (!controller.signal.aborted) setContent(data.slice(0, 50000));
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [open, url, value.command_sha256]);
  if (!value.command_preview && !url) return null;
  return <div className="space-y-1" data-testid="operation-command"><dt className="font-medium">{tr("Comando lanciato", "Command run")}</dt><dd><pre className="max-h-36 overflow-auto whitespace-pre-wrap break-all rounded bg-muted/40 p-2">{value.command_preview}</pre>
    {value.command_sha256 && <p className="text-muted-foreground">{tr("Identificativo del comando:", "Command identifier:")} {value.command_sha256.slice(0, 12)}</p>}
    {url && <details onToggle={event => setOpen(event.currentTarget.open)}><summary className="cursor-pointer underline">{tr("Apri comando completo / script inline", "Open full command / inline script")}</summary>{open && <div className="space-y-2">{error ? <p>{tr("Testo non disponibile; resta l’estratto registrato.", "Text unavailable; the recorded excerpt remains.")}</p> : <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all rounded border p-2">{content ?? tr("Caricamento…", "Loading…")}</pre>}{!error && <a className="underline" href={url} download>{tr("Scarica testo del comando", "Download command text")}</a>}</div>}</details>}
    <p className="text-muted-foreground">{tr("Valori riservati oscurati. Il testo serve a ispezionare l’operazione; controllalo prima di riutilizzarlo.", "Confidential values redacted. The text is for inspecting the operation; check it before reusing it.")}</p></dd></div>;
}
export function OperationDetails({ value, threadId }: { value?: OperationContext; threadId?: string }) {useUiLanguage();
  if (!value || !value.tool) return null;
  return <details className="mt-1 text-xs" data-testid="operation-details"><summary className="cursor-pointer text-muted-foreground">{tr("Dettagli operazione", "Operation details")}</summary>
    <dl className="mt-2 space-y-1 rounded border p-2"><div><dt className="inline font-medium">{tr("Strumento:", "Tool:")} </dt><dd className="inline">{value.tool} · {value.action}</dd></div>
      {threadId && <CommandDetails key={`${threadId}:${value.command_path ?? value.command_sha256 ?? value.id}`} value={value} threadId={threadId}/>}
      {value.duration_seconds !== undefined && <div><dt className="inline font-medium">{tr("Durata:", "Duration:")} </dt><dd className="inline">{value.duration_seconds.toFixed(2)} s</dd></div>}
      <div><dt className="inline font-medium">{tr("Codice d’uscita:", "Exit code:")} </dt><dd className="inline">{value.exit_code ?? tr("Non comunicato dallo strumento", "Not reported by the tool")}</dd></div>
      {value.diagnostic && <div><dt className="inline font-medium">{tr("Diagnostica:", "Diagnostics:")} </dt><dd className="inline">{value.diagnostic}</dd></div>}
      {!!value.files?.length && <div><dt className="font-medium">{tr("File indicati nel comando", "Files named in the command")}</dt><dd><ul>{value.files.map(file=><li className="break-all" key={file}>{file}</li>)}</ul></dd></div>}
      {!!value.changed_files?.length && <div><dt className="font-medium">{tr("File cambiati durante l’operazione", "Files changed during the operation")}</dt><dd><ul>{value.changed_files.map(file=><li className="break-all" key={file}>{file}</li>)}</ul></dd></div>}
      {value.record_path && <div><dt className="font-medium">{tr("Prova tecnica registrata", "Technical evidence recorded")}</dt><dd className="break-all"><code>{value.record_path}</code></dd></div>}
      <div className="text-muted-foreground">{tr("I dettagli dei comandi precedenti all’aggiornamento possono essere incompleti.", "Details of commands from before the update may be incomplete.")}</div>
    </dl></details>;
}
export function ConversationAudit({ threadId }: { threadId: string }) {useUiLanguage();
  const [events,setEvents]=useState<Event[]>([]), [before,setBefore]=useState<number|null>(null);
  const [error,setError]=useState(""), [onlyErrors,setOnlyErrors]=useState(false), [loading,setLoading]=useState(false);
  const latest=useRef(0), generation=useRef(0);
  const base=`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-audit`;
  useEffect(()=>{
    const owner=++generation.current; let stopped=false;
    latest.current=0;setEvents([]);setBefore(null);setError("");
    async function refresh() {
      try {
        const response=await fetch(base+(latest.current?`?after=${latest.current}`:""));
        if (!response.ok) throw new Error(tr("Registro non disponibile. Riprovo automaticamente.", "Log unavailable. Retrying automatically."));
        const value=await response.json();
        if(stopped||generation.current!==owner)return;
        if(!latest.current)setBefore(value.next_before);
        setEvents(previous=>Array.from(new Map<number,Event>([...previous,...value.events].map((event:Event)=>[event.seq,event])).values()).sort((a,b)=>a.seq-b.seq));
        if(value.events.length)latest.current=value.events[value.events.length-1].seq;
        setError("");
      } catch(reason) {if(!stopped)setError(reason instanceof Error?reason.message:tr("Registro non disponibile", "Log unavailable"));}
    }
    void refresh();const timer=setInterval(()=>void refresh(),3000);
    return ()=>{stopped=true;clearInterval(timer);};
  },[base,threadId]);
  async function older() {
    if(before===null)return;setLoading(true);const owner=generation.current;
    try {
      const response=await fetch(`${base}?before=${before}`);if(!response.ok)throw new Error(tr("Eventi precedenti non disponibili.", "Earlier events unavailable."));
      const value=await response.json();if(generation.current!==owner)return;
      setEvents(previous=>Array.from(new Map<number,Event>([...value.events,...previous].map((event:Event)=>[event.seq,event])).values()).sort((a,b)=>a.seq-b.seq));setBefore(value.next_before);
    }catch(reason){if(generation.current===owner)setError(String(reason));}finally{setLoading(false);}
  }
  const visible=events.filter(event=>!onlyErrors||["failed","interrupted"].includes(event.status));
  return <section className="space-y-3" data-testid="conversation-audit">
    <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold">{tr("Registro della conversazione", "Conversation log")}</h4>
      <a className="rounded border px-3 py-2 text-sm" href={`${base}?export=true`} download>{tr("Scarica CSV", "Download CSV")}</a></div>
    <p className="text-muted-foreground text-xs">{tr("Coordinatore, strumenti e sandbox. Orari locali; CSV in UTC.", "Coordinator, tools and sandboxes. Local times; CSV in UTC.")}</p>
    <details className="text-xs text-muted-foreground"><summary className="cursor-pointer">{tr("Copertura del registro", "Log coverage")}</summary>{tr("Registrazione disponibile dall’aggiornamento. I passaggi precedenti non vengono ricostruiti con orari ipotizzati. I dettagli dei comandi sono disponibili per le nuove operazioni registrate da questa versione.", "Logging is available since the update. Earlier steps are not reconstructed with guessed times. Command details are available for new operations recorded by this version.")}</details>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={onlyErrors} onChange={event=>setOnlyErrors(event.target.checked)}/>{tr("Solo errori e interruzioni", "Errors and interruptions only")}</label>
    {error&&<p role="alert" className="text-sm">{error}</p>}
    {before!==null&&<button type="button" className="rounded border px-3 py-2 text-sm" disabled={loading} onClick={()=>void older()}>{loading?tr("Carico…", "Loading…"):tr("Carica eventi precedenti", "Load earlier events")}</button>}
    <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr>{[tr("Quando", "When"),tr("Attore", "Actor"),tr("Operazione", "Operation"),tr("Esito", "Outcome")].map(title=><th className="border-b p-2" key={title}>{title}</th>)}</tr></thead><tbody>
      {visible.map(event=><tr key={event.seq} className={event.status==="failed"?"bg-amber-500/10":""}><td className="whitespace-nowrap border-b p-2"><time dateTime={event.at}>{new Date(event.at).toLocaleString()}</time></td><td className="border-b p-2">{event.actor}</td><td className="border-b p-2">{event.operation}<OperationDetails value={event.context} threadId={threadId}/>{event.detail&&<p className="mt-1 text-muted-foreground">{event.detail}</p>}{event.correlation&&<details className="mt-1"><summary className="cursor-pointer text-muted-foreground">{tr("Riferimento", "Reference")}</summary><code className="break-all">{event.correlation}</code></details>}</td><td className="whitespace-nowrap border-b p-2">{labels[event.status]||event.status}</td></tr>)}
    </tbody></table></div>
    {!visible.length&&<p className="text-sm">{onlyErrors?tr("Nessun errore negli eventi caricati.", "No errors in the loaded events."):tr("Nessun evento registrato: compariranno qui alla prossima attività.", "No events recorded: they will appear here with the next activity.")}</p>}
  </section>;
}
