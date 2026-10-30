"use client";
import {useEffect,useState} from "react";
import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";

export type Governance={phase:string;policy_plan?:{settled:boolean;sheets:string[];optional_available?:string[]};
 policy_validation?:{status:string;at?:string;integrity?:{status:string;issue:string};sheets:{id:string;title?:string;status:string}[]}};

const PHASES:Record<string,string>={briefing:"Definizione del risultato",planning:"Execution Plan e Policy Plan",execution:"Esecuzione degli incarichi",
 validation:"Validazione finale delle policy",delivery:"Pronto per la consegna",delivered:"Consegnato"};
const VERDICTS:Record<string,string>={passed:"Superata",failed:"Da correggere",pending:"Da validare",needs_review:"Verifica incompleta",blocked:"Consegna non integra"};

/** Which policies govern this project and how far the final validation got. */
export function ProjectGovernance({governance}:{governance?:Governance}){
 const [titles,setTitles]=useState<Record<string,string>>({});
 useEffect(()=>{let live=true;void fetch(getBackendBaseURL()+"/api/harness/policy-book").then(r=>r.ok?r.json():{sheets:[]})
  .then((v:{sheets:{id:string;title:string}[]})=>{if(live)setTitles(Object.fromEntries(v.sheets.map(s=>[s.id,s.title])));}).catch(()=>undefined);return()=>{live=false;};},[]);
 if(!governance)return null;
 if(governance.phase==="legacy")return <p className="text-muted-foreground text-xs" data-testid="project-governance">Progetto avviato prima del Policy Book: valgono i controlli di qualità esistenti.</p>;
 const verdicts=Object.fromEntries((governance.policy_validation?.sheets??[]).map(s=>[s.id,s.status]));
 const plan=governance.policy_plan;
 return <section className="space-y-2 rounded-xl border p-4" data-testid="project-governance">
  <h4 className="font-semibold">Governance del progetto</h4>
  <p><strong>Fase:</strong> {PHASES[governance.phase]??governance.phase}</p>
  {plan&&!plan.settled&&<p>Il coordinatore deve ancora decidere quali policy facoltative applicare{plan.optional_available?.length?": "+plan.optional_available.map(id=>titles[id]??id).join(", "):""}. La produzione attende questa scelta.</p>}
  {plan&&<ul className="space-y-1">{plan.sheets.map(id=><li key={id} className="flex flex-wrap items-center gap-2">
   <span>{titles[id]??id}</span><span className="rounded-full border px-2 py-0.5 text-xs">{VERDICTS[verdicts[id]??"pending"]}</span></li>)}</ul>}
  {governance.policy_validation?.integrity?.status==="failed"&&<p role="alert">{governance.policy_validation.integrity.issue}</p>}
  {governance.policy_validation?.at&&<p className="text-muted-foreground text-xs">Ultima validazione: {governance.policy_validation.at.slice(0,16).replace("T"," ")} · esito {VERDICTS[governance.policy_validation.status]??governance.policy_validation.status}. La consegna richiede tutte le policy superate sul file esatto.</p>}
  <p className="text-xs"><a className="underline" href="/workspace/policies">Apri il Policy Book</a></p>
 </section>;
}
