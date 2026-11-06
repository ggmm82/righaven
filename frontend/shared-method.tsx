"use client";
import {useEffect,useRef,useState} from "react";

import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";
import {tr,useUiLanguage} from "@/core/i18n/ui-text";

type Choice={method:string;reason:string;status?:string};
type Method={signature:string;strategy:({method:string;reason:string;alternatives:Choice[]}|null);decision?:{method:string;note:string}|null;history:{method:string;note:string;at:string}[];recipe_available:boolean;recipe_stale:boolean};

/** Owner choices over the existing strategy: no second plan, no implicit recipe publication. */
export function SharedMethod({threadId,busyTeam,onContinue}:{threadId:string;busyTeam:boolean;onContinue?:(message?:string)=>void|Promise<void>}){
 useUiLanguage();
 const [value,setValue]=useState<Method|null>(null),[choice,setChoice]=useState(0),[note,setNote]=useState("");
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 const inFlight=useRef(false),owner=useRef(threadId); owner.current=threadId;
 const base=`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-method`;
 useEffect(()=>{let live=true;const controller=new AbortController();
  const load=async()=>{try{const r=await fetch(base,{signal:controller.signal,cache:"no-store"});if(!r.ok)throw Error(String(r.status));const v=await r.json() as Method;if(live)setValue(v);}catch(e){if(live&&!controller.signal.aborted)setError(e instanceof Error?e.message:String(e));}};
  setValue(null);void load();const timer=setInterval(()=>void load(),5000);return()=>{live=false;controller.abort();clearInterval(timer);};
 },[base]);
 async function choose(){if(!value||inFlight.current)return;inFlight.current=true;setBusy(true);setError("");setNotice("");
  try{const r=await fetch(base+"/choice",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({signature:value.signature,choice,note})});
   const v=await r.json() as Method&{detail?:string};if(!r.ok)throw Error(v.detail??String(r.status));if(owner.current!==threadId)return;setValue(v);setNote("");setNotice(tr("Scelta salvata.","Choice saved."));
   if(onContinue)try{await onContinue(tr("Applica la mia scelta del metodo salvata nel progetto. Spiega la prossima prova utile e procedi entro i vincoli concordati.","Apply my saved method choice. Explain the next useful trial and proceed within the agreed constraints."));}catch{setNotice(tr("Scelta salvata. Usa Prosegui per riavviare la squadra.","Choice saved. Use Continue to resume the team."));}
  }catch(e){setError(e instanceof Error?e.message:String(e));}finally{inFlight.current=false;setBusy(false);}
 }
 if(!value?.strategy)return error?<p role="alert">{error}</p>:null;
 const options:Choice[]=[value.strategy,...value.strategy.alternatives];
 return <section className="mt-3 space-y-3 border-t pt-3" data-testid="shared-method">
  {value.decision&&<p><strong>{tr("La tua scelta:","Your choice:")}</strong> {value.decision.method}{value.decision.note&&` · ${value.decision.note}`}</p>}
  <label className="block text-sm">{tr("Quale approccio vuoi provare?","Which approach would you like to try?")}
   <select className="bg-background mt-1 w-full rounded border p-2" value={choice} onChange={e=>setChoice(Number(e.target.value))} disabled={busy||busyTeam}>
    {options.map((o,i)=>options.findIndex(candidate=>candidate.method===o.method)===i?<option key={i} value={i} disabled={o.status==="unavailable"}>{o.method}</option>:null)}
   </select>
  </label>
  <label className="block text-sm">{tr("Indicazioni o vincoli aggiuntivi","Additional directions or constraints")}<textarea className="mt-1 w-full rounded border p-2" rows={2} maxLength={1500} value={note} onChange={e=>setNote(e.target.value)}/></label>
  <button type="button" className="rounded border px-3 py-2 disabled:opacity-50" disabled={busy||busyTeam} onClick={()=>void choose()}>{tr("Scegli e prosegui","Choose and continue")}</button>
  {value.recipe_available?<a className="ml-3 underline" href={`/workspace/recipes?from_thread=${encodeURIComponent(threadId)}`} target="_blank" rel="noopener noreferrer">{tr("Rivedi e salva la ricetta","Review and save the recipe")}</a>:<p className="text-muted-foreground text-xs">{value.recipe_stale?tr("Il metodo è cambiato: la bozza della ricetta va rivalutata.","The method changed: the recipe draft needs reassessment."):tr("Dopo una prova riuscita puoi chiedere in chat di proporre questo metodo come ricetta riutilizzabile. Rivedrai la bozza prima di salvarla; la pubblicazione sarà una scelta separata.","After a successful trial, ask in chat to propose this method as a reusable recipe. You review the draft before saving; publishing is a separate choice.")}</p>}
  {value.history.length>0&&<details className="text-xs"><summary>{tr("Decisioni sul metodo","Method decisions")}</summary><ol className="mt-2 space-y-2">{value.history.map((h,i)=><li key={i}><time>{new Date(h.at).toLocaleString()}</time> · {h.method}{h.note&&` · ${h.note}`}</li>)}</ol></details>}
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
 </section>;
}
