"use client";

import {useEffect,useRef,useState} from "react";
import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";

type Session={id:string;profile:string;finished:boolean;closing?:boolean;error?:string;output_base64?:string;cursor?:number;output_end?:number;reset?:boolean;limits?:{cpus:number;memory_mib:number}};
type Disposable={dispose:()=>void};
type Terminal={cols:number;rows:number;open:(element:HTMLElement)=>void;write:(text:string|Uint8Array)=>void;reset:()=>void;focus:()=>void;dispose:()=>void;loadAddon:(addon:unknown)=>void;onData:(callback:(data:string)=>void)=>Disposable;onResize:(callback:(size:{cols:number;rows:number})=>void)=>Disposable};
type Fit={fit:()=>void};
type Libraries={Terminal:new(options:Record<string,unknown>)=>Terminal;FitAddon:{FitAddon:new()=>Fit}};
const assets=new Map<string,Promise<void>>();
function script(url:string){let pending=assets.get(url);if(!pending){pending=new Promise<void>((resolve,reject)=>{const tag=document.createElement("script");tag.src=url;tag.onload=()=>resolve();tag.onerror=()=>{assets.delete(url);tag.remove();reject(Error("Caricamento del terminale non riuscito"));};document.head.append(tag);});assets.set(url,pending);}return pending;}

export default function EnvironmentTerminalPage(){
 const host=useRef<HTMLDivElement>(null),screen=useRef<Terminal|null>(null),sessionRef=useRef<Session|null>(null);
 const input=useRef<(text:string)=>void>(()=>{}),[session,setSession]=useState<Session|null>(null),[error,setError]=useState("");
 const [phase,setPhase]=useState("Avvio del terminale…"),[attempt,setAttempt]=useState(0),[closing,setClosing]=useState(false);
 const base=`${getBackendBaseURL()}/api/harness/environments`;
 useEffect(()=>{
  const clientId=crypto.randomUUID().replaceAll("-","");
  const controller=new AbortController();let released=false,disposed=false,term:Terminal|undefined,observer:ResizeObserver|undefined;
  let cursor=0,pending="",sending=false,inputBlocked=false,sendTimer:ReturnType<typeof setTimeout>|undefined,lastSize="",resizeBusy=false;
  const disposables:Disposable[]=[];
  const environment=new URLSearchParams(location.search).get("environment")||"";
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
   try{const r=await fetch(`${base}/terminals/${sessionRef.current.id}/input`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text}),signal:controller.signal});if(!r.ok)throw Error("Input non confermato: verifica la sessione prima di inviarlo nuovamente.");}
   catch(e){pending="";inputBlocked=true;if(!disposed)setError(e instanceof Error?e.message:"Collegamento interrotto");}
   finally{sending=false;if(pending&&!disposed)void send();}
  }
  input.current=(text)=>{if(disposed||inputBlocked||sessionRef.current?.finished)return;if(pending.length+text.length>65536){setError("Input troppo lungo: incolla il contenuto in parti più piccole.");return;}pending+=text;if(!sendTimer)sendTimer=setTimeout(()=>{sendTimer=undefined;void send();},8);};
  async function resize(){
   if(!term||!sessionRef.current||sessionRef.current.finished||disposed||resizeBusy)return;
   const size=`${term.cols}:${term.rows}`;if(size===lastSize)return;resizeBusy=true;
   try{const r=await fetch(`${base}/terminals/${sessionRef.current.id}/resize`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({cols:Math.min(1000,Math.max(2,term.cols)),rows:Math.min(500,Math.max(2,term.rows))}),signal:controller.signal});if(r.ok)lastSize=size;}
   catch{/* Retry after the next output poll; the Docker PTY may still be starting. */}
   finally{resizeBusy=false;}
  }
  async function run(){
   if(!environment){setError("Ambiente non specificato. Apri il terminale dalla pagina Ambienti.");return;}
   try{
    if(!document.querySelector('link[data-skill-terminal]')){const css=document.createElement("link");css.rel="stylesheet";css.href="/rh-terminal/xterm.css";css.dataset.righavenTerminal="true";document.head.append(css);}
    await script("/rh-terminal/xterm.js");await script("/rh-terminal/addon-fit.js");if(disposed||!host.current)return;
    const libraries=window as unknown as Libraries;
    term=new libraries.Terminal({cursorBlink:true,fontSize:14,fontFamily:"ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",scrollback:5000,theme:{background:"#09090b",foreground:"#e4e4e7",cursor:"#a3e635"},allowProposedApi:false});
    const fit=new libraries.FitAddon.FitAddon();term.loadAddon(fit);term.open(host.current);screen.current=term;
    observer=new ResizeObserver(()=>{fit.fit();void resize();});observer.observe(host.current);fit.fit();term.focus();
    disposables.push(term.onData(text=>input.current(text)),term.onResize(()=>void resize()));
    setPhase("Richiedo lo slot; un precaricamento facoltativo può essere sospeso…");
    const r=await fetch(`${base}/${encodeURIComponent(environment)}/terminal`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({client_id:clientId}),signal:controller.signal});
    const initial:Session&{detail?:string}=await r.json();if(!r.ok)throw Error(initial.detail||"Terminale non disponibile");if(disposed)return;
    sessionRef.current=initial;setSession(initial);setPhase("Connesso");void resize();
    while(!disposed){
     const response=await fetch(`${base}/terminals/${initial.id}/status?after=${cursor}`,{signal:controller.signal});
     if(!response.ok)throw Error(response.status===404?"Sessione non più disponibile":"Collegamento al terminale interrotto");
     const value:Session=await response.json();if(disposed)return;
     if(value.reset){term.reset();term.write("\x1b[33mUna parte dell’output precedente non è più disponibile.\x1b[0m\r\n");}
     if(value.output_base64){const bytes=Uint8Array.from(atob(value.output_base64),c=>c.charCodeAt(0));term.write(bytes);}
     cursor=value.cursor??cursor;sessionRef.current=value;setSession(value);void resize();
     if(value.error)setError(value.error);
     if(value.finished&&cursor>=(value.output_end??cursor)){setPhase(value.error?"Chiusura da verificare":"Sessione terminata · risorse liberate");term.write("\r\n\x1b[90mSessione terminata.\x1b[0m\r\n");break;}
     setPhase(value.closing?"Chiusura della sandbox…":"Connesso");
    }
   }catch(e){if(!disposed){setError(e instanceof Error?e.message:"Terminale non raggiungibile");setPhase("Collegamento non disponibile");}}
  }
  void run();
  return()=>{disposed=true;window.removeEventListener("pagehide",release);window.removeEventListener("beforeunload",release);release();controller.abort();if(sendTimer)clearTimeout(sendTimer);observer?.disconnect();for(const d of disposables)d.dispose();term?.dispose();screen.current=null;input.current=()=>{};};
 },[base,attempt]);
 async function stop(){const value=sessionRef.current;if(!value||value.finished)return;setClosing(true);try{const r=await fetch(`${base}/terminals/${value.id}`,{method:"DELETE"});if(!r.ok)throw Error("Chiusura non confermata");setPhase("Chiusura richiesta; attendo il rilascio delle risorse…");}catch(e){setClosing(false);setError(e instanceof Error?e.message:"Chiusura non confermata");}}
 return <main className="fixed inset-0 flex flex-col bg-zinc-950 text-zinc-100" data-testid="terminal-window">
  <header className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-zinc-800 px-4 py-3"><div><h1 className="font-semibold">Terminale · {session?.profile||"ambiente"}</h1><p role="status" className="text-xs text-zinc-400">{phase}{session?.limits?` · massimo ${session.limits.cpus} CPU / ${session.limits.memory_mib} MiB RAM`:""}</p></div><div className="flex gap-2"><button className="rounded border border-zinc-700 px-3 py-2 text-sm" onClick={()=>{input.current("\x03");screen.current?.focus();}}>Ctrl+C</button><button disabled={closing||!session||session.finished} className="rounded border border-zinc-700 px-3 py-2 text-sm disabled:opacity-50" onClick={()=>void stop()}>Termina sessione</button><a className="rounded border border-zinc-700 px-3 py-2 text-sm" href="/workspace/environments">Ambienti</a></div></header>
  {error&&<p role="alert" className="shrink-0 border-b border-red-900 px-4 py-2 text-sm text-red-300">{error}</p>}
  {(error||session?.finished)&&<button className="m-2 self-start rounded border border-zinc-700 px-3 py-2 text-sm" onClick={()=>{setError("");setClosing(false);setSession(null);sessionRef.current=null;setAttempt(value=>value+1);}}>Riconnetti o apri una nuova sessione</button>}
  <div ref={host} className="min-h-0 flex-1 overflow-hidden p-2" aria-label="Terminale interattivo"/>
  <footer className="shrink-0 border-t border-zinc-800 px-4 py-2 text-xs text-zinc-400">Sandbox temporanea senza credenziali o progetti montati. Uscire dalla pagina o chiudere la finestra richiede la chiusura della sua sessione. Se il browser non comunica la chiusura, il server la recupera entro 60 secondi senza collegamento. Durata massima 30 minuti.</footer>
 </main>;
}
