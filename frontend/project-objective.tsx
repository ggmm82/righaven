"use client";
import {useEffect,useRef,useState} from "react";

import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";
import {tr,useUiLanguage} from "@/core/i18n/ui-text";

type Base={id:string;goal:string;product_path?:string|null;files:string[];files_count:number};
type Objective={signature:string;goal:string;guided:boolean;can_change:boolean;scope?:{parent:Base;ancestors:{id:string;goal:string;product_path?:string|null}[]}|null};

export function ProjectObjective({threadId,busyTeam,onContinue}:{threadId:string;busyTeam:boolean;onContinue?:(message?:string)=>void|Promise<void>}){
 useUiLanguage();
 const [value,setValue]=useState<Objective|null>(null),[goal,setGoal]=useState("");
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 const pending=useRef(false),owner=useRef(threadId);owner.current=threadId;
 const base=`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-objective`;
 useEffect(()=>{let live=true;void fetch(base,{cache:"no-store"}).then(async r=>{const v=await r.json() as Objective&{detail?:string};if(!r.ok)throw Error(v.detail??String(r.status));if(live)setValue(v);}).catch(e=>{if(live)setError(e instanceof Error?e.message:String(e));});return()=>{live=false;};},[base,busyTeam]);
 async function evolve(){if(!value||pending.current||!goal.trim())return;pending.current=true;setBusy(true);setError("");
  try{const requestGoal=goal.trim();const r=await fetch(base,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({signature:value.signature,goal:requestGoal})});
   const v=await r.json() as {detail?:string};if(!r.ok)throw Error(v.detail??String(r.status));if(owner.current!==threadId)return;
   window.dispatchEvent(new CustomEvent("righaven-objective-changed",{detail:threadId}));
   setNotice(tr("Nuovo obiettivo salvato. I risultati precedenti sono conservati come base; le vecchie approvazioni non valgono per il nuovo lavoro.","New objective saved. Prior results are retained as a base; old approvals do not apply to new work."));setGoal("");
   const current=await fetch(base,{cache:"no-store"});if(current.ok&&owner.current===threadId)setValue(await current.json() as Objective);
   if(onContinue)try{await onContinue(requestGoal);}catch{setNotice(tr("Obiettivo salvato. Torna in chat e chiedi di proseguire: non devi ricreare il percorso.","Objective saved. Return to chat and ask to continue; you do not need to recreate the path."));}
  }catch(e){if(owner.current===threadId)setError(e instanceof Error?e.message:String(e));}finally{pending.current=false;setBusy(false);}
 }
 const viewer=(path:string)=>`/artifacts/view?${new URLSearchParams({path,thread_id:threadId})}`;
 return <section className="space-y-4 text-sm" data-testid="project-objective">
  <h3 className="font-semibold">{tr("Evolvi questo risultato","Evolve this result")}</h3>
  <p>{tr("Puoi cambiare metodo, chiedere una nuova versione o partire dai sorgenti per un obiettivo diverso. La ricetta iniziale resta un riferimento: non occorre ricominciare le sue fasi.","Change the method, request a new version, or use the sources for a different objective. The initial recipe remains a reference; you do not need to restart its phases.")}</p>
  {value&&<p><strong>{tr("Obiettivo attuale:","Current objective:")}</strong> {value.goal}</p>}
  {value?.scope&&<details className="rounded border p-3"><summary>{tr("Base e obiettivi precedenti","Base and previous objectives")}</summary>
   <p className="my-2">{value.scope.parent.goal}</p>
   {value.scope.parent.product_path&&<a className="underline" href={viewer(value.scope.parent.product_path)} target="_blank" rel="noopener noreferrer">{tr("Apri il risultato di partenza","Open the base result")}</a>}
   <ul className="mt-3 space-y-2">{value.scope.parent.files.map(path=><li key={path}><a className="break-all underline" href={viewer(path)} target="_blank" rel="noopener noreferrer">{path.split('/').pop()}</a></li>)}</ul>
   <p className="mt-3 text-xs">{tr("Questi file appartengono all’obiettivo precedente. I nuovi risultati compariranno come nuove consegne.","These files belong to the previous objective. New results will appear as new deliveries.")}</p>
   {value.scope.ancestors.length>1&&<ol className="mt-3 list-inside list-decimal">{value.scope.ancestors.map(a=><li key={a.id}>{a.goal}</li>)}</ol>}
  </details>}
  <label className="block">{tr("Quale risultato vuoi ottenere adesso?","What result do you want next?")}<textarea className="mt-2 w-full rounded border p-2" rows={4} maxLength={2000} value={goal} onChange={e=>setGoal(e.target.value)} placeholder={tr("Spiega cosa vuoi mantenere e cosa cambiare. Il coordinatore chiarirà con te le scelte importanti.","Explain what to retain and what to change. The coordinator will clarify important choices with you.")}/></label>
  <p className="text-muted-foreground text-xs">{tr("Conserva consegna, sorgenti e storico. Le connessioni rimangono selezionate; un nuovo consenso serve per scrivere. Le verifiche del nuovo risultato andranno eseguite di nuovo.","Keeps delivery, sources and history. Connections remain selected; writing needs new consent. The new result must be verified again.")}</p>
  <button type="button" className="rounded border px-3 py-2 disabled:opacity-50" disabled={busy||busyTeam||!value?.can_change||!goal.trim()} onClick={()=>void evolve()}>{tr("Avvia il nuovo obiettivo","Start the new objective")}</button>
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
 </section>;
}
