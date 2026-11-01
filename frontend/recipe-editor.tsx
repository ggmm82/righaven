"use client";
import {useEffect,useMemo,useState} from "react";

import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";

export type RecipePhase={title:string;detail:string;checkpoint:boolean};
export type RecipeDraft={title:string;summary:string;when:string;attach_required:string[];attach_optional:string[];attach_never:string[];
 questions:string[];outputs:string[];prerequisites:string[];phases:RecipePhase[];skills:string[];environment:string|null;tools:string[];
 keywords:string[];guidance:string;based_on?:string|null};
type Skill={name:string;description:string;kind:"method"|"tool"};
type Environment={id:string;name:string;purpose:string;tools:string[];skills:string[]};

export const emptyDraft=():RecipeDraft=>({title:"",summary:"",when:"",attach_required:[],attach_optional:[],attach_never:[],questions:[],outputs:[],prerequisites:[],
 phases:[{title:"",detail:"",checkpoint:true}],skills:[],environment:null,tools:[],keywords:[],guidance:""});

const CORE=["skill-harness","skill-workspace","skill-problem-solving","skill-quality-review"];
const lines=(value:string)=>value.split("\n").map(x=>x.trim()).filter(Boolean).slice(0,12);

/**
 * Recipe editor as four plain steps: the result, the phases, the team's tools, a preview of the card.
 * Skills follow from the environment; technical options stay collapsed.
 */
export function RecipeEditor({it,initial,identifier,revision,onSaved,onCancel}:{it:boolean;initial:RecipeDraft;identifier?:string;revision?:number;onSaved:(id:string)=>void;onCancel:()=>void}){
 const t=(a:string,b:string)=>it?a:b;
 const [draft,setDraft]=useState<RecipeDraft>(initial),[skills,setSkills]=useState<Skill[]>([]),[environments,setEnvironments]=useState<Environment[]>([]);
 const [step,setStep]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState(""),[filter,setFilter]=useState("");
 // Lists are edited as text, one item per line; they are cleaned when saving.
 const [text,setText]=useState<Record<string,string>>(()=>Object.fromEntries((["outputs","attach_required","attach_optional","attach_never","questions","prerequisites"] as const).map(k=>[k,initial[k].join("\n")])));
 useEffect(()=>{let live=true;void fetch(`${getBackendBaseURL()}/api/harness/recipes/editor/options`).then(async r=>{const v=await r.json() as {skills:Skill[];environments:Environment[];detail?:string};if(!r.ok)throw Error(v.detail??String(r.status));if(live){setSkills(v.skills);setEnvironments(v.environments);}}).catch(e=>{if(live)setError(e instanceof Error?e.message:String(e));});return()=>{live=false;};},[]);
 const set=<K extends keyof RecipeDraft>(key:K,value:RecipeDraft[K])=>setDraft(d=>({...d,[key]:value}));
 const environment=environments.find(e=>e.id===draft.environment);
 const authorized=new Set(skills.map(s=>s.name));
 // Choosing an environment proposes its skills; the author can still add or remove them.
 function chooseEnvironment(id:string){const next=environments.find(e=>e.id===id);set("environment",id||null);
  if(next)set("skills",[...new Set([...next.skills.filter(s=>authorized.has(s)&&!CORE.includes(s)),...draft.skills])].slice(0,8));}
 const tools=useMemo(()=>[...new Set([...(environment?.tools??[]),...draft.skills.filter(s=>skills.find(k=>k.name===s)?.kind==="tool").map(s=>s.replace(/^skill-/,""))])],[environment,draft.skills,skills]);
 const chosenSkills=draft.skills.length?draft.skills:skills.filter(s=>CORE.includes(s.name)).map(s=>s.name).slice(0,1);
 const phase=(index:number,change:Partial<RecipePhase>)=>set("phases",draft.phases.map((p,i)=>i===index?{...p,...change}:p));
 const move=(index:number,offset:number)=>{const next=[...draft.phases];const [item]=next.splice(index,1);next.splice(index+offset,0,item!);set("phases",next);};
 const missing=[
  [!draft.title.trim()||!draft.summary.trim()||!draft.when.trim()||!lines(text.outputs??"").length||!lines(text.attach_required??"").length,t("completa titolo, risultato, quando usarla, cosa si ottiene e cosa si allega","complete title, result, when to use it, what you get and what to attach")],
  [!draft.phases.length||draft.phases.some(p=>!p.title.trim()||!p.detail.trim()),t("dai un nome e un risultato a ogni fase","give each phase a name and a result")],
  [!tools.length||!chosenSkills.length,t("scegli un ambiente","choose an environment")],
 ] as const;
 const steps=[t("Risultato","Result"),t("Fasi","Phases"),t("Strumenti","Tools"),t("Riepilogo","Summary")];
 async function save(){setBusy(true);setError("");try{
  const body={...draft,...Object.fromEntries(Object.entries(text).map(([k,v])=>[k,lines(v)])),skills:chosenSkills,tools,expected_revision:revision??0};
  const response=await fetch(`${getBackendBaseURL()}/api/harness/recipes${identifier?"/"+encodeURIComponent(identifier):""}`,{method:identifier?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const value=await response.json() as {recipe?:{id:string};detail?:unknown};
  if(!response.ok||!value.recipe)throw Error(typeof value.detail==="string"?value.detail:t("Controlla i campi obbligatori","Check the required fields"));
  onSaved(value.recipe.id);
 }catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
 const input="w-full rounded border bg-background p-2 text-sm";
 const hint=(a:string,b:string)=><span className="text-muted-foreground block text-xs">{t(a,b)}</span>;
 const area=(key:string,label:string,help:string,rows=3)=><label className="block space-y-1 text-sm">{label}{hint(help,help)}<textarea className={input} rows={rows} value={text[key]??""} onChange={e=>setText(v=>({...v,[key]:e.target.value}))}/></label>;
 return <section className="space-y-5 rounded-xl border p-5" data-testid="recipe-editor">
  <header className="space-y-2">
   <h2 className="text-lg font-semibold">{identifier?t("Modifica ricetta","Edit recipe"):draft.based_on?t("Nuova ricetta da una copia","New recipe from a copy"):t("Nuova ricetta","New recipe")}</h2>
   <p className="text-muted-foreground text-sm">{t("Una ricetta è un modo ripetibile di fare un tipo di lavoro: quale risultato si ottiene, in quali fasi, con quali strumenti. Chi la usa scrive solo il proprio obiettivo; la squadra segue le fasi e si ferma dove chiedi un’approvazione.","A recipe is a repeatable way to do a kind of work: which result, in which phases, with which tools. Whoever uses it only writes their goal; the team follows the phases and stops where you ask for approval.")}</p>
   <ol className="flex flex-wrap gap-2 text-sm" aria-label={t("Passi","Steps")}>{steps.map((s,i)=><li key={s}><button type="button" className={`rounded-full border px-3 py-1 ${i===step?"bg-foreground text-background":""}`} aria-current={i===step?"step":undefined} onClick={()=>setStep(i)}>{i+1}. {s}</button></li>)}</ol>
  </header>

  {step===0&&<div className="space-y-3" data-testid="recipe-step-result">
   <label className="block space-y-1 text-sm">{t("Nome della ricetta","Recipe name")}{hint("Breve, come lo diresti a un collega. Es.: «Dashboard da un foglio Excel»","Short, as you would tell a colleague. E.g. “Dashboard from an Excel sheet”")}<input className={input} maxLength={80} value={draft.title} onChange={e=>set("title",e.target.value)}/></label>
   <label className="block space-y-1 text-sm">{t("Che risultato produce","What result it produces")}{hint("Una o due frasi. Es.: «Una dashboard consultabile nel browser con i grafici delle vendite»","One or two sentences. E.g. “A browser dashboard with sales charts”")}<textarea className={input} rows={2} maxLength={400} value={draft.summary} onChange={e=>set("summary",e.target.value)}/></label>
   <label className="block space-y-1 text-sm">{t("Quando conviene usarla","When to use it")}{hint("La situazione di partenza. Es.: «Hai dei dati in Excel e vuoi mostrarli in modo chiaro»","The starting situation. E.g. “You have data in Excel and want to show it clearly”")}<input className={input} maxLength={400} value={draft.when} onChange={e=>set("when",e.target.value)}/></label>
   <div className="grid gap-3 md:grid-cols-2">
    {area("outputs",t("Cosa si ottiene alla fine","What you get at the end"),t("Un elemento per riga. Es.: «Dashboard HTML» · «File sorgente modificabile»","One per line. E.g. “HTML dashboard” · “Editable source file”"))}
    {area("attach_required",t("Cosa deve allegare chi la usa","What the user must attach"),t("Un elemento per riga. Es.: «Il foglio Excel con i dati»","One per line. E.g. “The Excel sheet with the data”"))}
   </div>
  </div>}

  {step===1&&<div className="space-y-3" data-testid="recipe-step-phases">
   <p className="text-sm">{t("Le fasi sono le tappe del lavoro, in ordine. Ognuna consegna un risultato che puoi vedere. Spunta «mi fermo per l’approvazione» solo dove vuoi decidere tu prima di proseguire; le altre fasi si chiudono da sole quando il risultato è pronto.","Phases are the steps of the work, in order. Each delivers a result you can see. Tick “stop for approval” only where you want to decide before going on; the others close by themselves when the result is ready.")}</p>
   {draft.phases.map((p,i)=><div key={i} className="space-y-2 rounded-lg border p-3" data-testid="recipe-phase">
    <div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-sm">{t("Fase","Phase")} {i+1}</strong>
     <div className="flex gap-1 text-xs"><button type="button" className="rounded border px-2" disabled={i===0} onClick={()=>move(i,-1)} aria-label={t("Sposta su","Move up")}>↑</button>
      <button type="button" className="rounded border px-2" disabled={i===draft.phases.length-1} onClick={()=>move(i,1)} aria-label={t("Sposta giù","Move down")}>↓</button>
      <button type="button" className="rounded border px-2" disabled={draft.phases.length===1} onClick={()=>set("phases",draft.phases.filter((_,j)=>j!==i))}>{t("Rimuovi","Remove")}</button></div></div>
    <input className={input} aria-label={t(`Nome fase ${i+1}`,`Phase ${i+1} name`)} placeholder={t("Es.: Indicatori","E.g. Indicators")} maxLength={80} value={p.title} onChange={e=>phase(i,{title:e.target.value})}/>
    <input className={input} aria-label={t(`Risultato fase ${i+1}`,`Phase ${i+1} result`)} placeholder={t("Cosa si vede alla fine della fase. Es.: elenco dei grafici concordati","What you see at the end. E.g. list of agreed charts")} maxLength={300} value={p.detail} onChange={e=>phase(i,{detail:e.target.value})}/>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={p.checkpoint} onChange={e=>phase(i,{checkpoint:e.target.checked})}/>{t("Mi fermo per l’approvazione","Stop for approval")}</label>
   </div>)}
   <button type="button" className="rounded border px-3 py-1 text-sm" disabled={draft.phases.length>=12} onClick={()=>set("phases",[...draft.phases,{title:"",detail:"",checkpoint:false}])}>{t("Aggiungi fase","Add phase")}</button>
  </div>}

  {step===2&&<div className="space-y-3" data-testid="recipe-step-tools">
   <p className="text-sm">{t("Scegli l’ambiente: l’insieme di programmi con cui la squadra lavorerà. Le competenze (skill) adatte vengono proposte in automatico; i programmi si preparano da soli al primo uso.","Choose the environment: the set of programs the team will work with. Suitable skills are proposed automatically; programs are prepared by themselves on first use.")}</p>
   <div className="grid gap-2 md:grid-cols-2">{environments.map(e=><label key={e.id} className={`flex cursor-pointer gap-2 rounded-lg border p-3 text-sm ${draft.environment===e.id?"border-foreground bg-muted":""}`}>
    <input type="radio" name="recipe-environment" checked={draft.environment===e.id} onChange={()=>chooseEnvironment(e.id)}/>
    <span><span className="font-medium">{e.name}</span><span className="text-muted-foreground block text-xs">{e.purpose}</span></span></label>)}</div>
   <p className="text-xs" data-testid="recipe-tools">{t("Programmi: ","Programs: ")}{tools.length?tools.join(", "):t("scegli un ambiente","choose an environment")}</p>
   <p className="text-xs">{t("Competenze: ","Skills: ")}{chosenSkills.map(s=>s.replace(/^skill-/,"")).join(", ")}</p>
   <details className="rounded border p-3 text-sm"><summary className="cursor-pointer">{t("Cambia le competenze (facoltativo)","Change the skills (optional)")}</summary>
    <input className={`${input} mt-2`} placeholder={t("Cerca","Search")} value={filter} onChange={e=>setFilter(e.target.value)}/>
    <div className="mt-2 grid max-h-56 gap-1 overflow-auto md:grid-cols-2">{skills.filter(s=>!filter||(s.name+" "+s.description).toLowerCase().includes(filter.toLowerCase())).map(s=><label key={s.name} className="flex items-start gap-2" title={s.description}>
     <input type="checkbox" checked={draft.skills.includes(s.name)} onChange={e=>set("skills",e.target.checked?[...draft.skills,s.name].slice(0,8):draft.skills.filter(x=>x!==s.name))}/>
     <span>{s.name.replace(/^skill-/,"")}<span className="text-muted-foreground block text-xs">{s.description.slice(0,110)}</span></span></label>)}</div></details>
  </div>}

  {step===3&&<div className="space-y-3" data-testid="recipe-step-summary">
   <p className="text-sm">{t("Così la vedrà chi sceglie la ricetta:","This is how users will see the recipe:")}</p>
   <div className="space-y-2 rounded-lg border p-4 text-sm" data-testid="recipe-preview">
    <p className="text-base font-semibold">{draft.title||t("(senza nome)","(no name)")}</p><p>{draft.summary}</p><p className="text-muted-foreground">{t("Quando usarla: ","When to use it: ")}{draft.when}</p>
    <p><strong>{t("Alleghi: ","You attach: ")}</strong>{lines(text.attach_required??"").join("; ")}</p>
    <p><strong>{t("Ottieni: ","You get: ")}</strong>{lines(text.outputs??"").join("; ")}</p>
    <ol className="list-inside list-decimal">{draft.phases.map((p,i)=><li key={i}>{p.title} — {p.detail} {p.checkpoint?<em>({t("approvazione","approval")})</em>:null}</li>)}</ol>
    <p className="text-muted-foreground text-xs">{t("Ambiente: ","Environment: ")}{environment?.name??"—"} · {t("Programmi: ","Programs: ")}{tools.join(", ")}</p>
   </div>
   <details className="rounded border p-3 text-sm"><summary className="cursor-pointer">{t("Dettagli facoltativi","Optional details")}</summary>
    <div className="mt-2 grid gap-3 md:grid-cols-2">
     {area("attach_optional",t("Utile se disponibile","Useful if available"),t("Un elemento per riga","One per line"),2)}
     {area("attach_never",t("Da non allegare","Do not attach"),t("Es.: password di produzione","E.g. production passwords"),2)}
     {area("questions",t("Domande che la squadra farà se mancano","Questions the team asks if missing"),t("Un elemento per riga","One per line"),2)}
     {area("prerequisites",t("Prima di iniziare","Before you start"),t("Un elemento per riga","One per line"),2)}
    </div>
    <label className="mt-3 block space-y-1">{t("Indicazioni per la squadra","Directions for the team")}{hint("Vincoli di metodo e criteri di qualità. Niente password.","Method constraints and quality criteria. No passwords.")}<textarea className={input} rows={3} maxLength={2000} value={draft.guidance} onChange={e=>set("guidance",e.target.value)}/></label>
    <label className="mt-3 block space-y-1">{t("Parole chiave","Keywords")}{hint("Separate da virgola: il coordinatore propone la ricetta quando una richiesta le contiene.","Comma separated: the coordinator proposes the recipe when a request contains them.")}<input className={input} value={draft.keywords.join(", ")} onChange={e=>set("keywords",e.target.value.split(",").map(x=>x.trim()).filter(Boolean).slice(0,20))}/></label>
   </details>
   {missing.filter(([gap])=>gap).map(([,message])=><p key={message} className="text-sm text-amber-700 dark:text-amber-300">{t("Manca: ","Missing: ")}{message}</p>)}
  </div>}

  {error&&<p className="text-destructive text-sm" role="alert">{error}</p>}
  <div className="flex flex-wrap gap-2">
   {step>0&&<button className="rounded border px-3 py-2 text-sm" disabled={busy} onClick={()=>setStep(s=>s-1)}>{t("Indietro","Back")}</button>}
   {step<3?<button className="bg-primary text-primary-foreground rounded px-3 py-2 text-sm" onClick={()=>setStep(s=>s+1)}>{t("Avanti","Next")}</button>
    :<button className="bg-primary text-primary-foreground rounded px-3 py-2 text-sm" disabled={busy||missing.some(([gap])=>gap)} onClick={()=>void save()}>{busy?t("Salvataggio…","Saving…"):t("Salva ricetta","Save recipe")}</button>}
   <button className="rounded border px-3 py-2 text-sm" disabled={busy} onClick={onCancel}>{t("Annulla","Cancel")}</button>
  </div>
 </section>;
}
