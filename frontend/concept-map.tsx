"use client";
import {tr,useUiLanguage} from "@/core/i18n/ui-text";

export type Concept="project"|"recipe"|"team"|"skill"|"environment"|"connection"|"policy"|"delivery";

/** One shared vocabulary: how request, recipe, team, skills, environments, connections, policies and deliveries fit together. */
export function ConceptMap({current,open=false}:{current?:Concept;open?:boolean}){
 useUiLanguage();
 const items:[Concept,string,string,string][]=[
  ["project",tr("Progetto","Project"),tr("Il lavoro che chiedi in una conversazione. Ha un risultato atteso, scritto con parole tue.","The work you ask for in a conversation. It has an expected result, in your own words."),"/workspace/chats"],
  ["recipe",tr("Ricetta","Recipe"),tr("Facoltativa. Un percorso a fasi già pronto per un tipo di progetto: cosa allegare, le fasi, dove approvi tu.","Optional. A ready phased path for a kind of project: what to attach, the phases, where you approve."),"/workspace/recipes"],
  ["team",tr("Squadra","Team"),tr("I ruoli che il coordinatore compone per il progetto. Ogni ruolo lavora con skill, un ambiente e, se lo consenti, connessioni.","The roles the coordinator composes for the project. Each role works with skills, an environment and, if you allow it, connections."),"/workspace/harness"],
  ["skill",tr("Skill","Skill"),tr("Come lavorare: un metodo, i controlli di qualità, la competenza su uno strumento.","How to work: a method, quality checks, expertise on a tool."),"/workspace/capabilities"],
  ["environment",tr("Ambiente","Environment"),tr("Con quali programmi: il contenitore isolato, preparato al primo uso, in cui un ruolo lavora.","With which programs: the isolated container, prepared on first use, where a role works."),"/workspace/environments"],
  ["connection",tr("Connessione","Connection"),tr("Accesso a un database o a un account esterno. Lo assegni tu a un progetto; nessuno lo riceve senza il tuo consenso.","Access to a database or an external account. You assign it to a project; nobody receives it without your consent."),"/workspace/connections"],
  ["policy",tr("Policy","Policy"),tr("Regole dell’organizzazione che ogni consegna deve rispettare; vengono verificate prima della consegna finale.","Organization rules every delivery must respect; they are checked before the final delivery."),"/workspace/policies"],
  ["delivery",tr("Consegna e risultato","Delivery and result"),tr("Ogni consegna è una versione con file verificati. Il risultato è la versione che approvi perché soddisfa la tua richiesta.","Each delivery is a version with checked files. The result is the version you approve because it meets your request."),"/workspace/chats"],
 ];
 return <details className="rounded-xl border p-3 text-sm" open={open} data-testid="concept-map">
  <summary className="cursor-pointer font-semibold">{tr("Come si incastrano i pezzi","How the pieces fit together")}</summary>
  <p className="mt-2 text-xs" data-testid="concept-flow">{tr(
   "Richiesta (eventualmente con una ricetta) → progetto → squadra: ogni ruolo usa skill + ambiente (+ connessioni) → consegne in versioni → controlli di qualità e policy → risultato approvato da te.",
   "Request (optionally with a recipe) → project → team: each role uses skills + environment (+ connections) → deliveries as versions → quality checks and policies → result approved by you.")}</p>
  <dl className="mt-3 grid gap-2 md:grid-cols-2">{items.map(([id,name,text,href])=><div key={id} className={`rounded-lg border p-2 ${id===current?"border-foreground bg-muted":""}`}>
   <dt className="font-medium">{id===current?name:<a className="underline" href={href}>{name}</a>}{id===current&&<span className="text-muted-foreground"> · {tr("sei qui","you are here")}</span>}</dt>
   <dd className="text-muted-foreground text-xs">{text}</dd></div>)}</dl>
 </details>;
}
