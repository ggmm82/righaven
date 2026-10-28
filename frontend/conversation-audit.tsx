"use client";
import { useEffect, useRef, useState } from "react";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
export type OperationContext = { command_preview?: string; command_path?: string; command_sha256?: string; changed_files?: string[]; record_path?: string; tool?: string; action?: string; duration_seconds?: number; exit_code?: number; diagnostic?: string; files?: string[]; started_at?: string; finished_at?: string; id?: string };
type Event = { context?: OperationContext; seq: number; at: string; actor: string; operation: string; status: string; detail: string; correlation: string };
const labels: Record<string,string> = { progress: "Aggiornamento", received: "Ricevuto", started: "Avviata", completed: "Conclusa", failed: "Errore", interrupted: "Interrotta" };
function CommandDetails({ value, threadId }: { value: OperationContext; threadId: string }) {
  const [open, setOpen] = useState(false), [content, setContent] = useState<string>(), [error, setError] = useState(false);
  const url = value.command_path ? `${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-job-file?path=${encodeURIComponent(value.command_path)}` : undefined;
  useEffect(() => {
    if (!open || !url) return;
    setError(false); setContent(undefined);
    const controller = new AbortController();
    void fetch(url, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("Comando non disponibile");
      const data = await response.text();
      if (!value.command_sha256 || data.length > 50000) throw new Error("Comando senza impronta verificabile");
      const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(data));
      const actual = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
      if (actual !== value.command_sha256) throw new Error("Il testo del comando è stato modificato");
      if (!controller.signal.aborted) setContent(data.slice(0, 50000));
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [open, url, value.command_sha256]);
  if (!value.command_preview && !url) return null;
  return <div className="space-y-1" data-testid="operation-command"><dt className="font-medium">Comando lanciato</dt><dd><pre className="max-h-36 overflow-auto whitespace-pre-wrap break-all rounded bg-muted/40 p-2">{value.command_preview}</pre>
    {value.command_sha256 && <p className="text-muted-foreground">Identificativo del comando: {value.command_sha256.slice(0, 12)}</p>}
    {url && <details onToggle={event => setOpen(event.currentTarget.open)}><summary className="cursor-pointer underline">Apri comando completo / script inline</summary>{open && <div className="space-y-2">{error ? <p>Testo non disponibile; resta l’estratto registrato.</p> : <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all rounded border p-2">{content ?? "Caricamento…"}</pre>}{!error && <a className="underline" href={url} download>Scarica testo del comando</a>}</div>}</details>}
    <p className="text-muted-foreground">Valori riservati oscurati. Il testo serve a ispezionare l’operazione; controllalo prima di riutilizzarlo.</p></dd></div>;
}
export function OperationDetails({ value, threadId }: { value?: OperationContext; threadId?: string }) {
  if (!value || !value.tool) return null;
  return <details className="mt-1 text-xs" data-testid="operation-details"><summary className="cursor-pointer text-muted-foreground">Dettagli operazione</summary>
    <dl className="mt-2 space-y-1 rounded border p-2"><div><dt className="inline font-medium">Strumento: </dt><dd className="inline">{value.tool} · {value.action}</dd></div>
      {threadId && <CommandDetails key={`${threadId}:${value.command_path ?? value.command_sha256 ?? value.id}`} value={value} threadId={threadId}/>}
      {value.duration_seconds !== undefined && <div><dt className="inline font-medium">Durata: </dt><dd className="inline">{value.duration_seconds.toFixed(2)} s</dd></div>}
      <div><dt className="inline font-medium">Codice d’uscita: </dt><dd className="inline">{value.exit_code ?? "Non comunicato dallo strumento"}</dd></div>
      {value.diagnostic && <div><dt className="inline font-medium">Diagnostica: </dt><dd className="inline">{value.diagnostic}</dd></div>}
      {!!value.files?.length && <div><dt className="font-medium">File indicati nel comando</dt><dd><ul>{value.files.map(file=><li className="break-all" key={file}>{file}</li>)}</ul></dd></div>}
      {!!value.changed_files?.length && <div><dt className="font-medium">File cambiati durante l’operazione</dt><dd><ul>{value.changed_files.map(file=><li className="break-all" key={file}>{file}</li>)}</ul></dd></div>}
      {value.record_path && <div><dt className="font-medium">Prova tecnica registrata</dt><dd className="break-all"><code>{value.record_path}</code></dd></div>}
      <div className="text-muted-foreground">I dettagli dei comandi precedenti all’aggiornamento possono essere incompleti.</div>
    </dl></details>;
}
export function ConversationAudit({ threadId }: { threadId: string }) {
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
        if (!response.ok) throw new Error("Registro non disponibile. Riprovo automaticamente.");
        const value=await response.json();
        if(stopped||generation.current!==owner)return;
        if(!latest.current)setBefore(value.next_before);
        setEvents(previous=>Array.from(new Map<number,Event>([...previous,...value.events].map((event:Event)=>[event.seq,event])).values()).sort((a,b)=>a.seq-b.seq));
        if(value.events.length)latest.current=value.events[value.events.length-1].seq;
        setError("");
      } catch(reason) {if(!stopped)setError(reason instanceof Error?reason.message:"Registro non disponibile");}
    }
    void refresh();const timer=setInterval(()=>void refresh(),3000);
    return ()=>{stopped=true;clearInterval(timer);};
  },[base,threadId]);
  async function older() {
    if(before===null)return;setLoading(true);const owner=generation.current;
    try {
      const response=await fetch(`${base}?before=${before}`);if(!response.ok)throw new Error("Eventi precedenti non disponibili.");
      const value=await response.json();if(generation.current!==owner)return;
      setEvents(previous=>Array.from(new Map<number,Event>([...value.events,...previous].map((event:Event)=>[event.seq,event])).values()).sort((a,b)=>a.seq-b.seq));setBefore(value.next_before);
    }catch(reason){if(generation.current===owner)setError(String(reason));}finally{setLoading(false);}
  }
  const visible=events.filter(event=>!onlyErrors||["failed","interrupted"].includes(event.status));
  return <section className="space-y-3" data-testid="conversation-audit">
    <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold">Registro della conversazione</h4>
      <a className="rounded border px-3 py-2 text-sm" href={`${base}?export=true`} download>Scarica CSV</a></div>
    <p className="text-muted-foreground text-xs">Coordinatore, strumenti e sandbox. Orari locali; CSV in UTC.</p>
    <details className="text-xs text-muted-foreground"><summary className="cursor-pointer">Copertura del registro</summary>Registrazione disponibile dall’aggiornamento. I passaggi precedenti non vengono ricostruiti con orari ipotizzati. I dettagli dei comandi sono disponibili per le nuove operazioni registrate da questa versione.</details>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={onlyErrors} onChange={event=>setOnlyErrors(event.target.checked)}/>Solo errori e interruzioni</label>
    {error&&<p role="alert" className="text-sm">{error}</p>}
    {before!==null&&<button type="button" className="rounded border px-3 py-2 text-sm" disabled={loading} onClick={()=>void older()}>{loading?"Carico…":"Carica eventi precedenti"}</button>}
    <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr>{["Quando","Attore","Operazione","Esito"].map(title=><th className="border-b p-2" key={title}>{title}</th>)}</tr></thead><tbody>
      {visible.map(event=><tr key={event.seq} className={event.status==="failed"?"bg-amber-500/10":""}><td className="whitespace-nowrap border-b p-2"><time dateTime={event.at}>{new Date(event.at).toLocaleString()}</time></td><td className="border-b p-2">{event.actor}</td><td className="border-b p-2">{event.operation}<OperationDetails value={event.context} threadId={threadId}/>{event.detail&&<p className="mt-1 text-muted-foreground">{event.detail}</p>}{event.correlation&&<details className="mt-1"><summary className="cursor-pointer text-muted-foreground">Riferimento</summary><code className="break-all">{event.correlation}</code></details>}</td><td className="whitespace-nowrap border-b p-2">{labels[event.status]||event.status}</td></tr>)}
    </tbody></table></div>
    {!visible.length&&<p className="text-sm">{onlyErrors?"Nessun errore negli eventi caricati.":"Nessun evento registrato: compariranno qui alla prossima attività."}</p>}
  </section>;
}
