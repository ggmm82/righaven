"use client";

import { useEffect, useState } from "react";

import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import { tr, useUiLanguage } from "@/core/i18n/ui-text";

type Connection = { id: string; name: string; kind: string; host?: string; database?: string; read_only?: boolean; authentication?: string; tools?: string[]; missing?: boolean };

const kinds: Record<string, string> = { postgres: "PostgreSQL", sqlserver: "SQL Server", mysql: "MySQL", oracle: "Oracle", entra: "Microsoft Entra ID" };

/** The connections the user chose for this task; only roles declaring the authorized IDs receive them. */
export function ProjectConnections({ threadId }: { threadId: string }) {
  useUiLanguage();
  const [all, setAll] = useState<Connection[] | null>(null);
  const [assigned, setAssigned] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const base = getBackendBaseURL();
  useEffect(() => {
    let live = true;
    void Promise.all([
      fetch(`${base}/api/harness/connections`).then((r) => (r.ok ? r.json() : { connections: [] })),
      fetch(`${base}/api/threads/${encodeURIComponent(threadId)}/harness-connections`).then((r) => (r.ok ? r.json() : { assigned: [] })),
    ]).then(([mine, current]: [{ connections: Connection[] }, { assigned: Connection[] }]) => {
      if (!live) return;
      setAll(mine.connections);
      setAssigned(current.assigned.map((c) => c.id));
    }).catch(() => setAll([]));
    return () => { live = false; };
  }, [base, threadId]);
  async function save(ids: string[]) {
    setBusy(true);
    setMessage("");
    const response = await fetch(`${base}/api/threads/${encodeURIComponent(threadId)}/harness-connections`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }),
    });
    const value = (await response.json()) as { assigned?: Connection[]; detail?: string };
    setBusy(false);
    if (!response.ok) { setMessage(typeof value.detail === "string" ? value.detail : String(response.status)); return; }
    setAssigned((value.assigned ?? []).map((c) => c.id));
    setMessage(tr("Salvato: il coordinatore vedrà queste connessioni dal prossimo turno.", "Saved: the coordinator will see these connections from its next turn."));
  }
  if (all === null) return null;
  return <details className="rounded-xl border p-3 text-sm" data-testid="project-connections">
    <summary className="cursor-pointer font-medium">{tr("Connessioni del lavoro", "Task connections")} ({assigned.length})</summary>
    <p className="text-muted-foreground my-2 text-xs">{tr(
      "Scegli i database e gli account Microsoft che questo lavoro può usare: solo i ruoli del lavoro che ne hanno bisogno ricevono le connessioni autorizzate, e le perdono quando finiscono. Le password non sono mai mostrate al coordinatore.",
      "Choose the databases and Microsoft accounts this task may use: only roles declaring these authorized connection IDs receive them, and lose them when they end. Passwords are never shown to the coordinator.")}</p>
    {all.length === 0 && <p className="text-xs">{tr("Nessuna connessione necessaria per documenti e dati sintetici. Se serve un accesso esterno, puoi aggiungerlo in ", "No connection is needed for documents and synthetic data. For external access, add one in ")}<a className="underline" href="/workspace/connections">{tr("Connessioni", "Connections")}</a>.</p>}
    <ul className="space-y-1">{all.map((c) => <li key={c.id}><label className="flex items-start gap-2">
      <input type="checkbox" disabled={busy} checked={assigned.includes(c.id)} onChange={(event) => void save(event.target.checked ? [...assigned, c.id] : assigned.filter((id) => id !== c.id))}/>
      <span><strong>{c.name}</strong> · {kinds[c.kind] ?? c.kind}{c.database ? " · " + c.database : ""}{c.kind !== "entra" && !c.read_only && <span className="text-destructive"> · {tr("non dichiarata in sola lettura: gli strumenti la rifiuteranno", "not declared read-only: tools will refuse it")}</span>}</span>
    </label></li>)}</ul>
    {message && <p className="mt-2 text-xs">{message}</p>}
  </details>;
}
