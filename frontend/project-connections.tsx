"use client";

import { useEffect, useRef, useState } from "react";

import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import { tr, useUiLanguage } from "@/core/i18n/ui-text";

type Connection = { id: string; name: string; kind: string; host?: string; database?: string; read_only?: boolean; authentication?: string; tools?: string[]; missing?: boolean; write_enabled?: boolean; write_schema?: string; write?: boolean;use?:string;fulfillment?:string;deferred?:boolean };

const kinds: Record<string, string> = { postgres: "PostgreSQL", sqlserver: "SQL Server", mysql: "MySQL", oracle: "Oracle", entra: "Microsoft Entra ID", device: "IoT", network: "Network" };

/** The connections the user chose for this task; only roles declaring the authorized IDs receive them. */
export function ProjectConnections({ threadId, expanded = false, onAssigned }: { threadId: string; expanded?: boolean; onAssigned?: (ids: string[]) => void }) {
  useUiLanguage();
  const [all, setAll] = useState<Connection[] | null>(null);
  const [assigned, setAssigned] = useState<string[]>([]);
  const [writable, setWritable] = useState<string[]>([]);
  const [postponed,setPostponed]=useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const base = getBackendBaseURL();
  const notify = useRef(onAssigned); notify.current = onAssigned;
  useEffect(() => {
    let live = true;
    void Promise.all([
      fetch(`${base}/api/harness/connections`).then((r) => (r.ok ? r.json() : { connections: [] })),
      fetch(`${base}/api/threads/${encodeURIComponent(threadId)}/harness-connections`).then((r) => (r.ok ? r.json() : { assigned: [] })),
    ]).then(([mine, current]: [{ connections: Connection[] }, { assigned: Connection[] }]) => {
      if (!live) return;
      setAll(mine.connections.map(c=>({...c,...current.assigned.find(a=>a.id===c.id)})));
      setAssigned(current.assigned.map((c) => c.id));
      notify.current?.(current.assigned.map(c => c.id));
      setWritable(current.assigned.filter((c) => c.write).map((c) => c.id));
      setPostponed(current.assigned.filter(c=>c.deferred).map(c=>c.id));
    }).catch(() => { if(live) { setAll([]); setMessage(tr("Impossibile caricare le connessioni. Chiudi e riprova.","Could not load connections. Close and retry.")); } });
    return () => { live = false; };
  }, [base, threadId]);
  async function save(ids: string[], write: string[] = writable.filter((id) => ids.includes(id)),deferred:string[]=postponed.filter(id=>ids.includes(id)&&write.includes(id))) {
    setBusy(true);
    setMessage("");
    try {
    const response = await fetch(`${base}/api/threads/${encodeURIComponent(threadId)}/harness-connections`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids, write,deferred }),
    });
    const value = (await response.json()) as { assigned?: Connection[]; detail?: string };
    setBusy(false);
    if (!response.ok) { setMessage(typeof value.detail === "string" ? value.detail : String(response.status)); return; }
    setAssigned((value.assigned ?? []).map((c) => c.id));
    notify.current?.((value.assigned ?? []).map(c => c.id));
    setWritable((value.assigned ?? []).filter((c) => c.write).map((c) => c.id));
    setPostponed((value.assigned??[]).filter(c=>c.deferred).map(c=>c.id));
    setAll(previous=>previous?.map(c=>{const current=value.assigned?.find(a=>a.id===c.id);return {...c,...current,fulfillment:current?.fulfillment,deferred:current?.deferred};})??null);
    setMessage(tr("Salvato: il coordinatore vedrà queste connessioni dal prossimo turno.", "Saved: the coordinator will see these connections from its next turn."));
    } catch(e) { setMessage(e instanceof Error?e.message:String(e)); } finally { setBusy(false); }
  }
  if (all === null) return null;
  return <details open={expanded || undefined} className="rounded-xl border p-3 text-sm" data-testid="project-connections">
    <summary className="cursor-pointer font-medium">{tr("Connessioni del lavoro", "Task connections")} ({assigned.length})</summary>
    <p className="text-muted-foreground my-2 text-xs">{tr(
      "Scegli i database e gli account Microsoft che questo lavoro può usare: solo i ruoli del lavoro che ne hanno bisogno ricevono le connessioni autorizzate, e le perdono quando finiscono. Le password non sono mai mostrate al coordinatore.",
      "Choose the databases and Microsoft accounts this task may use: only roles declaring these authorized connection IDs receive them, and lose them when they end. Passwords are never shown to the coordinator.")}</p>
    {all.length === 0 && <p className="text-xs">{tr("Nessuna connessione necessaria per documenti e dati sintetici. Se serve un accesso esterno, puoi aggiungerlo in ", "No connection is needed for documents and synthetic data. For external access, add one in ")}<a className="underline" href="/workspace/connections">{tr("Connessioni", "Connections")}</a>.</p>}
    <ul className="space-y-1">{all.map((c) => <li key={c.id}><label className="flex items-start gap-2">
      <input type="checkbox" disabled={busy} checked={assigned.includes(c.id)} onChange={(event) => void save(event.target.checked ? [...assigned, c.id] : assigned.filter((id) => id !== c.id))}/>
      <span><strong>{c.name}</strong> · {kinds[c.kind] ?? c.kind}{c.database ? " · " + c.database : ""}{c.kind !== "entra" && c.kind !== "device" && c.kind !== "network" && !c.read_only && !c.write_enabled && <span className="text-destructive"> · {tr("non dichiarata in sola lettura: gli strumenti la rifiuteranno", "not declared read-only: tools will refuse it")}</span>}</span>
    </label>
    {c.write_enabled && assigned.includes(c.id) && <label className="ml-6 mt-1 flex items-start gap-2 text-xs" data-testid={"write-consent-" + c.id}>
      <input type="checkbox" disabled={busy} checked={writable.includes(c.id)} onChange={(event) => void save(assigned, event.target.checked ? [...writable, c.id] : writable.filter((id) => id !== c.id))}/>
      <span>{c.kind === "network" ? tr("Consenti la ricerca di vulnerabilità su queste reti in questo incarico. Ogni scansione (obiettivi e profilo) ti verrà comunque chiesta qui sotto. Senza consenso solo mappatura.", "Allow vulnerability checks on these networks in this task. Each scan (targets and profile) is still asked to you below. Without consent, mapping only.")
        : c.kind === "device" ? tr("Consenti scritture su questo dispositivo in questo incarico. Ogni singola scrittura (comando, firmware, app, riavvio) ti verrà comunque chiesta qui sotto prima di essere eseguita. Senza consenso il dispositivo resta in sola lettura.", "Allow writes to this device in this task. Each single write (command, firmware, app, reboot) is still asked to you below before it runs. Without consent the device stays read-only.")
        : tr(`Consenti scrittura in questo incarico (solo tabelle verificate, nello schema ${c.write_schema ?? ""}). Ogni consegna dell’accesso resta nel registro.`, `Allow writing in this task (verified tables only, in schema ${c.write_schema ?? ""}). Every delivery of this access is logged.`)}</span>
    </label>}{c.use==="destination"&&assigned.includes(c.id)&&<div className="ml-6 mt-2 space-y-1 text-xs"><p role="status">{tr("Destinazione richiesta:","Requested destination:")} {c.fulfillment==="passed"?tr("scrittura e rilettura verificate","write and read-back verified"):c.fulfillment==="deferred"?tr("rimandata da te; consegna locale","deferred by you; local delivery"):tr("scrittura ancora da eseguire o verificare; il risultato locale è parziale","write pending or not yet verified; the local result is partial")}</p>{writable.includes(c.id)&&<label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={postponed.includes(c.id)} onChange={e=>void save(assigned,writable,e.target.checked?[...postponed,c.id]:postponed.filter(id=>id!==c.id))}/><span>{tr("Rimanda la scrittura: per ora accetto il risultato locale. Il coordinatore non può scegliere questa opzione al mio posto.","Defer writing: I accept the local result for now. The coordinator cannot choose this on my behalf.")}</span></label>}</div>}</li>)}</ul>
    {message && <p className="mt-2 text-xs">{message}</p>}
    <DeviceChanges threadId={threadId}/>
  </details>;
}

type DeviceChange = { id: string; connection: string; device: string; action: string; status: string; note?: string; file?: string; sha256?: string; size?: number; package?: string; mode?: string; command?: Record<string, unknown>; requested_at: string };

const ACTIONS: Record<string, [string, string]> = {
  send: ["Invia un comando", "Send a command"], flash: ["Carica un firmware", "Flash firmware"], sideload: ["Aggiorna il sistema (OTA)", "System update (OTA)"],
  install: ["Installa o aggiorna un’app", "Install or update an app"], uninstall: ["Rimuovi un’app", "Remove an app"], disable: ["Disattiva un’app", "Disable an app"],
  enable: ["Riattiva un’app", "Enable an app"], reboot: ["Riavvia", "Reboot"], clear_codes: ["Cancella i codici di errore del veicolo", "Clear vehicle trouble codes"], scan: ["Ricerca di vulnerabilità", "Vulnerability scan"],
};

/** Every write to a device waits here for the owner: approve or reject that exact change. Reading never does. */
function DeviceChanges({ threadId }: { threadId: string }) {
  const [changes, setChanges] = useState<DeviceChange[]>([]);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const url = `${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/device-changes`;
  useEffect(() => {
    let live = true;
    void fetch(url).then((r) => (r.ok ? r.json() : { changes: [] })).then((v: { changes: DeviceChange[] }) => { if (live) setChanges(v.changes); }).catch(() => undefined);
    const timer = setInterval(() => setReload((n) => n + 1), 15000);
    return () => { live = false; clearInterval(timer); };
  }, [url, reload]);
  async function decide(id: string, decision: "approve" | "reject") {
    setError("");
    const r = await fetch(`${url}/${id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision }) });
    const v = (await r.json()) as { detail?: string };
    if (!r.ok) setError(typeof v.detail === "string" ? v.detail : String(r.status));
    setReload((n) => n + 1);
  }
  const pending = changes.filter((c) => c.status === "pending");
  const recent = changes.filter((c) => c.status !== "pending").slice(0, 5);
  if (!changes.length) return null;
  return <section className="mt-3 space-y-2 border-t pt-2 text-xs" data-testid="device-changes">
    <p className="font-medium">{tr("Operazioni su dispositivi e reti da approvare", "Device and network operations to approve")} ({pending.length})</p>
    {pending.map((c) => <div key={c.id} className="rounded-lg border border-amber-500 p-2" data-testid={"device-change-" + c.id}>
      <p><strong>{c.device}</strong> · {tr(...(ACTIONS[c.action] ?? [c.action, c.action]))}</p>
      {c.file && <p className="break-all">{c.file}{c.size !== undefined ? " · " + Math.round(c.size / 1024) + " KiB" : ""} · SHA-256 <code>{c.sha256}</code></p>}
      {c.package && <p>{tr("App: ", "App: ")}<code>{c.package}</code></p>}
      {c.mode && <p>{tr("Modalità: ", "Mode: ")}{c.mode}</p>}
      {c.command && <pre className="bg-muted overflow-x-auto rounded p-1">{JSON.stringify(c.command, null, 1)}</pre>}
      {c.note && <p className="text-muted-foreground">{c.note}</p>}
      <p className="text-muted-foreground">{tr("Verrà eseguita una sola volta, esattamente così. Assicurati che il dispositivo possa essere modificato ora (alimentazione, veicolo fermo, nessuno lo sta usando).", "It runs once, exactly like this. Make sure the device can be changed now (power, vehicle parked, nobody using it).")}</p>
      <div className="mt-1 flex gap-2">
        <button className="rounded bg-amber-600 px-2 py-1 text-white" onClick={() => void decide(c.id, "approve")}>{tr("Approva questa scrittura", "Approve this write")}</button>
        <button className="rounded border px-2 py-1" onClick={() => void decide(c.id, "reject")}>{tr("Rifiuta", "Reject")}</button>
      </div>
    </div>)}
    {recent.length > 0 && <ul className="text-muted-foreground space-y-0.5">{recent.map((c) => <li key={c.id}>{c.device} · {tr(...(ACTIONS[c.action] ?? [c.action, c.action]))} · {
      c.status === "approved" ? tr("approvata, in attesa di esecuzione", "approved, waiting to run") : c.status === "delivered" ? tr("consegnata all’incarico", "handed to the task") : tr("rifiutata", "rejected")}</li>)}</ul>}
    {error && <p className="text-destructive">{error}</p>}
  </section>;
}
