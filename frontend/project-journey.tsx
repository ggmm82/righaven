"use client";
import {useCallback,useEffect,useRef,useState} from "react";

import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";
import {tr,useUiLanguage} from "@/core/i18n/ui-text";

type Text={it:string;en:string};
type Stage={id:string;title:Text;outcome:Text;status:string;available:boolean;gate?:boolean;note:string;decision_note?:string;
 evidence:{path:string;sha256:string}[];proposal?:{action:"skip";reason:string}};
export type Journey={created_at?:string;mode?:"complete"|"first_result";previous_paths?:{at:string;mode:string;stages:{id:string;status:string;title?:Text}[]}[];recipe_id:string;recipe?:{title:string;skills:string[];environment:string|null;outputs?:{it:string[];en:string[]}};revision:number;answers:Record<string,string>;
 complete:boolean;current:string|null;awaiting_owner?:string[];stages:Stage[]};
export type JourneyAction="approve"|"revise"|"skip"|"reopen"|"keep";

const DONE=["approved","skipped"];
export const continueMessage=()=>tr("Prosegui il percorso guidato salvato con harness_journey. Leggi prima gli allegati e le mie scelte; presenta il prossimo risultato utile. Non chiedermi configurazioni tecniche. Mantieni l’obiettivo originale e usa le connessioni che ho scelto; non sostituire una destinazione richiesta con una prova locale.","Continue the saved guided project with harness_journey. Read attachments and my choices first; present the next useful result. Do not ask me to write technical configuration. Keep the original objective and use my selected connections; do not replace a requested destination with a local demonstration.");

/** One source of truth for the guided project of a thread, shared by the card strip and the Path tab. */
export function useJourney(threadId:string){
 const [value,setValue]=useState<{thread:string;journey:Journey|null}|null>(null),[error,setError]=useState(""),[busy,setBusy]=useState(false);
 const pending=useRef(false);
 const base=`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-journey`;
 useEffect(()=>{let live=true,sequence=0;const controller=new AbortController();
  const load=async()=>{const request=++sequence;try{const r=await fetch(base,{signal:controller.signal,cache:"no-store"});if(!r.ok)throw Error(String(r.status));const v=await r.json() as {journey:Journey|null};if(live&&request===sequence){setValue(old=>old?.thread===threadId&&old.journey&&v.journey&&old.journey.created_at===v.journey.created_at&&old.journey.revision>v.journey.revision?old:{thread:threadId,journey:v.journey});setError("");}}catch(e){if(live&&!controller.signal.aborted)setError(e instanceof Error?e.message:String(e));}};
  const changed=(event:Event)=>{if((event as CustomEvent<string>).detail===threadId){setValue({thread:threadId,journey:null});void load();}};
  window.addEventListener("righaven-objective-changed",changed);
  void load();const timer=setInterval(()=>void load(),5000);return()=>{live=false;controller.abort();clearInterval(timer);window.removeEventListener("righaven-objective-changed",changed);};},[base,threadId]);
 const journey=value?.thread===threadId?value.journey:null;
 const decide=useCallback(async(stage:string|string[],action:JourneyAction,note="")=>{if(!journey||pending.current)return null;pending.current=true;setBusy(true);setError("");try{
  const target=Array.isArray(stage)?{stage_ids:stage}:{stage_id:stage};
  const r=await fetch(base+"/decision",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...target,action,expected_revision:journey.revision,note})});
  const v=await r.json() as {journey:Journey;detail?:unknown};if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));setValue({thread:threadId,journey:v.journey});return v.journey;
 }catch(e){setError(e instanceof Error?e.message:String(e));return null;}finally{pending.current=false;setBusy(false);}},[base,journey,threadId]);
 const simplify=useCallback(async()=>{if(!journey||pending.current)return null;pending.current=true;setBusy(true);setError("");try{
  const r=await fetch(base+"/approach",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({expected_revision:journey.revision})});
  const v=await r.json() as {journey:Journey;detail?:unknown};if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));setValue({thread:threadId,journey:v.journey});return v.journey;
 }catch(e){setError(e instanceof Error?e.message:String(e));return null;}finally{pending.current=false;setBusy(false);}},[base,journey,threadId]);
 return {journey,error,busy,decide,simplify,continuationFailed:()=>setError(tr("Decisione salvata. Non è stato possibile avviare la squadra: usa Prosegui per riprovare senza approvare di nuovo.","Decision saved. The team could not start: use Continue to retry without approving again."))};
}
export type JourneyState=ReturnType<typeof useJourney>;

async function resumeTeam(saved:Journey|null,state:JourneyState,onContinue?:((message:string)=>unknown)){
 if(!saved||(saved.awaiting_owner??[]).length||!onContinue)return;
 try{await onContinue(continueMessage());}catch{state.continuationFailed();}
}

const statusLabel=(s:string)=>({working:tr("In lavorazione","In progress"),pending:tr("Da iniziare","Not started"),review:tr("Da approvare","Awaiting approval"),approved:tr("Approvata","Approved"),skipped:tr("Saltata","Skipped"),stale:tr("Da rivalidare","Recheck needed"),blocked:tr("Da correggere","Revision requested")}[s]??s);
const tone=(s:string)=>s==="approved"?"bg-emerald-500":s==="skipped"?"bg-muted-foreground/40":s==="review"?"bg-amber-500":s==="working"?"bg-blue-500":s==="blocked"||s==="stale"?"bg-red-500":"bg-muted";
const title=(s:Stage)=>tr(s.title.it,s.title.en);
const artifact=(threadId:string,p:string)=>`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/artifacts${p.split("/").map(encodeURIComponent).join("/")}`;

function Evidence({stage,threadId}:{stage:Stage;threadId:string}){
 return stage.evidence.length?<ul className="flex flex-wrap gap-x-3">{stage.evidence.map(e=><li key={e.path}><a className="underline" href={artifact(threadId,e.path)} target="_blank" rel="noreferrer">{e.path.split("/").pop()}</a></li>)}</ul>:null;
}

/** The owner's decision, inline in the project card: never hidden behind a menu and never asked in the chat. */
function Decision({stage,state,threadId,onContinue,busyTeam}:{stage:Stage;state:JourneyState;threadId:string;onContinue?:(message:string)=>unknown;busyTeam?:boolean}){
 const [note,setNote]=useState("");
 const act=async(action:JourneyAction)=>{const saved=await state.decide(stage.id,action,note);if(saved){setNote("");await resumeTeam(saved,state,onContinue);}};
 const review=stage.status==="review";
 return <div className="space-y-2 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3" data-testid="journey-decision">
  <p className="font-medium">{review?tr(`Tocca a te: la squadra ha consegnato «${title(stage)}».`,`Your turn: the team delivered “${title(stage)}”.`):tr(`La squadra propone di saltare «${title(stage)}».`,`The team proposes skipping “${title(stage)}”.`)}</p>
  {review?<><p className="text-xs">{tr(stage.outcome.it,stage.outcome.en)}</p>{stage.note&&<p>{stage.note}</p>}<Evidence stage={stage} threadId={threadId}/></>:<p>{stage.proposal?.reason}</p>}
  <label className="block text-xs">{review?tr("Osservazioni o correzioni (facoltative)","Feedback or corrections (optional)"):tr("Nota (facoltativa)","Note (optional)")}<textarea className="mt-1 w-full rounded border p-2 text-sm" rows={2} maxLength={1500} value={note} onChange={e=>setNote(e.target.value)}/></label>
  <div className="flex flex-wrap gap-2">
   {review&&<button type="button" disabled={state.busy||busyTeam===true} className="bg-foreground text-background rounded-lg px-3 py-2" onClick={()=>void act("approve")}>{tr("Approva fase","Approve phase")}</button>}
   {review&&<button type="button" disabled={state.busy||busyTeam===true||!note.trim()} title={tr("Scrivi cosa correggere","Write what to fix")} className="rounded-lg border px-3 py-2" onClick={()=>void act("revise")}>{tr("Chiedi correzioni","Request changes")}</button>}
   <button type="button" disabled={state.busy||busyTeam===true} className="rounded-lg border px-3 py-2" onClick={()=>void act("skip")}>{tr("Salta fase","Skip phase")}</button>
   {!review&&<button type="button" disabled={state.busy||busyTeam===true} className="rounded-lg border px-3 py-2" onClick={()=>void act("keep")}>{tr("Mantieni la fase","Keep the phase")}</button>}
  </div>
 </div>;
}

/** Several skip proposals answered at once: the team compared the goal with the recipe's phases. */
function Proposals({stages,state,onContinue,busyTeam}:{stages:Stage[];state:JourneyState;onContinue?:(message:string)=>unknown;busyTeam?:boolean}){
 const act=async(action:JourneyAction)=>{await resumeTeam(await state.decide(stages.map(s=>s.id),action),state,onContinue);};
 return <div className="space-y-2 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3" data-testid="journey-proposals">
  <p className="font-medium">{tr(`Tocca a te: per il tuo obiettivo la squadra propone di saltare ${stages.length} fasi.`,`Your turn: for your goal the team proposes skipping ${stages.length} phases.`)}</p>
  <ul className="list-inside list-disc">{stages.map(s=><li key={s.id}><strong>{title(s)}</strong>: {s.proposal?.reason}</li>)}</ul>
  <div className="flex flex-wrap gap-2">
   <button type="button" disabled={state.busy||busyTeam===true} className="bg-foreground text-background rounded-lg px-3 py-2" onClick={()=>void act("skip")}>{tr(`Salta queste ${stages.length} fasi`,`Skip these ${stages.length} phases`)}</button>
   <button type="button" disabled={state.busy||busyTeam===true} className="rounded-lg border px-3 py-2" onClick={()=>void act("keep")}>{tr("Mantienile tutte","Keep them all")}</button>
  </div>
  <p className="text-muted-foreground text-xs">{tr("Per sceglierle una per una apri «Tutte le fasi».","To choose one by one open “All phases”.")}</p>
 </div>;
}

export const settledPhases=(journey:Journey)=>journey.stages.filter(s=>DONE.includes(s.status)).length;

/** Compact path strip shown in the project card: where we are, what waits for the owner, how to go on. */
export function JourneyStrip({threadId,state,onOpen,onContinue,busyTeam,embedded=false,currentGoal}:{currentGoal?:string;threadId:string;state:JourneyState;onOpen?:()=>void;onContinue?:(message:string)=>unknown;busyTeam?:boolean;embedded?:boolean}){
 const language=useUiLanguage();
 const journey=state.journey;
 if(!journey)return null;
 const settled=journey.stages.filter(s=>DONE.includes(s.status)).length;
 const current=journey.stages.find(s=>s.id===journey.current);
 const waiting=journey.stages.filter(s=>(journey.awaiting_owner??[]).includes(s.id));
 // Embedded in the project card the strip has no title, counter or buttons of its own: the card provides one header and one action row.
 return <section className={embedded?"space-y-2 text-sm":"space-y-2 border-b p-3 text-sm"} data-testid="project-journey" aria-label={tr("Percorso guidato","Guided project")}>
  {!embedded&&<div className="flex flex-wrap items-baseline justify-between gap-2">
   <p className="font-semibold">{tr("Percorso guidato","Guided project")}{journey.recipe?.title?` · ${journey.recipe.title}`:""}</p>
   <p className="text-muted-foreground text-xs" data-testid="journey-progress">{settled}/{journey.stages.length} {tr("fasi concluse","phases settled")}</p>
  </div>}
  <ol className="flex gap-1" aria-label={tr("Fasi del percorso","Guided phases")}>{journey.stages.map(s=><li key={s.id} className="min-w-0 flex-1" title={`${title(s)} · ${statusLabel(s.status)}`}>
   <span className={`block h-1.5 rounded-full ${tone(s.status)} ${s.id===journey.current?"ring-2 ring-offset-1 ring-blue-500/60":""}`}/><span className="sr-only">{title(s)}: {statusLabel(s.status)}</span></li>)}</ol>
  <p data-testid="journey-goal"><strong>{tr("Obiettivo:","Goal:")}</strong> {currentGoal?.trim()?currentGoal:journey.answers.goal}</p>
  {currentGoal&&currentGoal!==journey.answers.goal&&<details className="text-xs text-muted-foreground"><summary>{tr("Obiettivo iniziale del percorso","Initial guided goal")}</summary><p>{journey.answers.goal}</p></details>}
  {journey.mode!=="first_result"&&!journey.complete&&<button type="button" className="text-xs underline" disabled={state.busy||busyTeam===true} onClick={()=>{
   if(window.confirm(tr("Passare a un risultato da provare con sorgenti e verifiche, senza una seconda fase di confezionamento? File, obiettivo, connessioni e storico restano conservati. Le nuove fasi richiedono risultati verificati.","Switch to a working result with sources and verification, without a second packaging stage? Files, goal, connections and history are retained. New phases require verified results.")))void state.simplify().then(saved=>resumeTeam(saved,state,onContinue));
  }}>{tr("Semplifica il percorso conservando i file","Simplify the path and keep files")}</button>}
  {!!journey.recipe?.outputs&&<details className="text-xs"><summary className="cursor-pointer">{currentGoal&&currentGoal!==journey.answers.goal?tr("Riferimento della ricetta iniziale","Original recipe reference"):tr("Cosa ottieni alla fine","What you get at the end")}</summary>
   <ul className="mt-1 list-inside list-disc">{journey.recipe.outputs[language].map(o=><li key={o}>{o}</li>)}</ul>
   {journey.stages.some(s=>s.status==="skipped")&&<p className="text-muted-foreground mt-1">{tr("Le fasi saltate non producono i loro risultati.","Skipped phases do not produce their results.")}</p>}</details>}
  {journey.complete?<p>{tr("Tutte le fasi sono concluse: la squadra può completare la consegna.","All phases are settled: the team can complete the delivery.")}</p>
   :current&&<p data-testid="journey-current"><strong>{tr(`Fase ${journey.stages.indexOf(current)+1} di ${journey.stages.length}:`,`Phase ${journey.stages.indexOf(current)+1} of ${journey.stages.length}:`)}</strong> {title(current)} · {statusLabel(current.status)}{current.gate===false?tr(" · senza approvazione"," · no approval needed"):""}</p>}
  {waiting.filter(s=>s.status==="review"||waiting.filter(w=>w.status!=="review").length===1).map(s=><Decision key={s.id+":"+journey.revision} stage={s} state={state} threadId={threadId} onContinue={onContinue} busyTeam={busyTeam}/>)}
  {waiting.filter(s=>s.status!=="review").length>1&&<Proposals stages={waiting.filter(s=>s.status!=="review")} state={state} onContinue={onContinue} busyTeam={busyTeam}/>}
  {state.error&&<p className="text-xs" role="alert">{state.error}</p>}
  {!embedded&&<div className="flex flex-wrap gap-2">
   {onOpen&&<button type="button" className="rounded-lg border px-3 py-1.5" onClick={onOpen}>{tr("Tutte le fasi","All phases")}</button>}
   {onContinue&&!waiting.length&&!journey.complete&&!busyTeam&&<button type="button" disabled={state.busy} className="rounded-lg border px-3 py-1.5" onClick={()=>onContinue(continueMessage())}>{tr("Prosegui con la squadra","Continue with the team")}</button>}
  </div>}
 </section>;
}

/** Every phase with its result and the owner's controls: approve, revise, skip or resume a skipped phase. */
export function JourneyPhases({threadId,state,currentGoal}:{threadId:string;state:JourneyState;currentGoal?:string}){
 useUiLanguage();
 const journey=state.journey;
 const [note,setNote]=useState<Record<string,string>>({});
 if(!journey)return null;
 const waiting=journey.awaiting_owner??[];
 return <div className="space-y-3 text-sm" data-testid="journey-phases">
  <section className="bg-muted/30 space-y-1 rounded-xl border p-3"><h4 className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">{tr("Obiettivo","Goal")}</h4><p>{currentGoal?.trim()?currentGoal:journey.answers.goal}</p>
   <p className="text-muted-foreground text-xs">{tr("Allega i documenti nella chat: li leggeremo prima di chiederti le informazioni mancanti. Puoi completare il laboratorio senza connessioni reali.","Attach documents in chat: we read them before asking for missing information. You can complete the lab without real connections.")}</p>
   {journey.recipe&&<p className="text-muted-foreground text-xs">{tr("Skill:","Skills:")} {journey.recipe.skills.map(s=>s.replace(/^skill-/,"")).join(", ")}{journey.recipe.environment?` · ${tr("Ambiente:","Environment:")} ${journey.recipe.environment}`:""}</p>}</section>
  {!!journey.previous_paths?.length&&<details className="rounded border p-3 text-xs"><summary>{tr("Percorso precedente e decisioni conservate","Previous path and retained decisions")}</summary>{journey.previous_paths.map(p=><ul key={p.at} className="mt-2">{p.stages.map(s=><li key={s.id}>{s.title?tr(s.title.it,s.title.en):s.id} · {statusLabel(s.status)}</li>)}</ul>)}</details>}
  <ol className="space-y-2">{journey.stages.map((s,i)=><li key={s.id} className={`space-y-2 rounded-xl border p-3 ${s.id===journey.current?"border-blue-500/40 bg-blue-500/5":""}`} data-testid="journey-phase">
   <div className="flex flex-wrap items-center justify-between gap-2"><strong>{i+1}. {title(s)}</strong><span className="flex items-center gap-1 text-xs"><span aria-hidden className={`inline-block h-2 w-2 rounded-full ${tone(s.status)}`}/>{statusLabel(s.status)}{s.gate===false?tr(" · senza approvazione"," · no approval needed"):""}</span></div>
   <p className="text-muted-foreground">{tr(s.outcome.it,s.outcome.en)}</p>
   {s.note&&<p>{s.note}</p>}{s.decision_note&&<p className="text-xs">{tr("Tua nota:","Your note:")} {s.decision_note}</p>}
   <Evidence stage={s} threadId={threadId}/>
   {waiting.includes(s.id)?<p className="text-xs font-medium">{tr("Decidi dal riquadro «Tocca a te» nella scheda del progetto.","Decide from the “Your turn” box in the project card.")}</p>
    :<div className="flex flex-wrap items-center gap-2">
     {s.available&&!DONE.includes(s.status)&&<><input className="min-w-0 flex-1 rounded border p-1 text-xs" aria-label={tr(`Motivo per saltare ${title(s)}`,`Reason to skip ${title(s)}`)} placeholder={tr("Motivo (facoltativo)","Reason (optional)")} maxLength={1500} value={note[s.id]??""} onChange={e=>setNote(n=>({...n,[s.id]:e.target.value}))}/>
      <button type="button" disabled={state.busy} className="rounded-lg border px-2 py-1 text-xs" onClick={()=>void state.decide(s.id,"skip",note[s.id]??"")}>{tr("Salta fase","Skip phase")}</button></>}
     {s.status==="skipped"&&s.available&&<button type="button" disabled={state.busy} className="rounded-lg border px-2 py-1 text-xs" onClick={()=>void state.decide(s.id,"reopen")}>{tr("Riprendi questa fase","Resume this phase")}</button>}
    </div>}
  </li>)}</ol>
  {state.error&&<p role="alert">{state.error}</p>}
 </div>;
}

/** Standalone card before a native project exists: strip plus all phases inline. */
export function ProjectJourney({threadId,state,onContinue}:{threadId:string;state:JourneyState;onContinue?:(message:string)=>unknown}){
 useUiLanguage();
 const [open,setOpen]=useState(false);
 if(!state.journey)return null;
 return <div className="bg-background mb-2 rounded-2xl border shadow-sm" data-testid="journey-card">
  <JourneyStrip threadId={threadId} state={state} onContinue={onContinue} onOpen={()=>setOpen(o=>!o)}/>
  {open&&<div className="max-h-[60dvh] overflow-auto p-3"><JourneyPhases threadId={threadId} state={state}/></div>}
 </div>;
}
