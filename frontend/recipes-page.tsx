"use client";
import {useRouter} from "next/navigation";
import {useEffect,useState} from "react";

import {ConceptMap} from "@/components/workspace/concept-map";
import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";
import {useI18n} from "@/core/i18n/hooks";
import {createThread} from "@/core/threads/api";

import {RecipeEditor,emptyDraft,type RecipeDraft} from "./recipe-editor";

type Phase={title:string;detail:string;checkpoint:boolean};
type Recipe={id:string;title:string;summary:string;when:string;phases:Phase[];starter:string;tools:string[];skills:string[];environment:string|null;
 custom:boolean;mine:boolean;shared:boolean;revision:number;based_on:string|null;intake:string[];
 attach_required:string[];attach_optional:string[];attach_never:string[];questions:string[];outputs:string[];prerequisites:string[]};

/** Recipes: phased paths that combine method skills with an environment of tools; built-in, personal or shared. */
export default function RecipesPage(){
 const {locale}=useI18n();const it=locale==="it-IT";const t=(a:string,b:string)=>it?a:b;
 const router=useRouter();
 const [reload,setReload]=useState(0),[canShare,setCanShare]=useState(false);
 const [chosen,setChosen]=useState<string|null>(null),[step,setStep]=useState(0),[busy,setBusy]=useState(false);
 const [recipes,setRecipes]=useState<Recipe[]|null>(null),[open,setOpen]=useState<string|null>(null),[error,setError]=useState("");
 useEffect(()=>{let live=true;
  void fetch(`${getBackendBaseURL()}/api/harness/recipes?locale=${it?"it":"en"}`).then(async r=>{const v=await r.json();if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));return v as {recipes:Recipe[];can_share?:boolean};})
   .then(v=>{if(live){setRecipes(v.recipes);setCanShare(!!v.can_share);setOpen(o=>o??v.recipes[0]?.id??null);
    // Links from the Community Gallery: ?use=ID starts the guided intake, ?duplicate=ID opens a copy in the editor.
    const params=new URLSearchParams(location.search);const use=params.get("use"),copy=params.get("duplicate");
    const target=v.recipes.find(r=>r.id===(use??copy));if(target&&use){setChosen(target.id);setStep(0);setOpen(target.id);}if(target&&copy)void edit(target,true);
    if(use??copy)history.replaceState(null,"",location.pathname);}}).catch(e=>{if(live)setError(e instanceof Error?e.message:String(e));});
  return()=>{live=false;};},[it,reload]);
 const [editing,setEditing]=useState<{draft:RecipeDraft;id?:string;revision?:number}|null>(null);
 async function call(url:string,init?:RequestInit){const r=await fetch(`${getBackendBaseURL()}/api/harness/recipes${url}`,init);const v=await r.json() as {draft?:RecipeDraft;detail?:unknown};if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));return v;}
 async function edit(r:Recipe,copy:boolean){setError("");try{const v=await call(`/${encodeURIComponent(r.id)}/draft?locale=${it?"it":"en"}`);setChosen(null);
  setEditing(copy?{draft:{...v.draft!,title:((it?"Copia di ":"Copy of ")+v.draft!.title).slice(0,80),based_on:r.id}}:{draft:v.draft!,id:r.id,revision:r.revision});window.scrollTo({top:0});}catch(e){setError(e instanceof Error?e.message:String(e));}}
 async function remove(r:Recipe){if(!window.confirm(t(`Eliminare la ricetta «${r.title}»? I progetti già avviati conservano le loro fasi.`,`Delete the recipe “${r.title}”? Projects already started keep their phases.`)))return;
  try{await call(`/${encodeURIComponent(r.id)}`,{method:"DELETE"});setReload(x=>x+1);}catch(e){setError(e instanceof Error?e.message:String(e));}}
 async function share(r:Recipe){try{await call(`/${encodeURIComponent(r.id)}/sharing`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({shared:!r.shared})});setReload(x=>x+1);}catch(e){setError(e instanceof Error?e.message:String(e));}}
 const [answers,setAnswers]=useState<Record<string,string>>({goal:"",source:"",destination:"",bi:"",frequency:"",notes:""});
 const [createdThread,setCreatedThread]=useState<string|null>(null);
 const selected=recipes?.find(r=>r.id===chosen);const intake=selected?.intake??["notes"];
 async function start(){if(!chosen||!(answers.goal??"").trim())return;setBusy(true);setError("");try{
  const id=createdThread??crypto.randomUUID();setCreatedThread(id);await createThread(id);
  const response=await fetch(`${getBackendBaseURL()}/api/threads/${id}/harness-journey`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({recipe_id:chosen,answers,expected_revision:0})});
  const body=await response.json() as {detail?:string};if(!response.ok)throw Error(body.detail??String(response.status));router.push(`/workspace/chats/${id}`);
 }catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
 const field=(key:string,label:string)=><label className="block space-y-1 text-sm">{label}<textarea className="w-full rounded border p-2" rows={key==="goal"?3:1} maxLength={key==="goal"||key==="notes"?2000:key==="frequency"?400:200} value={answers[key]??""} onChange={e=>setAnswers(v=>({...v,[key]:e.target.value}))}/></label>;
 const list=(title:string,items:string[],tone="")=>items.length?<div><h3 className={"text-sm font-semibold "+tone}>{title}</h3><ul className="mt-1 list-disc pl-5 text-sm">{items.map(i=><li key={i}>{i}</li>)}</ul></div>:null;
 return <div className="mx-auto w-full max-w-5xl space-y-6 p-6">
  <header className="space-y-2">
   <h1 className="text-2xl font-semibold">{t("Ricette","Recipes")}</h1>
   <p className="text-muted-foreground text-sm">{t(
    "Descrivi il risultato e avvia un percorso salvato nel progetto. Allega poi la documentazione in chat: la squadra la legge, propone le scelte mancanti e ti presenta risultati da approvare. Nessuna connessione reale è necessaria per il laboratorio di prova.",
    "Describe your outcome and start a saved guided project. Attach documentation in chat: the team reads it, proposes missing choices and presents results for approval. No real connection is needed for the test laboratory.")}</p>
   <p className="text-muted-foreground text-sm">{t("Non serve sceglierle a mano: se descrivi un lavoro che corrisponde a una ricetta, il coordinatore te la propone.","You do not have to pick them by hand: if you describe work that matches a recipe, the coordinator proposes it.")}</p>
   <ConceptMap current="recipe"/>
   {!editing&&<button className="rounded border px-3 py-2 text-sm" onClick={()=>{setChosen(null);setEditing({draft:emptyDraft()});}}>{t("Nuova ricetta","New recipe")}</button>}
  </header>
  {editing&&<RecipeEditor key={editing.id??editing.draft.based_on??"new"} it={it} initial={editing.draft} identifier={editing.id} revision={editing.revision}
   onCancel={()=>setEditing(null)} onSaved={id=>{setEditing(null);setOpen(id);setReload(x=>x+1);}}/>}
  {chosen&&<section className="space-y-4 rounded-xl border p-5" data-testid="guided-intake">
   <h2 className="text-lg font-semibold">{selected?.title} · {t("Iniziamo dal risultato","Start with the outcome")} · {step+1}/3</h2>
   {step===0&&<>{field("goal",t("Cosa vuoi realizzare? Descrivilo con parole tue.","What do you want to achieve? Use your own words."))}<p className="text-sm">{t("I documenti si allegano nella chat del progetto. Non occorre riscriverne il contenuto.","Attach documents in the project chat. You do not need to transcribe them.")}</p></>}
   {step===1&&<><p className="text-sm">{t("Queste indicazioni sono facoltative. Lascia vuoto ciò che vuoi decidere insieme alla squadra.","These choices are optional. Leave anything you want to decide with the team empty.")}</p>{intake.includes("source")&&field("source",t("Database o file sorgenti, se noti","Source database or files, if known"))}{intake.includes("destination")&&field("destination",t("Destinazione desiderata, se nota","Preferred destination, if known"))}{intake.includes("bi")&&field("bi",t("Report e strumento BI, se noti","Reports and BI tool, if known"))}{intake.includes("frequency")&&field("frequency",t("Frequenze desiderate","Desired frequencies"))}{field("notes",t("Vincoli e altre indicazioni","Constraints and other directions"))}</>}
   {step===2&&<><p>{answers.goal}</p><p className="text-sm">{t("Creeremo un progetto con fasi e approvazioni salvate. Skills, ambienti e controlli saranno applicati dalla squadra. Gli accessi reali potranno essere aggiunti successivamente; non inserire password qui.","We will create a project with saved phases and approvals. The team applies skills, environments and checks. Real connections can be added later; do not enter passwords here.")}</p></>}
   <div className="flex flex-wrap gap-2">{step>0&&<button className="rounded border px-3 py-2" disabled={busy} onClick={()=>setStep(s=>s-1)}>{t("Indietro","Back")}</button>}{step<2?<button className="rounded border px-3 py-2" disabled={!(answers.goal??"").trim()} onClick={()=>setStep(s=>s+1)}>{step===1?t("Rivedi e avvia","Review and start"):t("Avanti","Next")}</button>:<button className="rounded border px-3 py-2" disabled={busy} onClick={()=>void start()}>{busy?t("Salvataggio…","Saving…"):t("Crea progetto guidato","Create guided project")}</button>}<button className="rounded border px-3 py-2" disabled={busy} onClick={()=>setChosen(null)}>{t("Annulla","Cancel")}</button></div>
  </section>}
  {error&&<p className="text-destructive text-sm">{error}</p>}
  {recipes===null&&!error&&<p className="text-sm">{t("Caricamento…","Loading…")}</p>}
  {recipes?.map(r=><section key={r.id} className="rounded-lg border p-5" data-testid={"recipe-"+r.id}>
   <div className="flex flex-wrap items-start justify-between gap-3">
    <div className="space-y-1"><h2 className="text-lg font-semibold">{r.title} <span className="rounded border px-1 align-middle text-xs font-normal">{!r.custom?t("integrata","built-in"):r.mine?(r.shared?t("tua · nel catalogo","yours · in the catalog"):t("tua · privata","yours · private")):t("dal catalogo","from the catalog")}</span></h2><p className="text-sm">{r.summary}</p>
     <p className="text-muted-foreground text-sm"><span className="font-medium">{t("Quando usarla: ","When to use it: ")}</span>{r.when}</p></div>
    <div className="flex flex-wrap gap-2">
     {(r.mine||(canShare&&r.custom&&r.shared))&&<button className="rounded border px-3 py-2 text-sm" onClick={()=>void edit(r,false)}>{t("Modifica","Edit")}</button>}
     <button className="rounded border px-3 py-2 text-sm" onClick={()=>void edit(r,true)}>{t("Duplica","Duplicate")}</button>
     {r.custom&&(r.mine||canShare)&&<button className="rounded border px-3 py-2 text-sm" onClick={()=>void share(r)}>{r.shared?t("Ritira dal catalogo","Withdraw from the catalog"):t("Pubblica nel catalogo","Publish to the catalog")}</button>}
     {r.mine&&<button className="rounded border px-3 py-2 text-sm" onClick={()=>void remove(r)}>{t("Elimina","Delete")}</button>}
     <button className="rounded border px-3 py-2 text-sm" onClick={()=>setOpen(open===r.id?null:r.id)}>{open===r.id?t("Nascondi dettagli","Hide details"):t("Dettagli","Details")}</button>
     <button className="bg-primary text-primary-foreground rounded px-3 py-2 text-sm" onClick={()=>{setEditing(null);setChosen(r.id);setStep(0);setError("");window.scrollTo({top:0});}}>{t("Usa questa ricetta","Use this recipe")}</button>
    </div>
   </div>
   {open===r.id&&<div className="mt-4 grid gap-5 md:grid-cols-2">
    <div className="space-y-4">
     {list(t("1. Cosa alleghi","1. What you attach"),r.attach_required)}
     {list(t("Utile, se lo hai","Useful, if you have it"),r.attach_optional)}
     {list(t("Da non allegare","Do not attach"),r.attach_never,"text-destructive")}
     {list(t("2. Cosa ti verrà chiesto (se non lo scrivi già)","2. What you will be asked (unless you already say it)"),r.questions)}
    </div>
    <div className="space-y-4">
     {list(t("3. Cosa ottieni","3. What you get"),r.outputs)}
     <div><h3 className="text-sm font-semibold">{t("Come si svolge","How it runs")}</h3>
      <ol className="mt-1 space-y-1 pl-5 text-sm" style={{listStyle:"decimal"}}>{r.phases.map(p=><li key={p.title}><span className="font-medium">{p.title}</span>{p.checkpoint?<span className="ml-2 rounded border px-1 text-xs">{t("ti chiedo conferma","I ask you to confirm")}</span>:<span className="text-muted-foreground ml-2 text-xs">{t("automatica","automatic")}</span>}<div className="text-muted-foreground">{p.detail}</div></li>)}</ol></div>
     {list(t("Prima di iniziare","Before you start"),r.prerequisites)}
     <div className="text-sm" data-testid={"recipe-blocks-"+r.id}><h3 className="font-semibold">{t("Con cosa lavora","What it works with")}</h3>
      <p><span className="font-medium">{t("Skill: ","Skills: ")}</span>{r.skills.map(s=>s.replace(/^skill-/,"")).join(", ")}</p>
      <p><span className="font-medium">{t("Ambiente: ","Environment: ")}</span>{r.environment??t("solo strumenti delle skill","skill tools only")} · <span className="text-muted-foreground">{r.tools.join(", ")}</span></p></div>
    </div>
   </div>}
  </section>)}
  {recipes?.length===0&&<p className="text-sm">{t("Nessuna ricetta disponibile.","No recipes available.")}</p>}
 </div>;
}
