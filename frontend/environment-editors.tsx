"use client";
import { useEffect, useState } from "react";

import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import { tr, useUiLanguage } from "@/core/i18n/ui-text";
type Editor = {
  id: string;
  name: string;
  mode: string;
  state: string;
  preload: boolean;
  message?: string;
  version?: string;
  integration: string;
};
export function EnvironmentEditors({ name }: { name: string }) {
  useUiLanguage();
  const [rows, setRows] = useState<Editor[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const url = `${getBackendBaseURL()}/api/harness/environments/${encodeURIComponent(name)}/editors`;
  useEffect(() => {
    let stopped = false,
      timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const r = await fetch(url);
        if (!r.ok) throw Error(String(r.status));
        const value = (await r.json()) as { editors: Editor[] };
        if (stopped) return;
        if (!Array.isArray(value.editors))
          throw Error(
            tr(
              "Impostazioni editor non disponibili",
              "Editor settings unavailable",
            ),
          );
        setRows(value.editors);
        if (value.editors.some((e) => e.state === "preparing"))
          timer = setTimeout(() => void load(), 2000);
      } catch (e) {
        if (!stopped) setError(String(e));
      }
    }
    void load();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [url, busy]);
  async function toggle(id: string, value: boolean) {
    setBusy(true);
    setError("");
    try {
      const selected = rows
        .filter((e) => e.preload && e.id !== id)
        .map((e) => e.id);
      if (value) selected.push(id);
      const r = await fetch(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ editors: selected }),
      });
      if (!r.ok) {
        const e = (await r.json()) as { detail?: string };
        throw Error(e.detail ?? String(r.status));
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  if (!rows.length && !error) return null;
  return (
    <section
      className="space-y-3 border-t pt-3"
      data-testid="environment-editors"
    >
      <h3 className="font-semibold">
        {tr("Editor interattivi", "Interactive editors")}
      </h3>
      <p className="text-xs text-muted-foreground">
        {tr(
          "Aprili dai file in chat. Scegli le interfacce da tenere pronte; le altre si preparano al primo utilizzo. Precaricare i programmi non mantiene una sessione accesa.",
          "Open editors from conversation files. Choose which interfaces to keep ready; others prepare on first use. Prepared software does not keep an editing session running.",
        )}
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {rows.map((e) => (
          <label key={e.id} className="rounded border p-3 text-sm">
            {e.id==="jupyter"&&<p className="text-xs">{tr("CLI nbconvert e interfaccia Jupyter Notebook hanno versioni distinte.","The nbconvert CLI and Jupyter Notebook interface have separate versions.")}</p>}
            <span className="flex gap-2">
              <input
                type="checkbox"
                checked={e.preload}
                disabled={busy}
                onChange={(event) => void toggle(e.id, event.target.checked)}
              />
              {e.name}
              <span className="ml-auto text-xs">{e.mode}</span>
            </span>
            <span className="mt-1 block text-xs text-muted-foreground">
              {e.state === "on_demand"
                ? tr("Su richiesta", "On demand")
                : e.state === "preparing"
                  ? tr("In preparazione", "Preparing")
                  : e.state === "ready"
                    ? tr("Pronto", "Ready")
                    : tr("Da correggere", "Needs attention")}
              {e.version ? ` · v${e.version}` : ""}
              {e.integration === "preview"
                ? ` · ${tr("In anteprima", "Preview integration")}`
                : ""}
            </span>
            {e.message && (
              <span className="mt-1 block break-words text-xs">
                {e.message}
              </span>
            )}
          </label>
        ))}
      </div>
      {error && (
        <p role="alert" className="text-red-700">
          {error}
        </p>
      )}
    </section>
  );
}
