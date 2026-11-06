"use client";

import {useEffect,useRef,useState} from "react";
import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";
import {tr, useUiLanguage} from "@/core/i18n/ui-text";

type Session={id:string;profile:string;assignment?:string;retained_until?:number|null;finished:boolean;closing?:boolean;error?:string;output_base64?:string;cursor?:number;output_end?:number;reset?:boolean;limits?:{cpus:number;memory_mib:number}};
type Disposable={dispose:()=>void};
type Terminal={cols:number;rows:number;open:(element:HTMLElement)=>void;write:(text:string|Uint8Array)=>void;reset:()=>void;focus:()=>void;dispose:()=>void;loadAddon:(addon:unknown)=>void;onData:(callback:(data:string)=>void)=>Disposable;onResize:(callback:(size:{cols:number;rows:number})=>void)=>Disposable};
type Fit={fit:()=>void};
type Libraries={Terminal:new(options:Record<string,unknown>)=>Terminal;FitAddon:{FitAddon:new()=>Fit}};
const assets=new Map<string,Promise<void>>();
function script(url:string){let pending=assets.get(url);if(!pending){pending=new Promise<void>((resolve,reject)=>{const tag=document.createElement("script");tag.src=url;tag.onload=()=>resolve();tag.onerror=()=>{assets.delete(url);tag.remove();reject(Error(tr("Caricamento del terminale non riuscito", "Terminal failed to load")));};document.head.append(tag);});assets.set(url,pending);}return pending;}

export default function EnvironmentTerminalPage(){useUiLanguage();
 const host=useRef<HTMLDivElement>(null),screen=useRef<Terminal|null>(null),sessionRef=useRef<Session|null>(null);
 const input=useRef<(text:string)=>void>(()=>{}),[session,setSession]=useState<Session|null>(null),[error,setError]=useState("");
 const [phase,setPhase]=useState(tr("Avvio del terminale…", "Starting the terminal…")),[attempt,setAttempt]=useState(0),[closing,setClosing]=useState(false);
 const [retaining,setRetaining]=useState(false);
 const base=`${getBackendBaseURL()}/api/harness/environments`;
 useEffect(()=>{
  const clientId=crypto.randomUUID().replaceAll("-","");
  const controller=new AbortController();let released=false,disposed=false,term:Terminal|undefined,observer:ResizeObserver|undefined;
  let cursor=0,pending="",sending=false,inputBlocked=false,sendTimer:ReturnType<typeof setTimeout>|undefined,lastSize="",resizeBusy=false;
  const disposables:Disposable[]=[];
  const params=new URLSearchParams(location.search),environment=params.get("environment")||"",thread=params.get("thread"),job=params.get("job"),editor=params.get("editor"),existing=params.get("session");
  const startUrl=thread&&editor?`${getBackendBaseURL()}/api/threads/${encodeURIComponent(thread)}/editors/${encodeURIComponent(editor)}/terminal?environment=${encodeURIComponent(environment)}`:existing?`${base}/terminals/${encodeURIComponent(existing)}/reconnect`:thread&&job?`${base}/assignments/${encodeURIComponent(thread)}/${encodeURIComponent(job)}/terminal`:`${base}/${encodeURIComponent(environment)}/terminal`;
  function release(){
   if(released)return;released=true;
   const url=`${base}/terminal-clients/${clientId}/close`;
   try{if(navigator.sendBeacon(url,new Blob([],{type:"text/plain"})))return;}catch{/* Use keepalive when the browser rejects a beacon. */}
   void window.fetch(url,{method:"POST",credentials:"include",keepalive:true}).catch(()=>{});
  }
  window.addEventListener("pagehide",release);window.addEventListener("beforeunload",release);

  async function send(){
   if(sending||!pending||disposed||!sessionRef.current)return;
   sending=true;const text=Array.from(pending).slice(0,4096).join("");pending=pending.slice(text.length);
   try{const r=await fetch(`${base}/terminals/${sessionRef.current.id}/input`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text}),signal:controller.signal});if(!r.ok)throw Error(tr("Input non confermato: verifica la sessione prima di inviarlo nuovamente.", "Input not confirmed: check the session before sending it again."));}
   catch(e){pending="";inputBlocked=true;if(!disposed)setError(e instanceof Error?e.message:tr("Collegamento interrotto", "Connection lost"));}
   finally{sending=false;if(pending&&!disposed)void send();}
  }
  input.current=(text)=>{if(disposed||inputBlocked||sessionRef.current?.finished)return;if(pending.length+text.length>65536){setError(tr("Input troppo lungo: incolla il contenuto in parti più piccole.", "Input too long: paste the content in smaller parts."));return;}pending+=text;if(!sendTimer)sendTimer=setTimeout(()=>{sendTimer=undefined;void send();},8);};
  async function resize(){
   if(!term||!sessionRef.current||sessionRef.current.finished||disposed||resizeBusy)return;
   const size=`${term.cols}:${term.rows}`;if(size===lastSize)return;resizeBusy=true;
   try{const r=await fetch(`${base}/terminals/${sessionRef.current.id}/resize`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({cols:Math.min(1000,Math.max(2,term.cols)),rows:Math.min(500,Math.max(2,term.rows))}),signal:controller.signal});if(r.ok)lastSize=size;}
   catch{/* Retry after the next output poll; the Docker PTY may still be starting. */}
   finally{resizeBusy=false;}
  }
  async function run(){
   if(!environment&&!existing&&!(thread&&(job||editor))){setError(tr("Ambiente non specificato. Apri il terminale dalla pagina Ambienti.", "Environment not specified. Open the terminal from the Environments page."));return;}
   try{
    if(!document.querySelector('link[data-skill-terminal]')){const css=document.createElement("link");css.rel="stylesheet";css.href="/rh-terminal/xterm.css";css.dataset.righavenTerminal="true";document.head.append(css);}
    await script("/rh-terminal/xterm.js");await script("/rh-terminal/addon-fit.js");if(disposed||!host.current)return;
    const libraries=window as unknown as Libraries;
    term=new libraries.Terminal({cursorBlink:true,fontSize:14,fontFamily:"ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",scrollback:5000,theme:{background:"#09090b",foreground:"#e4e4e7",cursor:"#a3e635"},allowProposedApi:false});
    const fit=new libraries.FitAddon.FitAddon();term.loadAddon(fit);term.open(host.current);screen.current=term;
    observer=new ResizeObserver(()=>{fit.fit();void resize();});observer.observe(host.current);fit.fit();term.focus();
    disposables.push(term.onData(text=>input.current(text)),term.onResize(()=>void resize()));
    setPhase(thread&&editor?tr("Apro il terminale sul progetto; se necessario preparo i programmi dell’editor…", "Opening the project terminal; preparing editor software if needed…"):tr("Richiedo lo slot; un precaricamento facoltativo può essere sospeso…", "Requesting the slot; an optional preload may be suspended…"));
    const r=await fetch(startUrl,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({client_id:clientId}),signal:controller.signal});
    const initial:Session&{detail?:string}=await r.json();if(!r.ok)throw Error(initial.detail||tr("Terminale non disponibile", "Terminal unavailable"));if(disposed)return;
    sessionRef.current=initial;setSession(initial);setPhase(tr("Connesso", "Connected"));void resize();
    while(!disposed){
     const response=await fetch(`${base}/terminals/${initial.id}/status?after=${cursor}`,{signal:controller.signal});
     if(!response.ok)throw Error(response.status===404?tr("Sessione non più disponibile", "Session no longer available"):tr("Collegamento al terminale interrotto", "Terminal connection lost"));
     const value:Session=await response.json();if(disposed)return;
     if(value.reset){term.reset();term.write(tr("\u001b[33mUna parte dell’output precedente non è più disponibile.\u001b[0m\r\n", "\u001b[33mPart of the earlier output is no longer available.\u001b[0m\r\n"));}
     if(value.output_base64){const bytes=Uint8Array.from(atob(value.output_base64),c=>c.charCodeAt(0));term.write(bytes);}
     cursor=value.cursor??cursor;sessionRef.current=value;setSession(value);void resize();
     if(value.error)setError(value.error);
     if(value.finished&&cursor>=(value.output_end??cursor)){setPhase(value.error?tr("Chiusura da verificare", "Shutdown to verify"):tr("Sessione terminata · risorse liberate", "Session ended · resources released"));term.write(tr("\r\n\u001b[90mSessione terminata.\u001b[0m\r\n", "\r\n\u001b[90mSession ended.\u001b[0m\r\n"));break;}
     setPhase(value.closing?tr("Chiusura della sandbox…", "Closing the sandbox…"):tr("Connesso", "Connected"));
    }
   }catch(e){if(!disposed){setError(e instanceof Error?e.message:tr("Terminale non raggiungibile", "Terminal unreachable"));setPhase(tr("Collegamento non disponibile", "Connection unavailable"));}}
  }
  void run();
  return()=>{disposed=true;window.removeEventListener("pagehide",release);window.removeEventListener("beforeunload",release);release();controller.abort();if(sendTimer)clearTimeout(sendTimer);observer?.disconnect();for(const d of disposables)d.dispose();term?.dispose();screen.current=null;input.current=()=>{};};
 },[base,attempt]);
 async function stop(){const value=sessionRef.current;if(!value||value.finished)return;setClosing(true);try{const r=await fetch(`${base}/terminals/${value.id}`,{method:"DELETE"});if(!r.ok)throw Error(tr("Chiusura non confermata", "Shutdown not confirmed"));setPhase(tr("Chiusura richiesta; attendo il rilascio delle risorse…", "Shutdown requested; waiting for resources to be released…"));}catch(e){setClosing(false);setError(e instanceof Error?e.message:tr("Chiusura non confermata", "Shutdown not confirmed"));}}
 async function retain(minutes:number){const value=sessionRef.current;if(!value||value.finished)return;setRetaining(true);setError("");try{const r=await fetch(`${base}/terminals/${value.id}/retention`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({minutes})});const next=await r.json();if(!r.ok)throw Error(next.detail??tr("Conservazione non confermata", "Retention not confirmed"));sessionRef.current=next;setSession(next);}catch(e){setError(e instanceof Error?e.message:tr("Conservazione non confermata", "Retention not confirmed"));}finally{setRetaining(false);}}
 return <main className="fixed inset-0 flex flex-col bg-zinc-950 text-zinc-100" data-testid="terminal-window">
  <header className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-zinc-800 px-4 py-3"><div><h1 className="font-semibold">{tr("Terminale ·", "Terminal ·")} {session?.profile||"ambiente"}</h1><p role="status" className="text-xs text-zinc-400">{phase}{session?.limits?tr(` · massimo ${session.limits.cpus} CPU / ${session.limits.memory_mib} MiB RAM`, ` · maximum ${session.limits.cpus} CPU / ${session.limits.memory_mib} MiB RAM`):""}</p></div><div className="flex gap-2"><button className="rounded border border-zinc-700 px-3 py-2 text-sm" onClick={()=>{input.current("\x03");screen.current?.focus();}}>Ctrl+C</button><button disabled={closing||!session||session.finished} className="rounded border border-zinc-700 px-3 py-2 text-sm disabled:opacity-50" onClick={()=>void stop()}>{tr("Termina sessione", "End session")}</button><a className="rounded border border-zinc-700 px-3 py-2 text-sm" href="/workspace/environments">{tr("Ambienti", "Environments")}</a></div></header>
  {session&&!session.finished&&<div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-zinc-800 px-4 py-2 text-xs"><span>{session.retained_until?tr(`Conservato fino alle ${new Date(session.retained_until*1000).toLocaleTimeString()}`,`Kept until ${new Date(session.retained_until*1000).toLocaleTimeString()}`):tr("Chiusura automatica quando esci", "Closes automatically when you leave")}</span><button disabled={retaining||closing} className="rounded border border-zinc-700 px-2 py-1 disabled:opacity-50" onClick={()=>void retain(10)}>{tr("Mantieni per 10 minuti", "Keep for 10 minutes")}</button><button disabled={retaining||closing} className="rounded border border-zinc-700 px-2 py-1 disabled:opacity-50" onClick={()=>void retain(30)}>{tr("Mantieni per 30 minuti", "Keep for 30 minutes")}</button>{session.retained_until&&<button disabled={retaining||closing} className="rounded border border-zinc-700 px-2 py-1 disabled:opacity-50" onClick={()=>void retain(0)}>{tr("Ripristina chiusura automatica", "Restore automatic closing")}</button>}</div>}
  {error&&<p role="alert" className="shrink-0 border-b border-red-900 px-4 py-2 text-sm text-red-300">{error}</p>}
  {(error||session?.finished)&&<button className="m-2 self-start rounded border border-zinc-700 px-3 py-2 text-sm" onClick={()=>{setError("");setClosing(false);setSession(null);sessionRef.current=null;setAttempt(value=>value+1);}}>{tr("Riconnetti o apri una nuova sessione", "Reconnect or open a new session")}</button>}
  <div ref={host} className="min-h-0 flex-1 overflow-hidden p-2" aria-label={tr("Terminale interattivo", "Interactive terminal")}/>
  <footer className="shrink-0 border-t border-zinc-800 px-4 py-2 text-xs text-zinc-400">{session?.assignment?tr("Stessi programmi dell’incarico; progetto in /workspace/project e file provvisori, se presenti, in /workspace/output, entrambi in sola lettura. Credenziali e processi dello specialista esclusi. Le modifiche locali del terminale non diventano consegne.","Same assignment software; read-only project at /workspace/project and temporary files, when present, at /workspace/output. No specialist credentials or processes. Local terminal changes do not become deliveries."):tr("Sandbox temporanea senza credenziali o progetti montati.","Temporary sandbox with no credentials or projects mounted.")} {tr("Chiudere la pagina termina la sessione, salvo conservazione esplicita a tempo. Senza collegamento, recupero entro 60 secondi; durata totale massima 30 minuti. La conservazione occupa risorse. Puoi riaprire o terminare la sessione dalla pagina Ambienti.","Closing the page ends the session unless explicitly kept for a limited time. Without a connection, reclaimed within 60 seconds; maximum total duration 30 minutes. Kept sessions use resources. Reopen or end the session from Environments.")}</footer>
 </main>;
}
