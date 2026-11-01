"use client";
import {useEffect,useState} from "react";

import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";
import {tr,useUiLanguage} from "@/core/i18n/ui-text";

type Stage={id:string;title:{it:string;en:string};outcome:{it:string;en:string};status:string;available:boolean;note:string;evidence:{path:string;sha256:string}[]};
type Journey={recipe_id:string;revision:number;answers:Record<string,string>;complete:boolean;current:string|null;stages:Stage[]};
export function ProjectJourney({threadId,onContinue}:{threadId:string;onContinue?:(message:string)=>unknown}){
 useUiLanguage();
 const [value,setValue]=useState<{thread:string;journey:Journey|null}|null>(null),[error,setError]=useState(""),[busy,setBusy]=useState(false);
 const [selected,setSelected]=useState<string|null>(null),[revisionNote,setRevisionNote]=useState("");
 const base=`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-journey`;
 useEffect(()=>{let live=true;const controller=new AbortController();
  const load=async()=>{try{const r=await fetch(base,{signal:controller.signal,cache:"no-store"});if(!r.ok)throw Error(String(r.status));const v=await r.json() as {journey:Journey|null};if(live){setValue(old=>old?.thread===threadId&&(old.journey?.revision??0)>(v.journey?.revision??0)?old:{thread:threadId,journey:v.journey});setError("");}}catch(e){if(live)setError(e instanceof Error?e.message:String(e));}};
  void load();const timer=setInterval(()=>void load(),5000);return()=>{live=false;controller.abort();clearInterval(timer);};},[base,threadId]);
 const journey=value?.thread===threadId?value.journey:null;
 if(!journey)return null;
 const stage=journey.stages.find(s=>s.id===(selected??journey.current))??journey.stages.at(-1);
 const status=(s:string)=>({working:tr("In lavorazione","In progress"),pending:tr("Da iniziare","Not started"),review:tr("Da approvare","Awaiting approval"),approved:tr("Approvata","Approved"),stale:tr("Da rivalidare","Recheck needed"),blocked:tr("Da correggere","Revision requested")}[s]??s);
 async function decide(approve:boolean){if(!journey||!stage)return;setBusy(true);setError("");try{
  const r=await fetch(base+"/decision",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({stage_id:stage.id,approve,expected_revision:journey.revision,note:revisionNote})});
  const v=await r.json() as {journey:Journey;detail?:string};if(!r.ok)throw Error(v.detail??String(r.status));setValue({thread:threadId,journey:v.journey});setSelected(null);setRevisionNote("");
 }catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
 const artifact=(p:string)=>`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/artifacts${p.split("/").map(encodeURIComponent).join("/")}`;
 return <details className="mb-2 rounded-xl border bg-background text-sm" data-testid="project-journey">
  <summary className="cursor-pointer p-3 font-semibold">{tr("Percorso guidato","Guided project")} · {journey.stages.filter(s=>s.status==="approved").length}/{journey.stages.length} · {stage?tr(stage.title.it,stage.title.en):""}</summary>
  <div className="max-h-[60dvh] space-y-3 overflow-auto border-t p-3">
   <p>{journey.answers.goal}</p><p className="text-muted-foreground text-xs">{tr("Allega i documenti nella chat: li leggeremo prima di chiederti le informazioni mancanti. Puoi completare il laboratorio senza connessioni reali.","Attach documents in chat: we read them before asking for missing information. You can complete the lab without real connections.")}</p>
   <nav className="flex flex-wrap gap-2" aria-label={tr("Fasi del percorso","Guided phases")}>{journey.stages.map(s=><button type="button" className="rounded border px-2 py-1 text-left" key={s.id} aria-pressed={stage?.id===s.id} onClick={()=>setSelected(s.id)}>{tr(s.title.it,s.title.en)} · {status(s.status)}</button>)}</nav>
   {stage&&<section className="space-y-2 rounded border p-3"><h4 className="font-semibold">{tr(stage.title.it,stage.title.en)}</h4><p>{tr(stage.outcome.it,stage.outcome.en)}</p>{stage.note&&<p>{stage.note}</p>}
    <ul>{stage.evidence.map(e=><li key={e.path}><a className="underline" href={artifact(e.path)} target="_blank" rel="noreferrer">{e.path.split("/").pop()}</a></li>)}</ul>
    {stage.status==="review"&&<><label className="block">{tr("Osservazioni o correzioni","Feedback or corrections")}<textarea className="mt-1 w-full rounded border p-2" rows={2} maxLength={1500} value={revisionNote} onChange={e=>setRevisionNote(e.target.value)}/></label><div className="flex gap-2"><button type="button" disabled={busy} className="rounded border px-3 py-2" onClick={()=>void decide(true)}>{tr("Approva questa fase","Approve this phase")}</button><button type="button" disabled={busy} className="rounded border px-3 py-2" onClick={()=>void decide(false)}>{tr("Richiedi correzioni","Request changes")}</button></div></>}
   </section>}
   {error&&<p role="alert">{error}</p>}
   {onContinue&&<button type="button" disabled={busy} className="rounded border px-3 py-2" onClick={()=>onContinue(tr("Prosegui il percorso guidato salvato con harness_journey. Leggi prima gli allegati e le mie scelte; presenta il prossimo risultato utile. Non chiedermi configurazioni tecniche. Le connessioni sono facoltative.","Continue the saved guided project with harness_journey. Read attachments and my choices first; present the next useful result. Do not ask me to write technical configuration. Connections are optional."))}>{tr("Prosegui con la squadra","Continue with the team")}</button>}
  </div>
 </details>;
}
