"use client";
import {useEffect,useState,type ReactNode} from "react";
import {useI18n} from "@/core/i18n/hooks";
import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";

type HandoffCheck={id:string;requirement:string;critical:boolean};
type FinalCheck=HandoffCheck&{method:string};
type Content={title:string;summary:string;mandatory:boolean;rules:string[];handoff_checks:HandoffCheck[];final_checks:FinalCheck[]|"acceptance";depends_on:string[];applies_to:string[]};
type Version={version:number;sheet:Content&{id:string;version:number};revision:string;published_at:string;published_by:string};
type Event={at:string;actor:string;action:string;version?:number};
type Detail={id:string;source:"builtin"|"organization";status:Status;active_version:number|null;draft:(Content&{saved_at:string;saved_by:string})|null;versions:Version[];history:Event[]};
type Status="draft"|"active"|"retired";
type Row={id:string;title:string;summary:string;source:"builtin"|"organization";status:Status;mandatory:boolean;active_version:number|null;has_draft:boolean};
type Overview={sheets:Row[];can_manage:boolean};

const METHODS=["content","visual","listening","structural","functional","reference","technical"];
const PURPOSES=["work","preview","integration","delivery"];
const SHEET_ID=/^[a-z][a-z0-9_]{0,39}$/;
const button="rounded border px-3 py-2 text-sm disabled:opacity-50";
const field="mt-1 w-full rounded border bg-background p-2";
const empty=():Content=>({title:"",summary:"",mandatory:false,rules:[],handoff_checks:[],final_checks:[],depends_on:[],applies_to:[...PURPOSES]});

export default function PolicyBookPage(){
 const {locale}=useI18n();const it=locale==="it-IT";
 const [overview,setOverview]=useState<Overview|null>(null),[selected,setSelected]=useState<string|null>(null),[detail,setDetail]=useState<Detail|null>(null);
 const [form,setForm]=useState<Content|null>(null),[newId,setNewId]=useState(""),[creating,setCreating]=useState(false);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState("");
 const base=getBackendBaseURL()+"/api/harness/policy-book";
 const t=(itText:string,en:string)=>it?itText:en;
 const statusLabel:Record<Status,string>={draft:t("Bozza","Draft"),active:t("Attiva","Active"),retired:t("Ritirata","Retired")};
 const actions:Record<string,string>={draft_saved:t("Bozza salvata","Draft saved"),draft_discarded:t("Bozza scartata","Draft discarded"),published:t("Pubblicata","Published"),retired:t("Ritirata","Retired"),reactivated:t("Riattivata","Reactivated"),restored_to_draft:t("Ripristinata come bozza","Restored to draft")};

 async function request<T>(path:string,method="GET",body?:unknown):Promise<T>{
  const response=await fetch(base+path,{method,...(body!==undefined?{headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}:{})});
  const value=await response.json().catch(()=>({}));
  if(!response.ok)throw Error(typeof value.detail==="string"?value.detail:t("Richiesta non riuscita","Request failed")+" ("+response.status+")");
  return value as T;
 }
 async function load(){setOverview(await request<Overview>(""));}
 async function choose(id:string){setSelected(id);setCreating(false);setError("");setMessage("");const value=await request<Detail>("/sheets/"+id);show(value);}
 function show(value:Detail){
  setDetail(value);
  const active=value.versions.find(v=>v.version===value.active_version)?.sheet;
  const source=value.draft??active;
  setForm(source?{title:source.title,summary:source.summary,mandatory:source.mandatory,rules:[...source.rules],handoff_checks:source.handoff_checks.map(c=>({...c})),
   final_checks:source.final_checks==="acceptance"?"acceptance":source.final_checks.map(c=>({...c})),depends_on:[...source.depends_on],applies_to:[...source.applies_to]}:empty());
 }
 useEffect(()=>{void load().catch(e=>setError(String(e)));},[]);

 async function act(work:()=>Promise<void>,done?:string){setBusy(true);setError("");setMessage("");try{await work();await load();setMessage(done??"");}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
 const lifecycle=(action:string,body?:unknown)=>act(async()=>show(await request<Detail>("/sheets/"+selected+"/"+action,"POST",body)),actions[action==="publish"?"published":action==="retire"?"retired":action==="reactivate"?"reactivated":"restored_to_draft"]);
 const saveDraft=(id:string)=>act(async()=>{show(await request<Detail>("/sheets/"+id+"/draft","PUT",{...form,rules:form!.rules.filter(r=>r.trim())}));setSelected(id);setCreating(false);},actions.draft_saved);
 const discard=()=>act(async()=>{const value=await request<{sheet:Detail|null}>("/sheets/"+selected+"/draft","DELETE");if(value.sheet)show(value.sheet);else{setSelected(null);setDetail(null);setForm(null);}},actions.draft_discarded);
 const startNew=()=>{setCreating(true);setSelected(null);setDetail(null);setForm(empty());setNewId("");setError("");setMessage("");};

 const manage=Boolean(overview?.can_manage)&&(creating||detail?.source==="organization");
 const others=(overview?.sheets??[]).filter(s=>s.status==="active"&&s.id!==(selected??newId));
 const active=detail?.versions.find(v=>v.version===detail.active_version)?.sheet;
 const set=(change:Partial<Content>)=>setForm(f=>f?{...f,...change}:f);
 const finalList=form&&form.final_checks!=="acceptance"?form.final_checks:[];

 return <main className="mx-auto w-full max-w-6xl space-y-5 overflow-y-auto p-6">
  <header><h1 className="text-2xl font-semibold">Policy Book</h1>
   <p className="mt-2 text-muted-foreground">{t("Le policy sheet governano ogni nuovo progetto: regole per gli specialisti, controlli da dichiarare nella consegna intermedia e criteri della validazione finale. I progetti usano la versione fissata nel proprio Policy Plan.","Policy sheets govern every new project: rules for specialists, checks declared in each handoff and final validation criteria. Projects keep the version pinned in their Policy Plan.")}</p></header>
  <div className="grid gap-5 md:grid-cols-[18rem_1fr]">
   <nav aria-label={t("Policy sheet","Policy sheets")} className="space-y-2">
    {overview?.can_manage&&<button className={button+" w-full"} disabled={busy} onClick={startNew}>{t("Nuova policy sheet","New policy sheet")}</button>}
    <ul className="space-y-2">{(overview?.sheets??[]).map(s=><li key={s.id}><button aria-current={selected===s.id} onClick={()=>void choose(s.id).catch(e=>setError(String(e)))} className={"w-full rounded-xl border p-3 text-left "+(selected===s.id?"border-primary":"")}>
     <span className="block font-medium">{s.title}</span><span className="block font-mono text-xs text-muted-foreground">{s.id}</span>
     <span className="mt-1 flex flex-wrap gap-1 text-xs"><Badge>{statusLabel[s.status]}{s.active_version?" v"+s.active_version:""}</Badge>{s.mandatory&&<Badge>{t("Obbligatoria","Mandatory")}</Badge>}{s.source==="builtin"&&<Badge>{t("Inclusa in RigHaven","Built into RigHaven")}</Badge>}{s.has_draft&&s.status!=="draft"&&<Badge>{t("Bozza in corso","Pending draft")}</Badge>}</span>
    </button></li>)}</ul>
   </nav>
   <section className="space-y-5">
    {!detail&&!creating&&<p className="rounded-xl border p-4 text-muted-foreground">{t("Seleziona una policy sheet per vederne regole, controlli e storico.","Select a policy sheet to see its rules, checks and history.")}</p>}
    {detail&&<article className="space-y-3 rounded-xl border p-4" aria-label={t("Versione attiva","Active version")}>
     <h2 className="text-xl font-semibold">{active?.title??form?.title} <span className="font-mono text-sm text-muted-foreground">{detail.id}</span></h2>
     <p className="text-sm">{statusLabel[detail.status]}{detail.active_version?" · "+t("versione attiva","active version")+" "+detail.active_version:" · "+t("mai pubblicata","never published")}</p>
     {active?<SheetView sheet={active} t={t}/>:<p className="text-sm text-muted-foreground">{t("Nessuna versione pubblicata: i progetti non la usano ancora.","No published version: projects do not use it yet.")}</p>}
    </article>}
    {manage&&form&&<form className="space-y-4 rounded-xl border p-4" aria-label={t("Bozza","Draft")} onSubmit={e=>{e.preventDefault();void saveDraft(creating?newId:selected!);}}>
     <h2 className="font-semibold">{creating?t("Nuova policy sheet","New policy sheet"):detail?.draft?t("Bozza da pubblicare","Draft to publish")+" ("+detail.draft.saved_by+")":t("Prepara la prossima versione","Prepare the next version")}</h2>
     {creating&&<label className="block">{t("Identificativo","Identifier")}<input className={field+" font-mono"} value={newId} onChange={e=>setNewId(e.target.value)} placeholder="security"/>
      {newId&&!SHEET_ID.test(newId)&&<span className="text-sm text-red-600">{t("Minuscole, cifre e underscore; inizia con una lettera.","Lowercase letters, digits and underscores; start with a letter.")}</span>}</label>}
     <label className="block">{t("Titolo","Title")}<input className={field} value={form.title} onChange={e=>set({title:e.target.value})}/></label>
     <label className="block">{t("Descrizione","Summary")}<textarea className={field} rows={2} value={form.summary} onChange={e=>set({summary:e.target.value})}/></label>
     <label className="flex items-center gap-2"><input type="checkbox" checked={form.mandatory} onChange={e=>set({mandatory:e.target.checked})}/>{t("Obbligatoria per tutti i nuovi progetti","Mandatory for every new project")}</label>
     <label className="block">{t("Regole per gli specialisti (una per riga)","Rules for specialists (one per line)")}<textarea className={field} rows={4} value={form.rules.join("\n")} onChange={e=>set({rules:e.target.value.split("\n")})}/></label>
     <fieldset className="space-y-2"><legend className="font-medium">{t("Controlli dichiarati nell’handoff","Checks declared in the handoff")}</legend>
      {form.handoff_checks.map((c,i)=><CheckRow key={i} check={c} t={t} onChange={v=>set({handoff_checks:form.handoff_checks.map((x,j)=>j===i?{...x,...v}:x)})} onRemove={()=>set({handoff_checks:form.handoff_checks.filter((_,j)=>j!==i)})}/>)}
      <button type="button" className={button} onClick={()=>set({handoff_checks:[...form.handoff_checks,{id:"",requirement:"",critical:true}]})}>{t("Aggiungi controllo dell’handoff","Add handoff check")}</button></fieldset>
     <fieldset className="space-y-2"><legend className="font-medium">{t("Validazione finale","Final validation")}</legend>
      <label className="flex items-center gap-2"><input type="checkbox" checked={form.final_checks==="acceptance"} onChange={e=>set({final_checks:e.target.checked?"acceptance":[]})}/>{t("Usa la revisione sul contratto di accettazione del progetto","Use the review against the project acceptance contract")}</label>
      {form.final_checks!=="acceptance"&&<>{finalList.map((c,i)=><CheckRow key={i} check={c} t={t} method onChange={v=>set({final_checks:finalList.map((x,j)=>j===i?{...x,...v}:x)})} onRemove={()=>set({final_checks:finalList.filter((_,j)=>j!==i)})}/>)}
       <button type="button" className={button} onClick={()=>set({final_checks:[...finalList,{id:"",requirement:"",method:"content",critical:true}]})}>{t("Aggiungi criterio finale","Add final criterion")}</button></>}</fieldset>
     <fieldset><legend className="font-medium">{t("Si applica agli incarichi","Applies to assignments")}</legend><div className="flex flex-wrap gap-3">{PURPOSES.map(p=><label key={p} className="flex items-center gap-1"><input type="checkbox" checked={form.applies_to.includes(p)} onChange={e=>set({applies_to:e.target.checked?[...form.applies_to,p]:form.applies_to.filter(x=>x!==p)})}/>{p}</label>)}</div></fieldset>
     <fieldset><legend className="font-medium">{t("Validare dopo","Validate after")}</legend>{others.length?<div className="flex flex-wrap gap-3">{others.map(o=><label key={o.id} className="flex items-center gap-1"><input type="checkbox" checked={form.depends_on.includes(o.id)} onChange={e=>set({depends_on:e.target.checked?[...form.depends_on,o.id]:form.depends_on.filter(x=>x!==o.id)})}/>{o.title}</label>)}</div>:<p className="text-sm text-muted-foreground">{t("Nessun’altra sheet attiva.","No other active sheet.")}</p>}</fieldset>
     <div className="flex flex-wrap gap-2">
      <button type="submit" className={button} disabled={busy||(creating&&!SHEET_ID.test(newId))}>{t("Salva bozza","Save draft")}</button>
      {detail?.draft&&<button type="button" className={button+" border-primary"} disabled={busy} onClick={()=>void lifecycle("publish")}>{t("Pubblica la bozza","Publish draft")}</button>}
      {detail?.draft&&<button type="button" className={button} disabled={busy} onClick={()=>void discard()}>{detail.versions.length?t("Scarta la bozza","Discard draft"):t("Elimina la sheet","Delete sheet")}</button>}
      {detail?.status==="active"&&<button type="button" className={button+" border-red-500"} disabled={busy} onClick={()=>void lifecycle("retire")}>{t("Ritira","Retire")}</button>}
      {detail?.status==="retired"&&<button type="button" className={button} disabled={busy} onClick={()=>void lifecycle("reactivate")}>{t("Riattiva","Reactivate")}</button>}
     </div>
     <p className="text-sm text-muted-foreground">{t("Salvare non cambia la versione attiva. Pubblicare crea una nuova versione immutabile, usata dai Policy Plan creati da quel momento.","Saving does not change the active version. Publishing creates a new immutable version, used by Policy Plans created from then on.")}</p>
    </form>}
    {detail?.source==="organization"&&<section className="grid gap-4 md:grid-cols-2">
     <div className="rounded-xl border p-4"><h2 className="font-semibold">{t("Versioni pubblicate","Published versions")}</h2><ul className="mt-2 space-y-2 text-sm">{[...detail.versions].reverse().map(v=><li key={v.version} className="flex items-center justify-between gap-2"><span>v{v.version} · {v.published_by} · {v.published_at.slice(0,16).replace("T"," ")}</span>
      {overview?.can_manage&&<button className={button} disabled={busy} onClick={()=>void lifecycle("restore",{version:v.version})}>{t("Ripristina come bozza","Restore to draft")}</button>}</li>)}</ul></div>
     <div className="rounded-xl border p-4"><h2 className="font-semibold">{t("Storico","History")}</h2><ol className="mt-2 max-h-64 space-y-1 overflow-auto text-sm">{[...detail.history].reverse().map((h,i)=><li key={i}>{h.at.slice(0,16).replace("T"," ")} · {h.actor} · {actions[h.action]??h.action}{h.version?" v"+h.version:""}</li>)}</ol></div>
    </section>}
    {error&&<p role="alert" className="rounded border p-3 text-sm text-red-600">{error}</p>}{message&&<p role="status" className="text-sm">{message}</p>}
   </section>
  </div>
 </main>;
}

function Badge({children}:{children:ReactNode}){return <span className="rounded-full border px-2 py-0.5">{children}</span>;}

function SheetView({sheet,t}:{sheet:Content;t:(it:string,en:string)=>string}){
 return <div className="space-y-3 text-sm">
  {sheet.summary&&<p>{sheet.summary}</p>}
  <p>{sheet.mandatory?t("Obbligatoria per tutti i nuovi progetti.","Mandatory for every new project."):t("Facoltativa: il coordinatore la sceglie motivandola.","Optional: the coordinator selects it with a reason.")} {t("Incarichi","Assignments")}: {sheet.applies_to.join(", ")}.{sheet.depends_on.length?" "+t("Validata dopo","Validated after")+": "+sheet.depends_on.join(", ")+".":""}</p>
  {sheet.rules.length>0&&<div><h3 className="font-medium">{t("Regole","Rules")}</h3><ul className="list-disc pl-5">{sheet.rules.map((r,i)=><li key={i}>{r}</li>)}</ul></div>}
  {sheet.handoff_checks.length>0&&<div><h3 className="font-medium">{t("Controlli dell’handoff","Handoff checks")}</h3><ul className="list-disc pl-5">{sheet.handoff_checks.map(c=><li key={c.id}><code>{c.id}</code>{c.critical?" · "+t("critico","critical"):""}: {c.requirement}</li>)}</ul></div>}
  <div><h3 className="font-medium">{t("Validazione finale","Final validation")}</h3>{sheet.final_checks==="acceptance"?<p>{t("Revisione separata del prodotto sul contratto di accettazione del progetto.","Separate review of the product against the project acceptance contract.")}</p>:
   <ul className="list-disc pl-5">{sheet.final_checks.map(c=><li key={c.id}><code>{c.id}</code> [{c.method}]{c.critical?" · "+t("critico","critical"):""}: {c.requirement}</li>)}</ul>}</div>
 </div>;
}

function CheckRow({check,t,method,onChange,onRemove}:{check:HandoffCheck&{method?:string};t:(it:string,en:string)=>string;method?:boolean;onChange:(v:Partial<FinalCheck>)=>void;onRemove:()=>void}){
 return <div className="flex flex-wrap items-end gap-2 rounded border p-2">
  <label className="text-sm">ID<input className={field+" w-40 font-mono"} value={check.id} onChange={e=>onChange({id:e.target.value})}/></label>
  <label className="min-w-64 flex-1 text-sm">{t("Requisito","Requirement")}<input className={field} value={check.requirement} onChange={e=>onChange({requirement:e.target.value})}/></label>
  {method&&<label className="text-sm">{t("Metodo","Method")}<select className={field} value={check.method} onChange={e=>onChange({method:e.target.value})}>{METHODS.map(m=><option key={m}>{m}</option>)}</select></label>}
  <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={check.critical} onChange={e=>onChange({critical:e.target.checked})}/>{t("Critico","Critical")}</label>
  <button type="button" className={button} onClick={onRemove}>{t("Rimuovi","Remove")}</button>
 </div>;
}
