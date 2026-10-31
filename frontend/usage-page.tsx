"use client";
import {useEffect,useState} from "react";
import {useI18n} from "@/core/i18n/hooks";
import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";

type Tokens={input_tokens:number|null;cached_tokens:number|null;output_tokens:number|null;reasoning_tokens:number|null;cost?:number|null};
type Group=Tokens&{name:string;jobs:number;seconds:number;cpu_seconds:number;memory_peak_bytes:number|null;last_at:string;users:number;reused:number;extended:number;completed:number};
type Job=Tokens&{job_id:string;user_id:string;thread_id:string;finished_at:string;duration_seconds:number|null;role:string;engine:string;model:string;profile:string;mode:string;tools:string[];cpu_seconds:number|null;memory_peak_bytes:number|null;outcome:string;error_code?:string};
type Alert={engine:string;model:string;jobs:number;users:number;last_at:string};
type Report={days:number;scope:"all"|"own";currency:string;priced_models:string[];totals:Tokens&{jobs:number;seconds:number;cpu_seconds:number;memory_peak_bytes:number|null};machines:Group[];users:Group[];roles:Group[];models:Group[];jobs:Job[];quota_alerts:Alert[]};
type Price={input:number;cached_input:number;output:number};
type Prices={currency:string;models:Record<string,Price>;can_manage:boolean};

const hours=(seconds:number|null|undefined)=>seconds==null?"–":(seconds/3600).toFixed(seconds<360?2:1);
const memory=(bytes:number|null|undefined)=>bytes==null?"–":bytes>=1024**3?(bytes/1024**3).toFixed(1)+" GB":Math.round(bytes/1024**2)+" MB";
const when=(at:string)=>at?at.slice(0,16).replace("T"," "):"–";
const count=(n:number|null|undefined)=>n==null?"–":n>=1e6?(n/1e6).toFixed(n>=1e7?1:2)+" M":n>=1e3?(n/1e3).toFixed(n>=1e4?0:1)+" k":String(n);
const money=(amount:number|null|undefined,currency:string)=>amount==null?"–":new Intl.NumberFormat(undefined,{style:"currency",currency,maximumFractionDigits:amount<1?4:2}).format(amount);

export default function UsagePage(){
 const {locale}=useI18n();const it=locale==="it-IT";const t=(a:string,b:string)=>it?a:b;
 const [days,setDays]=useState(30),[report,setReport]=useState<Report|null>(null),[emails,setEmails]=useState<Record<string,string>>({}),[error,setError]=useState("");
 const [prices,setPrices]=useState<Prices|null>(null),[draft,setDraft]=useState<Record<string,Price>>({}),[currency,setCurrency]=useState("USD"),[saved,setSaved]=useState(""),[reload,setReload]=useState(0);
 useEffect(()=>{void fetch(`${getBackendBaseURL()}/api/harness/usage/prices`).then(r=>r.ok?r.json():null).then((v:Prices|null)=>{if(v){setPrices(v);setDraft(v.models);setCurrency(v.currency);}}).catch(()=>undefined);},[]);
 async function savePrices(){setSaved("");setError("");
  const models=Object.fromEntries(Object.entries(draft).filter(([,p])=>p.input>0||p.output>0||p.cached_input>0));
  const r=await fetch(`${getBackendBaseURL()}/api/harness/usage/prices`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({currency,models})});
  const v=await r.json();if(!r.ok){setError(typeof v.detail==="string"?v.detail:String(r.status));return;}
  setPrices(p=>p&&{...p,...v});setDraft(v.models);setSaved(t("Prezzi salvati: le stime sono ricalcolate.","Prices saved: estimates are recalculated."));setReload(n=>n+1);}
 useEffect(()=>{let live=true;setError("");
  void fetch(`${getBackendBaseURL()}/api/harness/usage?days=${days}`).then(async r=>{const v=await r.json();if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));return v as Report;})
   .then(v=>{if(!live)return;setReport(v);if(v.scope==="all")void fetch(`${getBackendBaseURL()}/api/v1/admin/users`).then(r=>r.ok?r.json():[]).then((users:{id:string;email:string}[])=>{if(live&&Array.isArray(users))setEmails(Object.fromEntries(users.map(u=>[u.id,u.email])));}).catch(()=>undefined);})
   .catch(e=>{if(live)setError(e instanceof Error?e.message:String(e));});
  return()=>{live=false;};},[days,reload]);
 const machine=(name:string)=>name==="dedicated"?t("Ambiente su misura","Dedicated environment"):name===""?t("Base comune (senza programmi aggiuntivi)","Common base (no extra software)"):name;
 const modes:Record<string,string>={reused:t("profilo riusato","profile reused"),extended:t("profilo esteso","profile extended"),not_reused:t("profilo non riusabile","profile not reusable"),none:t("su misura","dedicated"),dedicated:t("su misura","dedicated"),core:t("base comune","common base")};
 const outcomes:Record<string,string>={completed:t("completato","completed"),failed:t("non riuscito","failed"),timed_out:t("tempo scaduto","timed out")};
 const person=(id:string)=>emails[id]??(id||t("non attribuito","unattributed"));
 const table=(rows:Group[],label:(name:string)=>string,first:string,showModes:boolean)=><table className="w-full text-left text-sm"><thead><tr className="border-b">
  <th className="py-1">{first}</th><th>{t("Incarichi","Assignments")}</th>{showModes&&<th>{t("Riusi / estensioni","Reuses / extensions")}</th>}<th>{t("Ore di lavoro","Work hours")}</th><th>{t("Ore CPU","CPU hours")}</th><th>{t("Memoria di picco","Peak memory")}</th><th>{t("Token (ingresso / uscita)","Tokens (in / out)")}</th><th>{t("Costo stimato","Estimated cost")}</th><th>{t("Utenti","Users")}</th><th>{t("Ultimo uso","Last use")}</th></tr></thead>
  <tbody>{rows.map(r=><tr key={r.name} className="border-b"><td className="py-1">{label(r.name)}</td><td>{r.jobs} ({r.completed} {t("completati","completed")})</td>{showModes&&<td>{r.reused} / {r.extended}</td>}<td>{hours(r.seconds)}</td><td>{hours(r.cpu_seconds)}</td><td>{memory(r.memory_peak_bytes)}</td><td>{count(r.input_tokens)} / {count(r.output_tokens)}</td><td>{money(r.cost,report!.currency)}</td><td>{r.users}</td><td>{when(r.last_at)}</td></tr>)}</tbody></table>;
 return <main className="mx-auto w-full max-w-6xl space-y-5 overflow-y-auto p-6" data-testid="usage-page">
  <header className="space-y-2"><h1 className="text-2xl font-semibold">{t("Uso delle macchine","Machine usage")}</h1>
   <p className="text-muted-foreground">{t("Ogni incarico di uno specialista gira in una macchina: un profilo pronto riusato così com’è o esteso con i programmi mancanti, un ambiente preparato su misura, oppure la base comune. Qui vedi chi ha usato quale macchina, in che modo e quanto.","Every specialist assignment runs on a machine: a prepared profile reused as is or extended with missing software, a dedicated environment, or the common base. Here you see who used which machine, how and how much.")}</p>
   <p className="text-sm">{report?.scope==="all"?t("Sei amministratore: vedi gli incarichi di tutti gli utenti.","You are an administrator: you see every user’s assignments."):t("Vedi i tuoi incarichi.","You see your own assignments.")}</p>
   <label className="text-sm">{t("Periodo","Period")} <select className="rounded border bg-background p-1" value={days} onChange={e=>setDays(Number(e.target.value))}>{[7,30,90,365].map(d=><option key={d} value={d}>{t(`Ultimi ${d} giorni`,`Last ${d} days`)}</option>)}</select></label>
  </header>
  {error&&<p role="alert" className="rounded border p-3 text-sm text-red-600">{error}</p>}
  {!!report?.quota_alerts?.length&&<section role="alert" data-testid="quota-alerts" className="space-y-1 rounded-xl border border-amber-500/60 bg-amber-500/10 p-4 text-sm">
   <h2 className="font-semibold">{t("Quota del servizio AI esaurita","AI service quota exhausted")}</h2>
   {report.quota_alerts.map(a=><p key={a.engine+a.model}>{a.engine} {a.model}: {t(`${a.jobs} incarichi fermati nelle ultime 24 ore`,`${a.jobs} assignments stopped in the last 24 hours`)}{report.scope==="all"?t(` per ${a.users} utenti`,` for ${a.users} users`):""} · {t("ultimo","latest")} {when(a.last_at)}.</p>)}
   <p>{t("I file già salvati restano conservati. Scegli un servizio disponibile in La tua squadra oppure attendi il ripristino della quota, poi riprendi il lavoro dalla chat.","Files already saved are kept. Choose an available service in Your team or wait for the quota to reset, then resume the work from the chat.")}</p></section>}
  {report&&<>
   <section className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6" aria-label={t("Totali","Totals")}>{[[t("Incarichi","Assignments"),String(report.totals.jobs)],[t("Ore di lavoro","Work hours"),hours(report.totals.seconds)],[t("Ore CPU","CPU hours"),hours(report.totals.cpu_seconds)],[t("Memoria di picco","Peak memory"),memory(report.totals.memory_peak_bytes)],[t("Token (ingresso / uscita)","Tokens (in / out)"),count(report.totals.input_tokens)+" / "+count(report.totals.output_tokens)],[t("Costo stimato","Estimated cost"),money(report.totals.cost,report.currency)]].map(([label,value])=><div key={label} className="rounded-xl border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="text-xl font-semibold">{value}</p></div>)}</section>
   {!report.totals.jobs&&<p className="rounded-xl border p-4 text-muted-foreground">{t("Nessun incarico concluso nel periodo.","No finished assignment in this period.")}</p>}
   {!!report.machines.length&&<section className="space-y-2 rounded-xl border p-4" aria-label={t("Per macchina","By machine")}><h2 className="font-semibold">{t("Per macchina","By machine")}</h2>{table(report.machines,machine,t("Macchina","Machine"),true)}</section>}
   {!!report.users.length&&<section className="space-y-2 rounded-xl border p-4" aria-label={t("Per utente","By user")}><h2 className="font-semibold">{t("Per utente","By user")}</h2>{table(report.users,person,t("Utente","User"),true)}</section>}
   {!!report.roles.length&&<section className="space-y-2 rounded-xl border p-4" aria-label={t("Per ruolo","By role")}><h2 className="font-semibold">{t("Per ruolo","By role")}</h2>{table(report.roles,n=>n,t("Ruolo","Role"),false)}</section>}
   {!!report.models?.length&&<section className="space-y-2 rounded-xl border p-4" aria-label={t("Per modello","By model")}><h2 className="font-semibold">{t("Per modello","By model")}</h2>{table(report.models,n=>n||t("non indicato","not stated"),t("Modello","Model"),false)}
    <p className="text-xs text-muted-foreground">{t("I token sono quelli riportati dal servizio AI per ogni incarico; il costo è una stima con i prezzi impostati dall’amministratore e non sostituisce la fattura.","Tokens are those reported by the AI service for each assignment; the cost is an estimate from the prices set by the administrator and does not replace the invoice.")}</p></section>}
   {!!report.jobs.length&&<section className="space-y-2 rounded-xl border p-4" aria-label={t("Ultimi incarichi","Latest assignments")}><h2 className="font-semibold">{t("Ultimi incarichi","Latest assignments")}</h2>
    <table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="py-1">{t("Fine","Finished")}</th>{report.scope==="all"&&<th>{t("Utente","User")}</th>}<th>{t("Ruolo","Role")}</th><th>{t("Macchina e modo","Machine and mode")}</th><th>{t("Durata (ore)","Duration (h)")}</th><th>{t("Ore CPU","CPU hours")}</th><th>{t("Memoria","Memory")}</th><th>{t("Token (ingresso / uscita)","Tokens (in / out)")}</th><th>{t("Costo stimato","Estimated cost")}</th><th>{t("Esito","Outcome")}</th></tr></thead>
     <tbody>{report.jobs.map(j=><tr key={j.job_id} className="border-b align-top"><td className="py-1">{when(j.finished_at)}{j.thread_id&&<><br/><a className="text-xs underline" href={`/workspace/chats/${encodeURIComponent(j.thread_id)}`}>{t("Apri la conversazione","Open conversation")}</a></>}</td>
      {report.scope==="all"&&<td>{person(j.user_id)}</td>}<td>{j.role}<br/><span className="text-xs text-muted-foreground">{j.engine} {j.model}</span></td>
      <td>{j.profile||machine(j.mode==="core"?"":"dedicated")} · {modes[j.mode]??j.mode}{j.tools.length>0&&<><br/><span className="text-xs text-muted-foreground">{j.tools.join(", ")}</span></>}</td>
      <td>{hours(j.duration_seconds)}</td><td>{hours(j.cpu_seconds)}</td><td>{memory(j.memory_peak_bytes)}</td><td>{count(j.input_tokens)} / {count(j.output_tokens)}</td><td>{money(j.cost,report.currency)}</td><td>{j.error_code==="provider_quota"?t("quota esaurita","quota exhausted"):outcomes[j.outcome]??j.outcome}</td></tr>)}</tbody></table></section>}
   {prices?.can_manage&&<section className="space-y-2 rounded-xl border p-4" aria-label={t("Prezzi dei modelli","Model prices")} data-testid="model-prices"><h2 className="font-semibold">{t("Prezzi dei modelli","Model prices")}</h2>
    <p className="text-sm text-muted-foreground">{t("Prezzo per milione di token, come nel listino del fornitore. Solo gli amministratori li vedono e li modificano; i modelli senza prezzo non hanno costo stimato.","Price per million tokens, as in the provider’s price list. Only administrators see and change them; models without a price have no estimated cost.")}</p>
    <label className="text-sm">{t("Valuta","Currency")} <select className="rounded border bg-background p-1" value={currency} onChange={e=>setCurrency(e.target.value)}>{["USD","EUR","GBP","CHF"].map(c=><option key={c}>{c}</option>)}</select></label>
    <table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="py-1">{t("Modello","Model")}</th><th>{t("Ingresso","Input")}</th><th>{t("Ingresso in cache","Cached input")}</th><th>{t("Uscita","Output")}</th></tr></thead>
     <tbody>{[...new Set([...report.models.map(m=>m.name).filter(Boolean),...Object.keys(draft)])].sort().map(model=>{const p=draft[model]??{input:0,cached_input:0,output:0};
      return <tr key={model} className="border-b"><td className="py-1">{model}</td>{(["input","cached_input","output"] as const).map(field=><td key={field}><input aria-label={`${model} ${field}`} type="number" min={0} step="0.01" className="w-24 rounded border bg-background p-1" value={p[field]} onChange={e=>setDraft(d=>({...d,[model]:{...p,[field]:Number(e.target.value)}}))}/></td>)}</tr>;})}</tbody></table>
    <button type="button" className="rounded border px-3 py-2 text-sm" onClick={()=>void savePrices()}>{t("Salva prezzi","Save prices")}</button>{saved&&<p role="status" className="text-sm">{saved}</p>}</section>}
  </>}
 </main>;
}
