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
type T=(it:string,en:string)=>string;

const METHODS=["content","structural","functional","technical","reference","visual","listening"];
const PURPOSES=["work","preview","integration","delivery"];
const SHEET_ID=/^[a-z][a-z0-9_]{0,39}$/;
const button="rounded border px-3 py-2 text-sm disabled:opacity-50";
const field="mt-1 w-full rounded border bg-background p-2";
const empty=():Content=>({title:"",summary:"",mandatory:false,rules:[],handoff_checks:[],final_checks:[],depends_on:[],applies_to:[...PURPOSES]});

/** Readable names and explanations for every technical field of a sheet. */
function vocabulary(t:T){
 return {
  methods:{content:[t("Lettura del contenuto","Reading the content"),t("Il revisore legge testi e dati e li confronta con il requisito.","The reviewer reads texts and data and compares them with the requirement.")],
   structural:[t("Struttura del file","File structure"),t("Controlli su pagine, sezioni, formato e integrità del file.","Checks on pages, sections, format and file integrity.")],
   functional:[t("Prova di funzionamento","Functional test"),t("Il revisore esegue o apre il prodotto e verifica che funzioni.","The reviewer runs or opens the product and checks it works.")],
   technical:[t("Misura tecnica","Technical measurement"),t("Strumenti automatici: scansioni, conteggi, validatori.","Automated tools: scans, counts, validators.")],
   reference:[t("Confronto con un riferimento","Comparison with a reference"),t("Serve un file di riferimento fornito nel progetto; senza resta non verificato.","Needs a reference file provided in the project; without it the check stays unverified.")],
   visual:[t("Osservazione visiva","Visual inspection"),t("Il revisore guarda il risultato (pagine, immagini, video).","The reviewer looks at the result (pages, images, video).")],
   listening:[t("Ascolto","Listening"),t("Oggi non disponibile nei collegamenti dei modelli: il controllo resterà non verificato.","Not available with current model connections: the check will stay unverified.")]} as Record<string,[string,string]>,
  purposes:{work:t("Lavori di produzione","Production work"),preview:t("Campioni e prove","Samples and trials"),integration:t("Integrazione delle parti","Integration of parts"),delivery:t("Consegna finale","Final delivery")} as Record<string,string>,
 };
}
/** Stable codes for the audit trail, derived from the text the administrator writes. */
function code(text:string,taken:string[]){
 const base=(text.normalize("NFD").replace(/\p{M}/gu,"").toLowerCase().replace(/[^a-z0-9]+/g,"_").replace(/^_+|_+$/g,"").replace(/^([^a-z])/,"c_$1").slice(0,40))||"controllo";
 let value=base,n=2;while(taken.includes(value))value=base.slice(0,36)+"_"+n++;
 return value;
}

export default function PolicyBookPage(){
 const {locale}=useI18n();const it=locale==="it-IT";
 const t:T=(itText,en)=>it?itText:en;
 const words=vocabulary(t);
 const [overview,setOverview]=useState<Overview|null>(null),[selected,setSelected]=useState<string|null>(null),[detail,setDetail]=useState<Detail|null>(null);
 const [form,setForm]=useState<Content|null>(null),[newId,setNewId]=useState(""),[creating,setCreating]=useState(false),[step,setStep]=useState<number|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState("");
 const base=getBackendBaseURL()+"/api/harness/policy-book";
 const statusLabel:Record<Status,string>={draft:t("Bozza","Draft"),active:t("Attiva","Active"),retired:t("Ritirata","Retired")};
 const actions:Record<string,string>={draft_saved:t("Bozza salvata","Draft saved"),draft_discarded:t("Bozza scartata","Draft discarded"),published:t("Pubblicata","Published"),retired:t("Ritirata","Retired"),reactivated:t("Riattivata","Reactivated"),restored_to_draft:t("Ripristinata come bozza","Restored to draft")};

 async function request<R>(path:string,method="GET",body?:unknown):Promise<R>{
  const response=await fetch(base+path,{method,...(body!==undefined?{headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}:{})});
  const value=await response.json().catch(()=>({}));
  if(!response.ok)throw Error(typeof value.detail==="string"?value.detail:t("Richiesta non riuscita","Request failed")+" ("+response.status+")");
  return value as R;
 }
 async function load(){setOverview(await request<Overview>(""));}
 async function choose(id:string){setSelected(id);setCreating(false);setStep(null);setError("");setMessage("");show(await request<Detail>("/sheets/"+id));}
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
 function payload():Content{
  const f=form!;const used:string[]=[];
  const withCodes=<C extends HandoffCheck>(items:C[])=>items.filter(c=>c.requirement.trim()).map(c=>{const id=c.id||code(c.requirement,used);used.push(id);return {...c,id};});
  return {...f,rules:f.rules.filter(r=>r.trim()),handoff_checks:withCodes(f.handoff_checks),final_checks:f.final_checks==="acceptance"?"acceptance" as const:withCodes(f.final_checks)};
 }
 const saveDraft=(publishAfter:boolean)=>act(async()=>{
  const id=creating?newId:selected!;
  let value=await request<Detail>("/sheets/"+id+"/draft","PUT",payload());
  if(publishAfter)value=await request<Detail>("/sheets/"+id+"/publish","POST");
  show(value);setSelected(id);setCreating(false);setStep(null);
 },publishAfter?actions.published:actions.draft_saved);
 const discard=()=>act(async()=>{const value=await request<{sheet:Detail|null}>("/sheets/"+selected+"/draft","DELETE");if(value.sheet)show(value.sheet);else{setSelected(null);setDetail(null);setForm(null);}},actions.draft_discarded);
 const startNew=()=>{setCreating(true);setSelected(null);setDetail(null);setForm(empty());setNewId("");setStep(0);setError("");setMessage("");};

 const canManage=Boolean(overview?.can_manage);
 const others=(overview?.sheets??[]).filter(s=>s.status==="active"&&s.id!==(selected??newId));
 const active=detail?.versions.find(v=>v.version===detail.active_version)?.sheet;
 const set=(change:Partial<Content>)=>setForm(f=>f?{...f,...change}:f);
 const finalList=form&&form.final_checks!=="acceptance"?form.final_checks:[];
 const steps=[t("Scopo","Purpose"),t("Regole di lavoro","Working rules"),t("Controlli durante il lavoro","Checks during work"),t("Verifica finale","Final verification"),t("Ambito","Scope"),t("Riepilogo","Summary")];
 const stepIssue=(index:number):string=>{
  if(!form)return "";
  if(index===0&&creating&&!SHEET_ID.test(newId))return t("Scegli un identificativo: minuscole, cifre e underscore, iniziando con una lettera.","Choose an identifier: lowercase letters, digits and underscores, starting with a letter.");
  if(index===0&&!form.title.trim())return t("Dai un titolo alla policy.","Give the policy a title.");
  if(index===3&&form.final_checks!=="acceptance"&&!finalList.some(c=>c.requirement.trim())&&!form.rules.some(r=>r.trim())&&!form.handoff_checks.some(c=>c.requirement.trim()))return t("Una policy deve contenere almeno una regola o un controllo.","A policy needs at least one rule or check.");
  if(index===4&&!form.applies_to.length)return t("Scegli almeno un tipo di incarico.","Select at least one kind of assignment.");
  return "";
 };

 return <main className="mx-auto w-full max-w-6xl space-y-5 overflow-y-auto p-6">
  <header><h1 className="text-2xl font-semibold">Policy Book</h1>
   <p className="mt-2 text-muted-foreground">{t("Le policy sono le regole che RigHaven fa rispettare in ogni progetto: cosa devono fare gli specialisti mentre lavorano, cosa devono dichiarare e come viene verificato il prodotto finito prima della consegna. I progetti usano la versione fissata nel proprio Policy Plan.","Policies are the rules RigHaven enforces in every project: what specialists must do while working, what they must declare, and how the finished product is checked before delivery. Projects keep the version pinned in their Policy Plan.")}</p></header>
  <div className="grid gap-5 md:grid-cols-[18rem_1fr]">
   <nav aria-label={t("Policy sheet","Policy sheets")} className="space-y-2">
    {canManage&&<button className={button+" w-full"} disabled={busy} onClick={startNew}>{t("Nuova policy guidata","New guided policy")}</button>}
    <ul className="space-y-2">{(overview?.sheets??[]).map(s=><li key={s.id}><button aria-current={selected===s.id} onClick={()=>void choose(s.id).catch(e=>setError(String(e)))} className={"w-full rounded-xl border p-3 text-left "+(selected===s.id?"border-primary":"")}>
     <span className="block font-medium">{s.title}</span><span className="block font-mono text-xs text-muted-foreground">{s.id}</span>
     <span className="mt-1 flex flex-wrap gap-1 text-xs"><Badge>{statusLabel[s.status]}{s.active_version?" v"+s.active_version:""}</Badge>{s.mandatory&&<Badge>{t("Obbligatoria","Mandatory")}</Badge>}{s.source==="builtin"&&<Badge>{t("Inclusa in RigHaven","Built into RigHaven")}</Badge>}{s.has_draft&&s.status!=="draft"&&<Badge>{t("Bozza in corso","Pending draft")}</Badge>}</span>
    </button></li>)}</ul>
   </nav>
   <section className="space-y-5">
    {!detail&&!creating&&<p className="rounded-xl border p-4 text-muted-foreground">{t("Seleziona una policy per vederne regole, controlli e storico.","Select a policy to see its rules, checks and history.")}</p>}
    {detail&&step===null&&<article className="space-y-3 rounded-xl border p-4" aria-label={t("Versione attiva","Active version")}>
     <h2 className="text-xl font-semibold">{active?.title??form?.title} <span className="font-mono text-sm text-muted-foreground">{detail.id}</span></h2>
     <p className="text-sm">{statusLabel[detail.status]}{detail.active_version?" · "+t("versione attiva","active version")+" "+detail.active_version:" · "+t("mai pubblicata","never published")}</p>
     {active?<SheetView sheet={active} t={t}/>:<p className="text-sm text-muted-foreground">{t("Nessuna versione pubblicata: i progetti non la usano ancora.","No published version: projects do not use it yet.")}</p>}
     {detail.draft&&<p className="rounded border p-2 text-sm">{t("C’è una bozza non ancora pubblicata di","There is an unpublished draft by")} {detail.draft.saved_by}: {t("la versione attiva continua a valere finché non la pubblichi.","the active version keeps applying until you publish it.")}</p>}
     {canManage&&detail.source==="organization"&&<div className="flex flex-wrap gap-2">
      <button type="button" className={button} disabled={busy} onClick={()=>{setStep(0);setMessage("");}}>{detail.draft?t("Riprendi la bozza","Continue the draft"):t("Prepara una nuova versione","Prepare a new version")}</button>
      {detail.draft&&<button type="button" className={button+" border-primary"} disabled={busy} onClick={()=>void lifecycle("publish")}>{t("Pubblica la bozza","Publish draft")}</button>}
      {detail.draft&&<button type="button" className={button} disabled={busy} onClick={()=>void discard()}>{detail.versions.length?t("Scarta la bozza","Discard draft"):t("Elimina la sheet","Delete sheet")}</button>}
      {detail.status==="active"&&<button type="button" className={button+" border-red-500"} disabled={busy} onClick={()=>void lifecycle("retire")}>{t("Ritira","Retire")}</button>}
      {detail.status==="retired"&&<button type="button" className={button} disabled={busy} onClick={()=>void lifecycle("reactivate")}>{t("Riattiva","Reactivate")}</button>}
     </div>}
    </article>}
    {canManage&&form&&step!==null&&<form className="space-y-4 rounded-xl border p-4" aria-label={t("Percorso guidato","Guided setup")} onSubmit={e=>e.preventDefault()}>
     <ol className="flex flex-wrap gap-2 text-xs" aria-label={t("Passi","Steps")}>{steps.map((label,i)=><li key={label}><button type="button" aria-current={i===step} onClick={()=>setStep(i)} className={"rounded-full border px-2 py-1 "+(i===step?"border-primary font-semibold":"")}>{i+1}. {label}</button></li>)}</ol>
     <h2 className="text-lg font-semibold">{step+1}. {steps[step]}</h2>
     {step===0&&<div className="space-y-3">
      <Help>{t("Dai un nome alla policy e spiega a cosa serve: il coordinatore legge questa descrizione per decidere quando applicarla.","Name the policy and explain what it is for: the coordinator reads this description to decide when it applies.")}</Help>
      {creating&&<label className="block">{t("Identificativo","Identifier")}<input className={field+" font-mono"} value={newId} onChange={e=>setNewId(e.target.value)} placeholder="sicurezza"/>
       <span className="text-xs text-muted-foreground">{t("Codice stabile usato nei registri e nei Policy Plan; non si può cambiare dopo.","Stable code used in records and Policy Plans; it cannot change later.")}</span></label>}
      <label className="block">{t("Titolo","Title")}<input className={field} value={form.title} onChange={e=>set({title:e.target.value})}/></label>
      <label className="block">{t("A cosa serve","What it is for")}<textarea className={field} rows={2} value={form.summary} onChange={e=>set({summary:e.target.value})}/></label>
      <fieldset className="space-y-1"><legend className="font-medium">{t("Quando si applica","When it applies")}</legend>
       <label className="flex gap-2"><input type="radio" name="mandatory" checked={form.mandatory} onChange={()=>set({mandatory:true})}/>{t("Sempre: obbligatoria per ogni nuovo progetto, anche per quelli già pianificati.","Always: mandatory for every new project, also added to projects already planned.")}</label>
       <label className="flex gap-2"><input type="radio" name="mandatory" checked={!form.mandatory} onChange={()=>set({mandatory:false})}/>{t("Quando serve: il coordinatore la propone se pertinente al progetto e deve motivarlo.","When relevant: the coordinator applies it when it fits the project and must explain why.")}</label></fieldset>
     </div>}
     {step===1&&<div className="space-y-3">
      <Help>{t("Le regole vengono consegnate a ogni specialista insieme al suo incarico. Scrivi istruzioni concrete e verificabili, una per riga. Esempio: «Non inserire credenziali o token nei file consegnati».","Rules are handed to every specialist together with the assignment. Write concrete, verifiable instructions, one per line. Example: «Do not put credentials or tokens in delivered files».")}</Help>
      <label className="block">{t("Regole (una per riga)","Rules (one per line)")}<textarea className={field} rows={5} value={form.rules.join("\n")} onChange={e=>set({rules:e.target.value.split("\n")})}/></label>
     </div>}
     {step===2&&<div className="space-y-3">
      <Help>{t("Ogni specialista, quando consegna il suo lavoro, deve dichiarare di aver fatto questi controlli e con quale evidenza. Se un controllo bloccante manca o non è superato, l’attività torna in revisione. Un controllo non bloccante viene solo registrato.","When delivering their work, every specialist must declare these checks with evidence. If a blocking check is missing or fails, the activity goes back to revision. A non-blocking check is only recorded.")}</Help>
      {form.handoff_checks.map((c,i)=><CheckRow key={i} check={c} t={t} onChange={v=>set({handoff_checks:form.handoff_checks.map((x,j)=>j===i?{...x,...v}:x)})} onRemove={()=>set({handoff_checks:form.handoff_checks.filter((_,j)=>j!==i)})}/>)}
      <button type="button" className={button} onClick={()=>set({handoff_checks:[...form.handoff_checks,{id:"",requirement:"",critical:true}]})}>{t("Aggiungi un controllo","Add a check")}</button>
      {!form.handoff_checks.length&&<p className="text-sm text-muted-foreground">{t("Facoltativo: puoi passare al passo successivo.","Optional: you can move to the next step.")}</p>}
     </div>}
     {step===3&&<div className="space-y-3">
      <Help>{t("Prima della consegna un revisore indipendente verifica il prodotto finito. Scegli se basta la revisione di qualità sul contratto del progetto o se servono criteri propri di questa policy.","Before delivery an independent reviewer checks the finished product. Choose whether the quality review against the project contract is enough or this policy needs its own criteria.")}</Help>
      <label className="flex gap-2"><input type="radio" name="final" checked={form.final_checks==="acceptance"} onChange={()=>set({final_checks:"acceptance"})}/>{t("Revisione di qualità sul contratto di accettazione del progetto","Quality review against the project acceptance contract")}</label>
      <label className="flex gap-2"><input type="radio" name="final" checked={form.final_checks!=="acceptance"} onChange={()=>set({final_checks:finalList})}/>{t("Criteri propri di questa policy","This policy’s own criteria")}</label>
      {form.final_checks!=="acceptance"&&<>{finalList.map((c,i)=><CheckRow key={i} check={c} t={t} methods={words.methods} onChange={v=>set({final_checks:finalList.map((x,j)=>j===i?{...x,...v}:x)})} onRemove={()=>set({final_checks:finalList.filter((_,j)=>j!==i)})}/>)}
       <button type="button" className={button} onClick={()=>set({final_checks:[...finalList,{id:"",requirement:"",method:"content",critical:true}]})}>{t("Aggiungi un criterio","Add a criterion")}</button></>}
     </div>}
     {step===4&&<div className="space-y-3">
      <Help>{t("Scegli a quali incarichi consegnare le regole. Di solito tutti; puoi escludere ad esempio i campioni rapidi.","Choose which assignments receive the rules. Usually all; you can exclude, for example, quick samples.")}</Help>
      <fieldset><legend className="font-medium">{t("Incarichi che ricevono la policy","Assignments receiving the policy")}</legend><div className="space-y-1">{PURPOSES.map(p=><label key={p} className="flex items-center gap-2"><input type="checkbox" checked={form.applies_to.includes(p)} onChange={e=>set({applies_to:e.target.checked?[...form.applies_to,p]:form.applies_to.filter(x=>x!==p)})}/>{words.purposes[p]}</label>)}</div></fieldset>
      <Help>{t("Se questa verifica ha senso solo dopo che un’altra policy è superata (ad esempio la pubblicazione dopo la sicurezza), selezionala: le verifiche indipendenti girano in parallelo, quelle dipendenti dopo.","If this check only makes sense after another policy passes (for example publication after security), select it: independent checks run in parallel, dependent ones afterwards.")}</Help>
      <fieldset><legend className="font-medium">{t("Verificare dopo","Verify after")}</legend>{others.length?<div className="space-y-1">{others.map(o=><label key={o.id} className="flex items-center gap-2"><input type="checkbox" checked={form.depends_on.includes(o.id)} onChange={e=>set({depends_on:e.target.checked?[...form.depends_on,o.id]:form.depends_on.filter(x=>x!==o.id)})}/>{o.title}</label>)}</div>:<p className="text-sm text-muted-foreground">{t("Nessun’altra policy attiva.","No other active policy.")}</p>}</fieldset>
     </div>}
     {step===5&&<div className="space-y-3" data-testid="policy-summary">
      <Help>{t("Così verrà applicata. Salvare crea una bozza che non cambia nulla; pubblicare crea una nuova versione usata dai progetti pianificati da quel momento.","This is how it will apply. Saving creates a draft that changes nothing; publishing creates a new version used by projects planned from then on.")}</Help>
      <SheetView sheet={{...form,...payload()}} t={t}/>
     </div>}
     {stepIssue(step)&&<p className="text-sm text-amber-700">{stepIssue(step)}</p>}
     <div className="flex flex-wrap gap-2">
      <button type="button" className={button} disabled={step===0} onClick={()=>setStep(step-1)}>{t("Indietro","Back")}</button>
      {step<steps.length-1&&<button type="button" className={button} disabled={!!stepIssue(step)} onClick={()=>setStep(step+1)}>{t("Avanti","Next")}</button>}
      {step===steps.length-1&&<><button type="button" className={button} disabled={busy||steps.some((_,i)=>stepIssue(i))} onClick={()=>void saveDraft(false)}>{t("Salva come bozza","Save as draft")}</button>
       <button type="button" className={button+" border-primary"} disabled={busy||steps.some((_,i)=>stepIssue(i))} onClick={()=>void saveDraft(true)}>{t("Salva e pubblica","Save and publish")}</button></>}
      <button type="button" className={button} onClick={()=>{setStep(null);if(creating){setCreating(false);setForm(null);}}}>{t("Annulla","Cancel")}</button>
     </div>
    </form>}
    {detail?.source==="organization"&&step===null&&<section className="grid gap-4 md:grid-cols-2">
     <div className="rounded-xl border p-4"><h2 className="font-semibold">{t("Versioni pubblicate","Published versions")}</h2><ul className="mt-2 space-y-2 text-sm">{[...detail.versions].reverse().map(v=><li key={v.version} className="flex items-center justify-between gap-2"><span>v{v.version} · {v.published_by} · {v.published_at.slice(0,16).replace("T"," ")}</span>
      {canManage&&<button className={button} disabled={busy} onClick={()=>void lifecycle("restore",{version:v.version})}>{t("Ripristina come bozza","Restore to draft")}</button>}</li>)}</ul></div>
     <div className="rounded-xl border p-4"><h2 className="font-semibold">{t("Storico","History")}</h2><ol className="mt-2 max-h-64 space-y-1 overflow-auto text-sm">{[...detail.history].reverse().map((h,i)=><li key={i}>{h.at.slice(0,16).replace("T"," ")} · {h.actor} · {actions[h.action]??h.action}{h.version?" v"+h.version:""}</li>)}</ol></div>
    </section>}
    {error&&<p role="alert" className="rounded border p-3 text-sm text-red-600">{error}</p>}{message&&<p role="status" className="text-sm">{message}</p>}
   </section>
  </div>
 </main>;
}

function Badge({children}:{children:ReactNode}){return <span className="rounded-full border px-2 py-0.5">{children}</span>;}
function Help({children}:{children:ReactNode}){return <p className="rounded bg-muted/40 p-2 text-sm text-muted-foreground">{children}</p>;}

/** The sheet in plain language, as specialists and reviewers will receive it. */
function SheetView({sheet,t}:{sheet:Content;t:T}){
 const words=vocabulary(t);
 return <div className="space-y-3 text-sm">
  {sheet.summary&&<p>{sheet.summary}</p>}
  <p>{sheet.mandatory?t("Si applica sempre a ogni nuovo progetto.","Always applies to every new project."):t("Si applica quando il coordinatore la ritiene pertinente, motivandolo.","Applies when the coordinator finds it relevant and explains why.")} {t("Incarichi interessati","Assignments involved")}: {sheet.applies_to.map(p=>words.purposes[p]??p).join(", ")}.{sheet.depends_on.length?" "+t("Verificata dopo","Verified after")+": "+sheet.depends_on.join(", ")+".":""}</p>
  <div><h3 className="font-medium">{t("Regole consegnate agli specialisti","Rules handed to specialists")}</h3>{sheet.rules.length?<ul className="list-disc pl-5">{sheet.rules.map((r,i)=><li key={i}>{r}</li>)}</ul>:<p className="text-muted-foreground">{t("Nessuna regola.","No rules.")}</p>}</div>
  <div><h3 className="font-medium">{t("Controlli che ogni specialista deve dichiarare","Checks every specialist must declare")}</h3>{sheet.handoff_checks.length?<ul className="list-disc pl-5">{sheet.handoff_checks.map(c=><li key={c.id||c.requirement}>{c.requirement} · {c.critical?t("bloccante: se manca, l’attività torna in revisione","blocking: if missing, the activity goes back to revision"):t("registrato, non bloccante","recorded, not blocking")}</li>)}</ul>:<p className="text-muted-foreground">{t("Nessun controllo durante il lavoro.","No checks during work.")}</p>}</div>
  <div><h3 className="font-medium">{t("Verifica finale prima della consegna","Final verification before delivery")}</h3>{sheet.final_checks==="acceptance"?<p>{t("Revisione separata del prodotto sul contratto di accettazione del progetto.","Separate review of the product against the project acceptance contract.")}</p>:
   <ul className="list-disc pl-5">{sheet.final_checks.map(c=><li key={c.id||c.requirement}>{c.requirement} · {(words.methods[c.method]??[c.method])[0]} · {c.critical?t("bloccante","blocking"):t("non bloccante","not blocking")}</li>)}</ul>}</div>
 </div>;
}

function CheckRow({check,t,methods,onChange,onRemove}:{check:HandoffCheck&{method?:string};t:T;methods?:Record<string,[string,string]>;onChange:(v:Partial<FinalCheck>)=>void;onRemove:()=>void}){
 return <div className="space-y-2 rounded border p-2">
  <label className="block text-sm">{t("Cosa deve risultare vero","What must be true")}<input className={field} value={check.requirement} onChange={e=>onChange({requirement:e.target.value})}/></label>
  {methods&&<label className="block text-sm">{t("Come si verifica","How it is verified")}<select className={field} value={check.method} onChange={e=>onChange({method:e.target.value})}>{METHODS.map(m=><option key={m} value={m}>{methods[m]![0]}</option>)}</select>
   <span className="text-xs text-muted-foreground">{methods[check.method??"content"]?.[1]}</span></label>}
  <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={check.critical} onChange={e=>onChange({critical:e.target.checked})}/>{t("Bloccante: senza questo controllo superato non si prosegue","Blocking: work cannot proceed until this check passes")}</label>
  <button type="button" className={button} onClick={onRemove}>{t("Rimuovi","Remove")}</button>
 </div>;
}
