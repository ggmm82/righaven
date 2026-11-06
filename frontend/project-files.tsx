"use client";

import { useEffect, useRef, useState } from "react";

import { EditorLauncher } from "@/components/workspace/artifacts/editor-launcher";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import { useI18n } from "@/core/i18n/hooks";

type Entry = {
  name: string;
  path: string;
  virtual_path: string;
  directory: boolean;
  size: number | null;
  modified_at: number;
  file_count?: number;
  size_complete?: boolean;
  role: string;
  delivery_id: string;
  delivery?: string;
};
type Listing = {
  entries: Entry[];
  next_offset: number | null;
  truncated: boolean;
};
type Draft = {
  id: string;
  entry: string;
  editor: string;
  revision: number;
  published_revision?: number;
  updated_at?: string;
  source?: string;
};

export function ProjectFileBrowser({ threadId }: { threadId: string }) {
  const { locale } = useI18n(),
    it = locale === "it-IT",
    t = (a: string, b: string) => (it ? a : b);
  const [path, setPath] = useState(""),
    [query, setQuery] = useState(""),
    [role, setRole] = useState("all"),
    [entries, setEntries] = useState<Entry[]>([]),
    [selected, setSelected] = useState<Entry | null>(null),
    [editing, setEditing] = useState<string | null>(null),
    [drafts, setDrafts] = useState<Draft[]>([]),
    [view, setView] = useState("files"),
    [next, setNext] = useState<number | null>(null),
    [offset, setOffset] = useState(0),
    [epoch, setEpoch] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [truncated, setTruncated] = useState(false);
  const base = `${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}`;
  const labels: Record<string, string> = {
    attachment: t("Allegato", "Attachment"),
    editable_source: t("Sorgente", "Source"),
    source_archive: t("Pacchetto sorgenti", "Source package"),
    export: t("Risultato", "Result"),
    preview: t("Anteprima", "Preview"),
    report: t("Rapporto", "Report"),
    dependency: t("Risorsa", "Resource"),
    revision: t("Revisione", "Revision"),
    working_file: t("File di lavoro", "Working file"),
  };
  useEffect(() => {
    const abort = new AbortController();
    setBusy(true);
    setError("");
    const timer = setTimeout(
      () => {
        const endpoint =
          view === "drafts"
            ? `${base}/editors`
            : `${base}/project-files?${new URLSearchParams({ path, query, role, offset: String(offset) })}`;
        void fetch(endpoint, { signal: abort.signal, cache: "no-store" })
          .then(async (response) => {
            const value = (await response.json()) as Listing & {
              sessions: Draft[];
              detail?: string;
            };
            if (!response.ok)
              throw Error(value.detail ?? `HTTP ${response.status}`);
            if (view === "drafts") {
              if (!Array.isArray(value.sessions))
                throw Error("Invalid file response");
              setDrafts(value.sessions);
            } else {
              if (!Array.isArray(value.entries))
                throw Error("Invalid file response");
              setEntries((previous) =>
                offset
                  ? [
                      ...new Map(
                        [...previous, ...value.entries].map((item) => [
                          item.path,
                          item,
                        ]),
                      ).values(),
                    ]
                  : value.entries,
              );
              setNext(value.next_offset);
              setTruncated(Boolean(value.truncated));
            }
          })
          .catch((reason) => {
            if (!abort.signal.aborted) setError(String(reason));
          })
          .finally(() => {
            if (!abort.signal.aborted) setBusy(false);
          });
      },
      query ? 300 : 0,
    );
    return () => {
      abort.abort();
      clearTimeout(timer);
    };
  }, [base, path, query, role, offset, epoch, view]);
  function navigate(value: string) {
    setPath(value);
    setOffset(0);
    setSelected(null);
    setEditing(null);
    setEntries([]);
  }
  const viewer = (file: Entry) =>
    `/artifacts/view?${new URLSearchParams({ thread_id: threadId, path: file.virtual_path })}`;
  const download = (file: Entry) =>
    `${base}/artifacts/${file.virtual_path.replace(/^\//, "").split("/").map(encodeURIComponent).join("/")}?download=true`;
  function openEntry(file: Entry) {
    if (file.directory) navigate(file.path);
    else window.open(viewer(file), "_blank", "noopener,noreferrer");
  }
  function sizeLabel(bytes: number | null) {
    if (bytes === null) return "—";
    const units = ["B", "KiB", "MiB", "GiB", "TiB"];
    const exponent =
      bytes > 0 ? Math.min(4, Math.floor(Math.log(bytes) / Math.log(1024))) : 0;
    return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(bytes / 1024 ** exponent)} ${units[exponent]}`;
  }
  return (
    <section className="space-y-3" data-testid="project-file-browser">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded border px-3 py-2"
            aria-pressed={view === "files"}
            onClick={() => setView("files")}
          >
            {t("File e cartelle", "Files and folders")}
          </button>
          <button
            type="button"
            className="rounded border px-3 py-2"
            aria-pressed={view === "drafts"}
            onClick={() => setView("drafts")}
          >
            {t("Bozze editor", "Editor drafts")}
          </button>
        </div>
        <button
          type="button"
          className="rounded border px-3 py-2"
          disabled={busy}
          onClick={() => {
            setOffset(0);
            setEpoch((n) => n + 1);
          }}
        >
          {t("Aggiorna", "Refresh")}
        </button>
      </div>
      <p className="text-muted-foreground text-xs">
        {t(
          "I file restano accessibili anche se la squadra è ferma. Un file di lavoro può essere incompleto; le versioni consegnate sono nella sezione Versioni.",
          "Files remain accessible when the team is stopped. Working files may be incomplete; recorded deliveries are in Versions.",
        )}
      </p>
      {view === "files" && (
        <>
          <nav
            aria-label={t("Percorso cartella", "Folder path")}
            className="flex flex-wrap gap-2 text-sm"
          >
            <button className="underline" onClick={() => navigate("")}>
              {t("Progetto", "Project")}
            </button>
            {path
              .split("/")
              .filter(Boolean)
              .map((part, index) => (
                <span key={index}>
                  /{" "}
                  <button
                    className="break-all underline"
                    onClick={() =>
                      navigate(
                        path
                          .split("/")
                          .slice(0, index + 1)
                          .join("/"),
                      )
                    }
                  >
                    {part}
                  </button>
                </span>
              ))}
          </nav>
          <div className="flex flex-wrap gap-2">
            <input
              aria-label={t("Cerca nei file", "Search files")}
              className="min-w-0 flex-1 rounded border p-2"
              placeholder={t(
                "Cerca anche nelle sottocartelle…",
                "Search including subfolders…",
              )}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setOffset(0);
                setEntries([]);
                setSelected(null);
                setEditing(null);
              }}
            />
            <select
              aria-label={t("Tipo di file", "File category")}
              className="rounded border p-2"
              value={role}
              onChange={(event) => {
                setRole(event.target.value);
                setOffset(0);
                setSelected(null);
                setEditing(null);
              }}
            >
              <option value="all">{t("Tutti i file", "All files")}</option>
              {Object.entries(labels).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <p className="text-muted-foreground text-xs">
            {t(
              "Un clic seleziona; doppio clic o Invio apre. Su touch usa i pulsanti.",
              "One click selects; double-click or Enter opens. On touch use the buttons.",
            )}
          </p>
          <details className="text-muted-foreground text-xs"><summary>{t("Dimensioni e date (Europe/Rome)","Sizes and dates (Europe/Rome)")}</summary><p className="mt-1">{t("Le cartelle sommano i file visibili, senza collegamenti o dipendenze nascoste. I totali parziali sono limiti inferiori. Le date sono quelle di modifica nel filesystem.","Folders sum visible files, excluding links and hidden dependencies. Partial totals are lower bounds. Dates are filesystem modification times.")}</p></details>
          <ul
            className="divide-y rounded-lg border"
            aria-label={t("File del progetto", "Project files")}
          >
            {entries.map((file) => (
              <li
                key={file.path}
                className={`flex flex-wrap items-center gap-2 p-3 ${selected?.path === file.path ? "bg-muted/40" : ""}`}
              >
                <button
                  type="button"
                  className="min-w-0 flex-1 basis-full text-left break-all underline sm:basis-auto"
                  aria-pressed={selected?.path === file.path}
                  onClick={() => {setSelected(file);setEditing(null);}}
                  onDoubleClick={() => openEntry(file)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      openEntry(file);
                    }
                  }}
                >
                  {file.directory ? "▸ " : ""}
                  {query ? file.path : file.name}
                </button>
                <div className="text-muted-foreground flex basis-full flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  <span>
                    {file.directory
                      ? t("Cartella", "Folder")
                      : (labels[file.role] ?? labels.working_file)}
                  </span>
                  <span
                    title={
                      file.directory
                        ? t(
                            "Dimensione logica dei file visibili; non è l’occupazione sul disco.",
                            "Logical size of visible files; not disk usage.",
                          )
                        : `${new Intl.NumberFormat(locale).format(file.size ?? 0)} B`
                    }
                  >
                    {file.directory && file.size_complete === false ? "≥ " : ""}
                    {sizeLabel(file.size)}
                    {file.directory &&
                      ` · ${file.size_complete === false ? "≥ " : ""}${file.file_count ?? 0} file`}
                    {file.directory &&
                      file.size_complete === false &&
                      ` · ${t("parziale", "partial")}`}
                  </span>
                  {Number.isFinite(file.modified_at) && (
                    <time
                      dateTime={new Date(file.modified_at * 1000).toISOString()}
                      title={
                        file.directory
                          ? t(
                              "Data filesystem della cartella; i file contenuti hanno le proprie date.",
                              "Filesystem timestamp of this folder; contained files have their own dates.",
                            )
                          : undefined
                      }
                    >
                      {t("Modificato", "Modified")}:{" "}
                      {new Date(file.modified_at * 1000).toLocaleString(
                        locale,
                        {
                          timeZone: "Europe/Rome",
                          dateStyle: "medium",
                          timeStyle: "short",
                        },
                      )}
                    </time>
                  )}
                </div>
                {file.directory && (
                  <button
                    type="button"
                    className="text-sm underline"
                    onClick={() => navigate(file.path)}
                  >
                    {t("Apri cartella", "Open folder")}
                  </button>
                )}
                {!file.directory && (
                  <>
                    {file.delivery && (
                      <span className="text-muted-foreground basis-full text-xs">
                        {t("Lavorazione", "Work step")}: {file.delivery}
                      </span>
                    )}
                    <button
                      type="button"
                      className="text-sm underline"
                      aria-expanded={editing === file.path}
                      onClick={() => {
                        setSelected(file);
                        setEditing(editing === file.path ? null : file.path);
                      }}
                    >
                      {t("Apri con", "Open with")}
                    </button>
                    <a
                      className="text-sm underline"
                      href={viewer(file)}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {t("Anteprima", "Preview")}
                    </a>
                    <a
                      className="text-sm underline"
                      href={download(file)}
                      download
                    >
                      {t("Scarica", "Download")}
                    </a>
                  </>
                )}
                {editing === file.path && !file.directory && (
                  <section
                    className="bg-muted/20 min-w-0 basis-full space-y-2 rounded border p-2"
                    aria-label={t("Azioni del file", "File actions")}
                  >
                    <p className="text-xs break-all">{file.path}</p>
                    <EditorLauncher
                      key={file.virtual_path}
                      threadId={threadId}
                      path={file.virtual_path}
                      showUnavailable
                      preferSelected
                    />
                  </section>
                )}
              </li>
            ))}
          </ul>
          {truncated && (
            <p role="status" className="text-sm">
              {t(
                "Ricerca limitata: apri una sottocartella o rendi la ricerca più specifica.",
                "Search was limited: open a subfolder or narrow the search.",
              )}
            </p>
          )}
          {next !== null && (
            <button
              type="button"
              disabled={busy}
              className="rounded border px-3 py-2"
              onClick={() => setOffset(next)}
            >
              {t("Mostra altri", "Load more")}
            </button>
          )}
        </>
      )}
      {view === "drafts" && (
        <ul className="space-y-2">
          {drafts.map((draft) => (
            <li key={draft.id} className="rounded border p-3">
              <a
                className="break-all underline"
                target="_blank"
                rel="noopener noreferrer"
                href={`/edit?${new URLSearchParams({ thread: threadId, session: draft.id })}`}
              >
                {draft.entry}
              </a>
              <p className="text-xs">
                {draft.editor} · {t("Bozza", "Draft")} {draft.revision}
                {typeof draft.published_revision === "number" &&
                  ` · ${t("Ultima pubblicazione", "Last publication")}: ${draft.published_revision}`}
              </p>
              {draft.source && (
                <p className="text-muted-foreground text-xs break-all">
                  {draft.source.replace(/^\/mnt\/user-data\//, "")}
                </p>
              )}
              {draft.updated_at && (
                <time
                  className="text-muted-foreground text-xs"
                  dateTime={draft.updated_at}
                >
                  {new Date(draft.updated_at).toLocaleString(locale, {
                    timeZone: "Europe/Rome",
                  })}
                </time>
              )}
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      {busy && <p role="status">{t("Caricamento file…", "Loading files…")}</p>}
      {!busy &&
        !error &&
        !(view === "drafts" ? drafts.length : entries.length) && (
          <p>{t("Nessun file in questa vista.", "No files in this view.")}</p>
        )}
    </section>
  );
}

export function ProjectFiles({ threadId }: { threadId: string }) {
  const { locale } = useI18n(),
    it = locale === "it-IT";
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal();
  }, [open]);
  return (
    <>
      <button
        type="button"
        className="rounded-lg border px-3 py-2 text-sm"
        onClick={() => setOpen(true)}
      >
        {it ? "File" : "Files"}
      </button>
      {open && (
        <dialog
          ref={dialog}
          onCancel={() => setOpen(false)}
          onClose={() => setOpen(false)}
          aria-label={it ? "File del progetto" : "Project files"}
          className="bg-background text-foreground fixed inset-0 m-auto h-[85dvh] max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-4xl overflow-hidden rounded-2xl border p-0 shadow-xl backdrop:bg-black/40"
        >
          <div className="flex h-full flex-col">
            <header className="flex items-center justify-between border-b p-4">
              <h2 className="font-semibold">
                {it ? "File del progetto" : "Project files"}
              </h2>
              <button
                type="button"
                className="rounded border px-3 py-2"
                onClick={() => setOpen(false)}
              >
                {it ? "Chiudi" : "Close"}
              </button>
            </header>
            <div className="min-h-0 flex-1 overflow-auto p-4">
              <ProjectFileBrowser threadId={threadId} />
            </div>
          </div>
        </dialog>
      )}
    </>
  );
}
