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

const LISTS:[keyof RecipeDraft,string,string,string,string][]=[
 ["attach_required","Cosa allega l’utente (obbligatorio)","What the user attaches (required)","Un elemento per riga","One item per line"],
 ["attach_optional","Utile, se disponibile","Useful, if available","",""],
 ["attach_never","Da non allegare","Do not attach","Per esempio: password di produzione","For example: production passwords"],
 ["questions","Domande che la squadra farà se mancano","Questions the team asks when missing","",""],
 ["outputs","Cosa si ottiene (obbligatorio)","What you get (required)","",""],
 ["prerequisites","Prima di iniziare","Before you start","",""],
];

/** Recipe editor: a recipe is the phased path that combines method skills with an environment of tools. */
export function RecipeEditor({it,initial,identifier,revision,onSaved,onCancel}:{it:boolean;initial:RecipeDraft;identifier?:string;revision?:number;onSaved:(id:string)=>void;onCancel:()=>void}){
 const t=(a:string,b:string)=>it?a:b;
 const [draft,setDraft]=useState<RecipeDraft>(initial),[skills,setSkills]=useState<Skill[]>([]),[environments,setEnvironments]=useState<Environment[]>([]);
 const [filter,setFilter]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState("");
 useEffect(()=>{let live=true;void fetch(`${getBackendBaseURL()}/api/harness/recipes/editor/options`).then(async r=>{const v=await r.json() as {skills:Skill[];environments:Environment[];detail?:string};if(!r.ok)throw Error(v.detail??String(r.status));if(live){setSkills(v.skills);setEnvironments(v.environments);}}).catch(e=>{if(live)setError(e instanceof Error?e.message:String(e));});return()=>{live=false;};},[]);
 const set=<K extends keyof RecipeDraft>(key:K,value:RecipeDraft[K])=>setDraft(d=>({...d,[key]:value}));
 const environment=environments.find(e=>e.id===draft.environment);
 // Tools follow from the environment and the tool skills; the author never types program names.
 const tools=useMemo(()=>[...new Set([...(environment?.tools??[]),...draft.skills.filter(s=>skills.find(k=>k.name===s)?.kind==="tool").map(s=>s.replace(/^skill-/,""))])],[environment,draft.skills,skills]);
 const visible=skills.filter(s=>!filter||(s.name+" "+s.description).toLowerCase().includes(filter.toLowerCase()));
 const phase=(index:number,change:Partial<RecipePhase>)=>set("phases",draft.phases.map((p,i)=>i===index?{...p,...change}:p));
 const move=(index:number,step:number)=>{const next=[...draft.phases];const [item]=next.splice(index,1);next.splice(index+step,0,item!);set("phases",next);};
 const ready=draft.title.trim()&&draft.summary.trim()&&draft.when.trim()&&draft.attach_required.length&&draft.outputs.length&&draft.skills.length&&tools.length&&draft.phases.every(p=>p.title.trim()&&p.detail.trim());
 async function save(){setBusy(true);setError("");try{
  const body={...draft,tools,expected_revision:revision??0};
  const response=await fetch(`${getBackendBaseURL()}/api/harness/recipes${identifier?"/"+encodeURIComponent(identifier):""}`,{method:identifier?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const value=await response.json() as {recipe?:{id:string};detail?:unknown};
  if(!response.ok||!value.recipe)throw Error(typeof value.detail==="string"?value.detail:t("Controlla i campi obbligatori","Check the required fields"));
  onSaved(value.recipe.id);
 }catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
 const input="w-full rounded border p-2 text-sm";
 return <section className="space-y-5 rounded-xl border p-5" data-testid="recipe-editor">
  <h2 className="text-lg font-semibold">{identifier?t("Modifica ricetta","Edit recipe"):draft.based_on?t("Nuova ricetta da una copia","New recipe from a copy"):t("Nuova ricetta","New recipe")}</h2>
  <div className="grid gap-3 md:grid-cols-2">
   <label className="space-y-1 text-sm">{t("Titolo","Title")}<input className={input} maxLength={80} value={draft.title} onChange={e=>set("title",e.target.value)}/></label>
   <label className="space-y-1 text-sm">{t("Quando usarla","When to use it")}<input className={input} maxLength={400} value={draft.when} onChange={e=>set("when",e.target.value)}/></label>
   <label className="space-y-1 text-sm md:col-span-2">{t("Cosa produce, in breve","What it produces, briefly")}<textarea className={input} rows={2} maxLength={400} value={draft.summary} onChange={e=>set("summary",e.target.value)}/></label>
  </div>
  <fieldset className="space-y-2"><legend className="text-sm font-semibold">{t("1. Metodo: skill","1. Method: skills")}</legend>
   <p className="text-muted-foreground text-xs">{t("Le skill dicono come lavorare: metodi, controlli di qualità e competenza sugli strumenti. Sono quelle abilitate nel tuo account.","Skills say how to work: methods, quality checks and tool expertise. These are the ones enabled in your account.")}</p>
   <input className={input} placeholder={t("Filtra skill","Filter skills")} value={filter} onChange={e=>setFilter(e.target.value)}/>
   <div className="grid max-h-56 gap-1 overflow-auto rounded border p-2 md:grid-cols-2">{visible.map(s=><label key={s.name} className="flex items-start gap-2 text-sm" title={s.description}>
    <input type="checkbox" checked={draft.skills.includes(s.name)} onChange={e=>set("skills",e.target.checked?[...draft.skills,s.name].slice(0,8):draft.skills.filter(x=>x!==s.name))}/>
    <span><span className="font-medium">{s.name.replace(/^skill-/,"")}</span> <span className="rounded border px-1 text-xs">{s.kind==="tool"?t("strumento","tool"):t("metodo","method")}</span><span className="text-muted-foreground block text-xs">{s.description.slice(0,120)}</span></span></label>)}</div>
  </fieldset>
  <fieldset className="space-y-2"><legend className="text-sm font-semibold">{t("2. Strumenti: ambiente","2. Tools: environment")}</legend>
   <p className="text-muted-foreground text-xs">{t("L’ambiente dice con quali programmi lavorare; vengono preparati al primo utilizzo.","The environment says which programs to work with; they are prepared on first use.")}</p>
   <select className={input} aria-label={t("Ambiente","Environment")} value={draft.environment??""} onChange={e=>set("environment",e.target.value||null)}>
    <option value="">{t("Nessun ambiente: solo gli strumenti delle skill scelte","No environment: only the tools of the chosen skills")}</option>
    {environments.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select>
   {environment&&<p className="text-muted-foreground text-xs">{environment.purpose}</p>}
   <p className="text-xs" data-testid="recipe-tools">{t("Strumenti risultanti: ","Resulting tools: ")}{tools.length?tools.join(", "):t("nessuno, scegli un ambiente o una skill strumento","none, choose an environment or a tool skill")}</p>
  </fieldset>
  <fieldset className="space-y-2"><legend className="text-sm font-semibold">{t("3. Percorso: fasi","3. Path: phases")}</legend>
   <p className="text-muted-foreground text-xs">{t("Ogni fase consegna un risultato. Con «chiede approvazione» la squadra si ferma finché non approvi; senza, la fase si chiude quando il risultato è salvato. Il proprietario può sempre saltare una fase non utile.","Each phase delivers a result. With “asks for approval” the team waits for your approval; without it, the phase closes when the result is saved. The owner can always skip a phase that is not useful.")}</p>
   {draft.phases.map((p,i)=><div key={i} className="grid gap-2 rounded border p-2 md:grid-cols-[2rem_1fr_2fr_auto]" data-testid="recipe-phase">
    <span className="pt-2 text-sm font-semibold">{i+1}</span>
    <input className={input} aria-label={t(`Titolo fase ${i+1}`,`Phase ${i+1} title`)} maxLength={80} value={p.title} onChange={e=>phase(i,{title:e.target.value})}/>
    <input className={input} aria-label={t(`Risultato fase ${i+1}`,`Phase ${i+1} result`)} maxLength={300} placeholder={t("Risultato atteso","Expected result")} value={p.detail} onChange={e=>phase(i,{detail:e.target.value})}/>
    <div className="flex flex-wrap items-center gap-2 text-xs"><label className="flex items-center gap-1"><input type="checkbox" checked={p.checkpoint} onChange={e=>phase(i,{checkpoint:e.target.checked})}/>{t("chiede approvazione","asks for approval")}</label>
     <button type="button" className="rounded border px-2" disabled={i===0} onClick={()=>move(i,-1)} aria-label={t("Sposta su","Move up")}>↑</button>
     <button type="button" className="rounded border px-2" disabled={i===draft.phases.length-1} onClick={()=>move(i,1)} aria-label={t("Sposta giù","Move down")}>↓</button>
     <button type="button" className="rounded border px-2" disabled={draft.phases.length===1} onClick={()=>set("phases",draft.phases.filter((_,j)=>j!==i))}>{t("Rimuovi","Remove")}</button></div>
   </div>)}
   <button type="button" className="rounded border px-3 py-1 text-sm" disabled={draft.phases.length>=12} onClick={()=>set("phases",[...draft.phases,{title:"",detail:"",checkpoint:true}])}>{t("Aggiungi fase","Add phase")}</button>
  </fieldset>
  <fieldset className="grid gap-3 md:grid-cols-2"><legend className="mb-2 text-sm font-semibold">{t("4. Cosa serve e cosa si ottiene","4. What is needed and what you get")}</legend>
   {LISTS.map(([key,itLabel,enLabel,itHint,enHint])=><label key={key} className="space-y-1 text-sm">{t(itLabel,enLabel)}
    <textarea className={input} rows={3} placeholder={t(itHint,enHint)} value={(draft[key] as string[]).join("\n")} onChange={e=>set(key,e.target.value.split("\n").slice(0,12) as never)} onBlur={e=>set(key,e.target.value.split("\n").map(x=>x.trim()).filter(Boolean).slice(0,12) as never)}/></label>)}
  </fieldset>
  <label className="block space-y-1 text-sm">{t("Indicazioni per la squadra (facoltative)","Directions for the team (optional)")}
   <textarea className={input} rows={3} maxLength={2000} value={draft.guidance} onChange={e=>set("guidance",e.target.value)} placeholder={t("Vincoli di metodo, criteri di qualità, cosa non fare. Niente credenziali.","Method constraints, quality criteria, what not to do. No credentials.")}/></label>
  <label className="block space-y-1 text-sm">{t("Parole chiave con cui il coordinatore la propone","Keywords the coordinator uses to propose it")}
   <input className={input} value={draft.keywords.join(", ")} onChange={e=>set("keywords",e.target.value.split(",").map(x=>x.trim()).filter(Boolean).slice(0,20))}/></label>
  {error&&<p className="text-destructive text-sm" role="alert">{error}</p>}
  <div className="flex flex-wrap gap-2">
   <button className="bg-primary text-primary-foreground rounded px-3 py-2 text-sm" disabled={!ready||busy} onClick={()=>void save()}>{busy?t("Salvataggio…","Saving…"):t("Salva ricetta","Save recipe")}</button>
   <button className="rounded border px-3 py-2 text-sm" disabled={busy} onClick={onCancel}>{t("Annulla","Cancel")}</button>
  </div>
 </section>;
}
