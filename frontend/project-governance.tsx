"use client";
import {useState} from "react";
import {useI18n} from "@/core/i18n/hooks";
import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";
import type {ProfileUse} from "./delegate-progress-state";

export type Finding={requirement_id?:string;status:string;critical?:boolean;method?:string;criterion:string;evidence:string};
export type LiveSheet={id:string;title:string;version:number;mandatory:boolean;reason:string;steps:string[];depends_on:string[];
 final:"acceptance"|number;handoff:{required:number;declared:number;violations:string[]};status:string;reviewed_at?:string;findings?:Finding[]};
export type LiveGovernance={phase:string;settled?:boolean;planned_at?:string;selected_by?:string;optional_available?:string[];
 product?:{path:string;integrity:string;issue:string};sheets?:LiveSheet[];last_validation?:{at:string;status:string};
 checkpoints?:{enabled:boolean;pending:{steps:string[];at:string}|null;discussed:number}};

type T=(it:string,en:string)=>string;
const phases=(t:T):Record<string,string>=>({briefing:t("Definizione del risultato","Defining the result"),planning:t("Execution Plan e Policy Plan","Execution Plan and Policy Plan"),
 execution:t("Esecuzione degli incarichi","Running assignments"),validation:t("Validazione finale delle policy","Final policy validation"),delivery:t("Pronto per la consegna","Ready for delivery"),delivered:t("Consegnato","Delivered")});
const verdicts=(t:T):Record<string,string>=>({passed:t("Superata","Passed"),failed:t("Da correggere","To fix"),pending:t("Da validare","To validate"),needs_review:t("Verifica incompleta","Incomplete check")});
const TONES:Record<string,string>={passed:"border-emerald-500/50",failed:"border-red-500/60",needs_review:"border-amber-500/60",pending:""};
const when=(at?:string)=>at?at.slice(0,16).replace("T"," "):"";
function useT():T{const {locale}=useI18n();return (it,en)=>locale==="it-IT"?it:en;}

function nextStep(g:LiveGovernance,t:T):string{
 const sheets=g.sheets??[];
 if(g.phase==="planning")return g.settled?t("Il coordinatore deve completare l’Execution Plan.","The coordinator must complete the Execution Plan."):t("Il coordinatore deve decidere quali policy facoltative applicare: la produzione attende.","The coordinator must decide which optional policies apply: production is waiting.");
 if(g.phase==="execution")return t("Le policy vengono applicate agli incarichi; la validazione finale avverrà sul prodotto consegnato.","Policies apply to every assignment; final validation runs on the delivered product.");
 if(g.product?.integrity==="failed")return t("Il prodotto non supera il controllo di integrità: serve una nuova consegna.","The product fails the integrity check: a new delivery is needed.");
 if(sheets.some(s=>s.status==="failed"))return t("Ci sono violazioni da correggere prima della consegna.","There are violations to fix before delivery.");
 if(sheets.some(s=>s.status==="needs_review"))return t("Alcune verifiche non sono state possibili: servono i riferimenti mancanti o la tua decisione.","Some checks were not possible: missing references or your decision are needed.");
 if(sheets.some(s=>s.status==="pending"))return g.last_validation?t("Alcune policy devono ancora essere validate su questa versione.","Some policies still need validation on this version."):t("Validazione finale non ancora eseguita su questa versione.","Final validation has not run on this version yet.");
 return g.phase==="delivered"?t("Consegnato con tutte le policy superate.","Delivered with every policy passed."):t("Tutte le policy sono superate: la consegna è autorizzata.","Every policy passed: delivery is authorized.");
}

export type ToolDecision={id:string;decision:string;options:{id:string;label:string;tools:string[];pros:string[];cons:string[]}[];recommended:string;recommendation_reason:string;chosen:string};

/** Tool alternatives from the brief: the team recommends, the user chooses. */
export function ToolChoices({decisions}:{decisions?:ToolDecision[]}){
 const t=useT();
 if(!decisions?.length)return null;
 return <section className="space-y-3 rounded-xl border p-4" data-testid="tool-choices">
  <h4 className="font-semibold">{t("Scelta degli strumenti","Tool choices")}</h4>
  <p className="text-muted-foreground text-xs">{t("La squadra propone e consiglia; la scelta è tua. La produzione attende le scelte ancora aperte.","The team proposes and recommends; you choose. Production waits for open choices.")}</p>
  {decisions.map(d=><div key={d.id} className="space-y-2">
   <p><strong>{d.decision}</strong> · {d.chosen?t("scelta registrata","choice recorded"):<span className="font-medium text-amber-700">{t("in attesa della tua scelta: rispondi nella chat","waiting for your choice: reply in the chat")}</span>}</p>
   <ul className="grid gap-2 md:grid-cols-2">{d.options.map(o=><li key={o.id} className={"space-y-1 rounded border p-2 "+(d.chosen===o.id?"border-emerald-500":d.chosen?"opacity-60":"")}>
    <p className="font-medium">{o.label}{o.id===d.recommended?` · ${t("consigliata","recommended")}`:""}{d.chosen===o.id?` · ${t("scelta","chosen")}`:""}</p>
    {o.tools.length>0&&<p className="text-muted-foreground text-xs">{t("Programmi","Software")}: {o.tools.join(", ")}</p>}
    <p className="text-xs">{t("Pregi","Pros")}: {o.pros.join("; ")}</p>
    <p className="text-xs">{t("Difetti","Cons")}: {o.cons.join("; ")}</p>
   </li>)}</ul>
   <p className="text-xs">{t("Perché la consigliamo","Why we recommend it")}: {d.recommendation_reason}</p>
  </div>)}
 </section>;
}

/** How an assignment used the owner's prepared profiles, worded in the viewer's language. */
export function ProfileUseLine({use}:{use:ProfileUse}){
 const t=useT();
 if(use.mode==="none")return <p data-testid="job-environment-profile">{t("Nessun profilo pronto condivide skill o programmi con questo ruolo: ambiente preparato su misura.","No prepared profile shares skills or software with this role: a dedicated environment was prepared.")}</p>;
 const mode={reused:t("immagine riusata così com’è","image reused as is"),extended:t("immagine estesa con","image extended with")+" "+(use.added??[]).join(", "),not_reused:t("non riusabile per versioni o installazione diverse","not reusable because of different versions or installation")}[use.mode]??use.mode;
 return <p data-testid="job-environment-profile">{t("Profilo","Profile")} <strong>{use.profile}</strong> · {mode}. {t("Skill del ruolo presenti nel profilo","Role skills in the profile")}: {use.skills?.length??0}/{use.role_skills?.length??0}{use.skills?.length?` (${use.skills.join(", ")})`:""} · {t("programmi coperti","software covered")}: {use.covered?.length??0}/{use.wanted??0}{use.missing?.length?` · ${t("mancanti","missing")}: ${use.missing.join(", ")}`:""}.</p>;
}

/** Policies governing this project, recomputed from the recorded reviews at every refresh. */
export function GovernanceStrip({governance,expanded=false,threadId,onChanged}:{governance?:LiveGovernance|null;expanded?:boolean;threadId?:string;onChanged?:(g:LiveGovernance)=>void}){
 const t=useT();
 const [busy,setBusy]=useState(false),[error,setError]=useState("");
 if(!governance)return null;
 const checkpoints=governance.checkpoints;
 async function toggle(enabled:boolean){
  if(!threadId)return;setBusy(true);setError("");
  try{const r=await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-checkpoints`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled})});
   const v=await r.json() as {governance?:LiveGovernance;detail?:string};if(!r.ok)throw Error(v.detail??String(r.status));if(v.governance)onChanged?.(v.governance);}
  catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}
 }
 const PHASES=phases(t),VERDICTS=verdicts(t);
 if(governance.phase==="legacy")return <p className="text-muted-foreground text-xs" data-testid="project-governance">{t("Progetto avviato prima del Policy Book: valgono i controlli di qualità esistenti.","Project started before the Policy Book: existing quality checks apply.")}</p>;
 const sheets=governance.sheets??[];
 const count=(status:string)=>sheets.filter(s=>s.status===status).length;
 const summary=[["passed",t("superate","passed")],["failed",t("da correggere","to fix")],["needs_review",t("incomplete","incomplete")],["pending",t("da validare","to validate")]].filter(([s])=>count(s!)).map(([s,label])=>`${count(s!)} ${label}`).join(" · ");
 return <details className="rounded-lg border p-2 text-xs" open={expanded} data-testid="project-governance">
  <summary className="cursor-pointer"><strong>Policy</strong> · {PHASES[governance.phase]??governance.phase}{sheets.length?` · ${sheets.length} ${t("applicate","applied")}${summary?" ("+summary+")":""}`:""}</summary>
  {checkpoints?.pending&&<p className="mt-1 font-medium" data-testid="checkpoint-pending">{t("In attesa della tua risposta sulla fase","Waiting for your reply on phase")} {checkpoints.pending.steps.join(", ")}: {t("leggi risultati e prossimi passi proposti e rispondi nella chat.","read the results and proposed next steps and reply in the chat.")}</p>}
  <div className="mt-2 space-y-2">
   <p>{nextStep(governance,t)}</p>
   {checkpoints&&<div className="flex flex-wrap items-center gap-2" data-testid="checkpoint-settings"><span>{checkpoints.enabled?t("Pausa a ogni fase attiva: dopo ogni incarico il coordinatore discute con te risultati e prossimi passi.","Pause after each phase is on: after every assignment the coordinator discusses results and next steps with you."):t("Pausa a ogni fase disattivata: la squadra prosegue fino alla consegna.","Pause after each phase is off: the team continues until delivery.")}{checkpoints.discussed?` ${t("Fasi discusse","Phases discussed")}: ${checkpoints.discussed}.`:""}</span>
    {threadId&&<button type="button" className="rounded border px-2 py-1 disabled:opacity-50" disabled={busy} onClick={()=>void toggle(!checkpoints.enabled)}>{checkpoints.enabled?t("Disattiva le pause","Turn pauses off"):t("Attiva le pause","Turn pauses on")}</button>}
    {error&&<span role="alert">{error}</span>}</div>}
   {governance.planned_at&&<p className="text-muted-foreground">{t("Policy Plan fissato il","Policy Plan pinned on")} {when(governance.planned_at)}{governance.selected_by==="system"?t(" dal sistema (solo sheet obbligatorie)"," by the system (mandatory sheets only)"):t(" dal coordinatore"," by the coordinator")}.</p>}
   {!governance.settled&&!!governance.optional_available?.length&&<p>{t("Sheet facoltative da valutare","Optional sheets to evaluate")}: {governance.optional_available.join(", ")}.</p>}
   <ul className="space-y-2">{sheets.map(s=><li key={s.id} className={"space-y-1 rounded border-l-4 pl-2 "+(TONES[s.status]??"")}>
    <p><strong>{s.title}</strong> v{s.version} · {VERDICTS[s.status]??s.status}{s.reviewed_at?` · ${t("revisione del","reviewed on")} ${when(s.reviewed_at)}`:""}</p>
    <p className="text-muted-foreground">{s.mandatory?t("Obbligatoria","Mandatory"):`${t("Scelta","Selected")}: ${s.reason}`}{s.steps.length?` · ${t("solo per","only for")} ${s.steps.join(", ")}`:""}{s.depends_on.length?` · ${t("dopo","after")} ${s.depends_on.join(", ")}`:""}</p>
    <p className="text-muted-foreground">{t("Verifica finale","Final check")}: {s.final==="acceptance"?t("revisione sul contratto di accettazione","review against the acceptance contract"):`${s.final} ${t("criteri della sheet","sheet criteria")}`}{s.handoff.required?` · ${t("controlli nell’handoff dichiarati","handoff checks declared")}: ${s.handoff.declared}/${s.handoff.required}`:""}</p>
    {!!s.handoff.violations.length&&<p role="alert">{t("Violazioni negli incarichi","Violations in assignments")}: {s.handoff.violations.join(", ")}.</p>}
    {!!s.findings?.length&&<ul className="list-inside list-disc">{s.findings.map((f,i)=><li key={i}><span className="font-medium">{f.status==="failed"?t("Non superato","Not passed"):t("Non verificato","Not verified")}</span>{f.requirement_id?` (${f.requirement_id})`:""}: {f.criterion||f.requirement_id} — {f.evidence}</li>)}</ul>}
   </li>)}</ul>
   {governance.product?.integrity==="failed"&&<p role="alert">{governance.product.issue}</p>}
   {governance.last_validation&&<p className="text-muted-foreground">{t("Ultima validazione finale","Last final validation")}: {when(governance.last_validation.at)} · {VERDICTS[governance.last_validation.status]??governance.last_validation.status}.</p>}
   <p><a className="underline" href="/workspace/policies">{t("Apri il Policy Book","Open the Policy Book")}</a></p>
  </div>
 </details>;
}
