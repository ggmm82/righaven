"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { fetch as authenticatedFetch } from "@/core/api/fetcher";
import { useI18n } from "@/core/i18n/hooks";

type Profile = {engine:string; model:string; ready:boolean; connection_id?:string; base_url?:string};
type Catalogue = {profiles:{coordinator:Profile;squad:Profile}; connections:Record<string,{credentials_present:boolean; connection_id?:string; base_url?:string}>};
type Session = {engine:string;id:string; finished:boolean; text:string; authorization_url?:string; returncode?:number; error?:string};
const field="w-full rounded-lg border bg-background px-3 py-2";
const button="rounded-lg border px-4 py-2 text-sm disabled:opacity-50";
async function api<T>(path:string, init?:RequestInit):Promise<T> {
  const response=await authenticatedFetch("/harness/api/"+path, init);
  if (!response.ok) {
    const value=await response.json().catch(()=>({})) as {detail?:string};
    throw new Error(value.detail ?? "Request failed ("+response.status+")");
  }
  return response.json() as Promise<T>;
}
const json=(value:unknown,method="POST"):RequestInit=>({method,headers:{"Content-Type":"application/json"},body:JSON.stringify(value)});
const engines:Record<string,string>={codex:"OpenAI Codex",gemini:"Google Antigravity",deepseek:"DeepSeek",openai:"OpenAI-compatible API"};

export default function ModelsPage() {
  const {locale}=useI18n(); const it=locale==="it-IT";
  const router=useRouter();
  const [data,setData]=useState<Catalogue>();
  const [access,setAccess]=useState("loading");
  const [engine,setEngine]=useState("codex"),[model,setModel]=useState(""),[scope,setScope]=useState("both");
  const [key,setKey]=useState(""),[baseUrl,setBaseUrl]=useState("https://api.openai.com/v1"),[connection,setConnection]=useState<string>();
  const [models,setModels]=useState<string[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const [sessionId,setSessionId]=useState<string>(),[session,setSession]=useState<Session>(),[code,setCode]=useState("");

  function select(profile:Profile) {setEngine(profile.engine);setModel(profile.model);setConnection(profile.connection_id);setBaseUrl(profile.base_url||"https://api.openai.com/v1");setModels([]);setKey("");}
  async function refresh(){const value=await api<Catalogue>("catalog");setData(value);return value;}
  useEffect(()=>{
    let alive=true;
    void authenticatedFetch("/api/v1/cloud/edition").then(async response=>{
      if(!response.ok)throw Error("Deployment configuration unreachable");
      const edition=await response.json() as {edition:string};
      if(!alive)return;
      if(edition.edition==="cloud"){router.replace("/workspace/cloud");return;}
      const result=await authenticatedFetch("/harness/api/catalog");
      if(!alive)return;
      if(result.status===403){setAccess("user");return;}
      if(!result.ok)throw Error("Model configuration unreachable");
      const value=await result.json() as Catalogue;
      setData(value);select(value.profiles.coordinator);setAccess("admin");
    }).catch(reason=>{if(alive){setAccess("error");setError(String(reason.message));}});
    return()=>{alive=false;};
  },[router]);

  useEffect(()=>{
    if(!sessionId)return;
    let alive=true;let timer:ReturnType<typeof setTimeout>;
    const controller=new AbortController();
    async function poll(){
      try{
        const value=await api<Session>("login-session/"+sessionId,{signal:controller.signal});
        if(!alive)return;setSession(value);
        if(value.finished){await refresh();if(value.error||value.returncode!==0)setError(value.error|| (it?"Accesso non completato. Consulta il dettaglio della sessione.":"Sign-in did not complete. Check session details."));}
        else timer=setTimeout(()=>void poll(),2000);
      }catch(reason){if(alive)setError(String((reason as Error).message));}
    }
    void poll();
    return()=>{alive=false;clearTimeout(timer);controller.abort();void authenticatedFetch("/harness/api/login-session/"+sessionId,{method:"DELETE",keepalive:true}).catch(()=>{});};
  },[sessionId]);

  function payload(){return {engine,model,scope,...(key?{api_key:key}:{}),...(engine==="openai"?{base_url:baseUrl,...(connection?{connection_id:connection}:{})}:{})};}
  async function operation(action:()=>Promise<void>){setBusy(true);setError("");setNotice("");try{await action();}catch(reason){setError(String((reason as Error).message));}finally{setBusy(false);}}
  async function save(event:FormEvent){event.preventDefault();await operation(async()=>{
    await api("team",json(payload(),"PUT"));setKey("");const value=await refresh();select(value.profiles[scope==="squad"?"squad":"coordinator"]);
    setNotice(it?"Connessione verificata e modelli assegnati.":"Connection checked and model assignments saved.");
  });}
  async function loadModels(){await operation(async()=>{
    const result=engine==="openai"&&key ? await api<{models:string[]}>("team/models",json(payload())) : await api<{models:string[]}>("team/models?engine="+engine+(connection?"&connection_id="+connection:""));
    setModels(result.models);setNotice(it?"Elenco modelli aggiornato.":"Model list refreshed.");
  });}
  async function connect(){await operation(async()=>{setSession(undefined);setCode("");const value=await api<Session>("login/"+engine,json({}));setSession(value);setSessionId(value.id);});}
  const account=engine==="codex"||engine==="gemini";
  const url=session?.authorization_url?.startsWith("https://")?session.authorization_url:undefined;
  return <main className="flex-1 overflow-y-auto"><div className="mx-auto max-w-4xl space-y-8 p-6 md:p-10">
    <header className="space-y-3 border-b pb-6"><p className="text-xs uppercase tracking-widest text-muted-foreground">RigHaven / {it?"Configurazione":"Configuration"}</p><h1 className="text-3xl font-semibold tracking-tight">{it?"Modelli e risorse":"Models & resources"}</h1><p className="text-muted-foreground">{it?"Una connessione, due assegnazioni. Le skill utilizzano i modelli scelti per coordinatore e squadra.":"One connection, two assignments. Skills use the models selected for the coordinator and team."}</p></header>
    {error&&<p role="alert" className="rounded-xl border border-destructive p-4 text-sm">{error}</p>}
    {access==="loading"&&<p role="status">{it?"Verifica configurazione…":"Checking configuration…"}</p>}
    {access==="user"&&<p>{it?"L’amministratore configura le connessioni condivise. Puoi avviare un incarico con la squadra disponibile.":"Your administrator configures shared connections. You can start tasks with the available team."}</p>}
    {data&&<>
      <section className="grid gap-4 sm:grid-cols-2">{(["coordinator","squad"] as const).map(target=><div key={target} className="space-y-2 rounded-2xl border p-6"><h2 className="text-sm text-muted-foreground">{target==="coordinator"?it?"Coordinatore":"Coordinator":it?"Squadra":"Team"}</h2><p className="font-semibold">{data.profiles[target].model||"—"}</p><p className="text-sm text-muted-foreground">{engines[data.profiles[target].engine]} · {data.profiles[target].ready?it?"Collegato":"Connected":it?"Da collegare":"Not connected"}</p></div>)}</section>
      <form onSubmit={event=>void save(event)} className="space-y-5 rounded-2xl border p-6">
        <h2 className="text-lg font-semibold">{it?"Configura una connessione":"Configure a connection"}</h2>
        <div className="grid gap-5 sm:grid-cols-2"><label className="space-y-2 text-sm"><span>{it?"Assegna a":"Assign to"}</span><select className={field} value={scope} onChange={event=>{setScope(event.target.value);select(data.profiles[event.target.value==="squad"?"squad":"coordinator"]);}}><option value="both">{it?"Coordinatore e squadra":"Coordinator & team"}</option><option value="coordinator">{it?"Solo coordinatore":"Coordinator only"}</option><option value="squad">{it?"Solo squadra":"Team only"}</option></select></label><label className="space-y-2 text-sm"><span>Provider</span><select className={field} value={engine} onChange={event=>{setEngine(event.target.value);setModel(event.target.value==="gemini"?"auto":event.target.value==="deepseek"?"deepseek-chat":"");setModels([]);setKey("");setConnection(data.connections[event.target.value]?.connection_id);setBaseUrl(data.connections[event.target.value]?.base_url||"https://api.openai.com/v1");}}>{Object.entries(engines).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label></div>
        {engine==="openai"&&<label className="block space-y-2 text-sm"><span>Endpoint URL</span><input type="url" required className={field} value={baseUrl} onChange={event=>setBaseUrl(event.target.value)} /></label>}
        {account?<div className="flex flex-wrap items-center gap-3 rounded-xl bg-muted/40 p-4"><p className="flex-1 text-sm">{it?"Usa l’accesso ufficiale del tuo account; non inserire la password in RigHaven.":"Use your account's official sign-in; do not enter its password in RigHaven."}</p><button type="button" disabled={busy||!!sessionId&&!session?.finished} className={button} onClick={()=>void connect()}>{it?"Collega account":"Connect account"}</button></div>:<label className="block space-y-2 text-sm"><span>API key</span><input className={field} type="password" autoComplete="new-password" value={key} onChange={event=>setKey(event.target.value)} placeholder={it?"Lascia vuoto per mantenere la chiave salvata":"Leave blank to keep the saved key"}/></label>}
        <label className="block space-y-2 text-sm"><span>{it?"ID modello":"Model ID"}</span><input className={field} list="provider-models" value={model} maxLength={200} onChange={event=>setModel(event.target.value)} placeholder={it?"Scegli dall’elenco o inserisci un ID":"Choose from the list or enter an ID"}/><datalist id="provider-models">{models.map(value=><option key={value} value={value}/>)}</datalist></label>
        <div className="flex flex-wrap gap-3"><button type="button" className={button} disabled={busy} onClick={()=>void loadModels()}>{it?"Carica modelli disponibili":"Load available models"}</button><button disabled={busy} className={button+" bg-primary text-primary-foreground"}>{busy?it?"Verifica in corso…":"Checking…":it?"Verifica e salva":"Check & save"}</button></div>
        {notice&&<p role="status" className="text-sm">{notice}</p>}
      </form>
      {sessionId&&<section className="space-y-4 rounded-2xl border p-6"><div className="flex items-center justify-between gap-4"><h2 className="font-semibold">{it?"Accesso ufficiale":"Official sign-in"}</h2><button className={button} onClick={()=>{setSessionId(undefined);setSession(undefined);}}>{session?.finished?it?"Chiudi":"Close":it?"Annulla accesso":"Cancel sign-in"}</button></div>
        {url&&<div className="space-y-3"><a href={url} target="_blank" rel="noopener noreferrer" className="block break-all underline">{it?"Apri il login ufficiale":"Open official sign-in"}</a><button className={button} onClick={()=>void navigator.clipboard.writeText(url).catch(()=>setError(it?"Copia il link dal dettaglio qui sotto.":"Copy the link from the details below."))}>{it?"Copia link":"Copy link"}</button><input aria-label={it?"Link di accesso copiabile":"Copyable sign-in link"} className={field} value={url} readOnly onFocus={event=>event.target.select()}/></div>}
        {session?.engine==="gemini"&&!session?.finished&&<form className="flex gap-3" onSubmit={event=>{event.preventDefault();void operation(async()=>{await api("login-session/"+sessionId+"/input",json({text:code}));setCode("");});}}><input aria-label={it?"Codice restituito da Google":"Code returned by Google"} className={field} required value={code} onChange={event=>setCode(event.target.value)} autoComplete="off"/><button className={button} disabled={busy}>{it?"Invia codice":"Submit code"}</button></form>}
        <p role="status" className="text-sm">{session?.finished?session.returncode===0?it?"Account collegato. Ora scegli il modello e salva.":"Account connected. Now choose a model and save.":it?"Accesso non riuscito":"Sign-in failed":it?"In attesa del completamento dell’accesso…":"Waiting for sign-in to complete…"}</p><details><summary className="cursor-pointer text-sm">{it?"Dettaglio della sessione":"Session details"}</summary><pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-muted p-4 text-xs">{session?.text}</pre></details>
      </section>}
    </>}
    <section className="flex flex-wrap items-start justify-between gap-4 rounded-2xl border p-6"><div className="max-w-xl space-y-2"><h2 className="text-lg font-semibold">{it?"Risorse e parallelismo":"Resources & parallelism"}</h2><p className="text-sm text-muted-foreground">{it?"Controlla CPU, memoria, operazioni contemporanee e ambienti occupati nella pagina degli ambienti.":"Monitor CPU, memory, concurrent operations and busy environments on the environments page."}</p></div><Link className={button} href="/workspace/environments">{it?"Apri ambienti":"Open environments"}</Link></section>
  </div></main>;
}
