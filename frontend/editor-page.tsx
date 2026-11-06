"use client";
import CodeMirror from "@uiw/react-codemirror";
import { useEffect, useRef, useState } from "react";

import { EditorLauncher } from "@/components/workspace/artifacts/editor-launcher";
import { fetch } from "@/core/api/fetcher";
import { buildArtifactViewerURL } from "@/core/artifacts/viewer";
import { getBackendBaseURL } from "@/core/config";
import { useI18n } from "@/core/i18n/hooks";
type FileRow = { name: string; bytes: number; sha256: string };
type Session = {
  id: string;
  mode?: string;
  project_root?: string;
  virtual_path?: string;
  editor: string;
  editor_version: string;
  cli_version?: string;
  version_origin?: string;
  environment_profile?: string;
  native_extensions: string[];
  entry: string;
  source: string;
  revision: number;
  published_revision: number;
  files: FileRow[];
  files_truncated?: boolean;
  dependencies?: string[];
  missing_dependencies?: string[];
  publications: { path: string; revision: number }[];
};
type FailedSave = {
  name: string;
  data: ArrayBuffer | Uint8Array | string;
  entry: boolean;
  requestId?: string;
};
type FrameFile = { name: string; bytes: ArrayBuffer };
type LoadedFrame = {
  window: Window;
  files: Promise<FrameFile[]>;
  staged: boolean;
  opened: boolean;
};
type Status = {
  interface_version?: string;
  environment_profile?: string;
  cli_version?: string;
  state: string;
  message?: string;
  url?: string;
  error?: string;
};
type Message = {
  type?: string;
  name?: string;
  bytes?: ArrayBuffer | Uint8Array;
  dirty?: boolean;
  error?: string;
  document?: unknown;
  requestId?: string;
  saveAs?: boolean;
  cancelled?: boolean;
};
async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const value = (await response.json()) as { detail?: string };
    throw Error(value.detail ?? String(response.status));
  }
  return (await response.json()) as T;
}
const encoded = (name: string) =>
  name.split("/").map(encodeURIComponent).join("/");
export default function EditorPage() {
  const { locale } = useI18n(),
    it = locale === "it-IT",
    t = (a: string, b: string) => (it ? a : b);
  const [session, setSession] = useState<Session | null>(null),
    [thread, setThread] = useState(""),
    [file, setFile] = useState(""),
    [text, setText] = useState(""),
    [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [switchEditor, setSwitchEditor] = useState(false),
    [showFiles, setShowFiles] = useState(false),
    [terminalOptions, setTerminalOptions] = useState<
      | { name: string; display_name: string; runtime: { status: string } }[]
      | null
    >(null),
    [terminalEnvironment, setTerminalEnvironment] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [status, setStatus] = useState<Status | null>(null),
    [sourceReady, setSourceReady] = useState(false),
    [choosingDestination, setChoosingDestination] = useState(false),
    [effectRenderer, setEffectRenderer] = useState("compatible");
  const [failedSaves, setFailedSaves] = useState<FailedSave[]>([]);
  const frame = useRef<HTMLIFrameElement>(null),
    current = useRef<Session | null>(null),
    unsaved = useRef(false),
    queue = useRef(Promise.resolve()),
    pendingSaves = useRef(0),
    loadedFrame = useRef<LoadedFrame | null>(null),
    nativeHost = useRef(false);
  current.current = session;
  unsaved.current =
    choosingDestination ||
    dirty ||
    failedSaves.length > 0 ||
    pendingSaves.current > 0 ||
    Boolean(
      session &&
      ["jupyter", "blender", "freecad"].includes(session.editor) &&
      status?.state === "ready",
    );
  const base = `${getBackendBaseURL()}/api/threads/${encodeURIComponent(thread)}/editors`,
    url = session ? `${base}/${session.id}` : "";
  const interactive = Boolean(
      session && ["jupyter", "blender", "freecad"].includes(session.editor),
    ),
    running =
      interactive && status && !["stopped", "failed"].includes(status.state);
  useEffect(() => {
    let cancelled = false;
    const p = new URLSearchParams(location.search),
      tid = p.get("thread") ?? "",
      sid = p.get("session"),
      path = p.get("path"),
      editor = p.get("editor"),
      fromSession = p.get("from_session");
    setThread(tid);
    if (!tid || (!sid && (!(path || fromSession) || !editor))) {
      setError("Open an editor from a conversation file.");
      return;
    }
    const prefix = `${getBackendBaseURL()}/api/threads/${encodeURIComponent(tid)}/editors`;
    void (
      sid
        ? api<Session>(`${prefix}/${encodeURIComponent(sid)}`)
        : api<Session>(
            fromSession
              ? `${prefix}/${encodeURIComponent(fromSession)}/open-with`
              : prefix,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(
                fromSession
                  ? { editor, manual: p.get("manual") === "1" }
                  : {
                      path,
                      editor,
                      direct: true,
                      entry: p.get("entry") ?? "",
                      manual: p.get("manual") === "1",
                    },
              ),
            },
          )
    )
      .then((s) => {
        if (cancelled) return;
        current.current = s;
        setSession(s);
        setFile(s.entry);
        history.replaceState(
          null,
          "",
          `/edit?${new URLSearchParams({ thread: tid, session: s.id })}`,
        );
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);
  useEffect(() => {
    if (session?.editor !== "text" || !file) return;
    let cancelled = false;
    void fetch(`${url}/files/${encoded(file)}`)
      .then(async (r) => {
        if (!r.ok) throw Error(String(r.status));
        const bytes = await r.arrayBuffer();
        const value = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
        if (!cancelled) {
          setText(value);
          setDirty(false);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [url, file, session?.editor]);
  useEffect(() => {
    if (
      !session ||
      session.editor === "text" ||
      ["bpmn", "excalidraw"].includes(session.editor)
    )
      return;
    let cancelled = false,
      timer: ReturnType<typeof setTimeout>;
    const service = ["jupyter", "blender", "freecad"].includes(session.editor),
      endpoint = service ? "service" : "package";
    async function poll() {
      try {
        const value = await api<Status>(`${url}/${endpoint}`);
        if (cancelled) return;
        setStatus(value);
        if (["stopped", "failed"].includes(value.state)) {
          if (service) setSession(await api<Session>(url));
          if (value.state === "failed")
            setError(value.error ?? value.message ?? "Editor failed");
          return;
        }
        if (value.state !== "ready" || service)
          timer = setTimeout(() => void poll(), 2000);
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }
    void api<Status>(`${url}/${service ? "service" : "prepare"}`, {
      method: "POST",
    })
      .then((v) => {
        if (!cancelled) {
          setStatus(v);
          timer = setTimeout(() => void poll(), 1000);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    const close = () => {
      if (service)
        void fetch(`${url}/service`, {
          method: "DELETE",
          keepalive: true,
        }).catch(() => {
          /* Disconnected editors also expire server-side. */
        });
    };
    window.addEventListener("pagehide", close);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      window.removeEventListener("pagehide", close);
      close();
    };
  }, [url, session?.editor]);
  useEffect(() => {
    const guard = (e: BeforeUnloadEvent) => {
      if (unsaved.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, []);
  useEffect(() => {
    if (!session || !url) return;
    const client = crypto.randomUUID();
    const presence = (active: boolean) =>
      void fetch(`${url}/presence`, {
        method: "POST",
        keepalive: !active,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client, active }),
      }).catch(() => {
        /* Presence expires if the page disconnects. */
      });
    presence(true);
    const timer = setInterval(() => presence(true), 25000);
    const close = () => presence(false);
    window.addEventListener("pagehide", close);
    const resume = () => presence(true);
    window.addEventListener("pageshow", resume);
    return () => {
      clearInterval(timer);
      window.removeEventListener("pagehide", close);
      window.removeEventListener("pageshow", resume);
      close();
    };
  }, [url, session?.id]);
  useEffect(() => {
    if (!session) return;
    frame.current?.contentWindow?.postMessage(
      {
        type: "rh-editor-manifest",
        manifest: session.files.filter((row) =>
          session.native_extensions.some((ext) =>
            row.name.toLowerCase().endsWith(ext),
          ),
        ),
      },
      location.origin,
    );
  }, [session]);
  async function store(
    name: string,
    data: ArrayBuffer | Uint8Array | string,
    entry: boolean,
  ) {
    const s = current.current;
    if (!s) throw Error("Session not loaded");
    if (s.mode === "project" && !name.includes("/")) {
      const parent = s.entry.includes("/")
        ? s.entry.slice(0, s.entry.lastIndexOf("/") + 1)
        : "";
      name = parent + name;
    }
    const bytes =
      typeof data === "string" ? new TextEncoder().encode(data) : data;
    const value = await api<Session>(
      `${base}/${s.id}/files/${encoded(name)}?expected_revision=${s.revision}&entry=${entry}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/octet-stream" },
        body: bytes as BodyInit,
      },
    );
    current.current = value;
    setSession(value);
    setDirty(false);
    setNotice(
      t(
        s.mode === "project"
          ? "File salvato nella cartella della chat."
          : "Bozza salvata. Pubblica per passarla alla squadra.",
        s.mode === "project"
          ? "File saved in the chat folder."
          : "Draft saved. Publish to hand it to the team.",
      ),
    );
  }
  function save(
    name: string,
    data: ArrayBuffer | Uint8Array | string,
    entry: boolean,
    requestId?: string,
  ) {
    pendingSaves.current++;
    unsaved.current = true;
    setBusy(true);
    queue.current = queue.current
      .then(() => store(name, data, entry))
      .then(() => {
        setFailedSaves((previous) =>
          previous.filter((item) => item.name !== name),
        );
        frame.current?.contentWindow?.postMessage(
          { type: "rh-editor-saved", requestId },
          location.origin,
        );
      })
      .catch((e) => {
        setFailedSaves((previous) => [
          ...previous.filter((item) => item.name !== name),
          { name, data, entry, requestId },
        ]);
        setDirty(true);
        setError(String(e));
        frame.current?.contentWindow?.postMessage(
          { type: "rh-editor-saved", requestId, error: String(e) },
          location.origin,
        );
      })
      .finally(() => {
        pendingSaves.current--;
        if (pendingSaves.current === 0) setBusy(false);
      });
  }
  async function sendFiles(openNative = false) {
    const s = current.current,
      target = frame.current?.contentWindow;
    if (!s || !target) return;
    let state = loadedFrame.current;
    if (state?.window !== target) {
      const files = (async () => {
        const rows: FrameFile[] = [];
        for (const item of [
          ...s.files,
          ...(s.dependencies ?? [])
            .filter((name) => !s.files.some((item) => item.name === name))
            .map((name) => ({ name, bytes: 0, sha256: "" })),
        ].filter(
          (item) =>
            s.mode !== "project" ||
            item.name === s.entry ||
            s.dependencies?.includes(item.name),
        )) {
          const r = await fetch(`${base}/${s.id}/files/${encoded(item.name)}`);
          if (!r.ok) throw Error(`Cannot open ${item.name}`);
          rows.push({ name: item.name, bytes: await r.arrayBuffer() });
        }
        return rows.sort(
          (a, b) => Number(b.name === s.entry) - Number(a.name === s.entry),
        );
      })();
      state = { window: target, files, staged: false, opened: false };
      loadedFrame.current = state;
    }
    const rows = await state.files;
    if (
      frame.current?.contentWindow !== target ||
      loadedFrame.current !== state
    )
      return;
    if (!state.staged) {
      state.staged = true;
      target.postMessage(
        {
          type: "rh-editor-files",
          files: rows,
          projectRoot: s.project_root,
          manifest: s.files.filter((row) =>
            s.native_extensions.some((ext) =>
              row.name.toLowerCase().endsWith(ext),
            ),
          ),
          fileBase: `${base}/${s.id}/files/`,
        },
        location.origin,
        s.editor === "effectcraft" ? rows.map((row) => row.bytes) : [],
      );
      setSourceReady(true);
    }
    if (openNative && !state.opened && rows[0]) {
      state.opened = true;
      target.postMessage(
        { type: `${s.editor}:open`, name: rows[0].name, bytes: rows[0].bytes },
        location.origin,
      );
    }
  }
  async function reopenSource() {
    if (busy || choosingDestination || pendingSaves.current > 0) return;
    if (
      dirty &&
      !confirm(
        t(
          "Riaprire la bozza salvata? Le modifiche non salvate andranno perse.",
          "Reopen the saved draft? Unsaved changes will be lost.",
        ),
      )
    )
      return;
    try {
      loadedFrame.current = null;
      setSourceReady(false);
      await sendFiles(nativeHost.current);
      if (!nativeHost.current)
        frame.current?.contentWindow?.postMessage(
          { type: "rh-editor-open" },
          location.origin,
        );
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    if (!session) return;
    async function onMessage(e: MessageEvent<Message>) {
      if (
        e.origin !== location.origin ||
        e.source !== frame.current?.contentWindow
      )
        return;
      const s = current.current;
      if (!s) return;
      const value = e.data,
        type = value?.type;
      try {
        if (
          [
            "rh-editor-adapter",
            "rh-editor-ready",
            `${s.editor}:ready`,
          ].includes(type ?? "")
        ) {
          if (type === "rh-editor-adapter") {
            loadedFrame.current = null;
            nativeHost.current = false;
            setSourceReady(false);
          }
          const adapterProject = ["effectcraft", "filmcraft"].includes(
            s.editor,
          );
          if (
            type === `${s.editor}:ready` &&
            !adapterProject &&
            !nativeHost.current
          ) {
            nativeHost.current = true;
            if (loadedFrame.current) loadedFrame.current.opened = false;
          }
          await sendFiles(type === `${s.editor}:ready` && !adapterProject);
          if (
            type === "rh-editor-ready" &&
            !nativeHost.current &&
            loadedFrame.current &&
            !loadedFrame.current.opened
          ) {
            loadedFrame.current.opened = true;
            frame.current?.contentWindow?.postMessage(
              { type: "rh-editor-open" },
              location.origin,
            );
          }
          setNotice(
            t(
              "Caricamento del sorgente nell’editor.",
              "Opening the source in the editor.",
            ),
          );
        }
        if (type === `${s.editor}:dirty` || type === "rh-editor-dirty")
          setDirty(Boolean(value.dirty));
        if (type === `${s.editor}:failed` || type === "rh-editor-error")
          setError(value.error ?? "Editor failed");
        if (
          (type === `${s.editor}:save` || type === "rh-editor-save") &&
          value.name &&
          value.bytes
        ) {
          const name = value.name;
          if (
            type === `${s.editor}:save` &&
            (value.saveAs ||
              (name !== s.entry && name !== s.entry.split("/").pop()))
          ) {
            setChoosingDestination(true);
            frame.current?.contentWindow?.postMessage(
              { type: "rh-editor-native-save", name, bytes: value.bytes },
              location.origin,
            );
            return;
          }
          save(
            name,
            value.bytes,
            s.native_extensions.some((ext) => name.toLowerCase().endsWith(ext)),
            value.requestId,
          );
        }
        if (type === "rh-editor-device-lost") {
          setError(
            value.error ??
              t(
                "Dispositivo grafico perso. Salvataggio di recupero in corso…",
                "Graphics device lost. Saving a recovery copy…",
              ),
          );
        }
        if (type === "rh-editor-opened") {
          setError("");
          setNotice(
            t("Sorgente aperto nell’editor.", "Source opened in the editor."),
          );
        }
        if (type === "rh-editor-destination-settled") {
          setChoosingDestination(false);
          if (value.cancelled) setDirty(true);
        }
        if (type === "rh-editor-select" && value.name) {
          if (pendingSaves.current || unsaved.current)
            throw Error(
              t(
                "Salva prima le modifiche aperte.",
                "Save your current changes first.",
              ),
            );
          const selected = await api<Session>(`${base}/${s.id}/entry`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: value.name,
              expected_revision: s.revision,
            }),
          });
          current.current = selected;
          setSession(selected);
          setFile(selected.entry);
          loadedFrame.current = null;
          await sendFiles(nativeHost.current);
          if (!nativeHost.current)
            frame.current?.contentWindow?.postMessage(
              { type: "rh-editor-open" },
              location.origin,
            );
        }
        if (type === "rh-design-ready") {
          const r = await fetch(`${base}/${s.id}/files/${encoded(s.entry)}`);
          if (!r.ok) throw Error(String(r.status));
          const content = await r.text();
          frame.current?.contentWindow?.postMessage(
            {
              type: "rh-design-load",
              document:
                s.editor === "excalidraw"
                  ? (JSON.parse(content) as unknown)
                  : content,
            },
            location.origin,
          );
        }
        if (type === "rh-design-save")
          save(
            s.entry,
            typeof value.document === "string"
              ? value.document
              : JSON.stringify(value.document),
            true,
          );
      } catch (err) {
        setError(String(err));
      }
    }
    const handle = (e: MessageEvent<Message>) => {
      void onMessage(e);
    };
    window.addEventListener("message", handle);
    return () => window.removeEventListener("message", handle);
    // The iframe must retain unsaved state when the server revision changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);
  function downloadFailed(item: FailedSave) {
    const bytes =
      typeof item.data === "string"
        ? new TextEncoder().encode(item.data)
        : item.data;
    const link = document.createElement("a"),
      objectURL = URL.createObjectURL(new Blob([bytes as BlobPart]));
    link.href = objectURL;
    link.download = item.name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(objectURL), 1000);
  }
  async function chooseEntry(name: string) {
    if (
      !session ||
      busy ||
      choosingDestination ||
      pendingSaves.current > 0 ||
      failedSaves.length > 0 ||
      dirty ||
      running
    )
      return;
    setBusy(true);
    setError("");
    try {
      const value = await api<Session>(`${url}/entry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, expected_revision: session.revision }),
      });
      current.current = value;
      setSession(value);
      setFile(value.entry);
      setNotice(
        t(
          "Sorgente principale selezionato; riaprilo nell’editor per modificarlo.",
          "Primary source selected; reopen it in the editor to edit it.",
        ),
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function publish() {
    if (
      !session ||
      busy ||
      choosingDestination ||
      pendingSaves.current > 0 ||
      failedSaves.length > 0 ||
      dirty ||
      running
    )
      return;
    setBusy(true);
    setError("");
    try {
      await api(`${url}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: session.revision }),
      });
      setSession(await api<Session>(url));
      setNotice(
        t(
          "Revisione pubblicata. Torna in chat per chiederne l’integrazione; le esportazioni richiedono una nuova elaborazione.",
          "Revision published. Return to chat to request integration; exports need regeneration.",
        ),
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const primaryChoices =
    session?.files.filter((item) =>
      session.native_extensions.some((ext) =>
        item.name.toLowerCase().endsWith(ext),
      ),
    ) ?? [];
  const craft = session?.editor.endsWith("craft"),
    design = session?.editor === "bpmn" || session?.editor === "excalidraw";
  return (
    <main
      className="bg-background text-foreground flex h-dvh flex-col"
      data-testid="editor-workspace"
    >
      <header className="flex flex-wrap items-center gap-3 border-b p-3">
        <a
          className="underline"
          href={
            thread
              ? `/workspace/chats/${encodeURIComponent(thread)}`
              : "/workspace"
          }
        >
          ← {t("Conversazione", "Conversation")}
        </a>
        <h1
          className="max-w-[45vw] min-w-0 truncate font-semibold"
          title={session?.entry}
        >
          {session
            ? `${session.editor} · ${session.entry}`
            : t("Apertura editor…", "Opening editor…")}
        </h1>
        {session && showFiles && (
          <span className="text-xs">
            {session.editor === "jupyter"
              ? `CLI nbconvert ${session.cli_version ?? session.editor_version} · JupyterLab ${(status?.interface_version ?? "") !== "" ? status?.interface_version : t("da verificare", "not verified")}`
              : `v${session.editor_version.replace(/^v/, "")}`}{" "}
            ·{" "}
            {session.mode === "project"
              ? t("cartella condivisa", "shared folder")
              : t("bozza", "draft")}{" "}
            {session.revision}
            {session.version_origin?.startsWith("source_")
              ? ` · ${t("versione del sorgente", "source version")}`
              : session.version_origin === "default"
                ? ` · ${t("versione predefinita", "default version")}`
                : ""}
          </span>
        )}
        {session && showFiles && (
          <span
            className="text-xs"
            title={
              interactive
                ? t(
                    "La sessione si chiude uscendo dall’editor; software e bozze hanno una conservazione separata.",
                    "The session closes when you leave the editor; software and drafts have separate retention.",
                  )
                : t(
                    "L’applicazione gira nel browser, senza creare una sandbox.",
                    "The application runs in the browser without creating a sandbox.",
                  )
            }
          >
            {interactive
              ? t("Sessione server temporanea", "Temporary server session")
              : t("Nel browser · nessuna sandbox", "In browser · no sandbox")}
          </span>
        )}
        {showFiles &&
          (status?.environment_profile ?? session?.environment_profile) && (
            <a
              className="rounded border px-3 py-1 text-sm"
              target="_blank"
              rel="noopener noreferrer"
              href={`/workspace/environments?focus=${encodeURIComponent(status?.environment_profile ?? session?.environment_profile ?? "")}`}
            >
              {t("Gestisci ambiente", "Manage environment")}
            </a>
          )}
        <div className="ml-auto flex flex-wrap gap-2">
          {session?.editor === "jupyter" ? (
            <button
              className="rounded border px-3 py-1"
              disabled={status?.state !== "ready"}
              onClick={() =>
                frame.current?.contentWindow?.postMessage(
                  { type: "rh-lab-terminal" },
                  location.origin,
                )
              }
            >
              {t("Terminale", "Terminal")}
            </button>
          ) : session?.editor === "text" ? (
            <button
              className="rounded border px-3 py-1"
              onClick={() => {
                void api<{
                  environments: {
                    name: string;
                    display_name: string;
                    runtime: { status: string };
                  }[];
                }>(`${getBackendBaseURL()}/api/harness/environments`)
                  .then((result) => {
                    const rows = result.environments.filter(
                      (item) => item.runtime.status === "ready",
                    );
                    setTerminalOptions(rows);
                    setTerminalEnvironment(rows[0]?.name ?? "");
                  })
                  .catch((e: unknown) => setError(String(e)));
              }}
            >
              {t("Terminale", "Terminal")}
            </button>
          ) : session ? (
            <a
              className="rounded border px-3 py-1"
              target="_blank"
              rel="noopener noreferrer"
              href={`/terminal?thread=${encodeURIComponent(thread)}&editor=${encodeURIComponent(session.id)}`}
            >
              {t("Terminale", "Terminal")} ↗
            </a>
          ) : null}
          <button
            className="rounded border px-3 py-1"
            onClick={() => setShowFiles(!showFiles)}
            aria-expanded={showFiles}
          >
            {t("File e dettagli", "Files and details")}
          </button>
          <button
            className="rounded border px-3 py-1"
            onClick={() => {
              if (document.fullscreenElement) void document.exitFullscreen();
              else
                void (frame.current ?? document.documentElement)
                  .requestFullscreen()
                  .catch((e: unknown) => setError(String(e)));
            }}
          >
            {t("Schermo intero", "Full screen")}
          </button>
          {session?.editor === "effectcraft" && (
            <select
              disabled={busy || choosingDestination}
              aria-label={t("Rendering EffectCraft", "EffectCraft rendering")}
              className="rounded border px-2 py-1"
              value={effectRenderer}
              onChange={(event) => {
                if (
                  !confirm(
                    t(
                      "Salva le modifiche prima di cambiare modalità. L’editor verrà riaperto dal file sul server. Continuare?",
                      "Save your changes before changing mode. The editor will reopen the file saved on the server. Continue?",
                    ),
                  )
                )
                  return;
                loadedFrame.current = null;
                nativeHost.current = false;
                setEffectRenderer(event.target.value);
              }}
            >
              <option value="compatible">
                {t(
                  "Compatibilità · RAM ridotta",
                  "Compatibility · reduced RAM",
                )}
              </option>
              <option value="accelerated">
                {t("Accelerazione GPU", "GPU acceleration")}
              </option>
            </select>
          )}
          {showFiles && primaryChoices.length > 1 && (
            <select
              aria-label={t("Sorgente principale", "Primary source")}
              className="max-w-64 rounded border px-2 py-1"
              value={session?.entry}
              disabled={
                busy || dirty || failedSaves.length > 0 || Boolean(running)
              }
              onChange={(event) => void chooseEntry(event.target.value)}
            >
              {primaryChoices.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name}
                </option>
              ))}
            </select>
          )}
          {craft && status?.state === "ready" && (
            <button
              className="rounded border px-3 py-1"
              disabled={busy || choosingDestination || !sourceReady}
              onClick={() =>
                frame.current?.contentWindow?.postMessage(
                  { type: "rh-editor-save-current" },
                  location.origin,
                )
              }
            >
              {t("Salva nella chat", "Save to chat")}
            </button>
          )}
          {craft && status?.state === "ready" && (
            <button
              className="rounded border px-3 py-1"
              disabled={busy || choosingDestination || !sourceReady}
              onClick={() => void reopenSource()}
            >
              {t("Apri sorgente", "Open source")}
            </button>
          )}
          {session && (
            <button
              type="button"
              className="rounded border px-3 py-1"
              disabled={
                busy ||
                dirty ||
                failedSaves.length > 0 ||
                (Boolean(running) && session?.mode !== "project")
              }
              onClick={() => setSwitchEditor(!switchEditor)}
            >
              {t("Cambia editor", "Change editor")}
            </button>
          )}
          {session?.editor === "text" && (
            <button
              className="rounded border px-3 py-1"
              disabled={busy || !dirty}
              onClick={() => save(file, text, file === session.entry)}
            >
              {t("Salva file", "Save file")}
            </button>
          )}
          {showFiles && running && (
            <button
              className="rounded border px-3 py-1"
              onClick={() => {
                if (
                  confirm(
                    t(
                      "Hai salvato nell’editor? La chiusura conserva i file salvati e interrompe il programma.",
                      "Have you saved in the editor? Closing keeps saved files and stops the program.",
                    ),
                  )
                )
                  void api(`${url}/service`, { method: "DELETE" }).catch((e) =>
                    setError(String(e)),
                  );
              }}
            >
              {t("Chiudi ambiente", "Close environment")}
            </button>
          )}
          {session?.mode !== "project" && (
            <button
              className="bg-primary text-primary-foreground rounded px-3 py-1 disabled:opacity-50"
              disabled={
                !session ||
                busy ||
                dirty ||
                failedSaves.length > 0 ||
                Boolean(running) ||
                session.published_revision === session.revision ||
                !session.native_extensions.some((ext) =>
                  session.entry.toLowerCase().endsWith(ext),
                )
              }
              onClick={() => void publish()}
            >
              {t("Pubblica revisione", "Publish revision")}
            </button>
          )}
        </div>
      </header>
      {terminalOptions && session && (
        <section
          className="flex flex-wrap items-center gap-2 border-b p-3"
          aria-label={t("Ambiente del terminale", "Terminal environment")}
        >
          {terminalOptions.length ? (
            <>
              <label>
                {t("Ambiente pronto", "Ready environment")}{" "}
                <select
                  value={terminalEnvironment}
                  onChange={(event) =>
                    setTerminalEnvironment(event.target.value)
                  }
                >
                  {terminalOptions.map((item) => (
                    <option key={item.name} value={item.name}>
                      {item.display_name}
                    </option>
                  ))}
                </select>
              </label>
              <a
                className="rounded border px-3 py-1"
                target="_blank"
                rel="noopener noreferrer"
                href={`/terminal?thread=${encodeURIComponent(thread)}&editor=${encodeURIComponent(session.id)}&environment=${encodeURIComponent(terminalEnvironment)}`}
              >
                {t("Apri terminale", "Open terminal")} ↗
              </a>
            </>
          ) : (
            <p>
              {t(
                "Prepara un ambiente dalla pagina Ambienti per eseguire il codice di questo progetto.",
                "Prepare an environment from Environments to run this project's code.",
              )}{" "}
              <a
                className="underline"
                href="/workspace/environments"
                target="_blank"
                rel="noopener noreferrer"
              >
                {t("Ambienti", "Environments")}
              </a>
            </p>
          )}
          <button
            className="rounded border px-3 py-1"
            onClick={() => setTerminalOptions(null)}
          >
            {t("Chiudi", "Close")}
          </button>
        </section>
      )}
      {switchEditor && session && (
        <section className="space-y-2 border-b p-3">
          <p className="text-xs">
            {t(
              session.mode === "project"
                ? "Scegli un altro editor per lo stesso file e la stessa cartella."
                : "Apri la bozza salvata, incluse le risorse, in un’altra applicazione.",
              session.mode === "project"
                ? "Choose another editor for the same file and folder."
                : "Open the saved draft, including its assets, in another application.",
            )}
          </p>
          <EditorLauncher
            threadId={thread}
            path={
              session.mode === "project"
                ? (session.virtual_path ??
                  `/mnt/user-data/${session.project_root}/${session.entry}`)
                : session.source
            }
            draftSession={session.mode === "project" ? undefined : session.id}
            showUnavailable
          />
        </section>
      )}
      {(showFiles || session?.mode !== "project") && (
        <p className="border-b px-3 py-2 text-xs">
          {t(
            session?.mode === "project"
              ? "Modifiche dirette ai file della chat: salva nell’editor. Non serve pubblicare. Nei terminali: progetto in /workspace/output, altre cartelle in /workspace/chat."
              : "Lavora sulla tua copia. Salva nell’editor, poi pubblica per passarla alla squadra.",
            session?.mode === "project"
              ? "Edit chat files directly: save in the editor. No publication step. Terminals: project at /workspace/output, other folders at /workspace/chat."
              : "Work on your copy. Save in the editor, then publish to hand it to the team.",
          )}
          {dirty ? ` · ${t("Modifiche da salvare", "Unsaved changes")}` : ""}
        </p>
      )}
      {showFiles && session && !session.native_extensions.length && (
        <p className="border-b px-3 py-2 text-sm">
          {t(
            "Editor in anteprima: puoi scaricare le esportazioni. La pubblicazione di un sorgente completo non è ancora disponibile.",
            "Preview editor: exports can be downloaded. Complete source publication is not available yet.",
          )}
        </p>
      )}
      {session?.missing_dependencies?.length ? (
        <p role="alert" className="border-b p-2 text-sm">
          {t("Risorse da verificare: ", "Assets to check: ")}
          {session.missing_dependencies.join(", ")}
        </p>
      ) : null}
      {error && (
        <div
          role="alert"
          className="flex gap-3 bg-red-50 p-3 text-sm text-red-900"
        >
          <p>{error}</p>
          <button className="ml-auto" onClick={() => setError("")}>
            ×
          </button>
        </div>
      )}
      {failedSaves.length > 0 && (
        <section
          className="space-y-2 border-b p-3 text-sm"
          aria-label={t("Salvataggi da recuperare", "Pending saves to recover")}
        >
          <p>
            {t(
              "Queste modifiche sono ancora in questa finestra. Puoi riprovare il salvataggio o scaricare una copia prima di chiuderla.",
              "These changes are still in this window. Retry saving or download a copy before closing it.",
            )}
          </p>
          {failedSaves.map((item) => (
            <div key={item.name} className="flex flex-wrap items-center gap-2">
              <span className="break-all">{item.name}</span>
              <button
                disabled={busy}
                className="rounded border px-2 py-1"
                onClick={() =>
                  save(item.name, item.data, item.entry, item.requestId)
                }
              >
                {t("Riprova salvataggio", "Retry save")}
              </button>
              <button
                className="rounded border px-2 py-1"
                onClick={() => downloadFailed(item)}
              >
                {t("Scarica copia", "Download copy")}
              </button>
            </div>
          ))}
        </section>
      )}
      {notice && (
        <p role="status" className="px-3 py-2 text-sm">
          {notice}
        </p>
      )}
      <div className="flex min-h-0 flex-1">
        {showFiles && (
          <aside className="w-64 shrink-0 overflow-auto border-r p-3 text-xs max-sm:w-32">
            <h2 className="font-semibold">
              {t("Sorgente e risorse", "Source and assets")}
            </h2>
            {session?.files_truncated && (
              <p>
                {t(
                  "Elenco parziale. Usa il file browser dell’editor per esplorare l’intera cartella.",
                  "Partial listing. Use the editor file browser to explore the complete folder.",
                )}
              </p>
            )}
            {session?.files.map((f) => (
              <button
                key={f.name}
                className="block w-full py-2 text-left break-all disabled:opacity-50"
                disabled={
                  (Boolean(running) && session?.mode !== "project") || busy
                }
                onClick={() => {
                  if (
                    session.editor === "text" &&
                    session.native_extensions.some((ext) =>
                      f.name.toLowerCase().endsWith(ext),
                    ) &&
                    (!dirty ||
                      confirm(
                        t(
                          "Scartare le modifiche non salvate?",
                          "Discard unsaved changes?",
                        ),
                      ))
                  )
                    setFile(f.name);
                  else if (
                    session.editor.endsWith("craft") &&
                    frame.current?.contentWindow
                  ) {
                    const target = frame.current.contentWindow;
                    void fetch(`${url}/files/${encoded(f.name)}`)
                      .then(async (r) => {
                        if (!r.ok) throw Error(String(r.status));
                        target.postMessage(
                          {
                            type: "rh-editor-resource",
                            name: f.name,
                            bytes: await r.arrayBuffer(),
                          },
                          location.origin,
                        );
                      })
                      .catch((e: unknown) => setError(String(e)));
                  } else if (
                    session.editor !== "text" ||
                    !session.native_extensions.some((ext) =>
                      f.name.toLowerCase().endsWith(ext),
                    )
                  ) {
                    const link = document.createElement("a");
                    link.href = `${url}/files/${encoded(f.name)}`;
                    link.download = f.name;
                    link.click();
                  }
                }}
              >
                {f.name.startsWith("@chat/") ? f.name.slice(6) : f.name}
                {f.name === session.entry ? " ★" : ""}
                <span className="text-muted-foreground block">
                  {Math.ceil(f.bytes / 1024)} KiB
                </span>
              </button>
            ))}
            <label className="mt-3 block cursor-pointer rounded border p-2">
              {running
                ? t(
                    "Chiudi l’ambiente per aggiungere risorse",
                    "Close the environment to add assets",
                  )
                : t("Aggiungi risorse", "Add assets")}
              <input
                className="sr-only"
                type="file"
                multiple
                disabled={
                  (Boolean(running) && session?.mode !== "project") || busy
                }
                onChange={(e) => {
                  for (const f of Array.from(e.target.files ?? []))
                    void f
                      .arrayBuffer()
                      .then((data) => save(f.name, data, false))
                      .catch((err) => setError(String(err)));
                }}
              />
            </label>
            {Boolean(session?.publications.length) && (
              <h2 className="mt-5 font-semibold">
                {t("Revisioni pubblicate", "Published revisions")}
              </h2>
            )}
            {session?.publications
              .slice()
              .reverse()
              .map((p) => (
                <a
                  className="mt-2 block underline"
                  key={p.path}
                  target="_blank"
                  rel="noopener noreferrer"
                  href={buildArtifactViewerURL({
                    filepath: p.path,
                    threadId: thread,
                    isMock: false,
                  })}
                >
                  {t("Apri revisione", "Open revision")} {p.revision}
                </a>
              ))}
          </aside>
        )}
        <section className="min-h-0 min-w-0 flex-1">
          {session?.editor === "text" ? (
            <CodeMirror
              className="h-full"
              height="100%"
              value={text}
              onChange={(value) => {
                setText(value);
                setDirty(true);
              }}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === "s") {
                  e.preventDefault();
                  save(file, text, file === session.entry);
                }
              }}
            />
          ) : design ? (
            <iframe
              ref={frame}
              title={session.editor}
              className="h-full w-full border-0"
              src={`/rh-design/${session.editor}/index.html`}
              sandbox="allow-scripts allow-same-origin allow-downloads allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox"
              allow="fullscreen; clipboard-read; clipboard-write"
              allowFullScreen
            />
          ) : craft && status?.state === "ready" ? (
            <iframe
              ref={frame}
              title={session?.editor}
              className="h-full w-full border-0"
              src={`${url}/app/index.html?host=parent&empty&nosw${session?.editor === "effectcraft" ? `&storage=memory&rh-renderer=${effectRenderer}${effectRenderer === "compatible" ? "&noworkers" : "&frameworkers=1&nogpuworkers"}` : ""}`}
              sandbox="allow-scripts allow-same-origin allow-downloads allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox"
              allow="fullscreen; clipboard-read; clipboard-write"
              allowFullScreen
            />
          ) : interactive && status?.state === "ready" ? (
            <iframe
              ref={frame}
              title={session?.editor}
              className="h-full w-full border-0"
              src={status.url}
              sandbox="allow-scripts allow-same-origin allow-downloads allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox"
              allow="fullscreen; clipboard-read; clipboard-write"
              allowFullScreen
            />
          ) : (
            <div className="p-8">
              <p>
                {status?.message ??
                  t("Preparazione editor…", "Preparing editor…")}
              </p>
              {status && ["failed", "stopped"].includes(status.state) && (
                <button
                  className="mt-3 rounded border px-3 py-2"
                  onClick={() => location.reload()}
                >
                  {t("Riprova", "Retry")}
                </button>
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
