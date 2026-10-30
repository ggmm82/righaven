"use client";

export type Finding={requirement_id?:string;status:string;critical?:boolean;method?:string;criterion:string;evidence:string};
export type LiveSheet={id:string;title:string;version:number;mandatory:boolean;reason:string;steps:string[];depends_on:string[];
 final:"acceptance"|number;handoff:{required:number;declared:number;violations:string[]};status:string;reviewed_at?:string;findings?:Finding[]};
export type LiveGovernance={phase:string;settled?:boolean;planned_at?:string;selected_by?:string;optional_available?:string[];
 product?:{path:string;integrity:string;issue:string};sheets?:LiveSheet[];last_validation?:{at:string;status:string}};

const PHASES:Record<string,string>={briefing:"Definizione del risultato",planning:"Execution Plan e Policy Plan",execution:"Esecuzione degli incarichi",
 validation:"Validazione finale delle policy",delivery:"Pronto per la consegna",delivered:"Consegnato"};
const VERDICTS:Record<string,string>={passed:"Superata",failed:"Da correggere",pending:"Da validare",needs_review:"Verifica incompleta"};
const TONES:Record<string,string>={passed:"border-emerald-500/50",failed:"border-red-500/60",needs_review:"border-amber-500/60",pending:""};
const when=(at?:string)=>at?at.slice(0,16).replace("T"," "):"";

function nextStep(g:LiveGovernance):string{
 const sheets=g.sheets??[];
 if(g.phase==="planning")return g.settled?"Il coordinatore deve completare l’Execution Plan.":"Il coordinatore deve decidere quali policy facoltative applicare: la produzione attende.";
 if(g.phase==="execution")return "Le policy vengono applicate agli incarichi; la validazione finale avverrà sul prodotto consegnato.";
 if(g.product?.integrity==="failed")return "Il prodotto non supera il controllo di integrità: serve una nuova consegna.";
 if(sheets.some(s=>s.status==="failed"))return "Ci sono violazioni da correggere prima della consegna.";
 if(sheets.some(s=>s.status==="needs_review"))return "Alcune verifiche non sono state possibili: servono i riferimenti mancanti o la tua decisione.";
 if(sheets.some(s=>s.status==="pending"))return g.last_validation?"Alcune policy devono ancora essere validate su questa versione.":"Validazione finale non ancora eseguita su questa versione.";
 return g.phase==="delivered"?"Consegnato con tutte le policy superate.":"Tutte le policy sono superate: la consegna è autorizzata.";
}

/** Policies governing this project, recomputed from the recorded reviews at every refresh. */
export function GovernanceStrip({governance,expanded=false}:{governance?:LiveGovernance|null;expanded?:boolean}){
 if(!governance)return null;
 if(governance.phase==="legacy")return <p className="text-muted-foreground text-xs" data-testid="project-governance">Progetto avviato prima del Policy Book: valgono i controlli di qualità esistenti.</p>;
 const sheets=governance.sheets??[];
 const count=(status:string)=>sheets.filter(s=>s.status===status).length;
 const summary=[["passed","superate"],["failed","da correggere"],["needs_review","incomplete"],["pending","da validare"]].filter(([s])=>count(s!)).map(([s,label])=>`${count(s!)} ${label}`).join(" · ");
 return <details className="rounded-lg border p-2 text-xs" open={expanded} data-testid="project-governance">
  <summary className="cursor-pointer"><strong>Policy</strong> · {PHASES[governance.phase]??governance.phase}{sheets.length?` · ${sheets.length} applicate${summary?" ("+summary+")":""}`:""}</summary>
  <div className="mt-2 space-y-2">
   <p>{nextStep(governance)}</p>
   {governance.planned_at&&<p className="text-muted-foreground">Policy Plan fissato il {when(governance.planned_at)}{governance.selected_by==="system"?" dal sistema (solo sheet obbligatorie)":" dal coordinatore"}.</p>}
   {!governance.settled&&!!governance.optional_available?.length&&<p>Sheet facoltative da valutare: {governance.optional_available.join(", ")}.</p>}
   <ul className="space-y-2">{sheets.map(s=><li key={s.id} className={"space-y-1 rounded border-l-4 pl-2 "+(TONES[s.status]??"")}>
    <p><strong>{s.title}</strong> v{s.version} · {VERDICTS[s.status]??s.status}{s.reviewed_at?` · revisione del ${when(s.reviewed_at)}`:""}</p>
    <p className="text-muted-foreground">{s.mandatory?"Obbligatoria":`Scelta: ${s.reason}`}{s.steps.length?` · solo per ${s.steps.join(", ")}`:""}{s.depends_on.length?` · dopo ${s.depends_on.join(", ")}`:""}</p>
    <p className="text-muted-foreground">Verifica finale: {s.final==="acceptance"?"revisione sul contratto di accettazione":`${s.final} criteri della sheet`}{s.handoff.required?` · controlli nell’handoff dichiarati: ${s.handoff.declared}`:""}</p>
    {!!s.handoff.violations.length&&<p role="alert">Violazioni negli incarichi: {s.handoff.violations.join(", ")}.</p>}
    {!!s.findings?.length&&<ul className="list-inside list-disc">{s.findings.map((f,i)=><li key={i}><span className="font-medium">{f.status==="failed"?"Non superato":"Non verificato"}</span>{f.requirement_id?` (${f.requirement_id})`:""}: {f.criterion||f.requirement_id} — {f.evidence}</li>)}</ul>}
   </li>)}</ul>
   {governance.product?.integrity==="failed"&&<p role="alert">{governance.product.issue}</p>}
   {governance.last_validation&&<p className="text-muted-foreground">Ultima validazione finale: {when(governance.last_validation.at)} · esito {VERDICTS[governance.last_validation.status]??governance.last_validation.status}.</p>}
   <p><a className="underline" href="/workspace/policies">Apri il Policy Book</a></p>
  </div>
 </details>;
}
