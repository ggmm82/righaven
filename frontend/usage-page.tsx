"use client";
import {useEffect,useState} from "react";
import {useI18n} from "@/core/i18n/hooks";
import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";

type Group={name:string;jobs:number;seconds:number;cpu_seconds:number;memory_peak_bytes:number|null;last_at:string;users:number;reused:number;extended:number;completed:number};
type Job={job_id:string;user_id:string;thread_id:string;finished_at:string;duration_seconds:number|null;role:string;engine:string;model:string;profile:string;mode:string;tools:string[];cpu_seconds:number|null;memory_peak_bytes:number|null;outcome:string};
type Report={days:number;scope:"all"|"own";totals:{jobs:number;seconds:number;cpu_seconds:number;memory_peak_bytes:number|null};machines:Group[];users:Group[];roles:Group[];jobs:Job[]};

const hours=(seconds:number|null|undefined)=>seconds==null?"–":(seconds/3600).toFixed(seconds<360?2:1);
const memory=(bytes:number|null|undefined)=>bytes==null?"–":bytes>=1024**3?(bytes/1024**3).toFixed(1)+" GB":Math.round(bytes/1024**2)+" MB";
const when=(at:string)=>at?at.slice(0,16).replace("T"," "):"–";

export default function UsagePage(){
 const {locale}=useI18n();const it=locale==="it-IT";const t=(a:string,b:string)=>it?a:b;
 const [days,setDays]=useState(30),[report,setReport]=useState<Report|null>(null),[emails,setEmails]=useState<Record<string,string>>({}),[error,setError]=useState("");
 useEffect(()=>{let live=true;setError("");
  void fetch(`${getBackendBaseURL()}/api/harness/usage?days=${days}`).then(async r=>{const v=await r.json();if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));return v as Report;})
   .then(v=>{if(!live)return;setReport(v);if(v.scope==="all")void fetch(`${getBackendBaseURL()}/api/v1/admin/users`).then(r=>r.ok?r.json():[]).then((users:{id:string;email:string}[])=>{if(live&&Array.isArray(users))setEmails(Object.fromEntries(users.map(u=>[u.id,u.email])));}).catch(()=>undefined);})
   .catch(e=>{if(live)setError(e instanceof Error?e.message:String(e));});
  return()=>{live=false;};},[days]);
 const machine=(name:string)=>name==="dedicated"?t("Ambiente su misura","Dedicated environment"):name===""?t("Base comune (senza programmi aggiuntivi)","Common base (no extra software)"):name;
 const modes:Record<string,string>={reused:t("profilo riusato","profile reused"),extended:t("profilo esteso","profile extended"),not_reused:t("profilo non riusabile","profile not reusable"),none:t("su misura","dedicated"),dedicated:t("su misura","dedicated"),core:t("base comune","common base")};
 const outcomes:Record<string,string>={completed:t("completato","completed"),failed:t("non riuscito","failed"),timed_out:t("tempo scaduto","timed out")};
 const person=(id:string)=>emails[id]??(id||t("non attribuito","unattributed"));
 const table=(rows:Group[],label:(name:string)=>string,first:string,showModes:boolean)=><table className="w-full text-left text-sm"><thead><tr className="border-b">
  <th className="py-1">{first}</th><th>{t("Incarichi","Assignments")}</th>{showModes&&<th>{t("Riusi / estensioni","Reuses / extensions")}</th>}<th>{t("Ore di lavoro","Work hours")}</th><th>{t("Ore CPU","CPU hours")}</th><th>{t("Memoria di picco","Peak memory")}</th><th>{t("Utenti","Users")}</th><th>{t("Ultimo uso","Last use")}</th></tr></thead>
  <tbody>{rows.map(r=><tr key={r.name} className="border-b"><td className="py-1">{label(r.name)}</td><td>{r.jobs} ({r.completed} {t("completati","completed")})</td>{showModes&&<td>{r.reused} / {r.extended}</td>}<td>{hours(r.seconds)}</td><td>{hours(r.cpu_seconds)}</td><td>{memory(r.memory_peak_bytes)}</td><td>{r.users}</td><td>{when(r.last_at)}</td></tr>)}</tbody></table>;
 return <main className="mx-auto w-full max-w-6xl space-y-5 overflow-y-auto p-6" data-testid="usage-page">
  <header className="space-y-2"><h1 className="text-2xl font-semibold">{t("Uso delle macchine","Machine usage")}</h1>
   <p className="text-muted-foreground">{t("Ogni incarico di uno specialista gira in una macchina: un profilo pronto riusato così com’è o esteso con i programmi mancanti, un ambiente preparato su misura, oppure la base comune. Qui vedi chi ha usato quale macchina, in che modo e quanto.","Every specialist assignment runs on a machine: a prepared profile reused as is or extended with missing software, a dedicated environment, or the common base. Here you see who used which machine, how and how much.")}</p>
   <p className="text-sm">{report?.scope==="all"?t("Sei amministratore: vedi gli incarichi di tutti gli utenti.","You are an administrator: you see every user’s assignments."):t("Vedi i tuoi incarichi.","You see your own assignments.")}</p>
   <label className="text-sm">{t("Periodo","Period")} <select className="rounded border bg-background p-1" value={days} onChange={e=>setDays(Number(e.target.value))}>{[7,30,90,365].map(d=><option key={d} value={d}>{t(`Ultimi ${d} giorni`,`Last ${d} days`)}</option>)}</select></label>
  </header>
  {error&&<p role="alert" className="rounded border p-3 text-sm text-red-600">{error}</p>}
  {report&&<>
   <section className="grid gap-3 sm:grid-cols-4" aria-label={t("Totali","Totals")}>{[[t("Incarichi","Assignments"),String(report.totals.jobs)],[t("Ore di lavoro","Work hours"),hours(report.totals.seconds)],[t("Ore CPU","CPU hours"),hours(report.totals.cpu_seconds)],[t("Memoria di picco","Peak memory"),memory(report.totals.memory_peak_bytes)]].map(([label,value])=><div key={label} className="rounded-xl border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="text-xl font-semibold">{value}</p></div>)}</section>
   {!report.totals.jobs&&<p className="rounded-xl border p-4 text-muted-foreground">{t("Nessun incarico concluso nel periodo.","No finished assignment in this period.")}</p>}
   {!!report.machines.length&&<section className="space-y-2 rounded-xl border p-4" aria-label={t("Per macchina","By machine")}><h2 className="font-semibold">{t("Per macchina","By machine")}</h2>{table(report.machines,machine,t("Macchina","Machine"),true)}</section>}
   {!!report.users.length&&<section className="space-y-2 rounded-xl border p-4" aria-label={t("Per utente","By user")}><h2 className="font-semibold">{t("Per utente","By user")}</h2>{table(report.users,person,t("Utente","User"),true)}</section>}
   {!!report.roles.length&&<section className="space-y-2 rounded-xl border p-4" aria-label={t("Per ruolo","By role")}><h2 className="font-semibold">{t("Per ruolo","By role")}</h2>{table(report.roles,n=>n,t("Ruolo","Role"),false)}</section>}
   {!!report.jobs.length&&<section className="space-y-2 rounded-xl border p-4" aria-label={t("Ultimi incarichi","Latest assignments")}><h2 className="font-semibold">{t("Ultimi incarichi","Latest assignments")}</h2>
    <table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="py-1">{t("Fine","Finished")}</th>{report.scope==="all"&&<th>{t("Utente","User")}</th>}<th>{t("Ruolo","Role")}</th><th>{t("Macchina e modo","Machine and mode")}</th><th>{t("Durata (ore)","Duration (h)")}</th><th>{t("Ore CPU","CPU hours")}</th><th>{t("Memoria","Memory")}</th><th>{t("Esito","Outcome")}</th></tr></thead>
     <tbody>{report.jobs.map(j=><tr key={j.job_id} className="border-b align-top"><td className="py-1">{when(j.finished_at)}{j.thread_id&&<><br/><a className="text-xs underline" href={`/workspace/chats/${encodeURIComponent(j.thread_id)}`}>{t("Apri la conversazione","Open conversation")}</a></>}</td>
      {report.scope==="all"&&<td>{person(j.user_id)}</td>}<td>{j.role}<br/><span className="text-xs text-muted-foreground">{j.engine} {j.model}</span></td>
      <td>{j.profile||machine(j.mode==="core"?"":"dedicated")} · {modes[j.mode]??j.mode}{j.tools.length>0&&<><br/><span className="text-xs text-muted-foreground">{j.tools.join(", ")}</span></>}</td>
      <td>{hours(j.duration_seconds)}</td><td>{hours(j.cpu_seconds)}</td><td>{memory(j.memory_peak_bytes)}</td><td>{outcomes[j.outcome]??j.outcome}</td></tr>)}</tbody></table></section>}
  </>}
 </main>;
}
