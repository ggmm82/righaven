"use client";
import {useRouter} from "next/navigation";
import {useEffect,useState} from "react";

import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";
import {useI18n} from "@/core/i18n/hooks";

type Phase={title:string;detail:string;checkpoint:boolean};
type Recipe={id:string;title:string;summary:string;when:string;phases:Phase[];starter:string;tools:string[];
 attach_required:string[];attach_optional:string[];attach_never:string[];questions:string[];outputs:string[];prerequisites:string[]};

/** Recipes: tested workflows started from a prefilled task; their tools are prepared on demand. */
export default function RecipesPage(){
 const {locale}=useI18n();const it=locale==="it-IT";const t=(a:string,b:string)=>it?a:b;
 const router=useRouter();
 const [recipes,setRecipes]=useState<Recipe[]|null>(null),[open,setOpen]=useState<string|null>(null),[error,setError]=useState("");
 useEffect(()=>{let live=true;
  void fetch(`${getBackendBaseURL()}/api/harness/recipes?locale=${it?"it":"en"}`).then(async r=>{const v=await r.json();if(!r.ok)throw Error(typeof v.detail==="string"?v.detail:String(r.status));return v.recipes as Recipe[];})
   .then(v=>{if(live){setRecipes(v);setOpen(o=>o??v[0]?.id??null);}}).catch(e=>{if(live)setError(e instanceof Error?e.message:String(e));});
  return()=>{live=false;};},[it]);
 const list=(title:string,items:string[],tone="")=>items.length?<div><h3 className={"text-sm font-semibold "+tone}>{title}</h3><ul className="mt-1 list-disc pl-5 text-sm">{items.map(i=><li key={i}>{i}</li>)}</ul></div>:null;
 return <div className="mx-auto w-full max-w-5xl space-y-6 p-6">
  <header className="space-y-2">
   <h1 className="text-2xl font-semibold">{t("Ricette","Recipes")}</h1>
   <p className="text-muted-foreground text-sm">{t(
    "Una ricetta è un percorso già collaudato per un tipo di lavoro. Scegli «Usa questa ricetta»: si apre un nuovo lavoro con il messaggio già impostato. Completa le parti tra parentesi, allega i file e invia. Gli strumenti vengono preparati da soli quando servono; il coordinatore ti chiede solo ciò che manca e si ferma con te ai punti di verifica.",
    "A recipe is a tested path for one kind of work. Choose “Use this recipe”: a new task opens with the message already set. Fill in the bracketed parts, attach the files and send. Tools are prepared automatically when needed; the coordinator asks only for what is missing and stops with you at the checkpoints.")}</p>
   <p className="text-muted-foreground text-sm">{t("Non serve sceglierle a mano: se descrivi un lavoro che corrisponde a una ricetta, il coordinatore te la propone.","You do not have to pick them by hand: if you describe work that matches a recipe, the coordinator proposes it.")}</p>
  </header>
  {error&&<p className="text-destructive text-sm">{error}</p>}
  {recipes===null&&!error&&<p className="text-sm">{t("Caricamento…","Loading…")}</p>}
  {recipes?.map(r=><section key={r.id} className="rounded-lg border p-5" data-testid={"recipe-"+r.id}>
   <div className="flex flex-wrap items-start justify-between gap-3">
    <div className="space-y-1"><h2 className="text-lg font-semibold">{r.title}</h2><p className="text-sm">{r.summary}</p>
     <p className="text-muted-foreground text-sm"><span className="font-medium">{t("Quando usarla: ","When to use it: ")}</span>{r.when}</p></div>
    <div className="flex gap-2">
     <button className="rounded border px-3 py-2 text-sm" onClick={()=>setOpen(open===r.id?null:r.id)}>{open===r.id?t("Nascondi dettagli","Hide details"):t("Dettagli","Details")}</button>
     <button className="bg-primary text-primary-foreground rounded px-3 py-2 text-sm" onClick={()=>router.push("/workspace/chats/new?recipe="+encodeURIComponent(r.id))}>{t("Usa questa ricetta","Use this recipe")}</button>
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
      <ol className="mt-1 space-y-1 pl-5 text-sm" style={{listStyle:"decimal"}}>{r.phases.map(p=><li key={p.title}><span className="font-medium">{p.title}</span>{p.checkpoint&&<span className="ml-2 rounded border px-1 text-xs">{t("ti chiedo conferma","I ask you to confirm")}</span>}<div className="text-muted-foreground">{p.detail}</div></li>)}</ol></div>
     {list(t("Prima di iniziare","Before you start"),r.prerequisites)}
    </div>
   </div>}
  </section>)}
  {recipes?.length===0&&<p className="text-sm">{t("Nessuna ricetta disponibile.","No recipes available.")}</p>}
 </div>;
}
