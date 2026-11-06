"use client";

import { useEffect, useState } from "react";

import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import { useI18n } from "@/core/i18n/hooks";

type Choice = {
  id: string;
  name: string;
  entry?: string;
  source_path?: string;
  source_role?: string;
  relationship: string;
  integration: string;
  opening_mode?: string;
  manual?: boolean;
};
export function EditorLauncher({
  threadId,
  path,
  isMock = false,
  showUnavailable = false,
  preferSelected = false,
  draftSession,
}: {
  threadId: string;
  path: string;
  isMock?: boolean;
  showUnavailable?: boolean;
  preferSelected?: boolean;
  draftSession?: string;
}) {
  const { locale } = useI18n(),
    it = locale === "it-IT";
  const [choices, setChoices] = useState<Choice[]>([]),
    [available, setAvailable] = useState<Choice[]>([]),
    [loadedPath, setLoadedPath] = useState(""),
    [error, setError] = useState(""),
    [attempt, setAttempt] = useState(0),
    [selected, setSelected] = useState("0");
  const identity = `${threadId}:${draftSession ?? path}`;
  useEffect(() => {
    if (isMock || (!draftSession && !path.startsWith("/mnt/user-data/")))
      return;
    const abort = new AbortController();
    void fetch(
      `${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/editors?${draftSession ? `session=${encodeURIComponent(draftSession)}` : `path=${encodeURIComponent(path)}`}`,
      { signal: abort.signal },
    )
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        if (r.ok) {
          const value = (await r.json()) as {
            editors: Choice[];
            available_editors?: Choice[];
          };
          const rows = Array.isArray(value.editors) ? value.editors : [];
          setChoices(
            preferSelected
              ? [...rows].sort(
                  (a, b) =>
                    Number(
                      !(
                        a.source_role === "selected" &&
                        a.relationship === "source"
                      ),
                    ) -
                    Number(
                      !(
                        b.source_role === "selected" &&
                        b.relationship === "source"
                      ),
                    ),
                )
              : rows,
          );
          setAvailable(value.available_editors ?? []);
          setLoadedPath(identity);
          setError("");
          setSelected("0");
        }
      })
      .catch((reason: unknown) => {
        if (!abort.signal.aborted) {
          setError(String(reason));
          setLoadedPath(identity);
          setChoices([]);
          setAvailable([]);
        }
      });
    return () => abort.abort();
  }, [threadId, path, isMock, attempt, preferSelected, draftSession, identity]);
  if (loadedPath !== identity)
    return showUnavailable ? (
      <p className="text-xs" role="status">
        {it ? "Cerco gli editor disponibili…" : "Finding available editors…"}
      </p>
    ) : null;
  const options = [
    ...choices,
    ...available
      .filter(
        (item) =>
          !choices.some(
            (row) => row.id === item.id && row.source_role === "selected",
          ),
      )
      .map((item) => ({
        ...item,
        relationship: "manual",
        manual: true,
        source_role: "selected",
      })),
  ];
  if (!options.length)
    return showUnavailable || available.length > 0 ? (
      <p className="text-xs" role={error ? "alert" : undefined}>
        {error
          ? it
            ? "Elenco editor non disponibile."
            : "Editor discovery unavailable."
          : it
            ? "Nessun editor abilitato per questo file. Puoi visualizzarlo o scaricarlo."
            : "No enabled editor for this file. You can preview or download it."}
        {error && (
          <button
            type="button"
            className="ml-2 underline"
            onClick={() => setAttempt((value) => value + 1)}
          >
            {it ? "Riprova" : "Retry"}
          </button>
        )}
      </p>
    ) : null;
  const choice = options[Number(selected)];
  return (
    <div
      className="flex shrink-0 flex-wrap items-center gap-2 border-b px-3 py-2 text-sm"
      data-testid="editor-launcher"
    >
      <span>{it ? "Apri con" : "Open with"}</span>
      <select
        aria-label={it ? "Scegli editor" : "Choose editor"}
        className="max-w-72 rounded border px-2 py-1"
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
      >
        {options.map((item, index) => (
          <option
            key={`${item.id}:${item.source_path ?? path}:${item.entry ?? ""}`}
            value={String(index)}
          >
            {item.source_role !== "selected"
              ? it
                ? "Sorgente · "
                : "Source · "
              : ""}
            {item.source_role !== "selected" && item.source_path
              ? `${item.source_path.split("/").pop()} · `
              : ""}
            {item.entry ? `${item.entry} · ` : ""}
            {item.name}
            {item.manual
              ? it
                ? " · compatibilità da verificare"
                : " · compatibility unverified"
              : item.opening_mode === "text"
                ? it
                  ? " · file di testo"
                  : " · text file"
                : ""}
            {item.relationship === "import"
              ? it
                ? " · importa"
                : " · import"
              : ""}
            {item.integration === "preview"
              ? it
                ? " · anteprima"
                : " · preview"
              : ""}
          </option>
        ))}
      </select>
      <a
        target="_blank"
        rel="noopener noreferrer"
        className="rounded border px-3 py-1"
        href={`/edit?thread=${encodeURIComponent(threadId)}&path=${encodeURIComponent(choice?.source_path ?? path)}&editor=${encodeURIComponent(choice?.id ?? "")}&entry=${encodeURIComponent(choice?.entry ?? "")}&manual=${choice?.manual ? "1" : "0"}${draftSession ? `&from_session=${encodeURIComponent(draftSession)}` : ""}`}
      >
        {it ? "Apri editor" : "Open editor"} ↗
      </a>
      {choice?.manual && (
        <p className="basis-full text-xs">
          {it
            ? "Formato non dichiarato dall’editor: verifica il supporto prima di modificare il file. L’app potrebbe richiedere un’importazione o un salvataggio nel proprio formato nativo."
            : "This format is not declared by the editor: check support before changing the file. The app may require importing or saving in its native format."}
        </p>
      )}
    </div>
  );
}
